"""라이브 컨트롤러

Preview-Live 2단계 송출 로직을 관리
"""

from PySide6.QtCore import QObject, Signal

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

    def __init__(self, parent: QObject | None = None, slide_manager = None) -> None:
        super().__init__(parent)
        self._project: Project | None = None
        self._preview_hotspot: Hotspot | None = None
        self._preview_slide_index: int = -1
        self._live_hotspot: Hotspot | None = None
        self._live_slide_index: int = -1
        self._slide_manager = slide_manager

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

    def _emit_slide_if_available(self, slide_idx: int) -> None:
        """캐시된 슬라이드만 송출하고, 미변환이면 이전 프레임을 유지한다.

        인라인 변환(get_slide_image)은 큰 PPT에서 GUI 전체를 얼리므로
        라이브 경로에서도 쓰지 않는다. 변환이 끝나면 MainWindow가
        sync_live()를 다시 호출해 채워 넣는다.
        """
        if not self._slide_manager:
            return
        peek = getattr(self._slide_manager, "peek_slide_image", None)
        if peek is not None:
            image = peek(slide_idx)
        else:  # 테스트 더블 등 peek이 없는 매니저 폴백
            image = self._slide_manager.get_slide_image(slide_idx)
        if image is not None and not image.isNull():
            self.slide_changed.emit(image)

    def send_to_live(self) -> None:
        """Preview 내용을 Live로 송출"""
        if self._preview_hotspot:
            self._live_hotspot = self._preview_hotspot
            self._live_slide_index = -1
            self.live_changed.emit(self._live_hotspot.lyric)

            # [수정] 현재 절(Verse)에 맞는 슬라이드 인덱스 구득
            v_idx = self._project.current_verse_index if self._project else 0
            slide_idx = self._live_hotspot.get_slide_index(v_idx)

            # 현재 절 매핑이 없더라도 후렴(5) 매핑이 있다면 활용 (범용 내비게이션 대응)
            if slide_idx < 0:
                slide_idx = self._live_hotspot.get_slide_index(5)

            self._live_slide_index = slide_idx

            if self._slide_manager and slide_idx >= 0:
                self._emit_slide_if_available(slide_idx)
            else:
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
        self.live_changed.emit("")
        self.slide_changed.emit(None)

    def sync_live(self) -> None:
        """현재 Live 상태를 다시 송출 (이미 열린 창 동기화용)"""
        if self._live_hotspot:
            self.live_changed.emit(self._live_hotspot.lyric)

            v_idx = self._project.current_verse_index if self._project else 0
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
