"""핫스팟(Hotspot) 도메인 모델

악보 위의 특정 위치를 나타내며, 해당 위치에 가사가 매핑됨.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Hotspot:
    """악보 위의 핫스팟 (버튼)
    
    Attributes:
        x: X 좌표 (픽셀)
        y: Y 좌표 (픽셀)
        order: 표시 순서 (0부터 시작)
        lyric: 연결된 가사 텍스트
        id: 고유 식별자 (자동 생성)
    """
    
    x: int
    y: int
    order: int = 0
    lyric: str = ""
    slide_index: int = -1
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    def to_dict(self) -> dict[str, Any]:
        """딕셔너리로 변환 (JSON 직렬화용)"""
        return {
            "id": self.id,
            "x": self.x,
            "y": self.y,
            "order": self.order,
            "lyric": self.lyric,
            "slide_index": self.slide_index,
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
        )
