"""위치 이동 모드 테스트

우클릭 → "위치 이동" → 방향키로 이동, Enter 확정, Esc 취소(원위치 복귀).
이동 중에는 다른 카드가 비활성화된다.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent

from flow.domain.project import Project
from flow.domain.score_sheet import ScoreSheet
from flow.domain.song import Song
from flow.ui.editor.song_list_widget import SongListWidget, _PageCard, _SongCard


def _key(widget, key):
    ev = QKeyEvent(QKeyEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier)
    widget.keyPressEvent(ev)


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


def _sheet_widget(qtbot, tmp_path):
    sheets = [
        ScoreSheet(name=f"page_{n}", image_path=f"{n}.png") for n in "abcd"
    ]
    song = Song(
        name="song_x", folder=Path("songs/song_x"),
        score_sheets=sheets, project_dir=tmp_path,
    )
    w = SongListWidget()
    qtbot.addWidget(w)
    w.set_main_window(_FakeMainWindow(tmp_path))
    w.set_standalone(True)
    project = Project(name="single")
    project.selected_songs = [song]
    w.set_project(project)
    return w


def _song_widget(qtbot, tmp_path):
    w = SongListWidget()
    qtbot.addWidget(w)
    w.set_main_window(_FakeMainWindow(tmp_path / "p.json"))
    project = Project(name="setlist")
    project.selected_songs = [_make_song(n) for n in ("song_a", "song_b", "song_c")]
    project.song_order = ["song_a", "song_b", "song_c"]
    w.set_project(project)
    return w


class TestContextMenus:
    def test_page_card_menu_has_move_mode(self, qtbot):
        sheet = ScoreSheet(name="p", image_path="a.png")
        card = _PageCard(sheet, 1, False)
        qtbot.addWidget(card)
        fired = []
        card.move_mode_requested.connect(fired.append)

        by_text = {
            a.text(): a for a in card._build_context_menu().actions() if a.text()
        }
        assert "위치 이동" in by_text
        by_text["위치 이동"].trigger()
        assert fired == [sheet]

    def test_song_card_menu_has_move_mode(self, qtbot):
        song = _make_song("song_a")
        card = _SongCard(song, 1)
        qtbot.addWidget(card)
        fired = []
        card.move_mode_requested.connect(fired.append)

        by_text = {
            a.text(): a for a in card._build_context_menu().actions() if a.text()
        }
        assert "위치 이동" in by_text
        by_text["위치 이동"].trigger()
        assert fired == [song]


class TestSheetMoveMode:
    def _names(self, w):
        return [s.name for s in w._project.selected_songs[0].score_sheets]

    def test_arrow_moves_without_persisting(self, qtbot, tmp_path):
        w = _sheet_widget(qtbot, tmp_path)
        sheet = w._project.selected_songs[0].score_sheets[0]

        w._enter_move_mode("sheet", sheet)
        assert w._move_mode is not None
        _key(w, Qt.Key.Key_Down)
        _key(w, Qt.Key.Key_Down)

        assert self._names(w) == ["page_b", "page_c", "page_a", "page_d"]
        assert not w._main_window.dirty  # 확정 전에는 저장 안 함

    def test_enter_confirms_and_marks_dirty(self, qtbot, tmp_path):
        w = _sheet_widget(qtbot, tmp_path)
        sheet = w._project.selected_songs[0].score_sheets[0]

        w._enter_move_mode("sheet", sheet)
        _key(w, Qt.Key.Key_Down)
        _key(w, Qt.Key.Key_Return)

        assert w._move_mode is None
        assert self._names(w) == ["page_b", "page_a", "page_c", "page_d"]
        assert w._main_window.dirty

    def test_escape_restores_original_position(self, qtbot, tmp_path):
        w = _sheet_widget(qtbot, tmp_path)
        sheet = w._project.selected_songs[0].score_sheets[0]

        w._enter_move_mode("sheet", sheet)
        _key(w, Qt.Key.Key_Down)
        _key(w, Qt.Key.Key_Down)
        _key(w, Qt.Key.Key_Escape)

        assert w._move_mode is None
        assert self._names(w) == ["page_a", "page_b", "page_c", "page_d"]
        assert not w._main_window.dirty

    def test_boundary_no_wrap(self, qtbot, tmp_path):
        w = _sheet_widget(qtbot, tmp_path)
        sheet = w._project.selected_songs[0].score_sheets[0]

        w._enter_move_mode("sheet", sheet)
        _key(w, Qt.Key.Key_Up)  # 이미 맨 위

        assert self._names(w) == ["page_a", "page_b", "page_c", "page_d"]

    def test_other_cards_disabled_during_move(self, qtbot, tmp_path):
        w = _sheet_widget(qtbot, tmp_path)
        sheet = w._project.selected_songs[0].score_sheets[1]

        w._enter_move_mode("sheet", sheet)

        panel = w._standalone_panel
        cards = [
            panel._pages_layout.itemAt(i).widget()
            for i in range(panel._pages_layout.count())
        ]
        page_cards = [c for c in cards if isinstance(c, _PageCard)]
        moving = [c for c in page_cards if c._sheet is sheet]
        others = [c for c in page_cards if c._sheet is not sheet]
        assert moving and all(c.isEnabled() for c in moving)
        assert others and all(not c.isEnabled() for c in others)

        _key(w, Qt.Key.Key_Escape)
        # 종료 후 전부 다시 활성화
        panel = w._standalone_panel
        cards = [
            panel._pages_layout.itemAt(i).widget()
            for i in range(panel._pages_layout.count())
        ]
        assert all(
            c.isEnabled() for c in cards if isinstance(c, _PageCard)
        )


class TestSongMoveMode:
    def _names(self, w):
        return [s.name for s in w._project.selected_songs]

    def test_confirm_updates_order_and_reloads_once(self, qtbot, tmp_path):
        w = _song_widget(qtbot, tmp_path)
        song = w._project.selected_songs[0]

        w._enter_move_mode("song", song)
        _key(w, Qt.Key.Key_Down)
        _key(w, Qt.Key.Key_Down)
        assert w._main_window.songs_changed_calls == 0  # 이동 중 저장 안 함
        _key(w, Qt.Key.Key_Return)

        assert self._names(w) == ["song_b", "song_c", "song_a"]
        assert w._project.song_order == ["song_b", "song_c", "song_a"]
        assert w._main_window.songs_changed_calls == 1

    def test_escape_restores_and_never_persists(self, qtbot, tmp_path):
        w = _song_widget(qtbot, tmp_path)
        song = w._project.selected_songs[2]

        w._enter_move_mode("song", song)
        _key(w, Qt.Key.Key_Up)
        _key(w, Qt.Key.Key_Escape)

        assert self._names(w) == ["song_a", "song_b", "song_c"]
        assert w._main_window.songs_changed_calls == 0

    def test_blocked_during_live(self, qtbot, tmp_path):
        w = _song_widget(qtbot, tmp_path)
        w._main_window._is_live = True

        w._enter_move_mode("song", w._project.selected_songs[0])

        assert w._move_mode is None


class TestMoveModeVisualReset:
    """카드 풀 재사용 후에도 모드 종료 시 강조/흐림이 반드시 원복돼야 한다."""

    def _widget_with_project(self, qtbot):
        from pathlib import Path

        from flow.domain.project import Project
        from flow.domain.song import Song
        from flow.ui.editor.song_list_widget import SongListWidget

        class _MW:
            _project_path = Path("/tmp/p.json")
            _is_live = False
            def _mark_dirty(self): pass
            def _on_songs_changed(self): pass
            def statusBar(self):  # noqa: N802
                class _B:
                    def showMessage(self, *a):  # noqa: N802
                        pass
                return _B()

        w = SongListWidget()
        qtbot.addWidget(w)
        w.set_main_window(_MW())
        p = Project(name="p")
        p.selected_songs = [
            Song(name=f"곡{i}", folder=Path(f"songs/곡{i}")) for i in range(3)
        ]
        w.set_project(p)
        return w, p

    def test_escape_restores_card_visuals(self, qtbot):
        w, p = self._widget_with_project(qtbot)
        target = p.selected_songs[1]

        w._enter_move_mode("song", target)
        w._shift_moving(1)
        w._exit_move_mode(confirm=False)

        for card in w._cards:
            assert card.isEnabled(), "모드 종료 후에도 카드가 비활성"
            assert card.graphicsEffect() is None, "흐림 효과가 남음"
            assert "2px solid" not in card.styleSheet(), "이동 강조 테두리가 남음"

    def test_repeated_marks_do_not_accumulate_style(self, qtbot):
        w, p = self._widget_with_project(qtbot)
        target = p.selected_songs[1]

        w._enter_move_mode("song", target)
        for _ in range(5):
            w._shift_moving(1)
            w._shift_moving(-1)

        card = next(c for c in w._cards if c._song is target)
        assert card.styleSheet().count("2px solid") <= 1, "강조 스타일 누적"
        w._exit_move_mode(confirm=True)
