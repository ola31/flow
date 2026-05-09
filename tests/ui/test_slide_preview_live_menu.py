# tests/ui/test_slide_preview_live_menu.py
"""Live-mode slide preview thumbnail menu offers patch actions."""
from __future__ import annotations

import pytest

from flow.ui.editor.slide_preview_panel import SlidePreviewPanel


def test_signals_exist() -> None:
    assert hasattr(SlidePreviewPanel, "emergency_patch_requested")
    assert hasattr(SlidePreviewPanel, "append_slide_requested")


def test_set_live_markdown_mode(qtbot) -> None:
    panel = SlidePreviewPanel()
    qtbot.addWidget(panel)
    panel.set_live_mode(is_live=True, slide_source="markdown")
    assert panel._live_emergency_enabled is True


def test_set_live_pptx_mode_disables_patches(qtbot) -> None:
    panel = SlidePreviewPanel()
    qtbot.addWidget(panel)
    panel.set_live_mode(is_live=True, slide_source="pptx")
    assert panel._live_emergency_enabled is False


def test_set_live_off_disables_patches(qtbot) -> None:
    panel = SlidePreviewPanel()
    qtbot.addWidget(panel)
    panel.set_live_mode(is_live=True, slide_source="markdown")
    panel.set_live_mode(is_live=False, slide_source="markdown")
    assert panel._live_emergency_enabled is False
