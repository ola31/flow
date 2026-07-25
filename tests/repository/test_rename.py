"""곡/프로젝트 이름 변경 — 폴더명이 정체성이므로 참조까지 함께 옮긴다."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from flow.domain.workspace import Workspace
from flow.repository.project_repository import ProjectRepository


@pytest.fixture
def repo(tmp_path):
    return ProjectRepository(tmp_path)


def _make_song(ws: Workspace, name: str) -> Path:
    d = ws.library_song_dir(name)
    (d / "sheets").mkdir(parents=True)
    (d / "song.json").write_text(
        json.dumps({"name": name, "sheets": []}), encoding="utf-8-sig"
    )
    return d


def _make_project(ws: Workspace, name: str, song_names: list[str]) -> Path:
    d = ws.project_dir(name)
    d.mkdir(parents=True)
    (d / "project.json").write_text(
        json.dumps({
            "id": "pid",
            "name": name,
            "selected_songs": [
                {"name": s, "order": i, "source": "library"}
                for i, s in enumerate(song_names)
            ],
            "song_order": list(song_names),
        }),
        encoding="utf-8-sig",
    )
    return d


class TestValidateFolderName:
    @pytest.mark.parametrize("bad", ["", "   ", "..", "  .  "])
    def test_empty_rejected(self, repo, bad):
        with pytest.raises(ValueError):
            repo.validate_folder_name(bad)

    @pytest.mark.parametrize(
        "bad", ["a/b", chr(92).join("ab"), "a:b", "a?b", 'a"b', "a*b"]
    )
    def test_path_characters_rejected(self, repo, bad):
        with pytest.raises(ValueError):
            repo.validate_folder_name(bad)

    def test_trims_whitespace_and_trailing_dot(self, repo):
        assert repo.validate_folder_name("  새 곡.  ") == "새 곡"


class TestRenameSongFolder:
    def test_renames_folder_and_song_json(self, repo, tmp_path):
        ws = Workspace.create(tmp_path / "ws")
        old = _make_song(ws, "옛이름")

        new = repo.rename_song_folder(old, "새이름", workspace=ws)

        assert not old.exists()
        assert new == ws.library_song_dir("새이름")
        assert (new / "sheets").is_dir()  # 내용물도 함께 이동
        with open(new / "song.json", encoding="utf-8-sig") as f:
            assert json.load(f)["name"] == "새이름"

    def test_updates_project_references(self, repo, tmp_path):
        ws = Workspace.create(tmp_path / "ws")
        _make_song(ws, "옛이름")
        _make_song(ws, "다른곡")
        pdir = _make_project(ws, "정기모임", ["옛이름", "다른곡"])

        repo.rename_song_folder(
            ws.library_song_dir("옛이름"), "새이름", workspace=ws
        )

        with open(pdir / "project.json", encoding="utf-8-sig") as f:
            data = json.load(f)
        assert data["song_order"] == ["새이름", "다른곡"]
        assert [s["name"] for s in data["selected_songs"]] == ["새이름", "다른곡"]

    def test_rejects_existing_name(self, repo, tmp_path):
        ws = Workspace.create(tmp_path / "ws")
        _make_song(ws, "곡A")
        _make_song(ws, "곡B")

        with pytest.raises(FileExistsError):
            repo.rename_song_folder(ws.library_song_dir("곡A"), "곡B")

    def test_same_name_is_noop(self, repo, tmp_path):
        ws = Workspace.create(tmp_path / "ws")
        d = _make_song(ws, "곡A")

        assert repo.rename_song_folder(d, "곡A") == d

    def test_missing_folder_raises(self, repo, tmp_path):
        with pytest.raises(FileNotFoundError):
            repo.rename_song_folder(tmp_path / "없음", "새이름")


class TestRenameWorkspaceProject:
    def test_renames_folder_and_project_json(self, repo, tmp_path):
        ws = Workspace.create(tmp_path / "ws")
        _make_song(ws, "곡A")
        old = _make_project(ws, "정기모임", ["곡A"])

        new = repo.rename_workspace_project(old, "정기모임 오전")

        assert not old.exists()
        assert new == ws.project_dir("정기모임 오전")
        with open(new / "project.json", encoding="utf-8-sig") as f:
            assert json.load(f)["name"] == "정기모임 오전"

    def test_rejects_existing_name(self, repo, tmp_path):
        ws = Workspace.create(tmp_path / "ws")
        _make_project(ws, "오전", [])
        _make_project(ws, "오후", [])

        with pytest.raises(FileExistsError):
            repo.rename_workspace_project(ws.project_dir("오전"), "오후")

    def test_rejects_invalid_name(self, repo, tmp_path):
        ws = Workspace.create(tmp_path / "ws")
        d = _make_project(ws, "오전", [])

        with pytest.raises(ValueError):
            repo.rename_workspace_project(d, "오전/오후")
