# tests/ui/test_score_canvas_live_menu.py
"""Live-mode hotspot context menu shows '긴급 수정' for markdown songs only."""
from __future__ import annotations

import pytest

from flow.ui.editor.score_canvas import ScoreCanvas


def test_emergency_patch_signal_exists() -> None:
    # Sanity: signal is declared on the class
    assert hasattr(ScoreCanvas, "emergency_patch_requested")


def test_set_live_markdown_mode_enables_emergency_menu(qtbot) -> None:
    canvas = ScoreCanvas()
    qtbot.addWidget(canvas)
    canvas.set_live_mode(is_live=True, slide_source="markdown")
    assert canvas._live_emergency_enabled is True


def test_set_live_pptx_mode_disables_emergency_menu(qtbot) -> None:
    canvas = ScoreCanvas()
    qtbot.addWidget(canvas)
    canvas.set_live_mode(is_live=True, slide_source="pptx")
    assert canvas._live_emergency_enabled is False


def test_set_live_off_disables_emergency_menu(qtbot) -> None:
    canvas = ScoreCanvas()
    qtbot.addWidget(canvas)
    canvas.set_live_mode(is_live=True, slide_source="markdown")
    canvas.set_live_mode(is_live=False, slide_source="markdown")
    assert canvas._live_emergency_enabled is False
