"""카드 뷰는 2단계다: 분류 타일 → 그 분류의 곡 → 뒤로.

타일 화면에서는 곡이 보이지 않는다(미리보기 몇 줄만). 곡은 타일을 눌러
들어간 뒤에 나온다.
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


@pytest.fixture
def screen(qtbot, isolated_home, tmp_path):
    ws = _workspace(tmp_path, ["song_a", "song_b", "song_c", "song_d"])
    set_category(ws.library_song_dir("song_a"), "바다")
    set_category(ws.library_song_dir("song_b"), "바다")
    set_category(ws.library_song_dir("song_c"), "노을")
    view = LibraryScreen()
    qtbot.addWidget(view)
    view._toolbar.set_view(VIEW_CARDS)
    view.set_workspace(ws)
    return view


def _visible_tiles(screen) -> list[str]:
    # 창을 띄우지 않은 테스트에서는 isVisible()이 항상 False다 — 명시적으로
    # 숨겼는지만 본다.
    return [name for name, tile in screen._tiles.items() if not tile.isHidden()]


def test_tile_screen_shows_categories_not_songs(screen):
    assert _visible_tiles(screen) == ["노을", "바다", UNCATEGORIZED]
    assert all(card.isHidden() for card in screen._cards.values())


def test_tile_counts_the_songs_inside(screen):
    assert screen._tiles["바다"].count() == 2
    assert screen._tiles[UNCATEGORIZED].count() == 1


def test_tile_previews_a_few_song_names(screen):
    assert screen._tiles["바다"].preview_names() == ["song_a", "song_b"]


def test_opening_a_tile_shows_only_that_category(screen):
    screen._open_category("바다")

    shown = [
        key for key, card in screen._cards.items() if not card.isHidden()
    ]
    assert sorted(screen._index[k]["path"].name for k in shown) == [
        "song_a",
        "song_b",
    ]
    assert not any(not tile.isHidden() for tile in screen._tiles.values())


def test_going_back_returns_to_the_tiles(screen):
    screen._open_category("바다")

    screen._close_category()

    assert _visible_tiles(screen) == ["노을", "바다", UNCATEGORIZED]
    assert all(card.isHidden() for card in screen._cards.values())


def test_header_follows_the_open_category(screen):
    screen._open_category("바다")
    assert screen._toolbar.title() == "바다"
    assert screen._toolbar.back_visible() is True

    screen._close_category()
    assert screen._toolbar.title() == "라이브러리"
    assert screen._toolbar.back_visible() is False


def test_list_view_is_unaffected_by_the_open_category(screen):
    screen._open_category("바다")

    screen._toolbar.set_view(VIEW_LIST)

    shown = [key for key, card in screen._cards.items() if not card.isHidden()]
    assert len(shown) == 4
    assert not any(not tile.isHidden() for tile in screen._tiles.values())


def test_search_skips_the_tiles_and_shows_songs(screen):
    """검색은 곡을 찾는 수단이다 — 분류 구분을 건너뛰고 결과를 바로 보여준다."""
    screen._on_search_changed("song_c")

    shown = [key for key, card in screen._cards.items() if not card.isHidden()]
    assert [screen._index[k]["path"].name for k in shown] == ["song_c"]
    assert not any(not tile.isHidden() for tile in screen._tiles.values())


def test_clearing_the_search_returns_to_the_tiles(screen):
    screen._on_search_changed("song_c")

    screen._on_search_changed("")

    assert _visible_tiles(screen) == ["노을", "바다", UNCATEGORIZED]


def test_search_inside_a_category_searches_everything(screen):
    """분류 안에서도 검색은 라이브러리 전체를 본다."""
    screen._open_category("바다")

    screen._on_search_changed("song_c")  # '노을' 분류의 곡

    shown = [key for key, card in screen._cards.items() if not card.isHidden()]
    assert [screen._index[k]["path"].name for k in shown] == ["song_c"]


def test_widgets_are_reused_across_state_changes(screen):
    """상태가 바뀔 때마다 위젯을 새로 만들면 큰 라이브러리에서 밀린다."""
    cards_before = {key: id(card) for key, card in screen._cards.items()}
    tiles_before = {name: id(tile) for name, tile in screen._tiles.items()}

    screen._open_category("바다")
    screen._close_category()
    screen._on_search_changed("song")
    screen._on_search_changed("")

    assert {key: id(card) for key, card in screen._cards.items()} == cards_before
    assert {name: id(tile) for name, tile in screen._tiles.items()} == tiles_before
