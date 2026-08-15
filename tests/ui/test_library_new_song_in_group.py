"""곡 만들기 진입점이 세 군데다 — 각각 어떤 분류를 싣는지 고정한다.

- 툴바 '새 곡 만들기': 분류 없이
- 분류 안의 '＋ 이 분류에 새 곡': 그 분류로
- 타일 화면의 '＋ 새 분류': 새로 입력한 이름으로
"""
from __future__ import annotations

import json

import pytest

from flow.domain.workspace import Workspace
from flow.services.song_meta import set_category
from flow.ui.screens._browser_widgets import VIEW_CARDS
from flow.ui.screens.library_screen import UNCATEGORIZED, LibraryScreen


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
def screen(qtbot, tmp_path):
    ws = _workspace(tmp_path, ["song_a", "song_b"])
    set_category(ws.library_song_dir("song_a"), "바다")
    view = LibraryScreen()
    qtbot.addWidget(view)
    view._toolbar.set_view(VIEW_CARDS)
    view.set_workspace(ws)
    return view


def test_toolbar_button_carries_no_category(screen):
    seen = []
    screen.new_song_requested.connect(seen.append)

    screen._toolbar.new_clicked.emit()

    assert seen == [""]


def test_inside_a_category_the_add_button_carries_it(screen):
    screen._open_category("바다")
    seen = []
    screen.new_song_requested.connect(seen.append)

    screen._add_here.click()

    assert seen == ["바다"]


def test_inside_uncategorized_the_add_button_carries_nothing(screen):
    screen._open_category(UNCATEGORIZED)
    seen = []
    screen.new_song_requested.connect(seen.append)

    screen._add_here.click()

    assert seen == [""]


def test_new_category_tile_asks_for_a_name_and_uses_it(screen, monkeypatch):
    monkeypatch.setattr(
        "flow.ui.dialogs.flow_input_text", lambda *a, **k: ("노을", True)
    )
    seen = []
    screen.new_song_requested.connect(seen.append)

    screen._new_tile.click()

    assert seen == ["노을"]


def test_new_category_tile_cancelled_creates_nothing(screen, monkeypatch):
    monkeypatch.setattr(
        "flow.ui.dialogs.flow_input_text", lambda *a, **k: ("", False)
    )
    seen = []
    screen.new_song_requested.connect(seen.append)

    screen._new_tile.click()

    assert seen == []


def test_the_add_button_is_hidden_on_the_tile_screen(screen):
    assert screen._add_here.isHidden()

    screen._open_category("바다")

    assert not screen._add_here.isHidden()
