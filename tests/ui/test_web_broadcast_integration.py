from __future__ import annotations

from flow.ui.main_window import MainWindow


def test_web_broadcast_attr_default(qapp):
    mw = MainWindow()
    try:
        assert mw._web_broadcast is None
    finally:
        mw.close()


def test_stop_web_broadcast_resets_action_text(qapp):
    from flow.services.web_broadcast import WebBroadcastServer

    mw = MainWindow()
    try:
        mw._web_broadcast = WebBroadcastServer()
        mw._web_broadcast.start()
        mw._stop_web_broadcast()
        assert not mw._web_broadcast.is_running()
        assert mw._display_action.text() == "송출 시작"
    finally:
        mw.close()


def test_slide_changed_pushes_to_web(qapp, monkeypatch):
    from PySide6.QtGui import QImage

    mw = MainWindow()
    try:
        pushes = []

        class _FakeServer:
            def is_running(self):
                return True

            def push_current_slide(self, song, local_idx, image):
                pushes.append((song, local_idx, image))

        mw._web_broadcast = _FakeServer()
        monkeypatch.setattr(
            type(mw._live_controller),
            "live_slide_index",
            property(lambda self: 0),
        )
        monkeypatch.setattr(
            mw._slide_manager, "global_to_local", lambda idx: ("곡A", 0)
        )
        img = QImage(4, 4, QImage.Format.Format_RGB32)
        mw._on_slide_changed(img)
        assert len(pushes) == 1
        assert pushes[0][2] is img
    finally:
        mw.close()


def test_web_broadcast_toggle_updates_display_action_text(qapp):
    """FIX-I2: F11 action text must track web-broadcast start/stop, and the
    web-broadcast screen must reflect the stopped server too."""
    mw = MainWindow()
    try:
        assert mw._display_action.text() == "송출 시작"

        mw._on_web_broadcast_toggle()
        assert mw._web_broadcast.is_running()
        assert mw._display_action.text() == "송출 중지"

        mw._stop_web_broadcast()
        assert not mw._web_broadcast.is_running()
        assert mw._display_action.text() == "송출 시작"
        assert mw._web_broadcast_screen._server is mw._web_broadcast
    finally:
        mw.close()


def test_display_closed_keeps_stop_text_while_web_broadcast_running(qapp):
    """FIX-I2: closing the (unrelated) physical display window must not
    reset the F11 label to "송출 시작" while web broadcast is still live."""
    from flow.services.web_broadcast import WebBroadcastServer

    mw = MainWindow()
    try:
        mw._web_broadcast = WebBroadcastServer()
        mw._web_broadcast.start()
        mw._display_action.setText("송출 중지")

        mw._on_display_closed()

        assert mw._display_action.text() == "송출 중지"
    finally:
        mw.close()


def test_slide_cleared_pushes_clear(qapp, monkeypatch):
    mw = MainWindow()
    try:
        pushes = []

        class _FakeServer:
            def is_running(self):
                return True

            def push_current_slide(self, song, local_idx, image):
                pushes.append((song, local_idx, image))

        mw._web_broadcast = _FakeServer()
        mw._on_slide_changed(None)
        assert pushes == [(None, -1, None)]
    finally:
        mw.close()


def test_hotspot_toggle_starts_when_confirmed(qapp, monkeypatch):
    import flow.ui.dialogs as dialogs
    from flow.ui.main_window import MainWindow

    mw = MainWindow()
    try:
        started = {}

        class _FakeHS:
            def is_active(self):
                return started.get("on", False)

            def start(self, ssid, pw):
                started["on"] = True
                started["args"] = (ssid, pw)
                return True

            def stop(self):
                started["on"] = False

            def last_error(self):
                return ""

            def is_supported(self):
                return True

            def support_message(self):
                return ""

            def captive_portal_installed(self):
                return False

            def captive_portal_install_command(self):
                return []

        mw._hotspot = _FakeHS()
        monkeypatch.setattr(dialogs, "flow_question", lambda *a, **k: True)
        mw._on_hotspot_toggle()
        assert started.get("on") is True
        assert started["args"][0]  # ssid auto-generated + non-empty
    finally:
        mw.close()


