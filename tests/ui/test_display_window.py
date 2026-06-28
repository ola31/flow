from __future__ import annotations

from PySide6.QtCore import Qt

from flow.ui.display.display_window import DisplayWindow


def test_show_on_screen_windowed_clears_fullscreen_state(qtbot) -> None:
    window = DisplayWindow()
    qtbot.addWidget(window)

    window.showFullScreen()
    assert window.isFullScreen()

    window.show_on_screen(None, windowed=True)

    assert not window.isFullScreen()
    assert window.windowState() == Qt.WindowState.WindowNoState
    assert window.size().width() == 960
    assert window.size().height() == 540
