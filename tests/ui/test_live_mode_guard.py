"""라이브 모드 편집 잠금 회귀 테스트

라이브 송출 중에는 곡 편집 모드로 전환되지 않아야 하고, UI 버튼도
사용자가 의도를 드러내기 전에 비활성화되어야 한다.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt


@pytest.fixture
def song_list_widget(qapp):
    from flow.ui.editor.song_list_widget import SongListWidget
    return SongListWidget()


def _make_minimal_project_with_song():
    """1개 곡을 담은 최소 Project 반환."""
    from pathlib import Path
    from flow.domain.project import Project
    from flow.domain.song import Song
    from flow.domain.score_sheet import ScoreSheet

    song = Song(
        name="테스트곡",
        folder=Path("songs/테스트곡"),
        score_sheets=[ScoreSheet(name="sheet1")],
    )
    project = Project(name="P", selected_songs=[song])
    return project, song


class TestSongListEditableCascade:
    """SongListWidget.set_editable이 카드 편집 버튼까지 반영하는지."""

    def test_set_editable_false_disables_card_edit_buttons(self, song_list_widget):
        project, _ = _make_minimal_project_with_song()
        song_list_widget.set_project(project)

        assert len(song_list_widget._cards) == 1
        card = song_list_widget._cards[0]
        assert card._btn_edit.isEnabled()

        song_list_widget.set_editable(False)
        assert not card._btn_edit.isEnabled()
        assert "라이브" in card._btn_edit.toolTip()

    def test_set_editable_true_re_enables_card_edit_buttons(self, song_list_widget):
        project, _ = _make_minimal_project_with_song()
        song_list_widget.set_project(project)
        card = song_list_widget._cards[0]

        song_list_widget.set_editable(False)
        assert not card._btn_edit.isEnabled()

        song_list_widget.set_editable(True)
        assert card._btn_edit.isEnabled()
        assert card._btn_edit.toolTip() == ""

    def test_top_level_add_buttons_follow_editable(self, song_list_widget):
        song_list_widget.set_editable(False)
        assert not song_list_widget._btn_add_lib.isEnabled()
        assert not song_list_widget._btn_new_song.isEnabled()

        song_list_widget.set_editable(True)
        assert song_list_widget._btn_add_lib.isEnabled()
        assert song_list_widget._btn_new_song.isEnabled()


class TestEnterSongEditModeBlocksLive:
    """MainWindow._enter_song_edit_mode가 라이브 모드 중에는 진입을 거부."""

    def test_live_mode_rejects_entry(self, qapp, monkeypatch):
        """_is_live=True면 _enter_song_edit_mode가 warning만 띄우고 상태 변경 없음."""
        from flow.ui.main_window import MainWindow

        mw = MainWindow()  # 워크스페이스 없이 시작 (레거시 경로)
        try:
            project, song = _make_minimal_project_with_song()
            mw._project = project
            mw._project_path = None
            mw._is_live = True
            mw._is_standalone = False

            # QMessageBox.warning이 실제 띄워지지 않도록 패치
            shown = {"called": False}
            from PySide6.QtWidgets import QMessageBox
            monkeypatch.setattr(
                QMessageBox,
                "warning",
                lambda *a, **k: (shown.update(called=True), QMessageBox.StandardButton.Ok)[1],
            )

            mw._enter_song_edit_mode(song)

            # 경고가 표시되었고, standalone 모드로 전환 안 됨
            assert shown["called"]
            assert mw._is_standalone is False
            assert mw._project is project  # 바뀌지 않음
        finally:
            mw.close()

    def test_live_mode_disables_home_button(self, qapp):
        """라이브 모드에서는 툴바 홈 버튼이 비활성화되어야 함."""
        from flow.ui.main_window import MainWindow

        mw = MainWindow()
        try:
            mw._set_project_editable(True)
            assert mw._close_project_action.isEnabled()

            mw._set_project_editable(False)  # 라이브 진입 시 호출되는 것과 동일
            assert not mw._close_project_action.isEnabled()
            assert "라이브" in mw._close_project_action.toolTip()
        finally:
            mw.close()

    def test_close_current_project_blocked_in_live(self, qapp):
        """키보드/API로 _close_current_project가 호출되어도 라이브면 차단."""
        from flow.ui.main_window import MainWindow
        from flow.domain.project import Project

        mw = MainWindow()
        try:
            mw._project = Project(name="test")
            mw._is_live = True

            before_project = mw._project
            mw._close_current_project()

            # 라이브 중이므로 프로젝트는 그대로여야 함
            assert mw._project is before_project
        finally:
            mw.close()

    def test_non_live_mode_allows_entry_attempt(self, qapp, monkeypatch):
        """라이브 모드가 아닐 때는 가드가 트리거되지 않음 (경고 메시지 미표시)."""
        from flow.ui.main_window import MainWindow

        mw = MainWindow()
        try:
            project, song = _make_minimal_project_with_song()
            mw._project = project
            mw._project_path = None
            mw._is_live = False
            mw._is_standalone = False

            shown = {"called": False}
            from PySide6.QtWidgets import QMessageBox
            monkeypatch.setattr(
                QMessageBox,
                "warning",
                lambda *a, **k: (shown.update(called=True), QMessageBox.StandardButton.Ok)[1],
            )

            # 실제 전환은 project_path 등이 부족해 실패하지만, 라이브 가드 경고는
            # 보여서는 안 된다.
            try:
                mw._enter_song_edit_mode(song)
            except Exception:
                pass  # 다른 이유 실패는 무관

            assert not shown["called"], "라이브 아닌데 라이브 가드 경고가 떴다"
        finally:
            mw.close()