def test_hotspot_toggle_cancel_does_not_start(qapp, monkeypatch):
    import flow.ui.dialogs as dialogs
    from flow.ui.main_window import MainWindow

    mw = MainWindow()
    try:
        started = {}

        class _FakeHS:
            def is_active(self):
                return False

            def start(self, ssid, pw):
                started["on"] = True
                return True

            def stop(self):
                pass

            def is_supported(self):
                return True

            def support_message(self):
                return ""

            def captive_portal_installed(self):
                return False

        mw._hotspot = _FakeHS()
        monkeypatch.setattr(dialogs, "flow_question", lambda *a, **k: False)
        mw._on_hotspot_toggle()
        assert "on" not in started
    finally:
        mw.close()


def test_captive_install_finished_failure_shows_warning(qapp, monkeypatch):
    """FIX-6 (I1): a non-zero pkexec exit (e.g. permission denied = 126) must
    surface a user-visible warning, not fail silently."""
    import flow.ui.dialogs as dialogs
    from flow.ui.main_window import MainWindow

    mw = MainWindow()
    try:
        warned = []
        monkeypatch.setattr(
            dialogs, "flow_warning", lambda *a, **k: warned.append(a)
        )
        mw._on_captive_install_finished(126)
        assert warned
    finally:
        mw.close()


def test_hotspot_toggle_auto_installs_captive_before_starting(
    qapp, monkeypatch, qtbot
):
    """Users shouldn't need to discover the separate '폰 튕김 방지 설정하기'
    button — turning the hotspot on when it isn't installed yet should
    install it automatically first, then start the hotspot."""
    import flow.ui.dialogs as dialogs
    from flow.ui.main_window import MainWindow

    mw = MainWindow()
    try:
        calls = []

        class _FakeHS:
            def is_active(self):
                return False

            def is_supported(self):
                return True

            def captive_portal_installed(self):
                return False

            def captive_portal_install_command(self):
                return ["true"]

            def start(self, ssid, pw):
                calls.append("start")
                return True

            def last_error(self):
                return ""

        mw._hotspot = _FakeHS()
        monkeypatch.setattr(dialogs, "flow_question", lambda *a, **k: True)
        mw._on_hotspot_toggle()
        assert "start" not in calls  # waits for install to finish first
        qtbot.waitUntil(lambda: "start" in calls, timeout=3000)
    finally:
        mw.close()


def test_hotspot_toggle_starts_directly_when_already_installed(qapp, monkeypatch):
    """No captive install step (and no QProcess round-trip) when it's
    already installed — the common case after the first run."""
    import flow.ui.dialogs as dialogs
    from flow.ui.main_window import MainWindow

    mw = MainWindow()
    try:
        calls = []

        class _FakeHS:
            def is_active(self):
                return False

            def is_supported(self):
                return True

            def captive_portal_installed(self):
                return True

            def captive_portal_install_command(self):
                raise AssertionError("should not be called when already installed")

            def start(self, ssid, pw):
                calls.append("start")
                return True

            def last_error(self):
                return ""

        mw._hotspot = _FakeHS()
        monkeypatch.setattr(dialogs, "flow_question", lambda *a, **k: True)
        mw._on_hotspot_toggle()
        assert calls == ["start"]
    finally:
        mw.close()


def test_captive_install_finished_success_restarts_active_hotspot(qapp):
    """FIX-6 (I1) / FIX-5 (C1): once the captive config is installed, an
    already-running hotspot must be restarted so dnsmasq/dispatcher pick up
    the new config."""
    from flow.ui.main_window import MainWindow

    mw = MainWindow()
    try:
        calls = []

        class _FakeHS:
            def is_active(self):
                return True

            def stop(self):
                calls.append("stop")

            def start(self, ssid, pw):
                calls.append(("start", ssid, pw))
                return True

        mw._hotspot = _FakeHS()
        mw._config_service.set_hotspot_ssid("Flow-TEST")
        mw._config_service.set_hotspot_password("pw123456")
        mw._on_captive_install_finished(0)
        assert calls[0] == "stop"
        assert calls[1] == ("start", "Flow-TEST", "pw123456")
    finally:
        mw.close()


def test_hotspot_toggle_stops_when_active(qapp):
    from flow.ui.main_window import MainWindow

    mw = MainWindow()
    try:
        state = {"on": True}

        class _FakeHS:
            def is_active(self):
                return state["on"]

            def start(self, ssid, pw):
                state["on"] = True
                return True

            def stop(self):
                state["on"] = False

            def last_error(self):
                return ""

            def is_supported(self):
                return True

            def support_message(self):
                return ""

            def captive_portal_installed(self):
                return False

        mw._hotspot = _FakeHS()
        mw._on_hotspot_toggle()
        assert state["on"] is False
    finally:
        mw.close()
