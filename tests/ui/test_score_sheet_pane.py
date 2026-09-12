"""마크다운 에디터 옆 악보 보기 패널."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtGui import QColor, QImage

from flow.domain.score_sheet import ScoreSheet
from flow.domain.song import Song
from flow.ui.editor.score_sheet_pane import ScoreSheetPane, resolve_sheet_images


def _png(path: Path, w: int = 400, h: int = 900) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = QImage(w, h, QImage.Format.Format_RGB32)
    img.fill(QColor("#dddddd"))
    img.save(str(path))
    return path


@pytest.fixture
def song(tmp_path: Path) -> Song:
    folder = tmp_path / "곡A"
    _png(folder / "sheets" / "p1.png")
    _png(folder / "sheets" / "p2.png", h=600)
    return Song(
        name="곡A",
        folder=folder,
        score_sheets=[
            ScoreSheet(name="1절", image_path="sheets/p1.png"),
            ScoreSheet(name="", image_path="sheets/p2.png"),
        ],
    )


class TestResolveSheetImages:
    def test_relative_paths_resolve_under_the_song_folder(self, song):
        out = resolve_sheet_images(song)
        assert [label for label, _ in out] == ["1절", "P2"]  # 이름 없으면 P{n}
        assert all(p.is_file() for _, p in out)

    def test_old_sheet_folder_spelling_is_tried(self, tmp_path):
        """옛 프로젝트는 sheets/ 대신 sheet/ 를 쓴다."""
        folder = tmp_path / "곡B"
        _png(folder / "sheet" / "a.png")
        s = Song(
            name="곡B", folder=folder,
            score_sheets=[ScoreSheet(name="p", image_path="sheets/a.png")],
        )
        out = resolve_sheet_images(s)
        assert len(out) == 1 and out[0][1].name == "a.png"

    def test_missing_images_are_skipped(self, tmp_path):
        folder = tmp_path / "곡C"
        _png(folder / "sheets" / "ok.png")
        s = Song(
            name="곡C", folder=folder,
            score_sheets=[
                ScoreSheet(name="없음", image_path="sheets/gone.png"),
                ScoreSheet(name="빈", image_path=""),
                ScoreSheet(name="있음", image_path="sheets/ok.png"),
            ],
        )
        assert [label for label, _ in resolve_sheet_images(s)] == ["있음"]


class TestScoreSheetPane:
    def test_shows_first_page_fitted_to_width(self, qtbot, song):
        pane = ScoreSheetPane(resolve_sheet_images(song))
        qtbot.addWidget(pane)
        pane.resize(300, 500)
        pane.show()
        qtbot.waitExposed(pane)

        assert pane.page_count() == 2
        assert pane.current_page() == 0
        pm = pane._image.pixmap()
        assert not pm.isNull()
        # 폭에 맞추고 세로는 스크롤 — 원본 400x900 이 뷰포트 폭으로 줄어든다
        assert pm.width() == pane._scroll.viewport().width()
        assert pm.height() > pm.width()

    def test_tabs_switch_pages(self, qtbot, song):
        pane = ScoreSheetPane(resolve_sheet_images(song))
        qtbot.addWidget(pane)
        pane.resize(300, 500)
        pane.show()
        qtbot.waitExposed(pane)
        first_h = pane._image.pixmap().height()

        pane._tabs[1].click()

        assert pane.current_page() == 1
        assert pane._tabs[1].isChecked() and not pane._tabs[0].isChecked()
        assert pane._image.pixmap().height() < first_h  # 두 번째 장은 더 짧다

    def test_single_sheet_hides_the_tab_row(self, qtbot, song):
        pane = ScoreSheetPane(resolve_sheet_images(song)[:1])
        qtbot.addWidget(pane)
        assert pane._tab_row.isHidden()

    def test_no_sheets_shows_empty_state(self, qtbot):
        pane = ScoreSheetPane([])
        qtbot.addWidget(pane)
        assert pane.page_count() == 0
        assert not pane._empty.isHidden()
        assert pane._scroll.isHidden()

    def test_refits_on_resize(self, qtbot, song):
        pane = ScoreSheetPane(resolve_sheet_images(song))
        qtbot.addWidget(pane)
        pane.resize(300, 500)
        pane.show()
        qtbot.waitExposed(pane)
        narrow = pane._image.pixmap().width()

        pane.resize(600, 500)
        qtbot.waitUntil(lambda: pane._image.pixmap().width() > narrow, timeout=2000)


class TestEditorIntegration:
    def _md(self, tmp_path: Path) -> Path:
        md = tmp_path / "slides.md"
        md.write_text("# 바다\n\n푸른 바다가 보이네\n", encoding="utf-8")
        return md

    def test_editor_shows_pane_when_song_has_sheets(self, qtbot, tmp_path, song):
        from flow.ui.editor.markdown_editor import MarkdownEditor

        ed = MarkdownEditor(self._md(tmp_path), sheets=resolve_sheet_images(song))
        qtbot.addWidget(ed)

        assert ed._score_btn.isEnabled() and ed._score_btn.isChecked()
        assert not ed._score_pane.isHidden()
        assert ed._score_pane.page_count() == 2

    def test_toggle_hides_and_restores_the_pane(self, qtbot, tmp_path, song):
        from flow.ui.editor.markdown_editor import MarkdownEditor

        ed = MarkdownEditor(self._md(tmp_path), sheets=resolve_sheet_images(song))
        qtbot.addWidget(ed)

        ed._score_btn.setChecked(False)
        assert ed._score_pane.isHidden()
        ed._score_btn.setChecked(True)
        assert not ed._score_pane.isHidden()

    def test_editor_without_sheets_locks_the_button(self, qtbot, tmp_path):
        from flow.ui.editor.markdown_editor import MarkdownEditor

        ed = MarkdownEditor(self._md(tmp_path))  # 기존 호출 방식 그대로
        qtbot.addWidget(ed)

        assert not ed._score_btn.isEnabled()
        assert ed._score_pane.isHidden()

    def test_screen_passes_the_songs_sheets(self, qtbot, tmp_path, song):
        from flow.ui.screens.markdown_editor_screen import MarkdownEditorScreen

        (song.abs_folder / "slides.md").write_text(
            "# 곡A\n\n첫 줄\n", encoding="utf-8"
        )
        screen = MarkdownEditorScreen()
        qtbot.addWidget(screen)

        screen.load_song(song)

        assert screen._editor._score_pane.page_count() == 2
