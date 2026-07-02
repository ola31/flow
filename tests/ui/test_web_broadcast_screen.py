from __future__ import annotations

from flow.ui.screens.web_broadcast_screen import WebBroadcastScreen


class _FakeSignal:
    def connect(self, *_):
        pass

    def disconnect(self, *_):
        pass


class _FakeServer:
    def __init__(self, running=True):
        self._running = running
        self.client_count_changed = _FakeSignal()

    def is_running(self):
        return self._running

    def local_urls(self):
        return ["http://192.168.0.10:8777"]

    def client_count(self):
        return 2


def test_screen_idle_state(qtbot):
    screen = WebBroadcastScreen()
    qtbot.addWidget(screen)
    screen.set_server(None)
    assert "꺼져" in screen._status_label.text()
    assert not screen._url_label.isVisibleTo(screen)


def test_screen_running_state_shows_urls_and_clients(qtbot):
    screen = WebBroadcastScreen()
    qtbot.addWidget(screen)
    screen.set_server(_FakeServer(running=True))
    assert "192.168.0.10" in screen._url_label.text()
    assert "2" in screen._clients_label.text()
    assert screen._qr_label.pixmap() is not None


def test_toggle_button_emits_signal(qtbot):
    screen = WebBroadcastScreen()
    qtbot.addWidget(screen)
    fired = []
    screen.toggle_requested.connect(lambda: fired.append(1))
    screen._toggle_btn.click()
    assert fired == [1]


def test_activity_bar_has_web_button(qapp):
    from flow.ui.activity_bar import ActivityBar

    bar = ActivityBar()
    assert hasattr(bar, "_btn_web_broadcast")


def test_main_window_navigates_to_web_screen(qapp):
    from flow.ui.main_window import MainWindow

    mw = MainWindow()
    try:
        mw._show_web_broadcast_screen()
        assert mw._stack.currentWidget() is mw._web_broadcast_screen
    finally:
        mw.close()


class _FakeHotspot:
    def __init__(self, supported=True, active=False, captive=False):
        self._sup, self._active, self._captive = supported, active, captive

        class _Sig:
            def connect(self, *_): pass
            def disconnect(self, *_): pass

        self.state_changed = _Sig()

    def is_supported(self): return self._sup
    def is_active(self): return self._active
    def support_message(self): return "" if self._sup else "미지원 메시지"
    def captive_portal_installed(self): return self._captive


def test_hotspot_section_unsupported_hides_toggle(qtbot):
    from flow.ui.screens.web_broadcast_screen import WebBroadcastScreen
    s = WebBroadcastScreen()
    qtbot.addWidget(s)
    s.set_hotspot(_FakeHotspot(supported=False))
    assert not s._hotspot_toggle_btn.isVisibleTo(s)
    assert "미지원" in s._hotspot_info_label.text()


def test_hotspot_toggle_emits(qtbot):
    from flow.ui.screens.web_broadcast_screen import WebBroadcastScreen
    s = WebBroadcastScreen()
    qtbot.addWidget(s)
    s.set_hotspot(_FakeHotspot(supported=True, active=False))
    fired = []
    s.hotspot_toggle_requested.connect(lambda: fired.append(1))
    s._hotspot_toggle_btn.click()
    assert fired == [1]
    assert s._hotspot_toggle_btn.text() == "핫스팟 켜기"


def test_captive_button_shown_when_active_and_not_installed(qtbot):
    from flow.ui.screens.web_broadcast_screen import WebBroadcastScreen
    s = WebBroadcastScreen()
    qtbot.addWidget(s)
    s.set_hotspot(_FakeHotspot(supported=True, active=True, captive=False))
    assert s._captive_btn.isVisibleTo(s)


def test_captive_hidden_when_installed(qtbot):
    from flow.ui.screens.web_broadcast_screen import WebBroadcastScreen
    s = WebBroadcastScreen()
    qtbot.addWidget(s)
    s.set_hotspot(_FakeHotspot(supported=True, active=True, captive=True))
    assert not s._captive_btn.isVisibleTo(s)
    assert "켜짐" in s._captive_status_label.text()


def test_set_hotspot_credentials_shown_when_active(qtbot):
    from flow.ui.screens.web_broadcast_screen import WebBroadcastScreen
    s = WebBroadcastScreen()
    qtbot.addWidget(s)
    s.set_hotspot(_FakeHotspot(supported=True, active=True))
    s.set_hotspot_credentials("Flow-0001", "pw123456")
    assert "Flow-0001" in s._hotspot_info_label.text()
    assert "pw123456" in s._hotspot_info_label.text()
