"""분류별 카드 뷰.

블록 하나가 분류 하나이고, 분류가 없는 곡은 항상 마지막 블록에 모인다.
검색은 블록 안에서 걸러지고, 카드는 뷰가 바뀌어도 재사용된다 — 수백 개
QFrame을 다시 만들면 큰 라이브러리에서 전환이 눈에 띄게 밀린다.
"""
from __future__ import annotations

import json

import pytest

from flow.domain.workspace import Workspace
from flow.services.song_meta import set_category
from flow.ui.screens._browser_widgets import VIEW_CARDS, VIEW_LIST
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


def _screen(qtbot, ws, mode=VIEW_CARDS):
    screen = LibraryScreen()
    qtbot.addWidget(screen)
    screen._toolbar.set_view(mode)
    screen.set_workspace(ws)
    return screen


def test_groups_by_category_with_uncategorized_last(qtbot, isolated_home, tmp_path):
    ws = _workspace(tmp_path, ["song_a", "song_b", "song_c"])
    set_category(ws.library_song_dir("song_a"), "노을")
    set_category(ws.library_song_dir("song_c"), "바다")
    screen = _screen(qtbot, ws)

    groups = [
        (name, len(keys)) for name, keys in screen._grouped(screen._applied_order)
    ]

    assert groups == [("노을", 1), ("바다", 1), (UNCATEGORIZED, 1)]


def test_search_filters_inside_the_groups(qtbot, isolated_home, tmp_path):
    ws = _workspace(tmp_path, ["song_a", "song_b"])
    set_category(ws.library_song_dir("song_a"), "바다")
    set_category(ws.library_song_dir("song_b"), "바다")
    screen = _screen(qtbot, ws)

    screen._on_search_changed("song_a")

    groups = [
        (name, len(keys)) for name, keys in screen._grouped(screen._applied_order)
    ]
    assert groups == [("바다", 1)]


def test_group_headers_show_the_song_count(qtbot, isolated_home, tmp_path):
    ws = _workspace(tmp_path, ["song_a", "song_b"])
    set_category(ws.library_song_dir("song_a"), "바다")
    set_category(ws.library_song_dir("song_b"), "바다")
    screen = _screen(qtbot, ws)

    assert screen._headers["바다"].text() == "바다 · 2곡"


def test_cards_are_reused_across_search_and_view_changes(
    qtbot, isolated_home, tmp_path
):
    ws = _workspace(tmp_path, ["song_a", "song_b"])
    screen = _screen(qtbot, ws)
    before = {key: id(card) for key, card in screen._cards.items()}

    screen._on_search_changed("song")
    screen._on_search_changed("")
    screen._toolbar.set_view(VIEW_LIST)
    screen._toolbar.set_view(VIEW_CARDS)

    assert {key: id(card) for key, card in screen._cards.items()} == before


def test_list_view_shows_no_group_headers(qtbot, isolated_home, tmp_path):
    ws = _workspace(tmp_path, ["song_a"])
    set_category(ws.library_song_dir("song_a"), "바다")
    screen = _screen(qtbot, ws, mode=VIEW_LIST)

    assert all(not h.isVisible() for h in screen._headers.values())
