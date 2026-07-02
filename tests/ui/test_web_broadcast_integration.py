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
