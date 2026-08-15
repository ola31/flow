"""블록에서 시작한 곡 만들기는 그 블록의 분류로 들어간다.

툴바의 '새 곡'은 분류 없이 만든다 — 두 진입점이 같은 신호를 쓰되 싣는
값이 다르다.
"""
from __future__ import annotations

import json

import pytest

from flow.domain.workspace import Workspace
from flow.services.song_meta import set_category
from flow.ui.screens._browser_widgets import VIEW_CARDS
from flow.ui.screens.library_screen import UNCATEGORIZED, LibraryScreen


@pytest.fixture
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    return tmp_path


def _workspace(tmp_path, names):
    ws = Workspace.create(tmp_path / "ws")
    for name in names:
        d = ws.library_song_dir(name)
        d.mkdir(parents=True)
        (d / "song.json").write_text(
            json.dumps({"name": name, "sheets": []}, ensure_ascii=False),
            encoding="utf-8-sig",
        )
    return ws


def _card_screen(qtbot, ws):
    screen = LibraryScreen()
    qtbot.addWidget(screen)
    screen._toolbar.set_view(VIEW_CARDS)
    screen.set_workspace(ws)
    return screen


def test_block_add_tile_carries_its_category(qtbot, isolated_home, tmp_path):
    ws = _workspace(tmp_path, ["song_a"])
    set_category(ws.library_song_dir("song_a"), "바다")
    screen = _card_screen(qtbot, ws)
    seen = []
    screen.new_song_requested.connect(seen.append)

    screen._add_tiles["바다"].click()

    assert seen == ["바다"]


def test_uncategorized_block_asks_for_no_category(qtbot, isolated_home, tmp_path):
    ws = _workspace(tmp_path, ["song_a"])
    screen = _card_screen(qtbot, ws)
    seen = []
    screen.new_song_requested.connect(seen.append)

    screen._add_tiles[UNCATEGORIZED].click()

    assert seen == [""]


def test_toolbar_new_button_carries_no_category(qtbot, isolated_home, tmp_path):
    ws = _workspace(tmp_path, ["song_a"])
    screen = LibraryScreen()
    qtbot.addWidget(screen)
    screen.set_workspace(ws)
    seen = []
    screen.new_song_requested.connect(seen.append)

    screen._toolbar.new_clicked.emit()

    assert seen == [""]


def test_add_tiles_are_hidden_in_the_list_view(qtbot, isolated_home, tmp_path):
    ws = _workspace(tmp_path, ["song_a"])
    set_category(ws.library_song_dir("song_a"), "바다")
    screen = _card_screen(qtbot, ws)

    screen._toolbar.set_view("list")

    assert all(not tile.isVisible() for tile in screen._add_tiles.values())
