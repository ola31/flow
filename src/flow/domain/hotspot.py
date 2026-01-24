"""핫스팟(Hotspot) 도메인 모델

시트 위의 특정 위치를 나타내며, 해당 위치에 슬라이드가 매핑됨.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Hotspot:
    """시트 위의 핫스팟 (버튼)
    
    Attributes:
        x: X 좌표 (픽셀)
        y: Y 좌표 (픽셀)
        order: 표시 순서 (0부터 시작)
        lyric: 연결된 텍스트
        slide_mappings: 절별 슬라이드 매핑 (str(verse_index) -> slide_index)
        id: 고유 식별자 (자동 생성)
    """
    
    x: int
    y: int
    order: int = 0
    lyric: str = ""
    slide_index: int = -1 # 기본 매핑 (Verse 1용)
    slide_mappings: dict[str, int] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    def get_slide_index(self, verse_index: int = 0) -> int:
        """특정 절에 매핑된 슬라이드 인덱스 반환"""
        # 1. 명시적 슬라이드 매핑 확인
        v_key = str(verse_index)
        if v_key in self.slide_mappings:
            return self.slide_mappings[v_key]
        
        # 2. Verse 1(0)인 경우 기본 slide_index 반환 (하위 호환)
        if verse_index == 0:
            return self.slide_index
            
        return -1

    def set_slide_index(self, slide_index: int, verse_index: int = 0) -> None:
        """특정 절에 슬라이드 매핑 설정"""
        self.slide_mappings[str(verse_index)] = slide_index
        if verse_index == 0:
            self.slide_index = slide_index

    def shift_indices(self, offset: int) -> None:
        """모든 슬라이드 인덱스를 오프셋만큼 이동 (전역/로컬 변환용)"""
        if self.slide_index != -1:
            self.slide_index += offset
        
        for k in self.slide_mappings:
            if self.slide_mappings[k] != -1:
                self.slide_mappings[k] += offset

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리로 변환 (JSON 직렬화용)"""
        return {
            "id": self.id,
            "x": self.x,
            "y": self.y,
            "order": self.order,
            "lyric": self.lyric,
            "slide_index": self.slide_index,
            "slide_mappings": self.slide_mappings,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Hotspot:
        """딕셔너리에서 생성 (JSON 역직렬화용)"""
        return cls(
            id=data["id"],
            x=data["x"],
            y=data["y"],
            order=data.get("order", 0),
            lyric=data.get("lyric", ""),
            slide_index=data.get("slide_index", -1),
            slide_mappings=data.get("slide_mappings", {}),
        )
