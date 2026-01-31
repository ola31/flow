"""악보 캔버스 위젯

악보 이미지를 표시하고 핫스팟을 생성/편집하는 UI
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QScrollArea, QMenu
from PySide6.QtGui import QPixmap, QPainter, QColor, QPen, QMouseEvent, QAction, QFont
from PySide6.QtCore import Signal, Qt, QPoint, QRect, QSize

from pathlib import Path

from flow.domain.score_sheet import ScoreSheet
from flow.domain.hotspot import Hotspot


class ScoreCanvas(QWidget):
    """악보 캔버스

    악보 이미지 위에 핫스팟을 표시하고 클릭으로 새 핫스팟을 생성

    Signals:
        hotspot_created: 새 핫스팟이 생성됨 (Hotspot)
        hotspot_selected: 핫스팟이 선택됨 (Hotspot)
        hotspot_removed: 핫스팟이 삭제됨 (str: hotspot_id)
    """

    hotspot_created_request = Signal(int, int, object)  # x, y 좌표, index(선택적)
    hotspot_removed_request = Signal(object)  # Hotspot 객체
    hotspot_selected = Signal(object)  # Hotspot
    hotspot_removed = Signal(str)  # hotspot_id
    hotspot_moved = Signal(object, tuple, tuple)  # Hotspot, old_pos, new_pos
    hotspot_unmap_request = Signal(object)  # [복구] Hotspot

    HOTSPOT_RADIUS = 15
    HOTSPOT_COLOR = QColor(
        255, 160, 0, 150
    )  # 비선택: 선명한 주황 (가시성 + 투명도 밸런스)
    HOTSPOT_SELECTED_COLOR = QColor(
        33, 150, 243, 180
    )  # 선택: 브랜드 블루 (투명도 조절)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._score_sheet: ScoreSheet | None = None
        self._pixmap: QPixmap | None = None
        self._selected_hotspot_id: str | None = None
        self._edit_mode = True
        self._scaled_pixmap: QPixmap | None = None  # 캐시된 스케일 이미지
        self._last_size = QSize(0, 0)
        self._scale_x = 1.0
        self._scale_y = 1.0
        self._offset_x = 0
        self._offset_y = 0
        self._verse_index = 0  # 현재 선택된 절 (UI 표시용)

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

        # 드래그 관련 상태
        self._is_dragging = False
        self._drag_hotspot_id = None

        # 이미지 캐시 (경로 -> QPixmap)
        self._pixmap_cache = {}

    def is_hotspot_editable(self, hotspot: Hotspot, verse_index: int) -> bool:
        """현재 레이어에서 이 핫스팟이 편집 가능한지 판별"""
        if not hotspot:
            return False

        # [수정] 1~5절(0~4)은 하나의 편집 그룹으로 묶고, 후렴(5)과만 분리
        is_verse_group = verse_index < 5

        # 실제로 어떤 매핑(기존 방식 포함)이라도 존재하는지 여부 (완전한 '새 버튼' 판별용)
        is_completely_new = not hotspot.slide_mappings and hotspot.slide_index == -1

        has_verse_mapping = any(str(i) in hotspot.slide_mappings for i in range(5)) or (
            hotspot.slide_index >= 0
        )
        has_chorus_mapping = "5" in hotspot.slide_mappings

        # 1. 절 그룹 모드(1~5절)일 때
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

            # 1. 캐시 확인
            if path_key in self._pixmap_cache:
                self._pixmap = self._pixmap_cache[path_key]
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
                    self._pixmap_cache[path_key] = self._pixmap
                else:
                    self._pixmap = None
        else:
            self._pixmap = None

        self._scaled_pixmap = None  # 악보 변경 시 캐시 초기화
        self.update()

    def set_edit_mode(self, enabled: bool) -> None:
        """편집 모드 설정"""
        self._edit_mode = enabled

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
            self._draw_placeholder(painter, "곡을 선택하세요")
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
                painter, f"악보: {self._score_sheet.name}\n(이미지를 추가하세요)"
            )

        # 핫스팟 그리기
        self._draw_hotspots(painter)

    def _draw_placeholder(self, painter: QPainter, text: str) -> None:
        """플레이스홀더 텍스트 그리기"""
        painter.setPen(QColor(150, 150, 150))
        painter.setFont(self._font_placeholder)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, text)

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

            # 모든 버튼을 보이게 하되, 타 레이어 버튼은 외곽선 스타일로 '편집 잠금' 표시
            if is_selected:
                color = self.HOTSPOT_SELECTED_COLOR
                pen = QPen(Qt.GlobalColor.white, 2)
            else:
                color = self.HOTSPOT_COLOR
                if is_editable:
                    pen = QPen(Qt.GlobalColor.white, 1)
                else:
                    # 타 레이어 전용 버튼 (Verse 모드에서만 보임): 연한 점선 외곽선
                    pen = QPen(QColor(200, 200, 200, 180), 1, Qt.PenStyle.DashLine)

            # 원 그리기
            painter.setBrush(color)
            painter.setPen(pen)
            painter.drawEllipse(pos, self.HOTSPOT_RADIUS, self.HOTSPOT_RADIUS)

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
            # [수정] 현재 절 매핑 우선, 없으면 후렴 매핑 표시 (내비게이션 지원)
            slide_idx = hotspot.get_slide_index(self._verse_index)

            # 현재 절 매핑이 없고, 후렴 버튼인 경우 후렴 슬라이드 번호 표시
            is_chorus_hotspot = hotspot.id in chorus_labels
            if slide_idx < 0 and is_chorus_hotspot:
                slide_idx = hotspot.get_slide_index(5)  # 후렴 슬라이드 가져오기

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
        """키보드 이벤트 - Delete/Backspace로 핫스팟 삭제"""
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            if self._edit_mode and self._selected_hotspot_id:
                hotspot = self.get_selected_hotspot()
                if hotspot and self.is_hotspot_editable(hotspot, self._verse_index):
                    self._delete_hotspot(hotspot)
                    return
        super().keyPressEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """마우스 클릭"""
        self.setFocus()  # 클릭 시 키보드 포커스 획득
        if not self._score_sheet:
            return

        pos = event.position().toPoint()

        # 기존 핫스팟 클릭 체크
        clicked_hotspot = self._find_hotspot_at(pos)

        if event.button() == Qt.MouseButton.LeftButton:
            if clicked_hotspot:
                # 선택 및 드래그 시작 준비
                self._selected_hotspot_id = clicked_hotspot.id
                self.hotspot_selected.emit(clicked_hotspot)

                # [수정] 현재 모드에서 편집 가능한 경우에만 드래그 허용
                if self._edit_mode and self.is_hotspot_editable(
                    clicked_hotspot, self._verse_index
                ):
                    self._is_dragging = True
                    self._drag_hotspot_id = clicked_hotspot.id
                    self._drag_start_pos = (clicked_hotspot.x, clicked_hotspot.y)
                    self.setCursor(Qt.CursorShape.ClosedHandCursor)
            elif self._edit_mode:
                # 새 핫스팟 생성 요청
                img_coords = self._widget_to_image_coords(pos.x(), pos.y())
                if img_coords:
                    self.hotspot_created_request.emit(
                        img_coords[0], img_coords[1], None
                    )

            self.update()

        elif event.button() == Qt.MouseButton.RightButton and clicked_hotspot:
            # [복구] 편집 모드에서만 우클릭 메뉴 허용
            if self._edit_mode:
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
            # 마우스 커서 변경 (핫스팟 위에 있을 때)
            if self._find_hotspot_at(pos):
                self.setCursor(Qt.CursorShape.PointingHandCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """마우스 뗌 (드래그 종료)"""
        if event.button() == Qt.MouseButton.LeftButton and self._is_dragging:
            if self._drag_hotspot_id and self._score_sheet:
                hotspot = self._score_sheet.find_hotspot_by_id(self._drag_hotspot_id)
                if hotspot:
                    new_pos = (hotspot.x, hotspot.y)
                    if new_pos != self._drag_start_pos:
                        self.hotspot_moved.emit(hotspot, self._drag_start_pos, new_pos)

            self._is_dragging = False
            self._drag_hotspot_id = None
            self.setCursor(Qt.CursorShape.ArrowCursor)

        super().mouseReleaseEvent(event)

    def _find_hotspot_at(self, pos: QPoint) -> Hotspot | None:
        """해당 위치의 핫스팟 찾기"""
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
            insert_before = QAction(f"➕ 이 위치 앞에 삽입", self)
            insert_before.triggered.connect(
                lambda: self._insert_hotspot_at(hotspot, before=True)
            )
            menu.addAction(insert_before)

            insert_after = QAction(f"➕ 이 위치 뒤에 삽입", self)
            insert_after.triggered.connect(
                lambda: self._insert_hotspot_at(hotspot, before=False)
            )
            menu.addAction(insert_after)

            menu.addSeparator()

            delete_action = QAction("🗑️ 삭제", self)
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
        """핫스팟 삭제 요청"""
        if self._score_sheet:
            self.hotspot_removed_request.emit(hotspot)

    def resizeEvent(self, event) -> None:
        """창 크기 변경 시 캐시된 이미지 무효화"""
        self._scaled_pixmap = None
        super().resizeEvent(event)
