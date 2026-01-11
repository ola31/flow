"""ScoreSheet(악보) 도메인 모델 테스트

TDD RED 단계: 실패하는 테스트 먼저 작성
"""

import pytest
from pathlib import Path
from flow.domain.score_sheet import ScoreSheet
from flow.domain.hotspot import Hotspot


class TestScoreSheetCreation:
    """악보 생성 테스트"""
    
    def test_create_score_sheet_with_name(self):
        """이름으로 악보 생성"""
        sheet = ScoreSheet(name="주 품에 품으소서")
        
        assert sheet.name == "주 품에 품으소서"
    
    def test_create_score_sheet_with_image_path(self):
        """이미지 경로로 악보 생성"""
        sheet = ScoreSheet(name="은혜", image_path="/images/grace.jpg")
        
        assert sheet.image_path == "/images/grace.jpg"
    
    def test_score_sheet_has_unique_id(self):
        """악보는 고유 ID를 가짐"""
        sheet1 = ScoreSheet(name="곡1")
        sheet2 = ScoreSheet(name="곡2")
        
        assert sheet1.id != sheet2.id


class TestScoreSheetHotspotManagement:
    """악보 핫스팟 관리 테스트"""
    
    def test_empty_score_sheet_has_no_hotspots(self):
        """빈 악보에는 핫스팟이 없음"""
        sheet = ScoreSheet(name="테스트")
        
        assert len(sheet.hotspots) == 0
    
    def test_add_hotspot(self):
        """핫스팟 추가"""
        sheet = ScoreSheet(name="테스트")
        hotspot = Hotspot(x=100, y=200)
        
        sheet.add_hotspot(hotspot)
        
        assert len(sheet.hotspots) == 1
        assert sheet.hotspots[0] == hotspot
    
    def test_add_multiple_hotspots(self):
        """여러 핫스팟 추가"""
        sheet = ScoreSheet(name="테스트")
        sheet.add_hotspot(Hotspot(x=100, y=200))
        sheet.add_hotspot(Hotspot(x=200, y=300))
        sheet.add_hotspot(Hotspot(x=300, y=400))
        
        assert len(sheet.hotspots) == 3
    
    def test_remove_hotspot(self):
        """핫스팟 제거"""
        sheet = ScoreSheet(name="테스트")
        hotspot = Hotspot(x=100, y=200)
        sheet.add_hotspot(hotspot)
        
        sheet.remove_hotspot(hotspot.id)
        
        assert len(sheet.hotspots) == 0
    
    def test_find_hotspot_by_id(self):
        """ID로 핫스팟 찾기"""
        sheet = ScoreSheet(name="테스트")
        hotspot = Hotspot(x=100, y=200)
        sheet.add_hotspot(hotspot)
        
        found = sheet.find_hotspot_by_id(hotspot.id)
        
        assert found == hotspot
    
    def test_find_nonexistent_hotspot_returns_none(self):
        """존재하지 않는 핫스팟은 None 반환"""
        sheet = ScoreSheet(name="테스트")
        
        found = sheet.find_hotspot_by_id("nonexistent-id")
        
        assert found is None


class TestScoreSheetNavigation:
    """악보 내 핫스팟 네비게이션 테스트"""
    
    def test_get_ordered_hotspots(self):
        """순서대로 정렬된 핫스팟 목록"""
        sheet = ScoreSheet(name="테스트")
        sheet.add_hotspot(Hotspot(x=100, y=200, order=2))
        sheet.add_hotspot(Hotspot(x=200, y=300, order=0))
        sheet.add_hotspot(Hotspot(x=300, y=400, order=1))
        
        ordered = sheet.get_ordered_hotspots()
        
        assert ordered[0].order == 0
        assert ordered[1].order == 1
        assert ordered[2].order == 2
    
    def test_get_next_hotspot(self):
        """다음 핫스팟 가져오기"""
        sheet = ScoreSheet(name="테스트")
        h1 = Hotspot(x=100, y=200, order=0)
        h2 = Hotspot(x=200, y=300, order=1)
        sheet.add_hotspot(h1)
        sheet.add_hotspot(h2)
        
        next_hotspot = sheet.get_next_hotspot(h1.id)
        
        assert next_hotspot == h2
    
    def test_get_previous_hotspot(self):
        """이전 핫스팟 가져오기"""
        sheet = ScoreSheet(name="테스트")
        h1 = Hotspot(x=100, y=200, order=0)
        h2 = Hotspot(x=200, y=300, order=1)
        sheet.add_hotspot(h1)
        sheet.add_hotspot(h2)
        
        prev_hotspot = sheet.get_previous_hotspot(h2.id)
        
        assert prev_hotspot == h1
    
    def test_get_next_hotspot_at_end_returns_none(self):
        """마지막 핫스팟에서 다음은 None"""
        sheet = ScoreSheet(name="테스트")
        h1 = Hotspot(x=100, y=200, order=0)
        sheet.add_hotspot(h1)
        
        next_hotspot = sheet.get_next_hotspot(h1.id)
        
        assert next_hotspot is None


class TestScoreSheetSerialization:
    """악보 직렬화 테스트"""
    
    def test_to_dict(self):
        """딕셔너리로 변환"""
        sheet = ScoreSheet(name="테스트곡", image_path="/images/test.jpg")
        sheet.add_hotspot(Hotspot(x=100, y=200, lyric="가사1"))
        
        data = sheet.to_dict()
        
        assert data["name"] == "테스트곡"
        assert data["image_path"] == "/images/test.jpg"
        assert len(data["hotspots"]) == 1
    
    def test_from_dict(self):
        """딕셔너리에서 생성"""
        data = {
            "id": "test-sheet-id",
            "name": "복원된 악보",
            "image_path": "/images/restored.jpg",
            "hotspots": [
                {"id": "h1", "x": 100, "y": 200, "order": 0, "lyric": "가사"}
            ]
        }
        
        sheet = ScoreSheet.from_dict(data)
        
        assert sheet.id == "test-sheet-id"
        assert sheet.name == "복원된 악보"
        assert len(sheet.hotspots) == 1
