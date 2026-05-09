# tests/ui/test_main_window_patch_focus.py
"""When the patch panel is focused, live single-key shortcuts no-op."""
from __future__ import annotations

import pytest

from flow.ui.main_window import MainWindow


def test_patch_panel_has_focus_returns_false_when_no_panel(qtbot) -> None:
    win = MainWindow()
    qtbot.addWidget(win)
    assert win._patch_panel is None
    assert not win._patch_panel_has_focus()


def test_patch_panel_has_focus_returns_true_when_panel_focused(qtbot) -> None:
    """Smoke test: helper returns True when fake panel claims focus."""
    win = MainWindow()
    qtbot.addWidget(win)
    win._is_live = True

    class FakePanel:
        def hasFocus(self) -> bool:
            return True
        def isAncestorOf(self, _w) -> bool:
            return False

    win._patch_panel = FakePanel()
    assert win._patch_panel_has_focus()


def test_toggle_patch_focus_no_op_without_panel(qtbot) -> None:
    win = MainWindow()
    qtbot.addWidget(win)
    # Should not crash when no panel
    win._toggle_patch_focus()
