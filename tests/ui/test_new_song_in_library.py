"""라이브러리 화면에서 만든 곡은 언제나 library/에 생긴다.

_new_song은 프로젝트가 열려 있으면 곡을 프로젝트의 songs/ 폴더에 만든다.
그런데 라이브러리 화면으로 이동해도 프로젝트는 닫히지 않으므로, 그대로
두면 라이브러리에서 만든 곡이 라이브러리에 없는 상태가 된다 — 분류까지
붙이는 지금은 더더욱 어긋난다.
"""
from __future__ import annotations

import json

import pytest

from flow.domain.project import Project
from flow.domain.workspace import Workspace
from flow.services.song_meta import read_category


@pytest.fixture
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    return tmp_path


@pytest.fixture
def window(qtbot, tmp_path, isolated_home, monkeypatch):
    from flow.ui.main_window import MainWindow

    ws = Workspace.create(tmp_path / "ws")
    (ws.projects_dir / "p1").mkdir(parents=True)
    (ws.projects_dir / "p1" / "project.json").write_text(
        json.dumps(
            {"id": "1", "name": "p1", "selected_songs": [], "song_order": []},
            ensure_ascii=False,
        ),
        encoding="utf-8-sig",
    )

    win = MainWindow(workspace=ws)
    qtbot.addWidget(win)
    # 프로젝트를 연 상태를 만든다 — 이 상태가 문제의 조건이다
    win._project = Project(name="p1")
    win._project_path = ws.projects_dir / "p1" / "project.json"

    monkeypatch.setattr(
        "flow.ui.dialogs.flow_input_text",
        lambda *a, **k: ("song_new", True),
    )
    monkeypatch.setattr(MainWindow, "_prompt_song_format", lambda self, song: None)

    yield win, ws

    win._slide_manager.shutdown()
    win._clear_dirty()
    win.close()


def test_library_request_creates_the_song_in_the_library(window):
    win, ws = window

    win._new_song(in_library=True)

    assert (ws.library_song_dir("song_new") / "song.json").exists()
    assert not (ws.projects_dir / "p1" / "songs" / "song_new").exists()


def test_library_request_applies_the_category(window):
    win, ws = window

    win._new_song("바다", in_library=True)

    assert read_category(ws.library_song_dir("song_new")) == "바다"


def test_no_category_leaves_the_song_uncategorized(window):
    win, ws = window

    win._new_song("", in_library=True)

    assert read_category(ws.library_song_dir("song_new")) == ""
