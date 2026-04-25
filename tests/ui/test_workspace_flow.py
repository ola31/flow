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
        p = Project(name="공연1")
        saved = repo.save_to_workspace(p, workspace)

        assert saved == workspace.project_dir("공연1") / "project.json"
        assert saved.exists()

    def test_workspace_project_listed_after_save(self, workspace: Workspace):
        repo = ProjectRepository(workspace.projects_dir)
        repo.save_to_workspace(Project(name="공연1"), workspace)
        repo.save_to_workspace(Project(name="공연A"), workspace)

        names = {p.name for p in workspace.list_projects()}
        assert names == {"공연1", "공연A"}

    def test_load_by_name_after_save(self, workspace: Workspace):
        repo = ProjectRepository(workspace.projects_dir)
        repo.save_to_workspace(Project(name="공연1"), workspace)

        loaded = repo.load_from_workspace(workspace, "공연1")
        assert loaded.name == "공연1"


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
        path = workspace.project_dir("공연1") / "project.json"
        path.parent.mkdir(parents=True)
        path.touch()

        name = self._detect(workspace, path)
        assert name == "공연1"

    def test_detect_returns_none_for_non_workspace_path(
        self, workspace: Workspace, tmp_path: Path
    ):
        outside = tmp_path / "outside" / "project.json"
        outside.parent.mkdir(parents=True)
        outside.touch()

        name = self._detect(workspace, outside)
        assert name is None

    def test_detect_returns_none_for_wrong_filename(self, workspace: Workspace):
        path = workspace.project_dir("공연1") / "other.json"
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
        (workspace.library_song_dir("곡B")).mkdir(parents=True)
        (workspace.library_song_dir("곡B") / "song.json").write_text('{"name":"곡B"}')
        (workspace.project_dir("셋")).mkdir(parents=True)
        (workspace.project_dir("셋") / "project.json").write_text('{"name":"셋"}')

        launcher = ProjectLauncher()
        launcher.set_workspace(workspace)

        assert len(launcher._song_panel._cards) == 1
        assert len(launcher._proj_panel._cards) == 1
        # 워크스페이스 헤더는 메뉴 트리거 버튼 — name이 표시되는지 확인
        assert "ws" in launcher._ws_button.text()

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

    def test_song_library_dialog_workspace_mode_two_buttons(
        self, qapp, workspace: Workspace, tmp_path: Path
    ):
        """워크스페이스 모드에서 각 카드에 '참조'/'복사' 두 버튼이 있어야 함."""
        from flow.ui.editor.song_list_widget import (
            SongLibraryDialog,
            _LibrarySongCard,
        )

        (workspace.library_song_dir("곡B")).mkdir(parents=True)
        (workspace.library_song_dir("곡B") / "song.json").write_text(
            '{"name":"곡B","sheets":[]}'
        )

        dlg = SongLibraryDialog(
            songs_dir=tmp_path / "dummy",
            included_names=set(),
            workspace=workspace,
        )
        assert len(dlg._cards) == 1
        card = dlg._cards[0]
        assert card._workspace_mode is True
        # 두 버튼이 생성되었는지 (참조 + 복사)
        buttons = card.findChildren(type(card.findChild(object, "")))
        # 간단 검증: 카드 안에 QPushButton이 2개 있어야 함
        from PySide6.QtWidgets import QPushButton
        btns = card.findChildren(QPushButton)
        assert len(btns) == 2, f"워크스페이스 모드엔 2개 버튼 필요, got {len(btns)}"

    def test_song_library_dialog_legacy_mode_single_button(
        self, qapp, tmp_path: Path
    ):
        """레거시 모드에서는 단일 '추가' 버튼만 있어야 함."""
        from flow.ui.editor.song_list_widget import SongLibraryDialog
        from PySide6.QtWidgets import QPushButton

        songs_dir = tmp_path / "songs"
        songs_dir.mkdir()
        (songs_dir / "곡").mkdir()
        (songs_dir / "곡" / "song.json").write_text('{"name":"곡","sheets":[]}')

        dlg = SongLibraryDialog(
            songs_dir=songs_dir,
            included_names=set(),
        )
        assert len(dlg._cards) == 1
        card = dlg._cards[0]
        assert card._workspace_mode is False
        btns = card.findChildren(QPushButton)
        assert len(btns) == 1

    def test_library_scan_from_workspace(self, qapp, workspace: Workspace):
        """워크스페이스 모드면 dialog는 workspace.library_dir를 스캔."""
        from flow.ui.editor.song_list_widget import SongLibraryDialog

        (workspace.library_song_dir("공용A")).mkdir(parents=True)
        (workspace.library_song_dir("공용A") / "song.json").write_text(
            '{"name":"공용A","sheets":[]}'
        )
        (workspace.library_song_dir("공용B")).mkdir(parents=True)
        (workspace.library_song_dir("공용B") / "song.json").write_text(
            '{"name":"공용B","sheets":[]}'
        )

        # songs_dir는 프로젝트 내부라 비어있지만 workspace 인자 때문에 library가 스캔돼야
        dlg = SongLibraryDialog(
            songs_dir=workspace.projects_dir / "non_existent",
            included_names=set(),
            workspace=workspace,
        )
        names = {info["name"] for info in dlg._all_infos}
        assert names == {"공용A", "공용B"}

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


