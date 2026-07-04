"""시트 단위 매핑 일괄 해제 기능 테스트

페이지 카드 우클릭 → "모든 매핑 해제": 해당 시트의 모든 핫스팟 매핑을
지우되(핫스팟 자체는 유지), Ctrl+Z로 되돌릴 수 있어야 한다.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtGui import QUndoStack

from flow.domain.hotspot import Hotspot
from flow.domain.project import Project
from flow.domain.score_sheet import ScoreSheet
from flow.domain.song import Song
from flow.ui.editor.song_list_widget import SongListWidget, _PageCard
from flow.ui.undo_commands import ClearSheetMappingsCommand


def _mapped_sheet() -> ScoreSheet:
    sheet = ScoreSheet(name="page_one", image_path="a.png")
    h1 = Hotspot(x=10, y=10)
    h1.set_slide_index(3, verse_index=0)
    h1.set_slide_index(7, verse_index=5)
    h2 = Hotspot(x=20, y=20)
    h2.set_slide_index(4, verse_index=1)
    sheet.hotspots = [h1, h2]
    return sheet


class TestClearSheetMappingsCommand:
    def test_redo_clears_all_mappings_but_keeps_hotspots(self):
        sheet = _mapped_sheet()
        cmd = ClearSheetMappingsCommand(sheet, update_cb=lambda: None)

        cmd.redo()

        assert len(sheet.hotspots) == 2
        for h in sheet.hotspots:
            assert h.slide_mappings == {} or all(
                v < 0 for v in h.slide_mappings.values()
            )
            assert h.slide_index == -1
            assert h.get_effective_slide_index(0) == -1
            assert h.get_effective_slide_index(5) == -1

    def test_undo_restores_exact_mappings(self):
        sheet = _mapped_sheet()
        h1, h2 = sheet.hotspots
        before = [
            (dict(h.slide_mappings), h.slide_index) for h in sheet.hotspots
        ]
        cmd = ClearSheetMappingsCommand(sheet, update_cb=lambda: None)

        cmd.redo()
        cmd.undo()

        after = [(dict(h.slide_mappings), h.slide_index) for h in sheet.hotspots]
        assert after == before
        assert h1.get_slide_index(5) == 7
        assert h2.get_slide_index(1) == 4

    def test_update_cb_called_on_redo_and_undo(self):
        sheet = _mapped_sheet()
        calls = []
        cmd = ClearSheetMappingsCommand(sheet, update_cb=lambda: calls.append(1))

        cmd.redo()
        cmd.undo()

        assert len(calls) == 2


class TestPageCardMenu:
    def test_menu_has_clear_mappings_action(self, qtbot):
        sheet = _mapped_sheet()
        card = _PageCard(sheet, 1, False)
        qtbot.addWidget(card)

        fired = []
        card.clear_mappings_requested.connect(fired.append)

        menu = card._build_context_menu()
        by_text = {a.text(): a for a in menu.actions() if a.text()}
        assert "모든 매핑 해제" in by_text

        by_text["모든 매핑 해제"].trigger()
        assert fired == [sheet]


class _FakeCanvas:
    def update(self):
        pass


class _FakeMainWindow:
    def __init__(self, project_path: Path):
        self._project_path = project_path
        self._is_live = False
        self._undo_stack = QUndoStack()
        self._canvas = _FakeCanvas()
        self.dirty = False

    def _mark_dirty(self):
        self.dirty = True

    def _update_mapped_slides_ui(self):
        pass


@pytest.fixture
def widget(qtbot, tmp_path):
    sheet = _mapped_sheet()
    song = Song(
        name="song_a",
        folder=Path("songs/song_a"),
        score_sheets=[sheet],
        project_dir=tmp_path,
    )
    w = SongListWidget()
    qtbot.addWidget(w)
    w.set_main_window(_FakeMainWindow(tmp_path))
    w.set_standalone(True)
    project = Project(name="single")
    project.selected_songs = [song]
    w.set_project(project)
    return w


class TestClearSheetMappingsHandler:
    def test_confirmed_clear_is_undoable(self, widget, monkeypatch):
        monkeypatch.setattr("flow.ui.dialogs.flow_question", lambda *a, **k: True)
        sheet = widget._project.selected_songs[0].score_sheets[0]

        widget._clear_sheet_mappings(sheet)

        assert all(h.get_effective_slide_index(0) == -1 for h in sheet.hotspots)
        assert widget._main_window._undo_stack.count() == 1
        assert widget._main_window.dirty

        widget._main_window._undo_stack.undo()
        assert sheet.hotspots[0].get_slide_index(5) == 7

    def test_cancelled_keeps_mappings(self, widget, monkeypatch):
        monkeypatch.setattr("flow.ui.dialogs.flow_question", lambda *a, **k: False)
        sheet = widget._project.selected_songs[0].score_sheets[0]

        widget._clear_sheet_mappings(sheet)

        assert sheet.hotspots[0].get_slide_index(0) == 3
        assert widget._main_window._undo_stack.count() == 0

    def test_blocked_during_live(self, widget, monkeypatch):
        widget._main_window._is_live = True
        monkeypatch.setattr(
            "flow.ui.dialogs.flow_question",
            lambda *a, **k: (_ for _ in ()).throw(AssertionError("다이얼로그 금지")),
        )
        sheet = widget._project.selected_songs[0].score_sheets[0]

        widget._clear_sheet_mappings(sheet)

        assert sheet.hotspots[0].get_slide_index(0) == 3
