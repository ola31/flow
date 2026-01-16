"""Project(프로젝트) 도메인 모델 테스트

TDD RED 단계: 실패하는 테스트 먼저 작성
"""

import pytest
from flow.domain.project import Project
from flow.domain.score_sheet import ScoreSheet
from flow.domain.hotspot import Hotspot


class TestProjectCreation:
    """프로젝트 생성 테스트"""
    
    def test_create_project_with_name(self):
        """이름으로 프로젝트 생성"""
        project = Project(name="2026-01-12 주일예배")
        
        assert project.name == "2026-01-12 주일예배"
    
    def test_project_has_unique_id(self):
        """프로젝트는 고유 ID를 가짐"""
        project1 = Project(name="프로젝트1")
        project2 = Project(name="프로젝트2")
        
        assert project1.id != project2.id
    
    def test_new_project_has_no_score_sheets(self):
        """새 프로젝트에는 시트가 없음"""
        project = Project(name="테스트")
        
        assert len(project.score_sheets) == 0


class TestProjectScoreSheetManagement:
    """프로젝트 시트 관리 테스트"""
    
    def test_add_score_sheet(self):
        """시트 추가"""
        project = Project(name="테스트")
        sheet = ScoreSheet(name="주 품에 품으소서")
        
        project.add_score_sheet(sheet)
        
        assert len(project.score_sheets) == 1
        assert project.score_sheets[0] == sheet
    
    def test_add_multiple_score_sheets(self):
        """여러 시트 추가"""
        project = Project(name="테스트")
        project.add_score_sheet(ScoreSheet(name="곡1"))
        project.add_score_sheet(ScoreSheet(name="곡2"))
        project.add_score_sheet(ScoreSheet(name="곡3"))
        
        assert len(project.score_sheets) == 3
    
    def test_remove_score_sheet(self):
        """시트 제거"""
        project = Project(name="테스트")
        sheet = ScoreSheet(name="삭제할 곡")
        project.add_score_sheet(sheet)
        
        project.remove_score_sheet(sheet.id)
        
        assert len(project.score_sheets) == 0
    
    def test_find_score_sheet_by_id(self):
        """ID로 시트 찾기"""
        project = Project(name="테스트")
        sheet = ScoreSheet(name="찾을 곡")
        project.add_score_sheet(sheet)
        
        found = project.find_score_sheet_by_id(sheet.id)
        
        assert found == sheet
    
    def test_reorder_score_sheets(self):
        """시트 순서 변경"""
        project = Project(name="테스트")
        sheet1 = ScoreSheet(name="곡1")
        sheet2 = ScoreSheet(name="곡2")
        sheet3 = ScoreSheet(name="곡3")
        project.add_score_sheet(sheet1)
        project.add_score_sheet(sheet2)
        project.add_score_sheet(sheet3)
        
        # 곡3을 맨 앞으로 이동
        project.move_score_sheet(sheet3.id, 0)
        
        assert project.score_sheets[0].name == "곡3"
        assert project.score_sheets[1].name == "곡1"


class TestProjectNavigation:
    """프로젝트 네비게이션 테스트"""
    
    def test_get_current_score_sheet(self):
        """현재 시트 가져오기"""
        project = Project(name="테스트")
        sheet = ScoreSheet(name="현재곡")
        project.add_score_sheet(sheet)
        project.current_sheet_index = 0
        
        current = project.get_current_score_sheet()
        
        assert current == sheet
    
    def test_next_score_sheet(self):
        """다음 시트로 이동"""
        project = Project(name="테스트")
        project.add_score_sheet(ScoreSheet(name="곡1"))
        project.add_score_sheet(ScoreSheet(name="곡2"))
        project.current_sheet_index = 0
        
        project.next_score_sheet()
        
        assert project.current_sheet_index == 1
    
    def test_previous_score_sheet(self):
        """이전 시트로 이동"""
        project = Project(name="테스트")
        project.add_score_sheet(ScoreSheet(name="곡1"))
        project.add_score_sheet(ScoreSheet(name="곡2"))
        project.current_sheet_index = 1
        
        project.previous_score_sheet()
        
        assert project.current_sheet_index == 0
    
    def test_next_at_end_stays(self):
        """마지막 시트에서 다음은 유지"""
        project = Project(name="테스트")
        project.add_score_sheet(ScoreSheet(name="곡1"))
        project.current_sheet_index = 0
        
        project.next_score_sheet()
        
        assert project.current_sheet_index == 0  # 유지됨


class TestProjectSerialization:
    """프로젝트 직렬화 테스트"""
    
    def test_to_dict(self):
        """딕셔너리로 변환"""
        project = Project(name="테스트 프로젝트")
        sheet = ScoreSheet(name="곡1")
        sheet.add_hotspot(Hotspot(x=100, y=200, lyric="가사"))
        project.add_score_sheet(sheet)
        
        data = project.to_dict()
        
        assert data["name"] == "테스트 프로젝트"
        assert len(data["score_sheets"]) == 1
        assert len(data["score_sheets"][0]["hotspots"]) == 1
    
    def test_from_dict(self):
        """딕셔너리에서 생성"""
        data = {
            "id": "project-123",
            "name": "복원된 프로젝트",
            "current_sheet_index": 1,
            "score_sheets": [
                {"id": "s1", "name": "곡1", "image_path": "", "hotspots": []},
                {"id": "s2", "name": "곡2", "image_path": "", "hotspots": []}
            ]
        }
        
        project = Project.from_dict(data)
        
        assert project.id == "project-123"
        assert project.name == "복원된 프로젝트"
        assert len(project.score_sheets) == 2
        assert project.current_sheet_index == 1
