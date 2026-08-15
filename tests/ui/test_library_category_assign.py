"""라이브러리 카드에서 분류를 지정한다.

목록 뷰·카드 뷰 어디서든 같은 우클릭 메뉴로 동작해야 하고, 분류 목록은
따로 관리하는 마스터 목록이 아니라 지금 쓰이고 있는 이름들이다.
"""
from __future__ import annotations

import json

from flow.domain.workspace import Workspace
from flow.services.song_meta import read_category, set_category
from flow.ui.screens.library_screen import LibraryScreen


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


def test_context_menu_offers_category_assignment(qtbot, tmp_path):
    screen = LibraryScreen()
    qtbot.addWidget(screen)
    screen.set_workspace(_workspace(tmp_path, ["song_a"]))

    card = next(iter(screen._cards.values()))
    labels = [a.text() for a in card.build_context_menu().actions() if a.text()]

    assert "분류 지정…" in labels


def test_known_categories_are_the_ones_in_use(qtbot, tmp_path):
    ws = _workspace(tmp_path, ["song_a", "song_b", "song_c"])
    set_category(ws.library_song_dir("song_a"), "노을")
    set_category(ws.library_song_dir("song_b"), "바다")
    screen = LibraryScreen()
    qtbot.addWidget(screen)
    screen.set_workspace(ws)

    assert screen._known_categories() == ["노을", "바다"]


def test_assigning_a_category_writes_and_refreshes(qtbot, tmp_path):
    ws = _workspace(tmp_path, ["song_a"])
    screen = LibraryScreen()
    qtbot.addWidget(screen)
    screen.set_workspace(ws)
    song_dir = ws.library_song_dir("song_a")

    screen._apply_category(str(song_dir), "바다")

    assert read_category(song_dir) == "바다"
    assert screen._index[str(song_dir)]["category"] == "바다"


def test_clearing_a_category_is_allowed(qtbot, tmp_path):
    ws = _workspace(tmp_path, ["song_a"])
    set_category(ws.library_song_dir("song_a"), "바다")
    screen = LibraryScreen()
    qtbot.addWidget(screen)
    screen.set_workspace(ws)
    song_dir = ws.library_song_dir("song_a")

    screen._apply_category(str(song_dir), "")

    assert read_category(song_dir) == ""
    assert screen._known_categories() == []
