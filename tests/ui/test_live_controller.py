import pytest
from PySide6.QtGui import QImage

from flow.domain.project import Project
from flow.domain.score_sheet import ScoreSheet
from flow.domain.hotspot import Hotspot
from flow.ui.live.live_controller import LiveController


class SignalSpy:
    """Qt 시그널 발생 여부와 인자를 기록하는 간단한 스파이 클래스"""

    def __init__(self, signal):
        self.called = False
        self.args = None
        signal.connect(self.callback)

    def callback(self, *args):
        self.called = True
        self.args = args


class MockSlideManager:
    """테스트용 슬라이드 매니저 모킹"""

    def get_slide_image(self, index):
        return QImage(100, 100, QImage.Format.Format_RGB32)


@pytest.fixture
def live_controller(qapp):
    """테스트용 LiveController 인스턴스"""
    manager = MockSlideManager()
    controller = LiveController(slide_manager=manager)
    project = Project(name="Test Project")
    sheet = ScoreSheet(name="Sheet 1")
    project.add_score_sheet(sheet)
    controller.set_project(project)
    return controller


class TestLiveControllerPreview:
    """Preview 설정 테스트"""

    def test_set_preview_emits_signal(self, live_controller):
        """핫스팟 Preview 설정 시 시그널 발생 확인"""
        spy = SignalSpy(live_controller.preview_changed)
        hotspot = Hotspot(x=10, y=20, lyric="Test Lyric")

        live_controller.set_preview(hotspot)

        assert spy.called
        assert spy.args[0] == "Test Lyric"
        assert live_controller.preview_hotspot == hotspot

    def test_set_preview_slide_direct_emits_signal(self, live_controller):
        """슬라이드 직접 선택 시 Preview 시그널 발생 확인"""
        spy = SignalSpy(live_controller.preview_changed)

        live_controller.set_preview_slide(5)

        assert spy.called
        assert spy.args[0] == "Slide 6 (Direct)"
        assert live_controller._preview_slide_index == 5


class TestLiveControllerBroadcast:
    """Live 송출(Send to Live) 테스트"""

    def test_send_hotspot_to_live(self, live_controller):
        """Preview 핫스팟을 Live로 송출"""
        hotspot = Hotspot(x=10, y=20, lyric="Sending to Live")
        hotspot.set_slide_index(0, verse_index=0)
        live_controller.set_preview(hotspot)

        live_spy = SignalSpy(live_controller.live_changed)
        slide_spy = SignalSpy(live_controller.slide_changed)

        live_controller.send_to_live()

        assert live_spy.called
        assert live_spy.args[0] == "Sending to Live"
        assert slide_spy.called
        assert isinstance(slide_spy.args[0], QImage)
        assert live_controller.live_hotspot == hotspot

    def test_send_direct_slide_to_live(self, live_controller):
        """직접 선택된 슬라이드를 Live로 송출"""
        live_controller.set_preview_slide(3)

        live_spy = SignalSpy(live_controller.live_changed)
        slide_spy = SignalSpy(live_controller.slide_changed)

        live_controller.send_to_live()

        assert live_spy.called
        assert live_spy.args[0] == "Slide 4"
        assert slide_spy.called
        assert isinstance(slide_spy.args[0], QImage)

    def test_clear_live_emits_empty_signals(self, live_controller):
        """Live 화면 초기화 시 빈 시그널 발생"""
        live_controller.set_preview_slide(0)
        live_controller.send_to_live()

        live_spy = SignalSpy(live_controller.live_changed)
        slide_spy = SignalSpy(live_controller.slide_changed)

        live_controller.clear_live()

        assert live_spy.called
        assert live_spy.args[0] == ""
        assert slide_spy.called
        assert slide_spy.args[0] is None


class TestLiveNeverConvertsInline:
    """라이브 송출도 GUI 스레드 인라인 변환 금지.

    캐시 미스 시 peek이 None을 돌려주면 이전 프레임을 유지하고,
    변환 완료(load_finished) 후 sync_live로 채워 넣는다.
    """

    class _PeekManager:
        def __init__(self, image=None):
            self.image = image
            self.peek_calls = 0
            self.inline_calls = 0

        def peek_slide_image(self, index):
            self.peek_calls += 1
            return self.image

        def get_slide_image(self, index):
            self.inline_calls += 1
            return QImage(100, 100, QImage.Format.Format_RGB32)

    def _controller(self, manager):
        controller = LiveController(slide_manager=manager)
        project = Project(name="Test Project")
        sheet = ScoreSheet(name="Sheet 1")
        project.add_score_sheet(sheet)
        controller.set_project(project)
        return controller

    def test_send_to_live_uses_peek_not_inline(self, qapp):
        img = QImage(64, 64, QImage.Format.Format_RGB32)
        mgr = self._PeekManager(image=img)
        controller = self._controller(mgr)
        h = Hotspot(x=1, y=1)
        h.set_slide_index(0, verse_index=0)
        controller.set_preview(h)

        spy = SignalSpy(controller.slide_changed)
        controller.send_to_live()

        assert mgr.inline_calls == 0, "라이브 송출이 인라인 변환을 호출하면 안 됨"
        assert mgr.peek_calls >= 1
        assert spy.called and spy.args[0] is img

    def test_send_to_live_keeps_last_frame_on_cache_miss(self, qapp):
        mgr = self._PeekManager(image=None)  # 캐시 미스
        controller = self._controller(mgr)
        h = Hotspot(x=1, y=1)
        h.set_slide_index(0, verse_index=0)
        controller.set_preview(h)

        spy = SignalSpy(controller.slide_changed)
        controller.send_to_live()

        # None을 쏘면 송출 화면이 꺼진다 — 미스 시에는 발신하지 않고 유지
        assert not spy.called
        assert mgr.inline_calls == 0

    def test_sync_live_uses_peek_and_fills_when_ready(self, qapp):
        mgr = self._PeekManager(image=None)
        controller = self._controller(mgr)
        h = Hotspot(x=1, y=1)
        h.set_slide_index(0, verse_index=0)
        controller.set_preview(h)
        controller.send_to_live()

        img = QImage(64, 64, QImage.Format.Format_RGB32)
        mgr.image = img  # 백그라운드 변환 완료 시뮬레이션
        spy = SignalSpy(controller.slide_changed)
        controller.sync_live()

        assert spy.called and spy.args[0] is img
        assert mgr.inline_calls == 0
