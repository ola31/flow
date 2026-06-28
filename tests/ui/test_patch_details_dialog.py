"""Tests for PatchDetailsDialog — per-patch reconciliation surface."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from flow.services.markdown import slide_hash
from flow.ui.editor.patch_details_dialog import PatchDetailsDialog


@pytest.fixture
def song_with_patches(tmp_path: Path) -> Path:
    md = tmp_path / "slides.md"
    md.write_text("# t\n\n원본 1\n\n원본 2\n", encoding="utf-8")
    (tmp_path / ".patches.json").write_text(
        json.dumps(
            {
                "version": 1,
                "patches": [
                    {
                        "id": "edit-1",
                        "type": "edit",
                        "patched_main": "고친 1",
                        "slide_hash": slide_hash("원본 1"),
                        "slide_index": 0,
                        "created_at": "t",
                        "created_during": "live",
                    },
                    {
                        "id": "append-1",
                        "type": "append",
                        "patched_main": "추가된",
                        "created_at": "u",
                        "created_during": "live",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    return md


def test_dialog_shows_summary_with_patch_count(qtbot, song_with_patches: Path) -> None:
    dlg = PatchDetailsDialog(song_with_patches)
    qtbot.addWidget(dlg)
    assert "2" in dlg._summary_label.text()


def test_apply_one_writes_to_md_and_removes_patch(
    qtbot, song_with_patches: Path
) -> None:
    dlg = PatchDetailsDialog(song_with_patches)
    qtbot.addWidget(dlg)
    from flow.services.markdown import PatchStore

    store_before = PatchStore(song_with_patches.parent / ".patches.json")
    edit_patch = next(p for p in store_before.patches if p.type.value == "edit")

    with qtbot.waitSignal(dlg.patches_changed, timeout=1000):
        dlg._apply_one(edit_patch)

    new_text = song_with_patches.read_text(encoding="utf-8")
    assert "고친 1" in new_text
    assert "원본 1" not in new_text

    store_after = PatchStore(song_with_patches.parent / ".patches.json")
    assert all(p.id != "edit-1" for p in store_after.patches)


def test_discard_one_only_removes_patch(qtbot, song_with_patches: Path) -> None:
    dlg = PatchDetailsDialog(song_with_patches)
    qtbot.addWidget(dlg)
    from flow.services.markdown import PatchStore

    store_before = PatchStore(song_with_patches.parent / ".patches.json")
    edit_patch = next(p for p in store_before.patches if p.id == "edit-1")

    with qtbot.waitSignal(dlg.patches_changed, timeout=1000):
        dlg._discard_one(edit_patch)

    text = song_with_patches.read_text(encoding="utf-8")
    assert "원본 1" in text  # md untouched
    store_after = PatchStore(song_with_patches.parent / ".patches.json")
    assert all(p.id != "edit-1" for p in store_after.patches)


def test_no_crash_when_no_patches(qtbot, tmp_path: Path) -> None:
    md = tmp_path / "slides.md"
    md.write_text("# t\n\n원본\n", encoding="utf-8")
    dlg = PatchDetailsDialog(md)
    qtbot.addWidget(dlg)
    assert "0" in dlg._summary_label.text() or "없음" in dlg._summary_label.text()
