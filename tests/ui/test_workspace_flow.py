"""워크스페이스 UI 흐름 통합 테스트"""
from __future__ import annotations

from pathlib import Path

import pytest

from flow.domain.project import Project
from flow.domain.workspace import Workspace
from flow.repository.project_repository import ProjectRepository


@pytest.fixture
def workspace(tmp_path: Path) -> Workspace:
    return Workspace.create(tmp_path / "ws")


class TestWorkspaceProjectRoundtrip:
    """워크스페이스 모드에서 새 프로젝트 생성 → 저장 → 감지 → 로드"""

    def test_save_creates_correct_path(self, workspace: Workspace):
        repo = ProjectRepository(workspace.projects_dir)
        p = Project(name="주일예배")
        saved = repo.save_to_workspace(p, workspace)

        assert saved == workspace.project_dir("주일예배") / "project.json"
        assert saved.exists()

    def test_workspace_project_listed_after_save(self, workspace: Workspace):
        repo = ProjectRepository(workspace.projects_dir)
        repo.save_to_workspace(Project(name="주일예배"), workspace)
        repo.save_to_workspace(Project(name="성탄절"), workspace)

        names = {p.name for p in workspace.list_projects()}
        assert names == {"주일예배", "성탄절"}

    def test_load_by_name_after_save(self, workspace: Workspace):
        repo = ProjectRepository(workspace.projects_dir)
        repo.save_to_workspace(Project(name="주일예배"), workspace)

        loaded = repo.load_from_workspace(workspace, "주일예배")
        assert loaded.name == "주일예배"


class TestWorkspaceProjectDetection:
    """MainWindow._detect_workspace_project 로직 검증

    MainWindow 전체를 생성하지 않고 순수 함수 로직만 확인.
    """

    def _detect(self, workspace: Workspace, path: Path) -> str | None:
        """MainWindow._detect_workspace_project와 동일한 로직"""
        if workspace is None:
            return None
        try:
            rel = Path(path).resolve().relative_to(workspace.projects_dir)
        except ValueError:
            return None
        parts = rel.parts
        if len(parts) == 2 and parts[1] == "project.json":
            return parts[0]
        return None

    def test_detect_workspace_project_path(self, workspace: Workspace):
        path = workspace.project_dir("주일예배") / "project.json"
        path.parent.mkdir(parents=True)
        path.touch()

        name = self._detect(workspace, path)
        assert name == "주일예배"

    def test_detect_returns_none_for_non_workspace_path(
        self, workspace: Workspace, tmp_path: Path
    ):
        outside = tmp_path / "outside" / "project.json"
        outside.parent.mkdir(parents=True)
        outside.touch()

        name = self._detect(workspace, outside)
        assert name is None

    def test_detect_returns_none_for_wrong_filename(self, workspace: Workspace):
        path = workspace.project_dir("주일예배") / "other.json"
        path.parent.mkdir(parents=True)
        path.touch()

        name = self._detect(workspace, path)
        assert name is None

    def test_detect_with_no_workspace(self, tmp_path: Path):
        assert self._detect(None, tmp_path / "any.json") is None


class TestWorkspaceProjectLauncher:
    """ProjectLauncher의 워크스페이스 연동"""

    def test_set_workspace_populates_both_panels(self, qapp, workspace: Workspace):
        from flow.ui.project_launcher import ProjectLauncher

        # 테스트 데이터
        (workspace.library_song_dir("은혜")).mkdir(parents=True)
        (workspace.library_song_dir("은혜") / "song.json").write_text('{"name":"은혜"}')
        (workspace.project_dir("예배")).mkdir(parents=True)
        (workspace.project_dir("예배") / "project.json").write_text('{"name":"예배"}')

        launcher = ProjectLauncher()
        launcher.set_workspace(workspace)

        assert len(launcher._song_panel._cards) == 1
        assert len(launcher._proj_panel._cards) == 1
        assert "워크스페이스: ws" in launcher._ws_label.text()

    def test_set_workspace_none_clears(self, qapp, workspace: Workspace):
        from flow.ui.project_launcher import ProjectLauncher

        (workspace.library_song_dir("곡")).mkdir(parents=True)
        (workspace.library_song_dir("곡") / "song.json").write_text('{"name":"곡"}')

        launcher = ProjectLauncher()
        launcher.set_workspace(workspace)
        assert len(launcher._song_panel._cards) == 1

        launcher.set_workspace(None)
        assert len(launcher._song_panel._cards) == 0
        assert len(launcher._proj_panel._cards) == 0

    def test_refresh_picks_up_new_project(self, qapp, workspace: Workspace):
        """파일시스템에 프로젝트 추가 후 refresh_workspace_items 호출 시 반영."""
        from flow.ui.project_launcher import ProjectLauncher

        launcher = ProjectLauncher()
        launcher.set_workspace(workspace)
        assert len(launcher._proj_panel._cards) == 0

        (workspace.project_dir("신규")).mkdir(parents=True)
        (workspace.project_dir("신규") / "project.json").write_text('{"name":"신규"}')

        launcher.refresh_workspace_items()
        assert len(launcher._proj_panel._cards) == 1
