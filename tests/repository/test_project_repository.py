"""ProjectRepository 테스트

TDD RED 단계: 실패하는 테스트 먼저 작성
"""

import pytest
import json
from pathlib import Path
from flow.repository.project_repository import ProjectRepository
from flow.domain.project import Project
from flow.domain.song import Song
from flow.domain.score_sheet import ScoreSheet
from flow.domain.hotspot import Hotspot


class TestProjectRepositorySave:
    """프로젝트 저장 테스트"""

    def test_save_empty_project(self, tmp_path: Path):
        """빈 프로젝트 저장"""
        repo = ProjectRepository(tmp_path)
        project = Project(name="테스트 프로젝트")

        file_path = repo.save(project)

        assert file_path.exists()
        assert file_path.suffix == ".json"

    def test_save_project_with_data(self, tmp_path: Path):
        """데이터가 있는 프로젝트 저장"""
        repo = ProjectRepository(tmp_path)
        project = Project(name="테스트")
        sheet = ScoreSheet(name="곡1", image_path="images/song1.jpg")
        sheet.add_hotspot(Hotspot(x=100, y=200, lyric="가사1"))
        project.add_score_sheet(sheet)

        file_path = repo.save(project)

        # JSON 파일 내용 확인 (utf-8-sig for BOM compatibility)
        with open(file_path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)

        assert data["name"] == "테스트"
        assert len(data["score_sheets"]) == 1
        assert data["score_sheets"][0]["hotspots"][0]["lyric"] == "가사1"

    def test_save_creates_directory_if_not_exists(self, tmp_path: Path):
        """저장 시 디렉토리가 없으면 생성"""
        new_dir = tmp_path / "new_subdir"
        repo = ProjectRepository(new_dir)
        project = Project(name="테스트")

        file_path = repo.save(project)

        assert new_dir.exists()
        assert file_path.exists()


class TestProjectRepositoryLoad:
    """프로젝트 로드 테스트"""

    def test_load_project(self, tmp_path: Path):
        """프로젝트 로드"""
        repo = ProjectRepository(tmp_path)
        project = Project(name="원본 프로젝트")
        sheet = ScoreSheet(name="곡1")
        sheet.add_hotspot(Hotspot(x=100, y=200, lyric="가사"))
        project.add_score_sheet(sheet)

        file_path = repo.save(project)
        loaded = repo.load(file_path)

        assert loaded.name == "원본 프로젝트"
        assert len(loaded.score_sheets) == 1
        assert loaded.score_sheets[0].hotspots[0].lyric == "가사"

    def test_load_preserves_ids(self, tmp_path: Path):
        """로드 시 ID 보존"""
        repo = ProjectRepository(tmp_path)
        project = Project(name="테스트")
        original_id = project.id

        file_path = repo.save(project)
        loaded = repo.load(file_path)

        assert loaded.id == original_id

    def test_load_nonexistent_file_raises_error(self, tmp_path: Path):
        """존재하지 않는 파일 로드 시 에러"""
        repo = ProjectRepository(tmp_path)

        with pytest.raises(FileNotFoundError):
            repo.load(tmp_path / "nonexistent.json")

    def test_load_invalid_json_raises_error(self, tmp_path: Path):
        """잘못된 JSON 파일 로드 시 에러"""
        repo = ProjectRepository(tmp_path)
        invalid_file = tmp_path / "invalid.json"
        invalid_file.write_text("{ invalid json }", encoding="utf-8")

        with pytest.raises(json.JSONDecodeError):
            repo.load(invalid_file)


class TestProjectRepositoryList:
    """프로젝트 목록 테스트"""

    def test_list_projects_empty(self, tmp_path: Path):
        """빈 디렉토리에서 프로젝트 목록"""
        repo = ProjectRepository(tmp_path)

        projects = repo.list_projects()

        assert len(projects) == 0

    def test_list_projects(self, tmp_path: Path):
        """프로젝트 목록 조회"""
        repo = ProjectRepository(tmp_path)
        repo.save(Project(name="프로젝트1"))
        repo.save(Project(name="프로젝트2"))

        projects = repo.list_projects()

        assert len(projects) == 2


class TestProjectRepositoryDelete:
    """프로젝트 삭제 테스트"""

    def test_delete_project(self, tmp_path: Path):
        """프로젝트 삭제"""
        repo = ProjectRepository(tmp_path)
        project = Project(name="삭제할 프로젝트")
        file_path = repo.save(project)

        repo.delete(file_path)

        assert not file_path.exists()


