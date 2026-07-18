"""단독 곡 편집 좌측의 곡 전환 목록 테스트

라이브러리 페이지로 돌아가지 않고 편집 화면에서 바로 다른 곡을 열 수
있어야 한다. 클릭 → 기존 _open_song_by_path 경로(저장 확인 포함).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from flow.domain.project import Project
from flow.domain.score_sheet import ScoreSheet
from flow.domain.song import Song
from flow.ui.editor.song_list_widget import SongListWidget


def _make_library(tmp_path: Path, names: list[str]) -> Path:
    lib = tmp_path / "library"
    for name in names:
        d = lib / name
        d.mkdir(parents=True)
        with open(d / "song.json", "w", encoding="utf-8-sig") as f:
            json.dump({"name": name, "sheets": []}, f, ensure_ascii=False)
    return lib


class _FakeWorkspace:
    def __init__(self, lib: Path):
        self.library_dir = lib


class _FakeMainWindow:
    def __init__(self, project_path: Path, workspace=None):
        self._project_path = project_path
        self._workspace = workspace
        self._is_live = False

    def _mark_dirty(self):
        pass


@pytest.fixture
def widget(qtbot, tmp_path):
    lib = _make_library(tmp_path, ["song_alpha", "song_beta", "song_gamma"])
    song_dir = lib / "song_beta"
    song = Song(
        name="song_beta",
        folder=song_dir,
        score_sheets=[ScoreSheet(name="page", image_path="a.png")],
        project_dir=song_dir,
    )
    w = SongListWidget()
    qtbot.addWidget(w)
    w.set_main_window(_FakeMainWindow(song_dir, workspace=_FakeWorkspace(lib)))
    w.set_standalone(True)
    project = Project(name="[곡 편집] song_beta")
    project.selected_songs = [song]
    w.set_project(project)
    return w


class TestSwitcherListing:
    def test_lists_library_songs_with_current_highlighted(self, widget):
        sw = widget._song_switcher
        assert sw is not None
        names = [r._name for r in sw._rows]
        assert names == ["song_alpha", "song_beta", "song_gamma"]
        current = [r._name for r in sw._rows if r._is_current]
        assert current == ["song_beta"]

    def test_click_emits_open_request_with_path(self, widget, qtbot):
        sw = widget._song_switcher
        opened = []
        widget.song_open_requested.connect(opened.append)

        row = next(r for r in sw._rows if r._name == "song_gamma")
        row.click()

        assert len(opened) == 1
        assert opened[0].endswith("song_gamma")

    def test_clicking_current_song_does_not_reopen(self, widget):
        sw = widget._song_switcher
        opened = []
        widget.song_open_requested.connect(opened.append)

        row = next(r for r in sw._rows if r._name == "song_beta")
        row.click()

        assert opened == []  # 현재 곡 재클릭은 무시 (저장 확인 팝업 방지)

    def test_search_filters_rows(self, widget):
        sw = widget._song_switcher
        sw._search.setText("alpha")
        visible = [r._name for r in sw._rows if not r.isHidden()]
        assert visible == ["song_alpha"]

        sw._search.setText("")
        visible = [r._name for r in sw._rows if not r.isHidden()]
        assert len(visible) == 3


class TestSwitcherCollapse:
    def test_toggle_collapses_and_survives_refresh(self, widget):
        sw = widget._song_switcher
        assert not sw._body.isHidden()  # 기본 펼침

        sw._toggle_collapsed()
        assert sw._body.isHidden()

        widget.refresh_list()  # 패널 재생성 후에도 접힘 유지
        assert widget._song_switcher._body.isHidden()


class TestSwitcherAbsentWithoutWorkspace:
    def test_no_switcher_in_legacy_mode(self, qtbot, tmp_path):
        song_dir = tmp_path / "solo"
        song_dir.mkdir()
        song = Song(name="solo", folder=song_dir, project_dir=song_dir)
        w = SongListWidget()
        qtbot.addWidget(w)
        w.set_main_window(_FakeMainWindow(song_dir, workspace=None))
        w.set_standalone(True)
        project = Project(name="[곡 편집] solo")
        project.selected_songs = [song]
        w.set_project(project)

        assert w._song_switcher is None


class TestMainWindowWiring:
    def test_open_request_switches_to_standalone_song(self, qtbot, tmp_path):
        """시그널 발신 → 실제로 해당 곡의 단독 편집 모드로 전환되는지."""
        from flow.ui.main_window import MainWindow

        song_dir = tmp_path / "switch_target"
        song_dir.mkdir()
        with open(song_dir / "song.json", "w", encoding="utf-8-sig") as f:
            json.dump({"name": "switch_target", "sheets": []}, f)

        mw = MainWindow()
        qtbot.addWidget(mw)
        try:
            mw._song_list.song_open_requested.emit(str(song_dir))
            qtbot.waitUntil(lambda: mw._is_standalone, timeout=3000)
            assert mw._project is not None
            assert mw._project.selected_songs[0].name == "switch_target"
        finally:
            mw._slide_manager.shutdown()
            mw._clear_dirty()
            mw.close()


class TestSwitcherWarnings:
    """곡 전환 목록 — 문제가 있는 곡은 앰버 경고를 이름 오른쪽에 표시."""

    def _make_full_song(self, lib, name, *, mapped=True):
        import json as _json

        d = lib / name
        (d / "sheets").mkdir(parents=True, exist_ok=True)
        (d / "sheets" / "page1.png").touch()
        (d / "slides.pptx").touch()
        data = {
            "name": name,
            "sheets": [{"hotspots": [{"slide_index": 0 if mapped else -1}]}],
        }
        with open(d / "song.json", "w", encoding="utf-8-sig") as f:
            _json.dump(data, f)

    def _widget(self, qtbot, tmp_path, lib):
        song_dir = lib / "song_beta"
        song = Song(
            name="song_beta",
            folder=song_dir,
            score_sheets=[ScoreSheet(name="page", image_path="a.png")],
            project_dir=song_dir,
        )
        w = SongListWidget()
        qtbot.addWidget(w)
        w.set_main_window(_FakeMainWindow(song_dir, workspace=_FakeWorkspace(lib)))
        w.set_standalone(True)
        project = Project(name="[곡 편집] song_beta")
        project.selected_songs = [song]
        w.set_project(project)
        return w

    def _row(self, widget, name):
        return next(r for r in widget._song_switcher._rows if r._name == name)

    def test_complete_song_has_no_warning(self, qtbot, tmp_path):
        lib = _make_library(tmp_path, ["song_beta"])
        self._make_full_song(lib, "song_ok")
        w = self._widget(qtbot, tmp_path, lib)
        assert self._row(w, "song_ok")._warning == ""

    def test_song_without_sheets_warns(self, qtbot, tmp_path):
        lib = _make_library(tmp_path, ["song_beta", "song_nosheet"])
        (lib / "song_nosheet" / "slides.pptx").touch()
        w = self._widget(qtbot, tmp_path, lib)
        assert "악보 없음" in self._row(w, "song_nosheet")._warning

    def test_unmapped_song_warns(self, qtbot, tmp_path):
        lib = _make_library(tmp_path, ["song_beta"])
        self._make_full_song(lib, "song_unmapped", mapped=False)
        w = self._widget(qtbot, tmp_path, lib)
        assert self._row(w, "song_unmapped")._warning == "매핑 없음"

    def test_warning_label_is_amber_on_second_line(self, qtbot, tmp_path):
        from PySide6.QtWidgets import QLabel

        from flow.ui.styles import AMBER

        lib = _make_library(tmp_path, ["song_beta"])
        self._make_full_song(lib, "song_ok")
        self._make_full_song(lib, "song_unmapped", mapped=False)
        w = self._widget(qtbot, tmp_path, lib)
        row = self._row(w, "song_unmapped")
        warn = [
            lbl for lbl in row.findChildren(QLabel)
            if lbl.text() == "매핑 없음"
        ]
        assert warn and AMBER in warn[0].styleSheet()
        # 경고는 이름 옆이 아니라 둘째 줄 — 정상 행보다 높아야 한다
        assert row.height() > self._row(w, "song_ok").height()


class TestSwitcherStatePreservedAcrossSwitch:
    """곡을 열면 목록이 재생성되는데, 검색어가 유지되고 현재 곡이 보여야 한다."""

    def test_search_text_survives_refresh(self, widget):
        widget._song_switcher._search.setText("gamma")

        widget.refresh_list()  # 곡 전환 시 재생성 경로

        sw = widget._song_switcher
        assert sw._search.text() == "gamma"
        visible = [r._name for r in sw._rows if not r.isHidden()]
        assert visible == ["song_gamma"]

    def test_current_row_scrolled_into_view(self, qtbot, tmp_path):
        names = [f"song_{i:02d}" for i in range(30)]
        lib = _make_library(tmp_path, names)
        current = "song_25"
        song_dir = lib / current
        song = Song(
            name=current,
            folder=song_dir,
            score_sheets=[ScoreSheet(name="page", image_path="a.png")],
            project_dir=song_dir,
        )
        w = SongListWidget()
        qtbot.addWidget(w)
        w.set_main_window(_FakeMainWindow(song_dir, workspace=_FakeWorkspace(lib)))
        w.set_standalone(True)
        project = Project(name=f"[곡 편집] {current}")
        project.selected_songs = [song]
        w.set_project(project)
        w.resize(260, 600)
        w.show()
        qtbot.waitExposed(w)
        qtbot.wait(80)  # 레이아웃 후 singleShot 스크롤 대기

        sw = w._song_switcher
        row = next(r for r in sw._rows if r._is_current)
        viewport = sw._list_scroll.viewport()
        top = row.mapTo(viewport, row.rect().topLeft()).y()
        bottom = row.mapTo(viewport, row.rect().bottomLeft()).y()
        assert top < viewport.height() and bottom > 0, (
            "현재 곡 행이 전환 목록 스크롤 밖에 있음"
        )
