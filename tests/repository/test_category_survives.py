"""분류는 어떤 저장 경로에서도 살아남아야 한다.

song.json을 통째로 다시 쓰는 경로가 여러 개라, 분류를 그 안에 두면
프로젝트를 한 번 저장하는 것만으로 사라진다 — 구버전 Flow가 같은
워크스페이스를 열었을 때도 마찬가지다. meta.json에 두었기 때문에
살아남는다는 사실을 여기서 고정한다.
"""
from __future__ import annotations

import json
from pathlib import Path

from flow.domain.project import Project
from flow.domain.song import Song
from flow.domain.workspace import Workspace
from flow.repository.project_repository import ProjectRepository
from flow.services.song_meta import read_category, set_category


def _workspace_with_categorized_song(tmp_path: Path) -> Workspace:
    ws = Workspace.create(tmp_path / "ws")
    song_dir = ws.library_song_dir("song_a")
    song_dir.mkdir(parents=True)
    (song_dir / "song.json").write_text(
        json.dumps({"name": "song_a", "sheets": []}, ensure_ascii=False),
        encoding="utf-8-sig",
    )
    set_category(song_dir, "바다")
    return ws


def _library_song(ws: Workspace) -> Song:
    return Song(
        name="song_a",
        folder=ws.library_song_dir("song_a"),
        source="library",
    )


def test_project_save_keeps_the_category(tmp_path):
    ws = _workspace_with_categorized_song(tmp_path)
    repo = ProjectRepository(ws.projects_dir)
    project = Project(name="p1", selected_songs=[_library_song(ws)])

    repo.save_to_workspace(project, ws)

    assert read_category(ws.library_song_dir("song_a")) == "바다"


def test_song_rename_keeps_the_category(tmp_path):
    ws = _workspace_with_categorized_song(tmp_path)
    repo = ProjectRepository(ws.projects_dir)

    repo.rename_song_folder(ws.library_song_dir("song_a"), "song_b", workspace=ws)

    assert read_category(ws.library_song_dir("song_b")) == "바다"


def test_project_clone_keeps_the_category(tmp_path):
    ws = _workspace_with_categorized_song(tmp_path)
    repo = ProjectRepository(ws.projects_dir)
    repo.save_to_workspace(Project(name="p1", selected_songs=[_library_song(ws)]), ws)

    repo.clone_workspace_project(ws, "p1", "p2")

    assert read_category(ws.library_song_dir("song_a")) == "바다"
