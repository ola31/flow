"""프로젝트 셋리스트 곡 순서 변경 테스트

곡 카드 우클릭 메뉴의 위로/아래로 이동으로 selected_songs와 song_order를
갱신하고, _on_songs_changed로 오프셋 재계산·저장을 트리거해야 한다.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from flow.domain.project import Project
from flow.domain.score_sheet import ScoreSheet
from flow.domain.song import Song
from flow.ui.editor.song_list_widget import SongListWidget, _SongCard


class _FakeMainWindow:
    def __init__(self, project_path: Path):
        self._project_path = project_path
        self._is_live = False
        self.songs_changed_calls = 0
        self.dirty = False

    def _on_songs_changed(self):
        self.songs_changed_calls += 1

    def _mark_dirty(self):
        self.dirty = True


def _make_song(name: str) -> Song:
    return Song(
        name=name,
        folder=Path(f"songs/{name}"),
        score_sheets=[ScoreSheet(name=f"{name}_sheet", image_path="a.png")],
    )


@pytest.fixture
def widget(qtbot, tmp_path):
    w = SongListWidget()
    qtbot.addWidget(w)
    w.set_main_window(_FakeMainWindow(tmp_path / "project.json"))
    project = Project(name="setlist")
    project.selected_songs = [
        _make_song("song_a"),
        _make_song("song_b"),
        _make_song("song_c"),
    ]
    project.song_order = ["song_a", "song_b", "song_c"]
    w.set_project(project)
    return w


def _names(widget) -> list[str]:
    return [s.name for s in widget._project.selected_songs]


class TestSongCardMoveMenu:
    def test_menu_has_move_actions(self, qtbot):
        song = _make_song("song_a")
        card = _SongCard(song, 1)
        qtbot.addWidget(card)

        events = []
        card.move_requested.connect(lambda s, d: events.append((s, d)))

        menu = card._build_context_menu()
        by_text = {a.text(): a for a in menu.actions() if a.text()}
        assert "위로 이동" in by_text
        assert "아래로 이동" in by_text

        by_text["위로 이동"].trigger()
        by_text["아래로 이동"].trigger()
        assert events == [(song, -1), (song, 1)]


class TestMoveSong:
    def test_move_down_swaps_and_updates_order(self, widget):
        first = widget._project.selected_songs[0]

        widget._move_song(first, 1)

        assert _names(widget) == ["song_b", "song_a", "song_c"]
        assert widget._project.song_order == ["song_b", "song_a", "song_c"]
        assert widget._main_window.songs_changed_calls == 1

    def test_move_up_swaps(self, widget):
        last = widget._project.selected_songs[2]

        widget._move_song(last, -1)

        assert _names(widget) == ["song_a", "song_c", "song_b"]

    def test_move_first_up_is_noop(self, widget):
        first = widget._project.selected_songs[0]

        widget._move_song(first, -1)

        assert _names(widget) == ["song_a", "song_b", "song_c"]
        assert widget._main_window.songs_changed_calls == 0

    def test_move_blocked_during_live(self, widget):
        widget._main_window._is_live = True
        first = widget._project.selected_songs[0]

        widget._move_song(first, 1)

        assert _names(widget) == ["song_a", "song_b", "song_c"]
        assert widget._main_window.songs_changed_calls == 0
