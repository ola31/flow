"""악보 캔버스 위젯

악보 이미지를 표시하고 핫스팟을 생성/편집하는 UI
"""

from pathlib import Path

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import (
    QAction,
    QColor,
    QDragEnterEvent,
    QDropEvent,
    QFont,
    QMouseEvent,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QMenu, QWidget

from flow.domain.hotspot import Hotspot
from flow.domain.score_sheet import ScoreSheet
from flow.ui.editor.hotspot_popover import HotspotPopover
from flow.ui.styles import (
    HOTSPOT_DEFAULT_FILL,
    HOTSPOT_MAPPED_FILL,
    HOTSPOT_SELECTED_FILL,
    HOTSPOT_UNMAPPED_BORDER,
)

# 프리페치 스레드가 도는 동안 캔버스를 살려 둔다. 스레드 클로저가 마지막
# 참조를 들면 Thread.run의 `del self._target`이 QWidget인 캔버스를 워커
# 스레드에서 파괴하고 프로세스가 죽는다(실측: Thread-N (_load)에서
# segfault). 해제는 반드시 메인 스레드에서 한다.
_PREFETCH_KEEPALIVE: set = set()


class ScoreCanvas(QWidget):
    """악보 캔버스

    악보 이미지 위에 핫스팟을 표시하고 클릭으로 새 핫스팟을 생성

    Signals:
        hotspot_created: 새 핫스팟이 생성됨 (Hotspot)
        hotspot_selected: 핫스팟이 선택됨 (Hotspot)
        hotspot_removed: 핫스팟이 삭제됨 (str: hotspot_id)
    """

    hotspot_created_request = Signal(int, int, object)
    hotspot_removed_request = Signal(object)
    hotspot_selected = Signal(object)
    hotspot_removed = Signal(str)
    hotspot_moved = Signal(object, tuple, tuple)
    hotspot_unmap_request = Signal(object)
    popover_mapping_requested = Signal(object, int)
    popover_unmap_requested = Signal(object)
    slide_dropped_on_hotspot = Signal(object, int)
    live_hotspot_clicked = Signal(object)
    emergency_patch_requested = Signal(object)  # Hotspot
    _prefetch_ready = Signal(str, object)  # (path_key, QImage) — 내부용
    # 워커 종료 → 메인 스레드에서 keepalive 해제
    _prefetch_finished = Signal()

    HOTSPOT_RADIUS = 15
    HOTSPOT_COLOR = QColor(*HOTSPOT_DEFAULT_FILL)
    HOTSPOT_SELECTED_COLOR = QColor(*HOTSPOT_SELECTED_FILL)
    HOTSPOT_MAPPED_COLOR = QColor(*HOTSPOT_MAPPED_FILL)
    HOTSPOT_UNMAPPED_PEN_COLOR = QColor(*HOTSPOT_UNMAPPED_BORDER)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._score_sheet: ScoreSheet | None = None
        self._pixmap: QPixmap | None = None
        self._selected_hotspot_id: str | None = None
        self._edit_mode = True
        self._hotspot_editable = True
        self._scaled_pixmap: QPixmap | None = None
        self._last_size = QSize(0, 0)
        self._scale_x = 1.0
        self._scale_y = 1.0
        self._offset_x = 0
        self._offset_y = 0
        self._verse_index = 0  # 현재 선택된 절 (UI 표시용)
        self._live_emergency_enabled = False

        # UI 리소스 캐시
        self._font_main = QFont("Malgun Gothic", 10)
        self._font_main.setPixelSize(12)
        self._font_main.setBold(True)
        self._font_small = QFont("Malgun Gothic", 10)
        self._font_small.setPixelSize(10)
        self._font_small.setBold(True)
        self._font_placeholder = QFont("Malgun Gothic", 10)
        self._font_placeholder.setPixelSize(14)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAcceptDrops(True)

        self._popover = HotspotPopover(self)
        self._popover.mapping_requested.connect(self._on_popover_mapping)
        self._popover.unmap_requested.connect(self._on_popover_unmap)

        self._is_dragging = False
        self._drag_hotspot_id = None

        self._mouse_pos: QPoint | None = None  # 위젯 좌표 (고스트용)

        self._pixmap_cache = {}
        # 이웃 시트 프리페치 — 디코드는 백그라운드, QPixmap 변환만 GUI에서
        self._prefetch_ready.connect(self._on_prefetch_ready)
        self._prefetch_finished.connect(self._on_prefetch_finished)
        self._prefetching: set[str] = set()

        # press 시점엔 팝오버를 띄우지 않고 예약만 해 둔다 — release에서
        # 드래그(이동)가 없었을 때만 표시 (드래그 화면 가림 방지).
        self._pending_popover_hotspot_id: str | None = None

    @staticmethod
    def _cache_key(path_str: str) -> tuple:
        """픽스맵 캐시 키 — 경로 + mtime.

        경로만 키로 쓰면 파일이 교체돼도(악보 다시 스캔, 같은 이름으로
        추가) 세션 내내 옛 이미지가 그대로 표시된다.
        """
        import os

        try:
            return (path_str, os.path.getmtime(path_str))
        except OSError:
            return (path_str, 0.0)

    def _cache_store(self, path_str: str, pixmap) -> None:
        """캐시에 담고, 같은 경로의 옛 항목은 버린다(무한 증식 방지)."""
        for key in [k for k in self._pixmap_cache if k[0] == path_str]:
            del self._pixmap_cache[key]
        self._pixmap_cache[self._cache_key(path_str)] = pixmap

    def prefetch_images(self, paths: list[str]) -> None:
        """이웃 시트 악보를 미리 디코드해 캐시에 넣는다 (방향키 전환 대비).

        큰 이미지 디코드(~100ms)가 전환 시점의 GUI를 막지 않도록
        백그라운드 스레드에서 QImage로 읽고, GUI에서 QPixmap으로 바꾼다.
        """
        todo = [
            p for p in paths
            if p
            and self._cache_key(p) not in self._pixmap_cache
            and p not in self._prefetching
        ]
        if not todo:
            return
        self._prefetching.update(todo)
        # 스레드가 이 캔버스의 마지막 참조를 들지 못하게 붙들어 둔다
        _PREFETCH_KEEPALIVE.add(self)

        import threading

        def _load() -> None:
            from PySide6.QtGui import QImage

            try:
                for p in todo:
                    img = QImage(p)
                    if not img.isNull():
                        self._prefetch_ready.emit(p, img)
            except RuntimeError:
                pass  # 위젯의 C++ 객체가 이미 삭제됨
            finally:
                try:
                    self._prefetch_finished.emit()
                except RuntimeError:
                    # C++ 객체가 없어 시그널을 못 쏨 — 파이썬 래퍼만 남았다
                    _PREFETCH_KEEPALIVE.discard(self)

        threading.Thread(target=_load, daemon=True).start()

    def _on_prefetch_finished(self) -> None:
        """프리페치 종료 — 메인 스레드에서 해제해야 파괴도 여기서 일어난다."""
        _PREFETCH_KEEPALIVE.discard(self)

    def _on_prefetch_ready(self, path_key: str, image) -> None:
        self._prefetching.discard(path_key)
        if self._cache_key(path_key) not in self._pixmap_cache:
            self._cache_store(path_key, QPixmap.fromImage(image))

    def is_hotspot_editable(self, hotspot: Hotspot, verse_index: int) -> bool:
        """현재 레이어에서 이 핫스팟이 편집 가능한지 판별"""
        if not hotspot:
            return False

        # [수정] 5번 인덱스는 '후렴'으로 고정, 나머지는 모두 '절' 그룹으로 간주 (확장성 대응)
        is_chorus = verse_index == 5
        is_verse_group = not is_chorus

        # 실제로 어떤 매핑(기존 방식 포함)이라도 존재하는지 여부 (완전한 '새 버튼' 판별용)
        is_completely_new = not hotspot.slide_mappings and hotspot.slide_index == -1

        # 절 매핑 확인 (5를 제외한 모든 키)
        has_verse_mapping = any(k != "5" for k in hotspot.slide_mappings) or (
            hotspot.slide_index >= 0
        )
        has_chorus_mapping = "5" in hotspot.slide_mappings

        # 1. 절 그룹 모드일 때
        if is_verse_group:
            # 절 매핑이 있거나, 아예 아무 소속도 없는 '완전한 새 버튼'인 경우 편집 가능
            return has_verse_mapping or is_completely_new

        # 2. 후렴 모드(5)일 때
        else:
            # 후렴 매핑이 있거나, 아예 아무 소속도 없는 '완전한 새 버튼'인 경우 편집 가능
            return has_chorus_mapping or is_completely_new

    def set_score_sheet(
        self, sheet: ScoreSheet | None, base_path: str | Path | None = None
    ) -> None:
        """악보 설정 (이미지 캐싱 지원)"""
        self._score_sheet = sheet
        self._selected_hotspot_id = None

        if sheet and sheet.image_path:
            img_path = Path(sheet.image_path)
            if not img_path.is_absolute() and base_path:
                img_path = (Path(base_path) / img_path).resolve()

            path_key = str(img_path)

            # 1. 캐시 확인 (경로+mtime — 파일이 바뀌면 자동 무효화)
            cache_key = self._cache_key(path_key)
            if cache_key in self._pixmap_cache:
                self._pixmap = self._pixmap_cache[cache_key]
            else:
                # 2. 신규 로딩
                self._pixmap = QPixmap(path_key)

                # 로드 실패 시 fallback 처리
                if self._pixmap.isNull() and base_path:
                    # sheet <-> sheets 교체 시도 등 (기존 로직 유지)
                    alt_path_str = sheet.image_path
                    if "sheets/" in alt_path_str:
                        alt_path_str = alt_path_str.replace("sheets/", "sheet/")
                    elif "sheet/" in alt_path_str:
                        alt_path_str = alt_path_str.replace("sheet/", "sheets/")

                    if alt_path_str != sheet.image_path:
                        alt_p = (Path(base_path) / alt_path_str).resolve()
                        self._pixmap = QPixmap(str(alt_p))
                        if not self._pixmap.isNull():
                            path_key = str(alt_p)

                # 여전히 실패 시 폴더 내 검색
                if self._pixmap.isNull() and base_path:
                    for sub in ["sheet", "sheets"]:
                        filename = Path(sheet.image_path).name
                        alt_p = (Path(base_path) / sub / filename).resolve()
                        self._pixmap = QPixmap(str(alt_p))
                        if not self._pixmap.isNull():
                            path_key = str(alt_p)
                            break

                # 최종 성공 시 캐시에 저장
                if not self._pixmap.isNull():
                    self._cache_store(path_key, self._pixmap)
                else:
                    self._pixmap = None
        else:
            self._pixmap = None

        self._scaled_pixmap = None  # 악보 변경 시 캐시 초기화
        self.update()

    def set_edit_mode(self, enabled: bool) -> None:
        self._edit_mode = enabled

    def set_live_mode(self, *, is_live: bool, slide_source: str) -> None:
        """Called by main_window on enter/exit live. slide_source is the
        current song's source ('markdown' | 'pptx' | 'none')."""
        self._live_emergency_enabled = is_live and slide_source == "markdown"

    def set_hotspot_editable(self, editable: bool) -> None:
        self._hotspot_editable = editable

    def select_hotspot(self, hotspot_id: str | None) -> None:
        """핫스팟 선택"""
        self._selected_hotspot_id = hotspot_id
        self.update()

    def set_verse_index(self, index: int) -> None:
        """현재 절 인덱스 설정 (UI 갱신)"""
        self._verse_index = index
        self.update()

    def get_selected_hotspot(self) -> Hotspot | None:
        """현재 선택된 핫스팟 반환"""
        if not self._score_sheet or not self._selected_hotspot_id:
            return None
        return self._score_sheet.find_hotspot_by_id(self._selected_hotspot_id)

    def get_score_sheet(self) -> ScoreSheet | None:
        """현재 표시 중인 악보 시트 반환"""
        return self._score_sheet

    def paintEvent(self, event) -> None:
        """그리기"""
        painter = QPainter(self)
        # Antialiasing과 SmoothPixmapTransform 모두 활성화하여 최상의 화질 보장
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        # 배경
        painter.fillRect(self.rect(), QColor(26, 26, 26))

        if not self._score_sheet:
            self._draw_placeholder(painter, "왼쪽 곡 목록에서 곡을 선택하세요")
            return

        if self._pixmap:
            # [화질 개선] High-DPI(고배율) 디스플레이 대응
            # logical size가 아닌 physical size(실제 픽셀)로 스케일링하여 선명도 유지
            ratio = self.devicePixelRatioF()
            target_size = self.size() * ratio

            if self._scaled_pixmap is None or target_size != self._last_size:
                self._scaled_pixmap = self._pixmap.scaled(
                    target_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                # Qt가 내부적으로 배율을 인식하게 설정
                self._scaled_pixmap.setDevicePixelRatio(ratio)
                self._last_size = target_size

                # 좌표 변환을 위한 캐시 업데이트
                sw = self._scaled_pixmap.width() / ratio
                sh = self._scaled_pixmap.height() / ratio
                self._scale_x = sw / self._pixmap.width()
                self._scale_y = sh / self._pixmap.height()
                self._offset_x = (self.width() - sw) // 2
                self._offset_y = (self.height() - sh) // 2

            # 중앙 배치 계산 (SetDevicePixelRatio 덕분에 logical 좌표로 그리면 됨)
            painter.drawPixmap(
                int(self._offset_x), int(self._offset_y), self._scaled_pixmap
            )
        else:
            self._draw_placeholder(
                painter,
                f"{self._score_sheet.name}\n\n악보 이미지가 없습니다\n곡 편집에서 이미지를 추가해 주세요",
            )

        # 핫스팟 그리기
        self._draw_hotspots(painter)

        # 빈 상태 안내 (핫스팟 없을 때)
        if (
            self._score_sheet
            and self._edit_mode
            and self._hotspot_editable
            and not self._score_sheet.hotspots
        ):
            self._draw_empty_hint(painter)

        # 고스트 핫스팟 (마우스 따라다니는 미리보기)
        # 팝오버가 떠있으면 다음 클릭은 새 핫스팟 추가가 아니라 팝오버 닫기로
        # 동작하므로 고스트도 그리지 않아 시각적 혼동 방지
        if (
            self._score_sheet
            and self._edit_mode
            and self._hotspot_editable
            and self._mouse_pos
            and not self._is_dragging
            and not self._popover.isVisible()
        ):
            self._draw_ghost_hotspot(painter)

    def _draw_placeholder(self, painter: QPainter, text: str) -> None:
        """플레이스홀더 텍스트 그리기"""
        painter.setPen(QColor(150, 150, 150))
        painter.setFont(self._font_placeholder)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, text)

    def _draw_empty_hint(self, painter: QPainter) -> None:
        """핫스팟이 없을 때 '클릭해서 추가' 안내 오버레이"""
        painter.save()
        painter.setPen(QColor(255, 255, 255, 60))
        f = QFont("Malgun Gothic")
        f.setPixelSize(16)
        painter.setFont(f)
        painter.drawText(
            self.rect(),
            Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
            "클릭해서 핫스팟 추가  |  Tab: 이동  |  Delete: 삭제",
        )
        painter.restore()

    def _draw_ghost_hotspot(self, painter: QPainter) -> None:
        """마우스 커서 위치에 반투명 핫스팟 미리보기"""
        if not self._mouse_pos:
            return

        pos = self._mouse_pos

        # 이미지 영역 밖이면 그리지 않음
        img_coords = self._widget_to_image_coords(pos.x(), pos.y())
        if not img_coords:
            return

        # 기존 핫스팟에 가까우면 고스트 숨김
        if self._find_hotspot_at(pos) is not None:
            return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        ghost_color = QColor(*HOTSPOT_DEFAULT_FILL[:3], 70)  # 더 연하게
        painter.setBrush(ghost_color)
        ghost_pen = QPen(QColor(*HOTSPOT_UNMAPPED_BORDER[:3], 120), 1, Qt.PenStyle.DashLine)
        painter.setPen(ghost_pen)
        painter.drawEllipse(pos, self.HOTSPOT_RADIUS, self.HOTSPOT_RADIUS)
        painter.restore()

    def _draw_hotspots(self, painter: QPainter) -> None:
        """핫스팟들 그리기"""
        if not self._score_sheet:
            return

        # 1. 후렴 레이블 대상 식별 및 할당 (ABC 순서 보장)
        ordered_hotspots = self._score_sheet.get_ordered_hotspots()
        chorus_labels = {}
        chorus_counter = 0

        v_idx = self._verse_index
        chorus_counter = 0
        verse_display_counter = 0

        for h in ordered_hotspots:
            # [수정] 후렴 매핑이 있거나, 후렴 레이어에서 생성된 버튼인 경우 ABC 레이블 할당
            # (slide_mappings에 '5' 키가 명시적으로 존재하는지 확인)
            has_chorus_intent = "5" in h.slide_mappings
            if has_chorus_intent:
                label_char = (
                    chr(65 + chorus_counter)
                    if chorus_counter < 26
                    else str(chorus_counter + 1)
                )
                chorus_labels[h.id] = label_char
                chorus_counter += 1

        # 2. 핫스팟 그리기 루프
        v_idx = self._verse_index
        for i, hotspot in enumerate(ordered_hotspots):
            # 레이어 기반 편집 상태 판별
            is_selected = hotspot.id == self._selected_hotspot_id
            is_editable = self.is_hotspot_editable(hotspot, v_idx)

            # [수정] 후렴 모드(5) 전용: 후렴 매핑이 없는 타 레이어 버튼은 아예 숨김
            if v_idx == 5 and not is_editable and not is_selected:
                continue

            # 좌표 변환 (이미지 좌표 → 위젯 좌표)
            pos = QPoint(
                int(hotspot.x * self._scale_x + self._offset_x),
                int(hotspot.y * self._scale_y + self._offset_y),
            )

            # 현재 레이어에서 매핑 여부 확인 — 절 레이어에서는 후렴(5) 폴백
            # 포함. 후렴 매핑된 핫스팟은 절에서도 실제로 동작하므로(클릭 시
            # 후렴 슬라이드 송출) '매핑 완료'로 보여야 한다.
            current_slide_idx = hotspot.get_effective_slide_index(v_idx)
            is_mapped = current_slide_idx >= 0

            # 색상/테두리: 선택 > 매핑완료 > 미매핑 > 타레이어 잠금 순서
            if is_selected:
                color = self.HOTSPOT_SELECTED_COLOR
                pen = QPen(Qt.GlobalColor.white, 2)
            elif not is_editable and not is_mapped:
                # 타 레이어 전용 버튼(유효 매핑도 없음): 연한 점선 외곽선
                color = self.HOTSPOT_COLOR
                pen = QPen(QColor(200, 200, 200, 180), 1, Qt.PenStyle.DashLine)
            elif is_mapped:
                # 매핑 완료: 초록 채우기 + 흰 테두리
                color = self.HOTSPOT_MAPPED_COLOR
                pen = QPen(Qt.GlobalColor.white, 1)
            else:
                # 미매핑: 주황 채우기 + 노란 점선 테두리 (경고)
                color = self.HOTSPOT_COLOR
                pen = QPen(self.HOTSPOT_UNMAPPED_PEN_COLOR, 2, Qt.PenStyle.DashLine)

            # 원 그리기
            painter.setBrush(color)
            painter.setPen(pen)
            painter.drawEllipse(pos, self.HOTSPOT_RADIUS, self.HOTSPOT_RADIUS)

            # 키보드 포커스 링: 선택 상태일 때 바깥쪽 점선 링 추가
            if is_selected and self.hasFocus():
                focus_pen = QPen(QColor(255, 255, 255, 180), 1, Qt.PenStyle.DotLine)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(focus_pen)
                painter.drawEllipse(pos, self.HOTSPOT_RADIUS + 4, self.HOTSPOT_RADIUS + 4)

            # 텍스트 드로잉 (잘림 방지를 위해 범위 확대 및 폰트 설정)
            painter.setPen(Qt.GlobalColor.white)

            # [수정] 레이블 결정 로직:
            # - 후렴 버튼으로 식별된 경우: 미리 계산된 알파벳(A, B, C...) 유지
            # - 그 외(절 전용 버튼): 별도의 카운터를 사용하여 숫자(1, 2, 3...) 부여 (건너뛰기 방지)
            if hotspot.id in chorus_labels:
                display_name = chorus_labels[hotspot.id]
            else:
                verse_display_counter += 1
                display_name = str(verse_display_counter)

            label = display_name
            # 현재 절 매핑 우선, 없으면 후렴 매핑 표시 (내비게이션 지원)
            slide_idx = hotspot.get_effective_slide_index(self._verse_index)

            if slide_idx >= 0:
                label = f"{display_name}-{slide_idx + 1}"
                painter.setFont(self._font_small)
            else:
                painter.setFont(self._font_main)

            # 원 안의 중앙에 텍스트 배치
            text_rect = QRect(
                pos.x() - self.HOTSPOT_RADIUS,
                pos.y() - self.HOTSPOT_RADIUS,
                self.HOTSPOT_RADIUS * 2,
                self.HOTSPOT_RADIUS * 2,
            )
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, label)

    def _image_to_widget_coords(self, img_x: int, img_y: int) -> QPoint:
        """이미지 좌표를 위젯 좌표로 변환"""
        if not self._pixmap:
            return QPoint(img_x, img_y)

        return QPoint(
            int(img_x * self._scale_x + self._offset_x),
            int(img_y * self._scale_y + self._offset_y),
        )

    def _widget_to_image_coords(
        self, widget_x: int, widget_y: int
    ) -> tuple[int, int] | None:
        """위젯 좌표를 이미지 좌표로 변환"""
        if not self._pixmap or self._scale_x == 0 or self._scale_y == 0:
            return widget_x, widget_y

        # 이미지 영역 밖 클릭 체크 (캐시된 오프셋 및 스케일 사용)
        img_w = self._pixmap.width()
        img_h = self._pixmap.height()

        rel_x = (widget_x - self._offset_x) / self._scale_x
        rel_y = (widget_y - self._offset_y) / self._scale_y

        if rel_x < 0 or rel_x >= img_w or rel_y < 0 or rel_y >= img_h:
            return None

        return int(rel_x), int(rel_y)

    def keyPressEvent(self, event) -> None:
        key = event.key()

        # Delete / Backspace: 선택된 핫스팟 삭제
        if key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            if self._edit_mode and self._hotspot_editable and self._selected_hotspot_id:
                hotspot = self.get_selected_hotspot()
                if hotspot and self.is_hotspot_editable(hotspot, self._verse_index):
                    self._delete_hotspot(hotspot)
                    return

        # Escape: 선택 해제 + 팝오버 닫기
        if key == Qt.Key.Key_Escape:
            if self._popover.isVisible():
                self._popover.dismiss()
                event.accept()
                return
            if self._selected_hotspot_id:
                self._selected_hotspot_id = None
                self.update()
                event.accept()
                return

        # Tab / Shift+Tab: 현재 레이어 내 핫스팟 순환
        if key in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab) and self._score_sheet:
            ordered = self._score_sheet.get_ordered_hotspots()
            visible = [
                h for h in ordered
                if self.is_hotspot_editable(h, self._verse_index)
                or h.id == self._selected_hotspot_id
            ]
            if not visible:
                super().keyPressEvent(event)
                return

            if not self._selected_hotspot_id:
                target = visible[0] if key == Qt.Key.Key_Tab else visible[-1]
            else:
                ids = [h.id for h in visible]
                try:
                    idx = ids.index(self._selected_hotspot_id)
                except ValueError:
                    idx = -1
                if key == Qt.Key.Key_Tab:
                    idx = (idx + 1) % len(visible)
                else:
                    idx = (idx - 1) % len(visible)
                target = visible[idx]

            self._selected_hotspot_id = target.id
            self.hotspot_selected.emit(target)
            self.update()
            event.accept()
            return

        super().keyPressEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self.setFocus()
        if not self._score_sheet:
            self._popover.dismiss()
            return

        pos = event.position().toPoint()
        popover_was_visible = self._popover.isVisible()
        popover_hotspot_id = (
            self._popover._hotspot.id
            if popover_was_visible and self._popover._hotspot
            else None
        )

        if popover_was_visible and not self._popover.geometry().contains(pos):
            self._popover.dismiss()

        clicked_hotspot = self._find_hotspot_at(pos)

        if event.button() == Qt.MouseButton.LeftButton:
            if clicked_hotspot:
                if popover_was_visible and clicked_hotspot.id == popover_hotspot_id:
                    self.update()
                    return

                self._selected_hotspot_id = clicked_hotspot.id
                self.hotspot_selected.emit(clicked_hotspot)

                if not self._edit_mode:
                    self.live_hotspot_clicked.emit(clicked_hotspot)
                    self.update()
                    return

                if not self._hotspot_editable:
                    self.update()
                    return

                if self.is_hotspot_editable(clicked_hotspot, self._verse_index):
                    self._is_dragging = True
                    self._drag_hotspot_id = clicked_hotspot.id
                    self._drag_start_pos = (clicked_hotspot.x, clicked_hotspot.y)
                    self.setCursor(Qt.CursorShape.ClosedHandCursor)

                if self._edit_mode:
                    self._pending_popover_hotspot_id = clicked_hotspot.id
            elif self._edit_mode and self._hotspot_editable and not popover_was_visible:
                img_coords = self._widget_to_image_coords(pos.x(), pos.y())
                if img_coords:
                    self.hotspot_created_request.emit(
                        img_coords[0], img_coords[1], None
                    )

            self.update()

        elif event.button() == Qt.MouseButton.RightButton and clicked_hotspot:
            if self._edit_mode and self._hotspot_editable:
                self._show_context_menu(pos, clicked_hotspot)
            else:
                event.ignore()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """마우스 이동 (드래그 처리)"""
        pos = event.position().toPoint()

        if self._is_dragging and self._drag_hotspot_id and self._score_sheet:
            hotspot = self._score_sheet.find_hotspot_by_id(self._drag_hotspot_id)
            if hotspot:
                img_coords = self._widget_to_image_coords(pos.x(), pos.y())
                if img_coords:
                    hotspot.x, hotspot.y = img_coords
                    self.update()
        else:
            hovered = self._find_hotspot_at(pos)
            if hovered:
                self.setCursor(Qt.CursorShape.PointingHandCursor)
                slide_idx = hovered.get_effective_slide_index(self._verse_index)
                tip = f"#{hovered.order + 1}"
                if hovered.lyric:
                    tip += f"  {hovered.lyric}"
                if slide_idx >= 0:
                    tip += f"  →  슬라이드 {slide_idx + 1}"
                self.setToolTip(tip)
            elif (
                self._edit_mode
                and self._hotspot_editable
                and self._score_sheet
                and self._widget_to_image_coords(pos.x(), pos.y())
                and not self._popover.isVisible()
            ):
                # 팝오버가 떠있을 땐 클릭이 핫스팟 추가가 아닌 팝오버 닫기로
                # 가니까 십자 커서/추가 안내를 숨김
                self.setCursor(Qt.CursorShape.CrossCursor)
                self.setToolTip("클릭해서 핫스팟 추가")
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)
                self.setToolTip("")

        # 고스트 핫스팟 갱신
        self._mouse_pos = pos
        self.update()

        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:
        self._mouse_pos = None
        self.update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """마우스 뗌 (드래그 종료 / 클릭이었으면 팝오버 표시)"""
        if event.button() == Qt.MouseButton.LeftButton:
            was_moved = False
            if self._is_dragging:
                if self._drag_hotspot_id and self._score_sheet:
                    hotspot = self._score_sheet.find_hotspot_by_id(
                        self._drag_hotspot_id
                    )
                    if hotspot:
                        new_pos = (hotspot.x, hotspot.y)
                        if new_pos != self._drag_start_pos:
                            was_moved = True
                            self.hotspot_moved.emit(
                                hotspot, self._drag_start_pos, new_pos
                            )

                self._is_dragging = False
                self._drag_hotspot_id = None
                self.setCursor(Qt.CursorShape.ArrowCursor)

            pending_id = self._pending_popover_hotspot_id
            self._pending_popover_hotspot_id = None
            if pending_id and not was_moved and self._score_sheet:
                hotspot = self._score_sheet.find_hotspot_by_id(pending_id)
                if hotspot:
                    anchor = self._image_to_widget_coords(hotspot.x, hotspot.y)
                    self._popover.show_for_hotspot(
                        hotspot, self._verse_index, anchor
                    )

        super().mouseReleaseEvent(event)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        from flow.ui.editor.slide_preview_panel import SLIDE_MIME_TYPE

        if (
            event.mimeData().hasFormat(SLIDE_MIME_TYPE)
            and self._edit_mode
            and self._hotspot_editable
        ):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:
        from flow.ui.editor.slide_preview_panel import SLIDE_MIME_TYPE

        if (
            event.mimeData().hasFormat(SLIDE_MIME_TYPE)
            and self._edit_mode
            and self._hotspot_editable
        ):
            pos = event.position().toPoint()
            hotspot = self._find_hotspot_at(pos)
            if hotspot:
                self._selected_hotspot_id = hotspot.id
                self.update()
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        from flow.ui.editor.slide_preview_panel import SLIDE_MIME_TYPE

        if (
            not event.mimeData().hasFormat(SLIDE_MIME_TYPE)
            or not self._edit_mode
            or not self._hotspot_editable
        ):
            event.ignore()
            return

        pos = event.position().toPoint()
        hotspot = self._find_hotspot_at(pos)
        if not hotspot:
            event.ignore()
            return

        data = event.mimeData().data(SLIDE_MIME_TYPE).data()
        slide_index = int(data.decode())

        self._selected_hotspot_id = hotspot.id
        self.hotspot_selected.emit(hotspot)
        self.slide_dropped_on_hotspot.emit(hotspot, slide_index)
        self.update()
        event.acceptProposedAction()

    def _find_hotspot_at(self, pos: QPoint) -> Hotspot | None:
        if not self._score_sheet:
            return None

        for hotspot in self._score_sheet.hotspots:
            # [수정] 후렴 모드(5)인 경우, 후렴 매핑이 있거나 선택된 것만 클릭 가능하도록 일관성 유지
            if self._verse_index == 5:
                if (
                    not self.is_hotspot_editable(hotspot, 5)
                    and hotspot.id != self._selected_hotspot_id
                ):
                    continue

            hotspot_pos = self._image_to_widget_coords(hotspot.x, hotspot.y)
            distance = (
                (pos.x() - hotspot_pos.x()) ** 2 + (pos.y() - hotspot_pos.y()) ** 2
            ) ** 0.5

            # 실제 원보다 약간 더 넓은 범위까지 클릭으로 인정 (작아진 버튼 보완)
            if distance <= self.HOTSPOT_RADIUS + 8:
                return hotspot

        return None

    def _show_context_menu(self, pos: QPoint, hotspot: Hotspot) -> None:
        """컨텍스트 메뉴 표시"""
        menu = QMenu(self)

        # [추가] 타 레이어 버튼 락 안내 (절 그룹 vs 후렴 그룹)
        if not self.is_hotspot_editable(hotspot, self._verse_index):
            v_name = "후렴" if self._verse_index < 5 else "절"
            lock_action = menu.addAction(f"🔒 {v_name} 전용 버튼")
            lock_action.setEnabled(False)
            menu.addSeparator()
        else:
            # 순서 기반 삽입 기능 추가
            insert_before = QAction("➕ 이 위치 앞에 삽입", self)
            insert_before.triggered.connect(
                lambda: self._insert_hotspot_at(hotspot, before=True)
            )
            menu.addAction(insert_before)

            insert_after = QAction("➕ 이 위치 뒤에 삽입", self)
            insert_after.triggered.connect(
                lambda: self._insert_hotspot_at(hotspot, before=False)
            )
            menu.addAction(insert_after)

            menu.addSeparator()

            delete_action = QAction("삭제", self)
            delete_action.triggered.connect(lambda: self._delete_hotspot(hotspot))
            menu.addAction(delete_action)

            # [복구] 매핑 해제 기능 추가 (현재 절 매핑이 있는 경우에만)
            if hotspot.get_slide_index(self._verse_index) >= 0:
                menu.addSeparator()
                unmap_action = QAction("🔌 매핑 해제", self)
                unmap_action.triggered.connect(
                    lambda: self.hotspot_unmap_request.emit(hotspot)
                )
                menu.addAction(unmap_action)

        if self._live_emergency_enabled:
            menu.addSeparator()
            emergency_action = QAction("긴급 수정", self)
            emergency_action.triggered.connect(
                lambda: self.emergency_patch_requested.emit(hotspot)
            )
            menu.addAction(emergency_action)

        menu.exec(self.mapToGlobal(pos))

    def _insert_hotspot_at(self, base_hotspot: Hotspot, before: bool = True) -> None:
        """특정 위치를 기준으로 새 핫스팟 삽입 요청"""
        if not self._score_sheet:
            return

        new_order = base_hotspot.order if before else base_hotspot.order + 1

        # 좌표는 기준 핫스팟 근처로 임시 설정
        new_x = base_hotspot.x + (0 if before else 30)
        new_y = base_hotspot.y + (0 if before else 30)

        # MainWindow에 삽입 위치(index) 포함하여 생성 요청
        self.hotspot_created_request.emit(new_x, new_y, new_order)

    def _delete_hotspot(self, hotspot: Hotspot) -> None:
        if self._score_sheet:
            self.hotspot_removed_request.emit(hotspot)

    def _on_popover_mapping(self, slide_index: int) -> None:
        hotspot = self.get_selected_hotspot()
        if hotspot:
            self.popover_mapping_requested.emit(hotspot, slide_index)

    def _on_popover_unmap(self) -> None:
        hotspot = self.get_selected_hotspot()
        if hotspot:
            self.popover_unmap_requested.emit(hotspot)

    @property
    def popover(self) -> HotspotPopover:
        return self._popover

    def resizeEvent(self, event) -> None:
        self._scaled_pixmap = None
        self._popover.dismiss()
        super().resizeEvent(event)
