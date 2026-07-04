"""셋리스트 곡 카드의 시트 이름 표시 옵션 테스트

기본은 P1, P2… 표기. 곡별 옵션(show_sheet_names)이 켜지면 시트 이름을
표시하고, 옵션은 song.json에 저장·복원된다. 카드 우클릭 메뉴에서 토글.
"""
from __future__ import annotations

from pathlib import Path

from flow.domain.project import Project
from flow.domain.score_sheet import ScoreSheet
from flow.domain.song import Song
from flow.repository.project_repository import ProjectRepository
from flow.ui.editor.song_list_widget import SongListWidget, _SongCard


def _make_song(name: str, show_sheet_names: bool = False) -> Song:
    sheets = [
        ScoreSheet(name="intro_page", image_path="a.png"),
        ScoreSheet(name="verse_page", image_path="b.png"),
    ]
    song = Song(name=name, folder=Path(f"songs/{name}"), score_sheets=sheets)
    song.show_sheet_names = show_sheet_names
    return song


class TestSongOption:
    def test_default_is_off(self):
        song = Song(name="x", folder=Path("songs/x"))
        assert song.show_sheet_names is False


class TestPersistence:
    def test_roundtrip_through_project_repository(self, tmp_path):
        repo = ProjectRepository(tmp_path)
        project = Project(name="proj")
        song_on = _make_song("named_song", show_sheet_names=True)
        song_off = _make_song("plain_song", show_sheet_names=False)
        project.selected_songs = [song_on, song_off]

        path = repo.save(project, tmp_path / "proj" / "project.json")
        loaded = repo.load(path)

        by_name = {s.name: s for s in loaded.selected_songs}
        assert by_name["named_song"].show_sheet_names is True
        assert by_name["plain_song"].show_sheet_names is False


class TestCardTabLabels:
    def test_default_shows_page_numbers(self, qtbot):
        card = _SongCard(_make_song("song_a"), 1)
        qtbot.addWidget(card)
        card.set_selected(True, None)

        assert [t.text() for t in card._sheet_tabs] == ["P1", "P2"]

    def test_option_shows_sheet_names(self, qtbot):
        card = _SongCard(_make_song("song_a", show_sheet_names=True), 1)
        qtbot.addWidget(card)
        card.set_selected(True, None)

        assert [t.text() for t in card._sheet_tabs] == ["intro_page", "verse_page"]


class TestSheetNameLayout:
    """시트 이름 표시 모드에서는 한 줄에 한 시트씩 크게 표시."""

    def test_name_mode_places_one_tab_per_row(self, qtbot):
        card = _SongCard(_make_song("song_a", show_sheet_names=True), 1)
        qtbot.addWidget(card)
        card.set_selected(True, None)

        layout = card._tabs_layout
        for i, tab in enumerate(card._sheet_tabs):
            item = layout.itemAtPosition(i, 0)
            assert item is not None and item.widget() is tab, (
                f"시트 {i}는 {i}행 0열에 있어야 함"
            )

    def test_default_mode_keeps_grid(self, qtbot):
        card = _SongCard(_make_song("song_a"), 1)
        qtbot.addWidget(card)
        card.set_selected(True, None)

        layout = card._tabs_layout
        # 기본 모드: 4열 격자 — 두 시트가 같은 행(0행)의 0, 1열
        assert layout.itemAtPosition(0, 0).widget() is card._sheet_tabs[0]
        assert layout.itemAtPosition(0, 1).widget() is card._sheet_tabs[1]

    def test_name_mode_tabs_are_taller(self, qtbot):
        card_named = _SongCard(_make_song("song_a", show_sheet_names=True), 1)
        qtbot.addWidget(card_named)
        card_named.set_selected(True, None)

        card_plain = _SongCard(_make_song("song_b"), 1)
        qtbot.addWidget(card_plain)
        card_plain.set_selected(True, None)

        assert (
            card_named._sheet_tabs[0].height()
            > card_plain._sheet_tabs[0].height()
        )


class TestContextMenuToggle:
    def test_menu_label_reflects_state(self, qtbot):
        card_off = _SongCard(_make_song("song_a"), 1)
        qtbot.addWidget(card_off)
        texts = [a.text() for a in card_off._build_context_menu().actions()]
        assert "시트 이름 표시" in texts
        assert "시트 이름 숨기기" not in texts

        card_on = _SongCard(_make_song("song_b", show_sheet_names=True), 1)
        qtbot.addWidget(card_on)
        texts = [a.text() for a in card_on._build_context_menu().actions()]
        assert "시트 이름 숨기기" in texts

    def test_toggle_flips_option_and_marks_dirty(self, qtbot, tmp_path):
        class _FakeMainWindow:
            def __init__(self):
                self._project_path = tmp_path / "project.json"
                self._is_live = False
                self.dirty = False

            def _mark_dirty(self):
                self.dirty = True

        w = SongListWidget()
        qtbot.addWidget(w)
        fake = _FakeMainWindow()
        w.set_main_window(fake)
        project = Project(name="proj")
        song = _make_song("song_a")
        project.selected_songs = [song]
        w.set_project(project)

        w._toggle_sheet_names(song)

        assert song.show_sheet_names is True
        assert fake.dirty
        # 카드가 다시 그려져 시트 이름이 보여야 함
        w._cards[0].set_selected(True, None)
        assert [t.text() for t in w._cards[0]._sheet_tabs] == [
            "intro_page",
            "verse_page",
        ]
