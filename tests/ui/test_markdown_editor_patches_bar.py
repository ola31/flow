# tests/ui/test_markdown_editor_patches_bar.py
"""Markdown editor surfaces unreconciled patches via a top notification bar."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from flow.ui.editor.markdown_editor import MarkdownEditor


def test_no_bar_when_no_patches(qtbot, tmp_path: Path) -> None:
    md = tmp_path / "slides.md"
    md.write_text("# t\n\n가사\n", encoding="utf-8")
    editor = MarkdownEditor(md)
    qtbot.addWidget(editor)
    assert not editor._patches_bar.isVisible()


def test_bar_shown_with_patches(qtbot, tmp_path: Path) -> None:
    md = tmp_path / "slides.md"
    md.write_text("# t\n\n가사\n", encoding="utf-8")
    (tmp_path / ".patches.json").write_text(
        json.dumps({
            "version": 1,
            "patches": [
                {"id": "x", "type": "edit", "patched_main": "y",
                 "slide_hash": "sha256:h", "slide_index": 0,
                 "created_at": "t", "created_during": "live"}
            ],
        }),
        encoding="utf-8",
    )
    editor = MarkdownEditor(md)
    qtbot.addWidget(editor)
    editor.show()
    assert editor._patches_bar.isVisible()
    assert "1" in editor._patches_bar_label.text()


def test_discard_action_clears_patches(qtbot, tmp_path: Path) -> None:
    md = tmp_path / "slides.md"
    md.write_text("# t\n\n가사\n", encoding="utf-8")
    (tmp_path / ".patches.json").write_text(
        json.dumps({
            "version": 1,
            "patches": [
                {"id": "x", "type": "edit", "patched_main": "y",
                 "slide_hash": "sha256:h", "slide_index": 0,
                 "created_at": "t", "created_during": "live"}
            ],
        }),
        encoding="utf-8",
    )
    editor = MarkdownEditor(md)
    qtbot.addWidget(editor)
    editor.show()
    editor._on_patches_discard()
    assert not editor._patches_bar.isVisible()
    raw = json.loads((tmp_path / ".patches.json").read_text(encoding="utf-8"))
    assert raw["patches"] == []


def test_load_file_refreshes_bar(qtbot, tmp_path: Path) -> None:
    """load_file() swaps the path and re-evaluates the patches bar."""
    md1 = tmp_path / "song1.md"
    md1.write_text("# t\n\n가사\n", encoding="utf-8")
    md2 = tmp_path / "sub" / "slides.md"
    md2.parent.mkdir()
    md2.write_text("# t2\n\n가사2\n", encoding="utf-8")
    (md2.parent / ".patches.json").write_text(
        json.dumps({
            "version": 1,
            "patches": [
                {"id": "y", "type": "edit", "patched_main": "z",
                 "slide_hash": "sha256:h2", "slide_index": 0,
                 "created_at": "t", "created_during": "live"}
            ],
        }),
        encoding="utf-8",
    )
    editor = MarkdownEditor(md1)
    qtbot.addWidget(editor)
    editor.show()
    assert not editor._patches_bar.isVisible()
    editor.load_file(md2)
    assert editor._patches_bar.isVisible()
    assert "1" in editor._patches_bar_label.text()


def test_apply_to_source_rewrites_md_and_clears_patches(qtbot, tmp_path: Path) -> None:
    md = tmp_path / "slides.md"
    md.write_text("# t\n\n원본\n", encoding="utf-8")
    from flow.services.markdown import slide_hash
    (tmp_path / ".patches.json").write_text(
        json.dumps({
            "version": 1,
            "patches": [
                {"id": "x", "type": "edit", "patched_main": "고친",
                 "slide_hash": slide_hash("원본"), "slide_index": 0,
                 "created_at": "t", "created_during": "live"}
            ],
        }),
        encoding="utf-8",
    )
    editor = MarkdownEditor(md)
    qtbot.addWidget(editor)
    editor.show()
    editor._on_patches_apply_to_source()

    new_text = md.read_text(encoding="utf-8")
    assert "고친" in new_text
    assert "원본" not in new_text
    patches_raw = json.loads((tmp_path / ".patches.json").read_text(encoding="utf-8"))
    assert patches_raw["patches"] == []
