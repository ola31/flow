import pytest
import json
from pathlib import Path
from flow.services.config_service import ConfigService

@pytest.fixture
def config_service(tmp_path):
    """테스트용 ConfigService 인스턴스 (임시 경로 사용)"""
    service = ConfigService()
    # 테스트를 위해 경로 재설정
    service._config_dir = tmp_path / ".flow"
    service._config_file = service._config_dir / "config.json"
    service._config = {"recent_projects": []}
    return service

class TestConfigServicePathNormalization:
    """경로 표준화 및 호환성 테스트"""
    
    def test_add_recent_project_normalizes_to_posix(self, config_service, tmp_path):
        """리눅스/윈도우 경로가 POSIX 스타일(/)로 통일되는지 확인"""
        # 실제 존재하는 파일이어야 함
        test_file = tmp_path / "test_project.json"
        test_file.touch()
        
        # 윈도우 스타일 경로 시뮬레이션
        win_path = str(test_file).replace("/", "\\")
        config_service.add_recent_project(win_path)
        
        projects = config_service.get_recent_projects()
        assert len(projects) == 1
        assert "\\" not in projects[0]
        assert "/" in projects[0]
        assert projects[0] == test_file.as_posix()

    def test_add_non_existent_project_does_not_save(self, config_service):
        """존재하지 않는 파일은 목록에 추가되지 않음"""
        config_service.add_recent_project("/non/existent/path.json")
        assert len(config_service.get_recent_projects()) == 0

class TestConfigServiceRecentProjects:
    """최근 프로젝트 목록 관리 테스트"""
    
    def test_add_recent_project_maintains_order(self, config_service, tmp_path):
        """새로 추가된 프로젝트가 항상 맨 앞에 오는지 확인"""
        p1 = tmp_path / "p1.json"
        p2 = tmp_path / "p2.json"
        p1.touch()
        p2.touch()
        
        config_service.add_recent_project(str(p1))
        config_service.add_recent_project(str(p2))
        
        projects = config_service.get_recent_projects()
        assert projects[0] == p2.as_posix()
        assert projects[1] == p1.as_posix()

    def test_add_duplicate_project_moves_it_to_front(self, config_service, tmp_path):
        """중복된 프로젝트 추가 시 목록의 맨 앞으로 이동"""
        p1 = tmp_path / "p1.json"
        p2 = tmp_path / "p2.json"
        p1.touch()
        p2.touch()
        
        config_service.add_recent_project(str(p1))
        config_service.add_recent_project(str(p2))
        config_service.add_recent_project(str(p1)) # 다시 p1 추가
        
        projects = config_service.get_recent_projects()
        assert len(projects) == 2
        assert projects[0] == p1.as_posix()

    def test_max_limit_is_10(self, config_service, tmp_path):
        """목록은 최대 10개까지만 유지"""
        for i in range(15):
            p = tmp_path / f"p{i}.json"
            p.touch()
            config_service.add_recent_project(str(p))
            
        assert len(config_service.get_recent_projects()) == 10
        # 가장 최근인 p14가 맨 앞
        assert config_service.get_recent_projects()[0] == (tmp_path / "p14.json").as_posix()

class TestConfigServicePersistence:
    """데이터 영구 저장 테스트"""
    
    def test_save_and_load(self, config_service, tmp_path):
        """파일로 저장되고 다시 로드되는지 확인"""
        p1 = tmp_path / "p1.json"
        p1.touch()
        path_str = p1.as_posix()
        
        config_service.add_recent_project(path_str)
        
        # 파일이 생성되었는지 확인
        assert config_service._config_file.exists()
        
        # 새로운 인스턴스로 로드 시도
        new_service = ConfigService()
        new_service._config_dir = config_service._config_dir
        new_service._config_file = config_service._config_file
        new_service.load()
        
        assert path_str in new_service.get_recent_projects()
