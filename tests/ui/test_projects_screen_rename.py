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


class TestCardContextMenuActions:
    """카드 우클릭 메뉴는 허용된 동작만 노출한다."""

    def _labels(self, card) -> list[str]:
        menu = card.build_context_menu()
        return [] if menu is None else [
            a.text() for a in menu.actions() if not a.isSeparator()
        ]

    def test_delete_action_fires_signal(self, qtbot):
        card = ItemCard(path="/p", title="t", deletable=True)
        qtbot.addWidget(card)
        received = []
        card.delete_requested.connect(received.append)

        menu = card.build_context_menu()
        next(a for a in menu.actions() if a.text() == "삭제").trigger()

        assert received == ["/p"]

    def test_rename_action_fires_signal(self, qtbot):
        card = ItemCard(path="/p", title="t", renamable=True)
        qtbot.addWidget(card)
        received = []
        card.rename_requested.connect(received.append)

        menu = card.build_context_menu()
        next(a for a in menu.actions() if a.text() == "이름 변경").trigger()

        assert received == ["/p"]

    def test_menu_lists_only_allowed_actions(self, qtbot):
        renamable = ItemCard(path="/p", title="t", renamable=True)
        deletable = ItemCard(path="/p", title="t", deletable=True)
        both = ItemCard(path="/p", title="t", renamable=True, deletable=True)
        for c in (renamable, deletable, both):
            qtbot.addWidget(c)

        assert self._labels(renamable) == ["이름 변경"]
        assert self._labels(deletable) == ["삭제"]
        assert self._labels(both) == ["이름 변경", "삭제"]

    def test_plain_card_has_no_menu(self, qtbot):
        from PySide6.QtCore import Qt

        card = ItemCard(path="/p", title="t")
        qtbot.addWidget(card)

        assert card.build_context_menu() is None
        assert card.contextMenuPolicy() != Qt.ContextMenuPolicy.CustomContextMenu