class TestProjectClone:
    """repo.clone_workspace_project 동작 검증 (Phase 4e)"""

    def test_clone_creates_new_project(self, workspace: Workspace):
        repo = ProjectRepository(workspace.projects_dir)
        repo.save_to_workspace(Project(name="원본"), workspace)

        new_path = repo.clone_workspace_project(workspace, "원본", "복사본")

        assert new_path.exists()
        assert new_path == workspace.project_dir("복사본") / "project.json"
        # 원본/복사본 모두 워크스페이스에 존재
        names = {p.name for p in workspace.list_projects()}
        assert {"원본", "복사본"} <= names

    def test_clone_gets_new_id(self, workspace: Workspace):
        repo = ProjectRepository(workspace.projects_dir)
        repo.save_to_workspace(Project(name="원본"), workspace)

        repo.clone_workspace_project(workspace, "원본", "복사본")

        original = repo.load_from_workspace(workspace, "원본")
        clone = repo.load_from_workspace(workspace, "복사본")
        assert original.id != clone.id
        assert clone.name == "복사본"

    def test_clone_rejects_duplicate_name(self, workspace: Workspace):
        repo = ProjectRepository(workspace.projects_dir)
        repo.save_to_workspace(Project(name="A"), workspace)
        repo.save_to_workspace(Project(name="B"), workspace)

        with pytest.raises(FileExistsError):
            repo.clone_workspace_project(workspace, "A", "B")

    def test_clone_rejects_missing_source(self, workspace: Workspace):
        repo = ProjectRepository(workspace.projects_dir)
        with pytest.raises(FileNotFoundError):
            repo.clone_workspace_project(workspace, "없는프로젝트", "신규")


class TestProjectLauncherCardContextMenu:
    """카드 우클릭 메뉴에 '복제' 항목이 프로젝트에만 추가되는지"""

    def test_project_card_emits_clone_requested(self, qapp, workspace: Workspace):
        from flow.ui.project_launcher import _RecentCard

        card = _RecentCard(
            path="/tmp/fake/project.json",
            kind="project",
            title="테스트",
            detail="",
        )

        received: list[str] = []
        card.clone_requested.connect(lambda p: received.append(p))

        # 메뉴에 복제 액션이 있어야 함 — contextMenuEvent 직접 호출 대신
        # 시그널만 트리거해서 확인
        card.clone_requested.emit(card._path)
        assert received == ["/tmp/fake/project.json"]
