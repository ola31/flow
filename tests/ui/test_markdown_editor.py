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


class TestExitReloadsEditedSong:
    """마크다운을 고치고 나오면 곡 화면에도 반영돼야 한다.

    예전에는 단일 파일 모드(_pptx_path)만 확인해서, 프로젝트 안 곡을
    고치면 에디터에서만 보이고 곡/프로젝트 화면은 옛 슬라이드를 그대로
    보여줬다.
    """

    def _song(self, tmp_path, name="곡A"):
        from flow.domain.song import Song

        d = tmp_path / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "slides.md").write_text(
            "---\n---\n\n## 1절\n\n가사\n", encoding="utf-8"
        )
        return Song(name=name, folder=d, project_dir=tmp_path)

    def test_exit_reloads_song_registered_with_manager(self, qtbot, tmp_path):
        from flow.ui.screens.markdown_editor_screen import MarkdownEditorScreen

        song = self._song(tmp_path)
        screen = MarkdownEditorScreen()
        qtbot.addWidget(screen)
        screen.load_song(song)

        assert screen.current_song() is song

    def test_reload_song_invalidates_and_recounts(self, qtbot, tmp_path):
        """reload_song은 캐시만 버리지 않고 슬라이드 수까지 다시 센다 —
        `---`나 `##`를 더하면 장수가 달라지기 때문."""
        from unittest.mock import MagicMock

        from flow.services.slide_manager import SlideManager

        song = self._song(tmp_path)
        mgr = SlideManager(converter=MagicMock())
        try:
            mgr._songs = [song]
            invalidated = []
            mgr._markdown_converter.invalidate_cache = invalidated.append

            mgr.reload_song(song)

            assert invalidated == [song.markdown_path]
            assert mgr._pending_reload_song is song
            # add_task가 큐를 비웠으므로 카운터도 한 건으로 맞춰져야
            # _loading이 True로 굳지 않는다
            assert mgr._pending_conversions == 1
        finally:
            mgr.shutdown()
