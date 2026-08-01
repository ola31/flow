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

    def test_live_slide_index_default_and_after_set(self, live_controller):
        """live_slide_index 프로퍼티 기본값 및 설정 반영 확인"""
        assert live_controller.live_slide_index == -1
        live_controller._live_slide_index = 3
        assert live_controller.live_slide_index == 3

    def test_live_slide_index_reflects_direct_slide_broadcast(self, live_controller):
        """직접 슬라이드 송출 시 live_slide_index가 반영됨"""
        live_controller.set_preview_slide(3)

        live_controller.send_to_live()

        assert live_controller.live_slide_index == 3

    def test_live_slide_index_reflects_hotspot_broadcast(self, live_controller):
        """핫스팟 송출 시에도 live_slide_index가 해당 전역 슬라이드 인덱스로 반영됨"""
        hotspot = Hotspot(x=10, y=20, lyric="Sending to Live")
        hotspot.set_slide_index(7, verse_index=0)
        live_controller.set_preview(hotspot)

        live_controller.send_to_live()

        assert live_controller.live_slide_index == 7

    def test_live_slide_index_reset_on_clear(self, live_controller):
        """Live 초기화 시 live_slide_index가 -1로 초기화됨"""
        live_controller.set_preview_slide(2)
        live_controller.send_to_live()
        assert live_controller.live_slide_index == 2

        live_controller.clear_live()

        assert live_controller.live_slide_index == -1


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


class TestVerseChangeDoesNotMoveLive:
    """절 이동은 프리뷰까지만 — 송출은 Enter로만 바뀐다.

    sync_live가 현재 절로 슬라이드를 다시 계산하면, 절 버튼을 누르는
    순간(또는 변환 완료로 sync_live가 불리는 순간) 송출 화면이 튄다.
    """

    class _PeekManager:
        def __init__(self, image=None):
            self.image = image

        def peek_slide_image(self, index):
            return self.image

    def _controller(self, mgr):
        controller = LiveController(slide_manager=mgr)
        project = Project(name="P")
        project.add_score_sheet(ScoreSheet(name="S"))
        controller.set_project(project)
        return controller

    def _hotspot(self):
        h = Hotspot(x=1, y=1)
        h.set_slide_index(10, verse_index=0)  # 1절 → 슬라이드 10
        h.set_slide_index(20, verse_index=1)  # 2절 → 슬라이드 20
        return h

    def test_sync_live_keeps_slide_after_verse_change(self, qapp):
        img = QImage(8, 8, QImage.Format.Format_RGB32)
        mgr = self._PeekManager(image=img)
        controller = self._controller(mgr)
        controller.set_preview(self._hotspot())
        controller.send_to_live()
        assert controller.live_slide_index == 10

        # 사용자가 2절로 이동 (프로젝트 상태만 바뀜)
        controller._project.current_verse_index = 1
        controller.sync_live()

        assert controller.live_slide_index == 10, (
            "절만 바꿨는데 송출 슬라이드가 따라 움직이면 안 됨"
        )

    def test_send_to_live_commits_new_verse(self, qapp):
        img = QImage(8, 8, QImage.Format.Format_RGB32)
        mgr = self._PeekManager(image=img)
        controller = self._controller(mgr)
        h = self._hotspot()
        controller.set_preview(h)
        controller.send_to_live()

        controller._project.current_verse_index = 1
        controller.set_preview(h)
        controller.send_to_live()  # Enter — 이때 비로소 2절이 송출됨

        assert controller.live_slide_index == 20


