# tests/ui/test_emergency_patch_panel.py
"""Tests for EmergencyPatchPanel — the live-mode split editor."""
from __future__ import annotations

from pathlib import Path

import pytest

from flow.services.markdown import (
    Frontmatter,
    Slide,
    SongSpec,
)
from flow.ui.live.emergency_patch_panel import EmergencyPatchPanel


def _make_spec(*mains: str) -> SongSpec:
    return SongSpec(
        title="t",
        frontmatter=Frontmatter(),
        slides=[
            Slide(main=m, sub_override=None, section_sub_default=None) for m in mains
        ],
    )


def test_open_in_edit_mode_loads_slide_text(qtbot, tmp_path: Path) -> None:
    spec = _make_spec("원본 1", "원본 2", "원본 3")
    panel = EmergencyPatchPanel(spec=spec, song_dir=tmp_path, initial_index=1)
    qtbot.addWidget(panel)
    assert panel.current_text() == "원본 2"


def test_open_in_add_mode_starts_empty(qtbot, tmp_path: Path) -> None:
    spec = _make_spec("원본 1", "원본 2")
    panel = EmergencyPatchPanel(
        spec=spec, song_dir=tmp_path, initial_index=None  # add mode
    )
    qtbot.addWidget(panel)
    assert panel.current_text() == ""
    assert panel.is_add_mode()


def test_typing_updates_pending_text(qtbot, tmp_path: Path) -> None:
    spec = _make_spec("원본 1")
    panel = EmergencyPatchPanel(spec=spec, song_dir=tmp_path, initial_index=0)
    qtbot.addWidget(panel)
    panel.set_text("고친 가사")
    assert panel.current_text() == "고친 가사"
    assert panel.has_pending_changes()


def test_preview_updates_when_text_changes(qtbot, tmp_path: Path) -> None:
    spec = _make_spec("원본 1")
    panel = EmergencyPatchPanel(spec=spec, song_dir=tmp_path, initial_index=0)
    qtbot.addWidget(panel)
    panel.show()
    pix_before = panel.preview_pixmap()
    assert pix_before is not None
    panel.set_text("크게 고친 가사")
    pix_after = panel.preview_pixmap()
    assert pix_after is not None
    # Image bytes should differ when text changed (rough but reliable smoke check)
    assert pix_before.toImage() != pix_after.toImage()


def test_next_slide_navigates_forward(qtbot, tmp_path: Path) -> None:
    spec = _make_spec("원본 1", "원본 2", "원본 3")
    panel = EmergencyPatchPanel(spec=spec, song_dir=tmp_path, initial_index=0)
    qtbot.addWidget(panel)
    panel.go_next()
    assert panel.current_text() == "원본 2"
    panel.go_next()
    assert panel.current_text() == "원본 3"


def test_prev_slide_navigates_backward(qtbot, tmp_path: Path) -> None:
    spec = _make_spec("원본 1", "원본 2", "원본 3")
    panel = EmergencyPatchPanel(spec=spec, song_dir=tmp_path, initial_index=2)
    qtbot.addWidget(panel)
    panel.go_prev()
    assert panel.current_text() == "원본 2"


def test_pending_text_preserved_across_navigation(qtbot, tmp_path: Path) -> None:
    spec = _make_spec("원본 1", "원본 2", "원본 3")
    panel = EmergencyPatchPanel(spec=spec, song_dir=tmp_path, initial_index=0)
    qtbot.addWidget(panel)
    panel.set_text("진행중 1")
    panel.go_next()
    assert panel.current_text() == "원본 2"  # slide 2 unedited
    panel.set_text("진행중 2")
    panel.go_prev()
    assert panel.current_text() == "진행중 1"  # came back to slide 1's pending


def test_can_go_next_at_last_returns_false(qtbot, tmp_path: Path) -> None:
    spec = _make_spec("원본 1", "원본 2")
    panel = EmergencyPatchPanel(spec=spec, song_dir=tmp_path, initial_index=1)
    qtbot.addWidget(panel)
    assert not panel.can_go_next()


def test_can_go_prev_at_first_returns_false(qtbot, tmp_path: Path) -> None:
    spec = _make_spec("원본 1", "원본 2")
    panel = EmergencyPatchPanel(spec=spec, song_dir=tmp_path, initial_index=0)
    qtbot.addWidget(panel)
    assert not panel.can_go_prev()
