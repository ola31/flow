"""프로젝트 편집 화면에서 새 곡을 만들 때 어디에 만들지 고른다.

곡은 라이브러리(공용)나 프로젝트의 songs/(전용) 두 곳에만 있을 수 있다 —
project.json은 곡을 이름으로만 참조하고, 다시 열 때 그 두 자리만 찾는다.
그래서 위치를 자유롭게 고르게 하는 대신 두 갈래로 묻는다.
"""
from __future__ import annotations

import json

import pytest

from flow.domain.project import Project
from flow.domain.workspace import Workspace
from flow.ui.editor.song_list_widget import SongListWidget


class _FakeMainWindow:
    def __init__(self, project_path, workspace):
        from PySide6.QtWidgets import QWidget

        from flow.repository.project_repository import ProjectRepository

        self._project_path = project_path
        self._workspace = workspace
        self._repo = ProjectRepository(workspace.projects_dir)
        self._is_live = False
        self._canvas = QWidget()
        self.dirty = False
        self.songs_changed = 0

    def _mark_dirty(self):
        self.dirty = True

    def _on_songs_changed(self):
        self.songs_changed += 1


@pytest.fixture
def widget(qtbot, tmp_path):
    ws = Workspace.create(tmp_path / "ws")
    proj_dir = ws.project_dir("p1")
    proj_dir.mkdir(parents=True)
    (proj_dir / "project.json").write_text(
        json.dumps(
            {"id": "1", "name": "p1", "selected_songs": [], "song_order": []},
            ensure_ascii=False,
        ),
        encoding="utf-8-sig",
    )

    w = SongListWidget()
    qtbot.addWidget(w)
    w.set_main_window(_FakeMainWindow(proj_dir / "project.json", ws))
    w.set_project(Project(name="p1"))
    return w, ws, proj_dir


def _answer(monkeypatch, *, name="song_new", to_library=True, ok=True):
    monkeypatch.setattr(
        "flow.ui.editor.song_list_widget.QInputDialog.getText",
        staticmethod(lambda *a, **k: (name, ok)),
    )
    def question(parent, title, message, **kwargs):
        if "어디" in title:          # 위치 선택
            return to_library
        return False                 # 슬라이드 형식 — PPT (에디터를 열지 않는다)

    monkeypatch.setattr("flow.ui.dialogs.flow_question", question)


def test_library_choice_creates_the_song_in_the_library(widget, monkeypatch):
    w, ws, proj_dir = widget
    _answer(monkeypatch, to_library=True)

    w._add_new_song_inline()

    assert (ws.library_song_dir("song_new") / "song.json").exists()
    assert not (proj_dir / "songs" / "song_new").exists()


def test_library_choice_is_referenced_not_copied(widget, monkeypatch):
    w, _ws, _proj_dir = widget
    _answer(monkeypatch, to_library=True)

    w._add_new_song_inline()

    song = w._project.selected_songs[0]
    assert song.name == "song_new"
    assert song.source == "library"


def test_project_choice_keeps_the_song_inside_the_project(widget, monkeypatch):
    w, ws, proj_dir = widget
    _answer(monkeypatch, to_library=False)

    w._add_new_song_inline()

    assert (proj_dir / "songs" / "song_new" / "song.json").exists()
    assert not (ws.library_song_dir("song_new")).exists()
    assert w._project.selected_songs[0].source == "local"


def test_cancelled_name_creates_nothing(widget, monkeypatch):
    w, ws, proj_dir = widget
    _answer(monkeypatch, ok=False)

    w._add_new_song_inline()

    assert w._project.selected_songs == []
    assert not (ws.library_song_dir("song_new")).exists()
    assert not (proj_dir / "songs" / "song_new").exists()


def test_existing_library_name_is_refused(widget, monkeypatch):
    """같은 이름이 라이브러리에 이미 있으면 덮어쓰지 않는다."""
    w, ws, _proj_dir = widget
    existing = ws.library_song_dir("song_new")
    existing.mkdir(parents=True)
    (existing / "song.json").write_text(
        json.dumps({"name": "song_new", "sheets": []}, ensure_ascii=False),
        encoding="utf-8-sig",
    )
    marker = existing / "keep.txt"
    marker.write_text("건드리지 말 것", encoding="utf-8")
    _answer(monkeypatch, to_library=True)
    warned = []
    monkeypatch.setattr(
        "flow.ui.editor.song_list_widget.QMessageBox.warning",
        staticmethod(lambda *a, **k: warned.append(a)),
    )

    w._add_new_song_inline()

    assert warned, "이미 있는 이름인데 경고하지 않았다"
    assert marker.exists()
    assert w._project.selected_songs == []