class TestPendingSlideRetry:
    """미변환 슬라이드는 변환이 끝나는 대로 자동으로 채워진다.

    load_finished만 믿으면 화면 전환 중이거나 워커 큐가 비워졌을 때
    재시도가 오지 않아 이전 슬라이드가 그대로 남는다.
    """

    class _LateManager:
        def __init__(self):
            self.image = None

        def peek_slide_image(self, index):
            return self.image

    def _controller(self, mgr):
        controller = LiveController(slide_manager=mgr)
        project = Project(name="P")
        project.add_score_sheet(ScoreSheet(name="S"))
        controller.set_project(project)
        return controller

    def test_retry_emits_once_conversion_lands(self, qtbot):
        mgr = self._LateManager()
        controller = self._controller(mgr)
        controller._RETRY_INTERVAL_MS = 10
        controller._retry_timer.setInterval(10)

        h = Hotspot(x=1, y=1)
        h.set_slide_index(3, verse_index=0)
        controller.set_preview(h)

        spy = SignalSpy(controller.slide_changed)
        controller.send_to_live()
        assert not spy.called  # 캐시 미스 — 이전 프레임 유지
        assert controller._retry_timer.isActive()

        img = QImage(8, 8, QImage.Format.Format_RGB32)
        mgr.image = img  # 백그라운드 변환 완료

        qtbot.waitUntil(lambda: spy.called, timeout=2000)
        assert spy.args[0] is img
        assert not controller._retry_timer.isActive()

    def test_clear_live_stops_retry(self, qapp):
        mgr = self._LateManager()
        controller = self._controller(mgr)
        h = Hotspot(x=1, y=1)
        h.set_slide_index(3, verse_index=0)
        controller.set_preview(h)
        controller.send_to_live()
        assert controller._retry_timer.isActive()

        controller.clear_live()

        assert not controller._retry_timer.isActive()


class TestRetryDoesNotStormConversions:
    """폴링이 매 틱 변환을 예약하면 PowerPoint가 초당 몇 번씩 뜬다."""

    class _CountingManager:
        def __init__(self):
            self.image = None
            self.scheduled = 0
            self.peeks = 0

        def peek_slide_image(self, index, *, schedule=True):
            self.peeks += 1
            if schedule:
                self.scheduled += 1
            return self.image

    def _controller(self, mgr):
        controller = LiveController(slide_manager=mgr)
        project = Project(name="P")
        project.add_score_sheet(ScoreSheet(name="S"))
        controller.set_project(project)
        return controller

    def _pending(self, mgr):
        controller = self._controller(mgr)
        h = Hotspot(x=1, y=1)
        h.set_slide_index(3, verse_index=0)
        controller.set_preview(h)
        controller.send_to_live()
        return controller

    def test_first_miss_schedules_once(self, qapp):
        mgr = self._CountingManager()
        controller = self._pending(mgr)

        assert mgr.scheduled == 1
        assert controller._retry_timer.isActive()

    def test_polling_does_not_reschedule_every_tick(self, qapp):
        mgr = self._CountingManager()
        controller = self._pending(mgr)
        before = mgr.scheduled

        for _ in range(controller._RESCHEDULE_EVERY_TICKS - 1):
            controller._retry_pending_slide()

        assert mgr.peeks > before  # 캐시는 계속 확인하되
        assert mgr.scheduled == before  # 변환 재예약은 하지 않는다

    def test_reschedules_occasionally(self, qapp):
        mgr = self._CountingManager()
        controller = self._pending(mgr)
        before = mgr.scheduled

        for _ in range(controller._RESCHEDULE_EVERY_TICKS):
            controller._retry_pending_slide()

        # 화면 전환 등으로 큐가 비워졌을 경우를 대비해 가끔 한 번만
        assert mgr.scheduled == before + 1

    def test_stop_pending_slide_halts_polling(self, qapp):
        mgr = self._CountingManager()
        controller = self._pending(mgr)

        controller.stop_pending_slide()

        assert not controller._retry_timer.isActive()
        assert controller._pending_slide_index == -1

    def test_set_project_halts_polling(self, qapp):
        mgr = self._CountingManager()
        controller = self._pending(mgr)

        controller.set_project(Project(name="다른 프로젝트"))

        assert not controller._retry_timer.isActive()
