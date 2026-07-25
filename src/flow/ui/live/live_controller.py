"""라이브 컨트롤러

Preview-Live 2단계 송출 로직을 관리
"""

from PySide6.QtCore import QObject, QTimer, Signal

from flow.domain.hotspot import Hotspot
from flow.domain.project import Project


class LiveController(QObject):
    """라이브 컨트롤러

    Preview-Live 2단계 송출을 관리합니다.
    - Preview: 다음에 송출될 슬라이드 미리보기
    - Live: 현재 송출 중인 슬라이드

    Signals:
        preview_changed: Preview 내용이 변경됨 (str)
        live_changed: Live 내용이 변경됨 (str)
    """

    preview_changed = Signal(str)
    live_changed = Signal(str)
    slide_changed = Signal(object)  # QImage 송출용

    # 미변환 슬라이드를 기다리는 폴링 주기/한도.
    _RETRY_INTERVAL_MS = 250
    _RETRY_MAX_TICKS = 120  # 30초

    def __init__(self, parent: QObject | None = None, slide_manager = None) -> None:
        super().__init__(parent)
        self._project: Project | None = None
        self._preview_hotspot: Hotspot | None = None
        self._preview_slide_index: int = -1
        self._live_hotspot: Hotspot | None = None
        self._live_slide_index: int = -1
        # 송출을 확정한 시점의 절 — 이후 절을 바꿔도 송출은 이 값을 따른다
        self._live_verse_index: int = 0
        self._slide_manager = slide_manager
        # 아직 변환되지 않아 송출하지 못한 슬라이드 — 변환이 끝나는 대로
        # 채워 넣는다. SlideManager의 load_finished만 믿으면 화면 전환 중
        # (_in_transition)이거나 워커 큐가 비워진 경우 재시도가 영영 오지
        # 않아 이전 슬라이드가 그대로 남는다 (핫스팟을 눌러도 안 바뀜).
        self._pending_slide_index: int = -1
        self._retry_ticks: int = 0
        self._retry_timer = QTimer(self)
        self._retry_timer.setInterval(self._RETRY_INTERVAL_MS)
        self._retry_timer.timeout.connect(self._retry_pending_slide)

    def set_project(self, project: Project) -> None:
        """프로젝트 설정"""
        self._project = project
        self._preview_hotspot = None
        self._live_hotspot = None

    def set_preview(self, hotspot: Hotspot) -> None:
        """Preview에 핫스팟 설정"""
        self._preview_hotspot = hotspot
        self._preview_slide_index = -1 # 핫스팟 설정 시 슬라이드 미리보기 해제
        self.preview_changed.emit(hotspot.lyric if hotspot else "")

    def set_preview_slide(self, index: int) -> None:
        """슬라이드 직접 선택 시 Preview에 설정"""
        self._preview_slide_index = index
        self._preview_hotspot = None # 슬라이드 직접 선택 시 핫스팟 미리보기 해제
        self.preview_changed.emit(f"Slide {index + 1} (Direct)")

    def _peek(self, slide_idx: int):
        peek = getattr(self._slide_manager, "peek_slide_image", None)
        if peek is not None:
            return peek(slide_idx)
        # 테스트 더블 등 peek이 없는 매니저 폴백
        return self._slide_manager.get_slide_image(slide_idx)

    def _emit_slide_if_available(self, slide_idx: int) -> None:
        """캐시된 슬라이드만 송출하고, 미변환이면 이전 프레임을 유지한다.

        인라인 변환(get_slide_image)은 큰 PPT에서 GUI 전체를 얼리므로
        라이브 경로에서도 쓰지 않는다. 미변환이면 변환이 끝날 때까지
        짧은 주기로 다시 확인해 채워 넣는다 (peek 자체가 백그라운드
        변환을 예약하므로 폴링이 곧 재요청이기도 하다).
        """
        if not self._slide_manager:
            return
        image = self._peek(slide_idx)
        if image is not None and not image.isNull():
            self._clear_pending_slide()
            self.slide_changed.emit(image)
            return

        self._pending_slide_index = slide_idx
        self._retry_ticks = 0
        if not self._retry_timer.isActive():
            self._retry_timer.start()

    def _clear_pending_slide(self) -> None:
        self._pending_slide_index = -1
        self._retry_ticks = 0
        self._retry_timer.stop()

    def _retry_pending_slide(self) -> None:
        """변환이 끝났는지 확인하고, 되면 송출한다."""
        idx = self._pending_slide_index
        if idx < 0 or not self._slide_manager:
            self._clear_pending_slide()
            return

        self._retry_ticks += 1
        image = self._peek(idx)
        if image is not None and not image.isNull():
            self._clear_pending_slide()
            self.slide_changed.emit(image)
            return

        if self._retry_ticks >= self._RETRY_MAX_TICKS:
            # 변환 엔진이 없거나 실패한 상태 — 무한 폴링은 하지 않는다.
            self._clear_pending_slide()

    def send_to_live(self) -> None:
        """Preview 내용을 Live로 송출"""
        if self._preview_hotspot:
            self._live_hotspot = self._preview_hotspot
            self._live_slide_index = -1
            self.live_changed.emit(self._live_hotspot.lyric)

            # [수정] 현재 절(Verse)에 맞는 슬라이드 인덱스 구득
            v_idx = self._project.current_verse_index if self._project else 0
            self._live_verse_index = v_idx
            slide_idx = self._live_hotspot.get_slide_index(v_idx)

            # 현재 절 매핑이 없더라도 후렴(5) 매핑이 있다면 활용 (범용 내비게이션 대응)
            if slide_idx < 0:
                slide_idx = self._live_hotspot.get_slide_index(5)

            self._live_slide_index = slide_idx

            if self._slide_manager and slide_idx >= 0:
                self._emit_slide_if_available(slide_idx)
            else:
                self._clear_pending_slide()
                self.slide_changed.emit(None)
        elif self._preview_slide_index >= 0:
            # 슬라이드 단독 송출
            self._live_hotspot = None
            self._live_slide_index = self._preview_slide_index
            self.live_changed.emit(f"Slide {self._live_slide_index + 1}")

            if self._slide_manager:
                self._emit_slide_if_available(self._live_slide_index)

    def clear_live(self) -> None:
        """Live 내용 지우기"""
        self._live_hotspot = None
        self._live_slide_index = -1
        self._clear_pending_slide()
        self.live_changed.emit("")
        self.slide_changed.emit(None)

    def sync_live(self) -> None:
        """현재 Live 상태를 다시 송출 (이미 열린 창 동기화용).

        송출 중인 슬라이드를 다시 계산하지 않고 send_to_live가 확정한
        _live_slide_index를 그대로 다시 내보낸다 — 여기서 현재 절로
        다시 계산하면 절 버튼만 눌러도 송출 화면이 즉시 바뀐다.
        절 이동은 프리뷰까지만 반영하고 송출은 Enter로만 바뀌어야 한다.
        """
        if self._live_hotspot:
            self.live_changed.emit(self._live_hotspot.lyric)

            slide_idx = self._live_slide_index
            if slide_idx < 0:
                # 아직 확정된 인덱스가 없을 때만(예: 프로젝트 복구 직후)
                # 송출 당시 절로 되짚는다.
                v_idx = self._live_verse_index
                slide_idx = self._live_hotspot.get_slide_index(v_idx)
                if slide_idx < 0:
                    slide_idx = self._live_hotspot.get_slide_index(5)
                self._live_slide_index = slide_idx

            if self._slide_manager and slide_idx >= 0:
                self._emit_slide_if_available(slide_idx)
        elif self._live_slide_index >= 0:
            self.live_changed.emit(f"Slide {self._live_slide_index + 1}")
            if self._slide_manager:
                self._emit_slide_if_available(self._live_slide_index)
        else:
            self._clear_pending_slide()
            self.live_changed.emit("")
            self.slide_changed.emit(None)

    def next_hotspot(self) -> Hotspot | None:
        """다음 핫스팟으로 Preview 이동"""
        if not self._project:
            return None

        sheet = self._project.get_current_score_sheet()
        if not sheet:
            return None

        ordered = sheet.get_ordered_hotspots()
        if not ordered:
            return None

        if not self._preview_hotspot:
            # 첫 번째 핫스팟 선택
            hotspot: Hotspot = ordered[0]
        else:
            # 다음 핫스팟 찾기
            next_hotspot = sheet.get_next_hotspot(self._preview_hotspot.id)
            if not next_hotspot:
                return None  # 마지막 핫스팟
            hotspot = next_hotspot

        self.set_preview(hotspot)
        return hotspot

    def previous_hotspot(self) -> Hotspot | None:
        """이전 핫스팟으로 Preview 이동"""
        if not self._project:
            return None

        sheet = self._project.get_current_score_sheet()
        if not sheet or not self._preview_hotspot:
            return None

        hotspot = sheet.get_previous_hotspot(self._preview_hotspot.id)
        if hotspot:
            self.set_preview(hotspot)

        return hotspot

    @property
    def preview_hotspot(self) -> Hotspot | None:
        """현재 Preview 핫스팟"""
        return self._preview_hotspot

    @property
    def live_hotspot(self) -> Hotspot | None:
        """현재 Live 핫스팟"""
        return self._live_hotspot

    @property
    def live_slide_index(self) -> int:
        """현재 Live 전역 슬라이드 인덱스 (없으면 -1)"""
        return self._live_slide_index
