"""PPT 가져오기 (곡에 slides.pptx 등록) UI 테스트

단독 곡 패널의 'PPT 가져오기' 버튼과 곡 카드 우클릭 메뉴에서
외부 .pptx를 곡 폴더의 slides.pptx로 복사하는 흐름을 검증한다.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QFileDialog, QMenu

from flow.domain.project import Project
from flow.domain.song import Song
from flow.ui.editor.song_list_widget import (
    SongListWidget,
    _SongCard,
    _StandalonePanel,
)

PPTX_BYTES = b"PK\x03\x04 fake pptx content"


class _FakeMainWindow:
    def __init__(self, project_path: Path, is_live: bool = False):
        self._project_path = project_path
        self._is_live = is_live
        self.dirty = False

    def _mark_dirty(self):
        self.dirty = True


@pytest.fixture
def song_env(tmp_path):
    """tmp 프로젝트 폴더 + 곡 폴더 + 가져올 원본 pptx."""
    song_dir = tmp_path / "songs" / "test_song_a"
    song_dir.mkdir(parents=True)
    src = tmp_path / "external_deck.pptx"
    src.write_bytes(PPTX_BYTES)
    song = Song(
        name="test_song_a", folder=Path("songs/test_song_a"), project_dir=tmp_path
    )
    return tmp_path, song, src


@pytest.fixture
def widget(qtbot, song_env):
    tmp_path, song, _src = song_env
    w = SongListWidget()
    qtbot.addWidget(w)
    project = Project(name="test_project")
    project.selected_songs = [song]
    w.set_project(project)
    w.set_main_window(_FakeMainWindow(tmp_path / "project.json"))
    return w


def _patch_file_dialog(monkeypatch, path: str):
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *a, **k: (path, "PowerPoint 파일 (*.pptx)")),
    )


def _forbid_file_dialog(monkeypatch):
    def _fail(*a, **k):
        raise AssertionError("파일 다이얼로그가 열리면 안 됨")

    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(_fail))


class TestImportPptToSong:
    def test_import_copies_file_as_slides_pptx(self, widget, song_env, monkeypatch):
        tmp_path, song, src = song_env
        _patch_file_dialog(monkeypatch, str(src))
        reloaded = []
        widget.song_reload_requested.connect(reloaded.append)

        widget._import_ppt_to_song(song)

        dest = tmp_path / "songs" / "test_song_a" / "slides.pptx"
        assert dest.read_bytes() == PPTX_BYTES
        assert reloaded == [song]

    def test_cancelled_dialog_does_nothing(self, widget, song_env, monkeypatch):
        tmp_path, song, _src = song_env
        _patch_file_dialog(monkeypatch, "")
        reloaded = []
        widget.song_reload_requested.connect(reloaded.append)

        widget._import_ppt_to_song(song)

        assert not (tmp_path / "songs" / "test_song_a" / "slides.pptx").exists()
        assert reloaded == []

    def test_blocked_for_markdown_song(self, widget, song_env, monkeypatch):
        tmp_path, song, _src = song_env
        song.markdown_path.write_text("# md song", encoding="utf-8")
        _forbid_file_dialog(monkeypatch)
        warnings = []
        monkeypatch.setattr(
            "flow.ui.dialogs.flow_warning",
            lambda parent, title, msg: warnings.append(title),
        )

        widget._import_ppt_to_song(song)

        assert warnings
        assert not (tmp_path / "songs" / "test_song_a" / "slides.pptx").exists()

    def test_blocked_during_live(self, widget, song_env, monkeypatch):
        tmp_path, song, _src = song_env
        widget._main_window._is_live = True
        _forbid_file_dialog(monkeypatch)
        warnings = []
        monkeypatch.setattr(
            "flow.ui.dialogs.flow_warning",
            lambda parent, title, msg: warnings.append(title),
        )

        widget._import_ppt_to_song(song)

        assert warnings
        assert not (tmp_path / "songs" / "test_song_a" / "slides.pptx").exists()

    def test_overwrite_declined_keeps_existing(self, widget, song_env, monkeypatch):
        tmp_path, song, src = song_env
        dest = tmp_path / "songs" / "test_song_a" / "slides.pptx"
        dest.write_bytes(b"old content")
        _patch_file_dialog(monkeypatch, str(src))
        monkeypatch.setattr(
            "flow.ui.dialogs.flow_question",
            lambda *a, **k: False,
        )
        reloaded = []
        widget.song_reload_requested.connect(reloaded.append)

        widget._import_ppt_to_song(song)

        assert dest.read_bytes() == b"old content"
        assert reloaded == []

    def test_overwrite_accepted_replaces(self, widget, song_env, monkeypatch):
        tmp_path, song, src = song_env
        dest = tmp_path / "songs" / "test_song_a" / "slides.pptx"
        dest.write_bytes(b"old content")
        _patch_file_dialog(monkeypatch, str(src))
        monkeypatch.setattr(
            "flow.ui.dialogs.flow_question",
            lambda *a, **k: True,
        )

        widget._import_ppt_to_song(song)

        assert dest.read_bytes() == PPTX_BYTES


class TestStandalonePanelButton:
    def test_panel_has_import_button_and_signal(self, qtbot):
        panel = _StandalonePanel()
        qtbot.addWidget(panel)
        fired = []
        panel.import_ppt_requested.connect(lambda: fired.append(True))

        panel._btn_import_ppt.click()

        assert fired == [True]

    def test_import_disabled_for_markdown_song(self, qtbot, song_env):
        tmp_path, song, _src = song_env
        song.markdown_path.write_text("# md song", encoding="utf-8")

        w = SongListWidget()
        qtbot.addWidget(w)
        w.set_main_window(_FakeMainWindow(tmp_path))
        w.set_standalone(True)
        project = Project(name="single")
        project.selected_songs = [song]
        w.set_project(project)

        assert w._standalone_panel is not None
        assert not w._standalone_panel._btn_import_ppt.isEnabled()

    def test_import_enabled_for_ppt_song(self, qtbot, song_env):
        tmp_path, song, _src = song_env

        w = SongListWidget()
        qtbot.addWidget(w)
        w.set_main_window(_FakeMainWindow(tmp_path))
        w.set_standalone(True)
        project = Project(name="single")
        project.selected_songs = [song]
        w.set_project(project)

        assert w._standalone_panel is not None
        assert w._standalone_panel._btn_import_ppt.isEnabled()

    def test_button_triggers_import_flow(self, qtbot, song_env, monkeypatch):
        """버튼 클릭 → 파일 선택 → slides.pptx 복사까지 전체 흐름."""
        tmp_path, song, src = song_env
        _patch_file_dialog(monkeypatch, str(src))

        w = SongListWidget()
        qtbot.addWidget(w)
        w.set_main_window(_FakeMainWindow(tmp_path))
        w.set_standalone(True)
        project = Project(name="single")
        project.selected_songs = [song]
        w.set_project(project)

        w._standalone_panel._btn_import_ppt.click()

        dest = tmp_path / "songs" / "test_song_a" / "slides.pptx"
        assert dest.read_bytes() == PPTX_BYTES


class TestReloadAfterImport:
    """가져오기 직후 리로드 라우팅.

    곡 없는 프로젝트로 열리면 load_songs가 호출되지 않아 SlideManager가
    빈 곡 목록을 유지한다. 그 뒤 추가된 곡의 PPT를 가져오면 reload_song은
    오프셋을 계산하지 못해 슬라이드가 로드되지 않는다 — 매니저가 모르는
    곡은 전체 load_songs로 폴백해야 한다.
    """

    def _make_window(self, qtbot):
        from flow.ui.main_window import MainWindow

        mw = MainWindow()
        qtbot.addWidget(mw)
        return mw

    def _record_manager_calls(self, mw, monkeypatch):
        calls = []
        monkeypatch.setattr(
            mw._slide_manager,
            "load_songs",
            lambda songs, **kw: calls.append(("load_songs", list(songs))),
        )
        monkeypatch.setattr(
            mw._slide_manager,
            "reload_song",
            lambda s: calls.append(("reload_song", s)),
        )
        monkeypatch.setattr(
            mw,
            "_localize_project_indices",
            lambda: calls.append(("localize",)),
        )
        return calls

    def test_unknown_song_falls_back_to_load_songs(
        self, qtbot, song_env, monkeypatch
    ):
        tmp_path, song, src = song_env
        (tmp_path / "songs" / "test_song_a" / "slides.pptx").write_bytes(PPTX_BYTES)

        mw = self._make_window(qtbot)
        try:
            project = Project(name="empty_start")
            project.selected_songs = [song]
            mw._project = project
            mw._project_path = tmp_path / "project.json"
            mw._is_standalone = False
            # 곡 없는 프로젝트로 열린 상태 재현: 매니저는 이 곡을 모름
            assert mw._slide_manager._songs == []

            calls = self._record_manager_calls(mw, monkeypatch)
            mw._on_reload_song_ppt(song)

            # globalize(songs_metadata_finished 핸들러)와 균형을 맞추기 위해
            # load_songs 전에 반드시 localize가 선행돼야 한다.
            assert calls == [("localize",), ("load_songs", [song])]
        finally:
            mw._slide_manager.shutdown()
            mw.close()

    def test_known_song_uses_reload_song(self, qtbot, song_env, monkeypatch):
        tmp_path, song, src = song_env
        (tmp_path / "songs" / "test_song_a" / "slides.pptx").write_bytes(PPTX_BYTES)

        mw = self._make_window(qtbot)
        try:
            project = Project(name="normal_start")
            project.selected_songs = [song]
            mw._project = project
            mw._project_path = tmp_path / "project.json"
            mw._is_standalone = False
            # 정상 경로: 매니저가 이미 곡 목록을 추적 중
            mw._slide_manager._songs = project.selected_songs

            calls = self._record_manager_calls(mw, monkeypatch)
            mw._on_reload_song_ppt(song)

            assert calls == [("reload_song", song)]
        finally:
            mw._slide_manager.shutdown()
            mw.close()


class TestSongCardContextMenu:
    def test_context_menu_has_import_action(self, qtbot, song_env):
        _tmp_path, song, _src = song_env
        card = _SongCard(song, 1)
        qtbot.addWidget(card)

        fired = []
        card.import_ppt_requested.connect(fired.append)

        menu = card._build_context_menu()
        assert isinstance(menu, QMenu)
        import_actions = [a for a in menu.actions() if a.text() == "PPT 가져오기"]
        assert import_actions, "메뉴에 'PPT 가져오기' 항목이 있어야 함"
        import_actions[0].trigger()
        assert fired == [song]
