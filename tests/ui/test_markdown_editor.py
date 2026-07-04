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


class TestCursorToSlideMapping:
    """커서 줄 → 슬라이드 인덱스 매핑이 파서의 슬라이드 분할과 일치해야 한다."""

    def _editor(self, qapp, tmp_path, text):
        md = tmp_path / "slides.md"
        md.write_text(text, encoding="utf-8")
        return MarkdownEditor(md)

    def test_empty_frontmatter_not_counted_as_slide(self, qapp, tmp_path):
        text = "---\n---\n\n# 제목\n\n첫 가사\n\n둘째 가사\n"
        ed = self._editor(qapp, tmp_path, text)
        lines = text.splitlines()

        assert ed._slide_index_at_line(lines.index("첫 가사")) == 0
        assert ed._slide_index_at_line(lines.index("둘째 가사")) == 1

    def test_full_frontmatter_not_counted_as_slide(self, qapp, tmp_path):
        text = (
            "---\nmain_size: 56\nbackground: \"#000000\"\n---\n"
            "\n# 제목\n\n첫 가사\n\n둘째 가사\n"
        )
        ed = self._editor(qapp, tmp_path, text)
        lines = text.splitlines()

        assert ed._slide_index_at_line(lines.index("첫 가사")) == 0
        assert ed._slide_index_at_line(lines.index("둘째 가사")) == 1

    def test_cursor_inside_frontmatter_maps_to_first_slide(self, qapp, tmp_path):
        text = "---\nmain_size: 56\n---\n\n# 제목\n\n첫 가사\n"
        ed = self._editor(qapp, tmp_path, text)

        assert ed._slide_index_at_line(1) == 0

    def test_section_header_separates_blocks(self, qapp, tmp_path):
        text = "# 제목\n\n일절 가사\n## 후렴\n후렴 가사\n"
        ed = self._editor(qapp, tmp_path, text)
        lines = text.splitlines()

        assert ed._slide_index_at_line(lines.index("일절 가사")) == 0
        assert ed._slide_index_at_line(lines.index("후렴 가사")) == 1
