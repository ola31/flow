"""ProjectRepository 테스트

TDD RED 단계: 실패하는 테스트 먼저 작성
"""

import pytest
import json
from pathlib import Path
from flow.repository.project_repository import ProjectRepository
from flow.domain.project import Project
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
        
        # JSON 파일 내용 확인
        with open(file_path, "r", encoding="utf-8") as f:
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