class TestProjectRepositoryNewStructure:
    """새 구조 (곡 기반) 저장/로드 테스트"""

    def test_save_new_structure_creates_song_json(self, tmp_path: Path):
        """새 구조 저장 시 song.json 파일 생성"""
        repo = ProjectRepository(tmp_path)
        project = Project(name="새 구조 프로젝트")

        # 곡 추가
        song = Song(name="곡1", folder=Path("songs/곡1"), project_dir=tmp_path)
        sheet = ScoreSheet(name="시트1")
        sheet.add_hotspot(Hotspot(x=100, y=200, lyric="가사1"))
        song.score_sheets.append(sheet)
        project.selected_songs.append(song)

        file_path = repo.save(project)

        # project.json 생성 확인
        assert file_path.exists()
        # song.json 생성 확인
        song_json_path = tmp_path / "songs" / "곡1" / "song.json"
        assert song_json_path.exists()

    def test_save_new_structure_project_json_format(self, tmp_path: Path):
        """새 구조 project.json 형식 확인"""
        repo = ProjectRepository(tmp_path)
        project = Project(name="테스트")
        song = Song(name="곡1", folder=Path("songs/곡1"), project_dir=tmp_path, order=1)
        project.selected_songs.append(song)

        file_path = repo.save(project)

        with open(file_path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)

        # 새 구조 필드 확인
        assert "selected_songs" in data
        assert data["selected_songs"][0]["name"] == "곡1"
        assert data["selected_songs"][0]["order"] == 1
        assert "score_sheets" not in data  # 레거시 필드 없음

    def test_load_new_structure(self, tmp_path: Path):
        """새 구조 프로젝트 로드"""
        repo = ProjectRepository(tmp_path)

        # 먼저 저장
        project = Project(name="원본")
        song = Song(name="곡1", folder=Path("songs/곡1"), project_dir=tmp_path)
        sheet = ScoreSheet(name="시트1")
        hotspot = Hotspot(x=100, y=200, lyric="가사")
        hotspot.set_slide_index(5, verse_index=0)
        sheet.add_hotspot(hotspot)
        song.score_sheets.append(sheet)
        project.selected_songs.append(song)

        file_path = repo.save(project)

        # 로드
        loaded = repo.load(file_path)

        assert loaded.name == "원본"
        assert len(loaded.selected_songs) == 1
        assert loaded.selected_songs[0].name == "곡1"
        assert len(loaded.selected_songs[0].score_sheets) == 1
        assert loaded.selected_songs[0].score_sheets[0].hotspots[0].lyric == "가사"

    def test_new_structure_roundtrip_preserves_data(self, tmp_path: Path):
        """새 구조 라운드트립 데이터 보존"""
        repo = ProjectRepository(tmp_path)

        # 원본 프로젝트 생성
        original = Project(name="라운드트립", current_verse_index=2)
        song = Song(name="곡1", folder=Path("songs/곡1"), project_dir=tmp_path, order=0)

        sheet = ScoreSheet(name="시트1")
        hotspot = Hotspot(x=100, y=200, lyric="가사", order=1)
        hotspot.set_slide_index(5, verse_index=0)
        hotspot.set_slide_index(10, verse_index=5)  # 후렴
        sheet.add_hotspot(hotspot)
        song.score_sheets.append(sheet)

        original.selected_songs.append(song)
        original_id = original.id

        # 저장 후 로드
        file_path = repo.save(original)
        loaded = repo.load(file_path)

        # 데이터 비교
        assert loaded.id == original_id
        assert loaded.name == "라운드트립"
        assert loaded.current_verse_index == 2
        assert loaded.selected_songs[0].order == 0
        assert (
            loaded.selected_songs[0].score_sheets[0].hotspots[0].get_slide_index(0) == 5
        )
        assert (
            loaded.selected_songs[0].score_sheets[0].hotspots[0].get_slide_index(5)
            == 10
        )

    def test_new_structure_multiple_songs(self, tmp_path: Path):
        """여러 곡이 있는 새 구조"""
        repo = ProjectRepository(tmp_path)
        project = Project(name="다중 곡")

        # 곡 1
        song1 = Song(
            name="곡1", folder=Path("songs/곡1"), project_dir=tmp_path, order=0
        )
        sheet1 = ScoreSheet(name="시트1", image_path="sheet1.png")
        sheet1.add_hotspot(Hotspot(x=10, y=20))
        song1.score_sheets.append(sheet1)
        project.selected_songs.append(song1)

        # 곡 2
        song2 = Song(
            name="곡2", folder=Path("songs/곡2"), project_dir=tmp_path, order=1
        )
        sheet2 = ScoreSheet(name="시트2", image_path="sheet2.png")
        sheet2.add_hotspot(Hotspot(x=30, y=40))
        song2.score_sheets.append(sheet2)
        project.selected_songs.append(song2)

        file_path = repo.save(project)
        loaded = repo.load(file_path)

        assert len(loaded.selected_songs) == 2
        assert loaded.selected_songs[0].name == "곡1"
        assert loaded.selected_songs[1].name == "곡2"
        assert loaded.all_score_sheets[0].name == "시트1"
        assert loaded.all_score_sheets[1].name == "시트2"
