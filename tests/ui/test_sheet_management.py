"""단독 곡 편집 패널의 시트(페이지) 관리 테스트

페이지 카드 우클릭 메뉴로 이름 변경 / 순서 이동 / 삭제가 가능해야 한다.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QMenu

from flow.domain.project import Project
from flow.domain.score_sheet import ScoreSheet
from flow.domain.song import Song
from flow.ui.editor.song_list_widget import SongListWidget, _PageCard


class _FakeMainWindow:
    def __init__(self, project_path: Path):
        self._project_path = project_path
        self._is_live = False
        self.dirty = False

    def _mark_dirty(self):
        self.dirty = True


def _make_song(tmp_path: Path, sheet_names: list[str]) -> Song:
    sheets = [ScoreSheet(name=n, image_path=f"{n}.png") for n in sheet_names]
    return Song(
        name="test_song_a",
        folder=Path("songs/test_song_a"),
        score_sheets=sheets,
        project_dir=tmp_path,
    )


@pytest.fixture
def widget(qtbot, tmp_path):
    song = _make_song(tmp_path, ["page_one", "page_two", "page_three"])
    w = SongListWidget()
    qtbot.addWidget(w)
    w.set_main_window(_FakeMainWindow(tmp_path))
    w.set_standalone(True)
    project = Project(name="single")
    project.selected_songs = [song]
    w.set_project(project)
    return w


def _sheets(widget) -> list[ScoreSheet]:
    return widget._project.selected_songs[0].score_sheets


class TestPageCardContextMenu:
    def test_menu_actions_emit_signals(self, qtbot, tmp_path):
        song = _make_song(tmp_path, ["page_one"])
        sheet = song.score_sheets[0]
        card = _PageCard(sheet, 1, False)
        qtbot.addWidget(card)

        events = []
        card.rename_requested.connect(lambda s: events.append(("rename", s)))
        card.move_requested.connect(lambda s, d: events.append(("move", s, d)))
        card.delete_requested.connect(lambda s: events.append(("delete", s)))

        menu = card._build_context_menu()
        assert isinstance(menu, QMenu)
        by_text = {a.text(): a for a in menu.actions() if a.text()}
        for label in ("이름 변경", "위로 이동", "아래로 이동", "삭제"):
            assert label in by_text, f"메뉴에 '{label}' 항목이 있어야 함"

        by_text["이름 변경"].trigger()
        by_text["위로 이동"].trigger()
        by_text["아래로 이동"].trigger()
        by_text["삭제"].trigger()

        assert events == [
            ("rename", sheet),
            ("move", sheet, -1),
            ("move", sheet, 1),
            ("delete", sheet),
        ]


class TestRenameSheet:
    def test_rename_updates_name(self, widget, monkeypatch):
        sheet = _sheets(widget)[0]
        monkeypatch.setattr(
            "flow.ui.dialogs.flow_input_text",
            lambda *a, **k: ("renamed_page", True),
        )

        widget._rename_sheet(sheet)

        assert sheet.name == "renamed_page"
        assert widget._main_window.dirty

    def test_rename_cancelled_keeps_name(self, widget, monkeypatch):
        sheet = _sheets(widget)[0]
        monkeypatch.setattr(
            "flow.ui.dialogs.flow_input_text",
            lambda *a, **k: ("", False),
        )

        widget._rename_sheet(sheet)

        assert sheet.name == "page_one"
        assert not widget._main_window.dirty


class TestMoveSheet:
    def test_move_down_swaps(self, widget):
        first = _sheets(widget)[0]

        widget._move_sheet(first, 1)

        assert [s.name for s in _sheets(widget)] == [
            "page_two",
            "page_one",
            "page_three",
        ]
        assert widget._main_window.dirty

    def test_move_up_swaps(self, widget):
        last = _sheets(widget)[2]

        widget._move_sheet(last, -1)

        assert [s.name for s in _sheets(widget)] == [
            "page_one",
            "page_three",
            "page_two",
        ]

    def test_move_first_up_is_noop(self, widget):
        first = _sheets(widget)[0]

        widget._move_sheet(first, -1)

        assert [s.name for s in _sheets(widget)] == [
            "page_one",
            "page_two",
            "page_three",
        ]
        assert not widget._main_window.dirty

    def test_move_last_down_is_noop(self, widget):
        last = _sheets(widget)[2]

        widget._move_sheet(last, 1)

        assert [s.name for s in _sheets(widget)] == [
            "page_one",
            "page_two",
            "page_three",
        ]


class TestDeleteSheet:
    def test_delete_removes_and_emits(self, widget, monkeypatch):
        sheet = _sheets(widget)[1]
        monkeypatch.setattr(
            "flow.ui.dialogs.flow_question", lambda *a, **k: True
        )
        removed = []
        widget.song_removed.connect(removed.append)

        widget._delete_sheet(sheet)

        assert [s.name for s in _sheets(widget)] == ["page_one", "page_three"]
        assert removed == [sheet.id]
        assert widget._main_window.dirty

    def test_delete_cancelled_keeps_sheet(self, widget, monkeypatch):
        sheet = _sheets(widget)[1]
        monkeypatch.setattr(
            "flow.ui.dialogs.flow_question", lambda *a, **k: False
        )
        removed = []
        widget.song_removed.connect(removed.append)

        widget._delete_sheet(sheet)

        assert len(_sheets(widget)) == 3
        assert removed == []


class TestPanelWiring:
    def test_panel_relays_card_signals_to_widget_handlers(self, widget, monkeypatch):
        """패널의 페이지 카드 → 위젯 핸들러까지 실제로 연결되는지."""
        monkeypatch.setattr(
            "flow.ui.dialogs.flow_input_text",
            lambda *a, **k: ("via_menu", True),
        )
        panel = widget._standalone_panel
        assert panel is not None

        cards = [
            panel._pages_layout.itemAt(i).widget()
            for i in range(panel._pages_layout.count())
        ]
        page_cards = [c for c in cards if isinstance(c, _PageCard)]
        assert len(page_cards) == 3

        page_cards[0].rename_requested.emit(page_cards[0]._sheet)

        assert _sheets(widget)[0].name == "via_menu"
