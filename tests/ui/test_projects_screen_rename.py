"""프로젝트 이름 변경 — 같은 날 오전/오후 셋리스트를 카드에서 구분하기 위함.

카드는 project.json 경로를 들고 있지만 이름 변경은 폴더에 대한 작업이라
화면이 폴더 경로로 바꿔서 올린다.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from flow.domain.workspace import Workspace
from flow.ui.screens._browser_widgets import ItemCard
from flow.ui.screens.projects_screen import ProjectsScreen


def _make_project(ws: Workspace, name: str) -> Path:
    d = ws.project_dir(name)
    d.mkdir(parents=True)
    (d / "project.json").write_text(
        json.dumps({"id": "x", "name": name, "song_order": []}),
        encoding="utf-8-sig",
    )
    return d


@pytest.fixture
def screen(qtbot, tmp_path):
    ws = Workspace.create(tmp_path / "ws")
    _make_project(ws, "정기모임")
    sc = ProjectsScreen()
    qtbot.addWidget(sc)
    sc.set_workspace(ws)
    return sc


def _first_card(screen) -> ItemCard:
    for i in range(screen._cards_layout.count()):
        w = screen._cards_layout.itemAt(i).widget()
        if isinstance(w, ItemCard):
            return w
    raise AssertionError("카드가 없음")


class TestProjectRenameSignal:
    def test_cards_are_renamable(self, screen):
        assert _first_card(screen)._renamable is True

    def test_relays_folder_path_not_json_path(self, screen, qtbot, tmp_path):
        card = _first_card(screen)
        received = []
        screen.project_rename_requested.connect(received.append)

        card.rename_requested.emit(card._path)

        assert received == [str(tmp_path / "ws" / "projects" / "정기모임")]


class TestItemCardContentUpdates:
    """검색 필터마다 카드를 새로 만들지 않도록 내용만 갈아끼울 수 있어야 한다."""

    def test_set_subtitle_shows_and_hides(self, qtbot):
        card = ItemCard(path="/p", title="t")
        qtbot.addWidget(card)
        assert not card._sub_lbl.isVisibleTo(card)

        card.set_subtitle("곡 3개")
        assert card._sub_lbl.text() == "곡 3개"
        assert card._sub_lbl.isVisibleTo(card)

        card.set_subtitle("")
        assert not card._sub_lbl.isVisibleTo(card)

    def test_set_match_snippet_updates_attribute(self, qtbot):
        card = ItemCard(path="/p", title="t")
        qtbot.addWidget(card)

        card.set_match_snippet("푸른 바다가")

        assert card._match_snippet == "푸른 바다가"
        assert "푸른 바다가" in card._snippet_lbl.text()
