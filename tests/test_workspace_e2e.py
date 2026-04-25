"""End-to-end 워크스페이스 통합 스모크 테스트

실제 파일시스템 + 도메인 + 리포지토리 전체를 관통하는 흐름 검증.
UI는 거치지 않지만 UI 핸들러가 호출하는 메서드 경로를 모두 포함한다.

각 테스트는 독립 tmp_path에서 깨끗한 워크스페이스를 만들어 실행.
실패하면 어느 단계에서 깨졌는지 assertion 메시지로 특정 가능.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from flow.domain.project import Project
from flow.domain.score_sheet import ScoreSheet
from flow.domain.song import Song
from flow.domain.workspace import Workspace
from flow.repository.project_repository import ProjectRepository


def _seed_library_song(workspace: Workspace, name: str) -> Path:
    """워크스페이스 라이브러리에 샘플 곡 폴더 + song.json + 가짜 PPT를 만든다."""
    song_dir = workspace.library_song_dir(name)
    song_dir.mkdir(parents=True, exist_ok=True)

    sheet = ScoreSheet(name=f"{name}_sheet")
    (song_dir / "song.json").write_text(
        json.dumps(
            {"name": name, "sheets": [sheet.to_dict()]},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    # SlideManager가 실제로 파싱을 시도할 수는 없지만, has_slides 경로는 True가 됨
    (song_dir / "slides.pptx").write_bytes(b"fake-pptx-content")
    (song_dir / "sheets").mkdir(exist_ok=True)
    return song_dir


# =============================================================================
# 1. 워크스페이스 생성 / 열기
# =============================================================================


class TestWorkspaceLifecycle:
    def test_create_and_reopen_workspace(self, tmp_path: Path):
        root = tmp_path / "내교회"

        ws = Workspace.create(root)
        assert ws.root == root.resolve()
        assert ws.library_dir.exists()
        assert ws.projects_dir.exists()

        # 앱 재시작을 시뮬레이션 — 기존 폴더를 open
        reopened = Workspace.open(root)
        assert reopened.is_valid()
        assert reopened.library_dir == ws.library_dir


# =============================================================================
# 2. 라이브러리 곡 관리
# =============================================================================


class TestLibraryBrowsing:
    def test_library_songs_visible_after_seeding(self, tmp_path: Path):
        ws = Workspace.create(tmp_path / "ws")
        _seed_library_song(ws, "곡A")
        _seed_library_song(ws, "곡B")

        names = {s.name for s in ws.list_library_songs()}
        assert names == {"곡A", "곡B"}

    def test_library_song_loads_with_absolute_path(self, tmp_path: Path):
        """Song.load_from_workspace로 로드한 곡은 abs_slides_path가
        project_dir 없이도 올바른 절대 경로를 반환해야 함."""
        ws = Workspace.create(tmp_path / "ws")
        _seed_library_song(ws, "곡B")

        song = Song.load_from_workspace(ws, "셋", "곡B")
        assert song is not None
        assert song.source == "library"
        assert song.abs_slides_path.is_absolute()
        assert song.abs_slides_path == ws.library_song_dir("곡B") / "slides.pptx"
        assert song.has_slides  # 가짜라도 파일 존재
        assert song.has_sheets


# =============================================================================
# 3. 프로젝트 전체 라이프사이클
# =============================================================================


class TestProjectLifecycle:
    def test_new_save_reload_with_library_reference(self, tmp_path: Path):
        """워크스페이스 + 라이브러리 곡 2개 → 새 프로젝트 생성 →
        둘 다 참조로 추가 → 저장 → 로드 → 정체성 유지."""
        ws = Workspace.create(tmp_path / "ws")
        _seed_library_song(ws, "곡A")
        _seed_library_song(ws, "곡B")
        repo = ProjectRepository(ws.root)

        # 1) 프로젝트 생성
        project = Project(name="2024-12 공연")

        # 2) 라이브러리에서 두 곡 참조 추가 (UI의 "참조" 버튼 클릭에 해당)
        for i, name in enumerate(["곡A", "곡B"]):
            song = Song.load_from_workspace(ws, project.name, name, order=i)
            assert song is not None
            assert song.source == "library"
            project.selected_songs.append(song)
            project.song_order.append(name)

        # 3) 저장
        saved_path = repo.save_to_workspace(project, ws)
        assert saved_path == ws.project_dir("2024-12 공연") / "project.json"

        # 4) 파일시스템 구조 검증
        # project.json만 있고, project/songs/는 생성되지 않아야 함 (참조니까)
        project_dir = ws.project_dir("2024-12 공연")
        assert (project_dir / "project.json").exists()
        assert not (project_dir / "songs" / "곡A").exists()
        assert not (project_dir / "songs" / "곡B").exists()

        # 라이브러리에는 원본 그대로 존재
        assert (ws.library_song_dir("곡A") / "song.json").exists()
        assert (ws.library_song_dir("곡B") / "song.json").exists()

        # 5) 재로드 (앱 재시작 시뮬레이션)
        reloaded = repo.load_from_workspace(ws, "2024-12 공연")
        assert reloaded.name == "2024-12 공연"
        assert len(reloaded.selected_songs) == 2
        assert all(s.source == "library" for s in reloaded.selected_songs)
        assert [s.name for s in reloaded.selected_songs] == ["곡A", "곡B"]

    def test_mixed_library_and_local_songs(self, tmp_path: Path):
        """library 1곡 참조 + library 1곡 로컬 복사 조합"""
        ws = Workspace.create(tmp_path / "ws")
        _seed_library_song(ws, "공용곡")
        _seed_library_song(ws, "커스터마이즈")
        repo = ProjectRepository(ws.root)

        project = Project(name="2024-12 공연")

        # 곡1: 참조
        ref_song = Song.load_from_workspace(ws, project.name, "공용곡", order=0)
        assert ref_song is not None
        project.selected_songs.append(ref_song)

        # 곡2: 로컬 복사 (UI의 "복사" 버튼 클릭에 해당)
        # → library/커스터마이즈/ 를 projects/공연A/songs/커스터마이즈/로 복사
        import shutil
        src = ws.library_song_dir("커스터마이즈")
        dst = ws.project_dir("2024-12 공연") / "songs" / "커스터마이즈"
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, dst)

        # load_from_workspace가 local을 우선 찾음
        local_song = Song.load_from_workspace(ws, project.name, "커스터마이즈", order=1)
        assert local_song is not None
        assert local_song.source == "local"
        project.selected_songs.append(local_song)

        repo.save_to_workspace(project, ws)

        # 재로드 후 source가 올바르게 유지되는지
        reloaded = repo.load_from_workspace(ws, "2024-12 공연")
        sources = {s.name: s.source for s in reloaded.selected_songs}
        assert sources == {"공용곡": "library", "커스터마이즈": "local"}

        # 로컬 곡을 수정해도 라이브러리 곡에 영향 없어야 함 (실제 독립성 검증)
        local_song_json = dst / "song.json"
        data = json.loads(local_song_json.read_text(encoding="utf-8-sig"))
        data["marker"] = "customized"
        local_song_json.write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8"
        )

        # library 원본은 변경 없음
        lib_data = json.loads(
            (ws.library_song_dir("커스터마이즈") / "song.json")
            .read_text(encoding="utf-8-sig")
        )
        assert "marker" not in lib_data


# =============================================================================
# 4. 프로젝트 복제
# =============================================================================


class TestProjectClone:
    def test_clone_preserves_library_refs_and_duplicates_local(self, tmp_path: Path):
        ws = Workspace.create(tmp_path / "ws")
        _seed_library_song(ws, "A")
        _seed_library_song(ws, "B")
        repo = ProjectRepository(ws.root)

        # 원본: A(참조) + B(로컬 복사)
        original = Project(name="원본")
        original.selected_songs.append(
            Song.load_from_workspace(ws, "원본", "A", order=0)
        )
        # B는 로컬 복사
        import shutil
        shutil.copytree(
            ws.library_song_dir("B"),
            ws.project_dir("원본") / "songs" / "B",
        )
        original.selected_songs.append(
            Song.load_from_workspace(ws, "원본", "B", order=1)
        )
        repo.save_to_workspace(original, ws)

        # 복제
        repo.clone_workspace_project(ws, "원본", "복제본")

        # 복제본 로컬 곡 복사됨
        assert (ws.project_dir("복제본") / "songs" / "B" / "song.json").exists()

        # 라이브러리는 여전히 하나만 (참조 중복 아님)
        assert len(list(ws.library_dir.iterdir())) == 2  # A, B

        # 복제본과 원본은 독립적인 id
        original_loaded = repo.load_from_workspace(ws, "원본")
        clone_loaded = repo.load_from_workspace(ws, "복제본")
        assert original_loaded.id != clone_loaded.id
        assert clone_loaded.name == "복제본"

        # 복제본의 로컬 B를 수정해도 원본에 영향 없음
        clone_b = ws.project_dir("복제본") / "songs" / "B" / "song.json"
        data = json.loads(clone_b.read_text(encoding="utf-8-sig"))
        data["edited_in_clone"] = True
        clone_b.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

        original_b = ws.project_dir("원본") / "songs" / "B" / "song.json"
        orig_data = json.loads(original_b.read_text(encoding="utf-8-sig"))
        assert "edited_in_clone" not in orig_data


# =============================================================================
# 5. 프로젝트 삭제
# =============================================================================


class TestProjectDeletion:
    def test_delete_project_removes_folder_but_preserves_library(
        self, tmp_path: Path
    ):
        ws = Workspace.create(tmp_path / "ws")
        _seed_library_song(ws, "보존될곡")
        repo = ProjectRepository(ws.root)

        project = Project(name="삭제대상")
        project.selected_songs.append(
            Song.load_from_workspace(ws, "삭제대상", "보존될곡", order=0)
        )
        repo.save_to_workspace(project, ws)

        # 로컬 복사된 곡도 하나 추가
        import shutil
        shutil.copytree(
            ws.library_song_dir("보존될곡"),
            ws.project_dir("삭제대상") / "songs" / "로컬곡",
        )

        assert ws.project_dir("삭제대상").exists()
        repo.delete_workspace_project(ws, "삭제대상")

        # 프로젝트 폴더와 로컬 곡 전부 사라짐
        assert not ws.project_dir("삭제대상").exists()
        # 라이브러리 곡은 그대로
        assert (ws.library_song_dir("보존될곡") / "song.json").exists()


# =============================================================================
# 6. 곡 편집 모드 — 워크스페이스 절대경로 핸들링
# =============================================================================


class TestEnterSongEditMode:
    """_enter_song_edit_mode가 workspace에서 로드된 곡(절대경로 folder)에
    대해 'NoneType .parent' 에러 없이 진입해야 함."""

    def _seed_library_song_with_pptx(self, workspace: Workspace, name: str) -> Path:
        song_dir = workspace.library_song_dir(name)
        song_dir.mkdir(parents=True, exist_ok=True)
        sheet = ScoreSheet(name=f"{name}_sheet")
        (song_dir / "song.json").write_text(
            json.dumps(
                {"name": name, "sheets": [sheet.to_dict()]},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (song_dir / "slides.pptx").write_bytes(b"fake")
        (song_dir / "sheets").mkdir(exist_ok=True)
        return song_dir

    def test_enter_song_edit_with_library_song(self, qapp, tmp_path: Path):
        from flow.ui.main_window import MainWindow

        ws = Workspace.create(tmp_path / "ws")
        self._seed_library_song_with_pptx(ws, "곡B")

        mw = MainWindow(workspace=ws)
        try:
            mw._project = Project(name="셋")
            repo = ProjectRepository(ws.projects_dir)
            mw._project_path = repo.save_to_workspace(mw._project, ws)

            song = Song.load_from_workspace(ws, "셋", "곡B", order=0)
            assert song is not None
            assert song.folder.is_absolute()  # workspace songs have absolute folder
            mw._project.selected_songs.append(song)

            mw._enter_song_edit_mode(song)
            assert mw._is_standalone is True
            assert mw._project.name == "[곡 편집] 곡B"
        finally:
            mw.close()

    def test_enter_song_edit_with_local_override_song(self, qapp, tmp_path: Path):
        """로컬로 복사된 곡도 절대경로지만 projects/ 하위 경로여야 함."""
        import shutil

        from flow.ui.main_window import MainWindow

        ws = Workspace.create(tmp_path / "ws")
        src = self._seed_library_song_with_pptx(ws, "곡A")

        mw = MainWindow(workspace=ws)
        try:
            mw._project = Project(name="Proj")
            repo = ProjectRepository(ws.projects_dir)
            mw._project_path = repo.save_to_workspace(mw._project, ws)

            local = ws.project_dir("Proj") / "songs" / "곡A"
            shutil.copytree(src, local)

            song = Song.load_from_workspace(ws, "Proj", "곡A", order=0)
            assert song.source == "local"
            mw._project.selected_songs.append(song)

            mw._enter_song_edit_mode(song)
            assert mw._is_standalone is True
        finally:
            mw.close()


# =============================================================================
# 7. 의심 구역: MainWindow가 workspace=None으로 생성 가능한지
# =============================================================================


class TestMainWindowConstruction:
    """MainWindow의 construction이 workspace 유무 모두에서 깨지지 않는지."""

    def test_mainwindow_with_workspace(self, qapp, tmp_path: Path):
        from flow.ui.main_window import MainWindow

        ws = Workspace.create(tmp_path / "ws")
        mw = MainWindow(workspace=ws)
        assert mw._workspace is ws
        assert mw._repo.base_path == ws.projects_dir
        mw.close()

    def test_mainwindow_without_workspace(self, qapp):
        from flow.ui.main_window import MainWindow

        mw = MainWindow()  # workspace=None
        assert mw._workspace is None
        # 레거시 기본 경로
        assert mw._repo.base_path == Path.home() / "flow_projects"
        mw.close()


# =============================================================================
# 8. 의심 구역: 같은 곡 이름이 library와 local에 동시에 있을 때
# =============================================================================


class TestLocalOverride:
    def test_local_wins_when_both_exist(self, tmp_path: Path):
        ws = Workspace.create(tmp_path / "ws")
        _seed_library_song(ws, "곡B")

        # 프로젝트에 로컬 "곡B"를 수동 생성 (라이브러리와 다른 내용)
        local_dir = ws.project_dir("셋") / "songs" / "곡B"
        local_dir.mkdir(parents=True)
        sheet = ScoreSheet(name="local_version")
        (local_dir / "song.json").write_text(
            json.dumps(
                {"name": "곡B", "sheets": [sheet.to_dict()], "marker": "LOCAL"},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        song = Song.load_from_workspace(ws, "셋", "곡B")
        assert song is not None
        assert song.source == "local"
        assert song.score_sheets[0].name == "local_version"
        assert song.folder == local_dir.resolve()
