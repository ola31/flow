from __future__ import annotations

from pathlib import Path

from flow.ui.editor.markdown_editor import MarkdownEditor


def test_editor_loads_existing_file(qapp, tmp_path: Path) -> None:
    md = tmp_path / "slides.md"
    md.write_text("# T\n\n가사\n", encoding="utf-8")
    ed = MarkdownEditor(md)
    assert "가사" in ed.text()
    assert ed.is_dirty() is False


def test_editor_save_writes_file(qapp, tmp_path: Path) -> None:
    md = tmp_path / "slides.md"
    md.write_text("# T\n\n가사 1\n", encoding="utf-8")
    ed = MarkdownEditor(md)
    ed.set_text("# T\n\n가사 2\n")
    assert ed.is_dirty() is True
    ed.save()
    assert md.read_text(encoding="utf-8") == "# T\n\n가사 2\n"
    assert ed.is_dirty() is False


def test_editor_dirty_after_text_change(qapp, tmp_path: Path) -> None:
    md = tmp_path / "slides.md"
    md.write_text("# T\n", encoding="utf-8")
    ed = MarkdownEditor(md)
    ed.set_text("# X\n")
    assert ed.is_dirty() is True
