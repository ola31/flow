"""새 곡 만들기는 열려 있는 프로젝트에 영향을 주지 않는다.

라이브러리·시작 화면으로 이동해도 편집하던 프로젝트는 닫히지 않는다.
그 상태를 '이 프로젝트에 곡 추가'로 해석하면, 라이브러리에서 만든 곡이
프로젝트 폴더 안에 생기고 셋리스트에 끼어들어가며 저장되지 않은 변경까지
남긴다 — 프로젝트를 열 때 뜨던 저장 확인창의 정체가 이것이었다.
"""
from __future__ import annotations

import json

import pytest

from flow.domain.project import Project
from flow.domain.workspace import Workspace


@pytest.fixture
def window(qtbot, tmp_path, monkeypatch):
    from flow.ui.main_window import MainWindow

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

    win = MainWindow(workspace=ws)
    qtbot.addWidget(win)
    # 프로젝트를 연 상태 — 이것이 문제의 조건이었다
    win._project = Project(name="p1")
    win._project_path = proj_dir / "project.json"
    win._is_standalone = False
    win._clear_dirty()

    monkeypatch.setattr(
        "flow.ui.dialogs.flow_input_text", lambda *a, **k: ("song_new", True)
    )
    monkeypatch.setattr(
        "flow.ui.main_window.QFileDialog.getExistingDirectory",
        lambda *a, **k: str(ws.library_dir),
    )
    monkeypatch.setattr(MainWindow, "_prompt_song_format", lambda self, song: None)

    yield win, ws, proj_dir

    win._slide_manager.shutdown()
    win._clear_dirty()
    win.close()


def test_song_is_not_created_inside_the_open_project(window):
    win, ws, proj_dir = window

    win._new_song()

    assert (ws.library_song_dir("song_new") / "song.json").exists()
    assert not (proj_dir / "songs" / "song_new").exists()


def test_open_project_setlist_is_untouched(window):
    win, _ws, _proj_dir = window

    win._new_song()

    # 편집하던 프로젝트가 아니라 새 곡의 단독 편집으로 전환된다
    assert win._is_standalone is True
    assert win._project.name != "p1"


def test_no_unsaved_changes_are_left_on_the_project(window):
    """저장 확인창이 뜨던 원인 — 새 곡 만들기가 프로젝트를 더럽혔다."""
    win, _ws, _proj_dir = window

    win._new_song()

    assert win._is_dirty is False


def test_prompt_does_not_promise_the_project_folder(window, monkeypatch):
    win, _ws, _proj_dir = window
    seen = {}

    def capture(parent, title, prompt, **kwargs):
        seen["prompt"] = prompt
        return ("song_new", True)

    monkeypatch.setattr("flow.ui.dialogs.flow_input_text", capture)

    win._new_song()

    assert "프로젝트" not in seen["prompt"]
