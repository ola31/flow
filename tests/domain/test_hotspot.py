"""Hotspot(핫스팟) 도메인 모델 테스트

TDD RED 단계: 실패하는 테스트 먼저 작성
"""

import pytest
from flow.domain.hotspot import Hotspot


class TestHotspotCreation:
    """핫스팟 생성 테스트"""
    
    def test_create_hotspot_with_coordinates(self):
        """좌표로 핫스팟 생성"""
        hotspot = Hotspot(x=100, y=200)
        
        assert hotspot.x == 100
        assert hotspot.y == 200
    
    def test_create_hotspot_with_id(self):
        """ID가 자동 생성되는지 확인"""
        hotspot = Hotspot(x=100, y=200)
        
        assert hotspot.id is not None
        assert len(hotspot.id) > 0
    
    def test_two_hotspots_have_different_ids(self):
        """두 핫스팟은 다른 ID를 가짐"""
        hotspot1 = Hotspot(x=100, y=200)
        hotspot2 = Hotspot(x=100, y=200)
        
        assert hotspot1.id != hotspot2.id


class TestHotspotLyricMapping:
    """핫스팟-텍스트 매핑 테스트"""
    
    def test_hotspot_has_empty_lyric_by_default(self):
        """기본 텍스트는 빈 문자열"""
        hotspot = Hotspot(x=100, y=200)
        
        assert hotspot.lyric == ""
    
    def test_set_lyric_text(self):
        """텍스트 설정"""
        hotspot = Hotspot(x=100, y=200)
        hotspot.lyric = "주 품에 품으소서"
        
        assert hotspot.lyric == "주 품에 품으소서"
    
    def test_set_multiline_lyric(self):
        """여러 줄 텍스트 설정"""
        hotspot = Hotspot(x=100, y=200)
        hotspot.lyric = "주 품에 품으소서\n내 주를 늘 섬기리"
        
        assert "주 품에 품으소서" in hotspot.lyric
        assert "내 주를 늘 섬기리" in hotspot.lyric


class TestHotspotOrder:
    """핫스팟 순서 테스트"""
    
    def test_hotspot_has_order(self):
        """핫스팟은 순서를 가짐"""
        hotspot = Hotspot(x=100, y=200, order=1)
        
        assert hotspot.order == 1
    
    def test_default_order_is_zero(self):
        """기본 순서는 0"""
        hotspot = Hotspot(x=100, y=200)
        
        assert hotspot.order == 0


class TestHotspotSlideMapping:
    """핫스팟-슬라이드 매핑 테스트 (절별 매핑 포함)"""
    
    def test_default_slide_index_is_minus_one(self):
        """기본 슬라이드 인덱스는 -1 (매핑 없음)"""
        hotspot = Hotspot(x=100, y=200)
        assert hotspot.get_slide_index(verse_index=0) == -1
        assert hotspot.get_slide_index(verse_index=1) == -1

    def test_set_slide_index_for_verse_1(self):
        """1절(0) 슬라이드 매핑 설정"""
        hotspot = Hotspot(x=100, y=200)
        hotspot.set_slide_index(slide_index=5, verse_index=0)
        
        assert hotspot.get_slide_index(verse_index=0) == 5
        assert hotspot.slide_index == 5  # 하위 호환성 확인

    def test_set_slide_index_for_different_verses(self):
        """여러 절에 각각 다른 슬라이드 매핑"""
        hotspot = Hotspot(x=100, y=200)
        hotspot.set_slide_index(10, verse_index=0) # 1절
        hotspot.set_slide_index(11, verse_index=1) # 2절
        hotspot.set_slide_index(12, verse_index=5) # 후렴
        
        assert hotspot.get_slide_index(0) == 10
        assert hotspot.get_slide_index(1) == 11
        assert hotspot.get_slide_index(5) == 12
        assert hotspot.get_slide_index(2) == -1 # 매핑 안 된 곳은 -1

    def test_slide_mappings_dictionary_key_type(self):
        """slide_mappings의 키는 항상 문자열이어야 함 (JSON 호환성)"""
        hotspot = Hotspot(x=100, y=200)
        hotspot.set_slide_index(7, verse_index=3)
        
        assert "3" in hotspot.slide_mappings
        assert hotspot.slide_mappings["3"] == 7


class TestHotspotSerialization:
    """핫스팟 직렬화 테스트 (JSON 저장용)"""
    
    def test_to_dict(self):
        """딕셔너리로 변환"""
        hotspot = Hotspot(x=100, y=200, order=1)
        hotspot.lyric = "가사 테스트"
        hotspot.set_slide_index(9, verse_index=1)
        
        data = hotspot.to_dict()
        
        assert data["x"] == 100
        assert data["y"] == 200
        assert data["order"] == 1
        assert data["lyric"] == "가사 테스트"
        assert data["slide_mappings"]["1"] == 9
        assert "id" in data
    
    def test_from_dict(self):
        """딕셔너리에서 생성"""
        data = {
            "id": "test-id-123",
            "x": 150,
            "y": 250,
            "order": 2,
            "lyric": "복원된 가사",
            "slide_index": 5,
            "slide_mappings": {"0": 5, "1": 6}
        }
        
        hotspot = Hotspot.from_dict(data)
        
        assert hotspot.id == "test-id-123"
        assert hotspot.x == 150
        assert hotspot.y == 250
        assert hotspot.get_slide_index(0) == 5
        assert hotspot.get_slide_index(1) == 6
        assert hotspot.lyric == "복원된 가사"
