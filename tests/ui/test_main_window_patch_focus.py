# tests/ui/test_main_window_patch_focus.py
"""When the patch panel is focused, live single-key shortcuts no-op."""
from __future__ import annotations

import pytest

from flow.ui.main_window import MainWindow


def test_live_side_panel_has_focus_returns_false_when_no_panel(qtbot) -> None:
    win = MainWindow()
    qtbot.addWidget(win)
    assert win._live_side_panel is None
    assert not win._live_side_panel_has_focus()


def test_live_side_panel_has_focus_returns_true_when_panel_focused(qtbot) -> None:
    """Smoke test: helper returns True when fake panel claims focus."""
    win = MainWindow()
    qtbot.addWidget(win)
    win._is_live = True

    class FakePanel:
        def hasFocus(self) -> bool:
            return True
        def isAncestorOf(self, _w) -> bool:
            return False

    win._live_side_panel = FakePanel()
    assert win._live_side_panel_has_focus()
    win._live_side_panel = None  # clean up


def test_toggle_live_side_panel_focus_no_op_without_panel(qtbot) -> None:
    win = MainWindow()
    qtbot.addWidget(win)
    # Should not crash when no panel
    win._toggle_live_side_panel_focus()


# Kept for backward-compatibility: _patch_panel is still set alongside
# _live_side_panel when the emergency patch panel is mounted.
def test_patch_panel_attr_still_exists(qtbot) -> None:
    win = MainWindow()
    qtbot.addWidget(win)
    assert win._patch_panel is None


def test_patch_panel_exposes_focus_target(qapp) -> None:
    import pathlib
    from flow.services.markdown import parse
    from flow.ui.live.emergency_patch_panel import EmergencyPatchPanel
    spec = parse("# t\n\n가사\n")
    panel = EmergencyPatchPanel(spec=spec, song_dir=pathlib.Path("."), initial_index=0)
    try:
        assert panel.focus_target() is panel._editor
    finally:
        panel.deleteLater()
