"""Workspace 도메인 모델 테스트"""
from __future__ import annotations

import json
import pytest
from pathlib import Path

from flow.domain.workspace import MARKER_NAME, Workspace


@pytest.fixture
def workspace_root(tmp_path: Path) -> Path:
    """임시 워크스페이스 루트 경로"""
    return tmp_path / "MyFlow"


@pytest.fixture
def workspace(workspace_root: Path) -> Workspace:
    """초기화된 워크스페이스"""
    return Workspace.create(workspace_root)


class TestWorkspaceCreation:
    def test_create_initializes_subfolders(self, workspace_root: Path):
        ws = Workspace.create(workspace_root)
        assert ws.root == workspace_root.resolve()
        assert ws.library_dir.exists()
        assert ws.projects_dir.exists()

    def test_create_is_idempotent(self, workspace_root: Path):
        Workspace.create(workspace_root)
        # 두 번째 호출도 성공해야 함
        ws = Workspace.create(workspace_root)
        assert ws.is_valid()

    def test_is_valid_requires_both_subfolders(self, tmp_path: Path):
        root = tmp_path / "partial"
        root.mkdir()
        (root / "library").mkdir()
        # projects/ 누락
        ws = Workspace(root=root)
        assert not ws.is_valid()

    def test_open_raises_on_invalid(self, tmp_path: Path):
        empty = tmp_path / "empty"
        empty.mkdir()
        with pytest.raises(ValueError):
            Workspace.open(empty)

    def test_open_succeeds_on_valid(self, workspace_root: Path):
        Workspace.create(workspace_root)
        ws = Workspace.open(workspace_root)
        assert ws.is_valid()


class TestWorkspacePaths:
    def test_library_song_dir(self, workspace: Workspace):
        path = workspace.library_song_dir("곡A")
        assert path == workspace.library_dir / "곡A"

    def test_project_dir(self, workspace: Workspace):
        path = workspace.project_dir("행사A")
        assert path == workspace.projects_dir / "행사A"

    def test_name_from_root(self, workspace: Workspace):
        assert workspace.name == workspace.root.name


class TestWorkspaceListing:
    def test_list_projects_empty(self, workspace: Workspace):
        assert workspace.list_projects() == []

    def test_list_projects_ignores_non_project_folders(self, workspace: Workspace):
        # 유효 프로젝트
        valid = workspace.project_dir("valid")
        valid.mkdir()
        (valid / "project.json").write_text("{}")

        # project.json 없는 폴더는 무시
        invalid = workspace.project_dir("no_json")
        invalid.mkdir()

        result = workspace.list_projects()
        assert len(result) == 1
        assert result[0] == valid

    def test_list_library_songs_empty(self, workspace: Workspace):
        assert workspace.list_library_songs() == []

    def test_list_library_songs_ignores_non_song_folders(self, workspace: Workspace):
        song = workspace.library_song_dir("valid_song")
        song.mkdir()
        (song / "song.json").write_text("{}")

        bad = workspace.library_song_dir("bad")
        bad.mkdir()

        result = workspace.list_library_songs()
        assert len(result) == 1
        assert result[0] == song


class TestSongResolution:
    """곡 경로 해석 우선순위: local → library"""

    def _create_library_song(self, workspace: Workspace, name: str) -> Path:
        path = workspace.library_song_dir(name)
        path.mkdir(parents=True)
        (path / "song.json").write_text(json.dumps({"name": name}))
        return path

    def _create_local_song(
        self, workspace: Workspace, project: str, name: str
    ) -> Path:
        path = workspace.project_dir(project) / "songs" / name
        path.mkdir(parents=True)
        (path / "song.json").write_text(json.dumps({"name": name}))
        return path

    def test_resolves_library_when_only_library_exists(self, workspace: Workspace):
        lib_song = self._create_library_song(workspace, "곡B")
        resolved = workspace.resolve_song_folder("행사A", "곡B")
        assert resolved == lib_song

    def test_resolves_local_when_both_exist(self, workspace: Workspace):
        self._create_library_song(workspace, "곡B")
        local_song = self._create_local_song(workspace, "행사A", "곡B")
        resolved = workspace.resolve_song_folder("행사A", "곡B")
        assert resolved == local_song

    def test_resolves_local_when_only_local_exists(self, workspace: Workspace):
        local_song = self._create_local_song(workspace, "행사A", "커스텀곡")
        resolved = workspace.resolve_song_folder("행사A", "커스텀곡")
        assert resolved == local_song

    def test_returns_none_when_nowhere(self, workspace: Workspace):
        assert workspace.resolve_song_folder("행사A", "없는곡") is None


class TestWorkspaceMarker:
    """루트 표시 마커 — .git·.idea처럼 어느 하위에서든 루트를 찾게 해준다."""

    def test_create_writes_the_marker(self, tmp_path):
        ws = Workspace.create(tmp_path / "ws")

        assert ws.marker_path.exists()
        assert json.loads(ws.marker_path.read_text(encoding="utf-8"))["version"] == 1

    def test_open_backfills_the_marker(self, tmp_path):
        """마커 도입 전에 만든 워크스페이스도 열면서 표시를 남긴다."""
        root = tmp_path / "old"
        (root / "library").mkdir(parents=True)
        (root / "projects").mkdir()
        assert not (root / MARKER_NAME).exists()

        ws = Workspace.open(root)

        assert ws.marker_path.exists()

    def test_marker_is_not_required_for_validity(self, tmp_path):
        root = tmp_path / "old"
        (root / "library").mkdir(parents=True)
        (root / "projects").mkdir()

        assert Workspace(root=root).is_valid()

    def test_find_root_from_a_nested_path(self, tmp_path):
        ws = Workspace.create(tmp_path / "ws")
        deep = ws.library_dir / "곡A" / "sheets"
        deep.mkdir(parents=True)

        assert Workspace.find_root(deep) == ws.root.resolve()

    def test_find_root_returns_none_outside(self, tmp_path):
        Workspace.create(tmp_path / "ws")
        outside = tmp_path / "다른곳"
        outside.mkdir()

        assert Workspace.find_root(outside) is None

    def test_write_marker_is_idempotent(self, tmp_path):
        ws = Workspace.create(tmp_path / "ws")
        ws.marker_path.write_text('{"version": 1, "note": "손댐"}', encoding="utf-8")

        ws.write_marker()

        assert "손댐" in ws.marker_path.read_text(encoding="utf-8")
