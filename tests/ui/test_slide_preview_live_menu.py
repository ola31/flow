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


def test_set_patched_indices_marks_thumbnails(qtbot) -> None:
    panel = SlidePreviewPanel()
    qtbot.addWidget(panel)

    # Seed it with 3 fake slides
    from PySide6.QtGui import QPixmap
    from PySide6.QtWidgets import QListWidgetItem
    from PySide6.QtCore import Qt

    for i in range(3):
        item = QListWidgetItem(f"#{i+1}")
        item.setData(Qt.ItemDataRole.UserRole, i)
        item.setIcon(QPixmap(144, 81))
        panel._list.addItem(item)

    panel.set_patched_indices({1})
    assert panel._patched_indices == {1}
    # Internal list also tracks them for paint
    assert panel._list._patched_indices == {1}
