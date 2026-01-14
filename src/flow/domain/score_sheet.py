"""ScoreSheet(악보) 도메인 모델

하나의 찬양곡을 나타내며, 악보 이미지와 핫스팟들을 포함함.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from flow.domain.hotspot import Hotspot


@dataclass
class ScoreSheet:
    """악보 (찬양곡)
    
    Attributes:
        name: 악보/곡 이름
        image_path: 악보 이미지 파일 경로
        hotspots: 핫스팟 목록
        id: 고유 식별자 (자동 생성)
    """
    
    name: str
    image_path: str = ""
    pptx_path: str = ""
    hotspots: list[Hotspot] = field(default_factory=list)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    def add_hotspot(self, hotspot: Hotspot, index: int | None = None) -> None:
        """핫스팟 추가 및 순서 재배치"""
        if index is None:
            # 맨 뒤에 추가
            hotspot.order = len(self.hotspots)
            self.hotspots.append(hotspot)
        else:
            # 특정 위치에 삽입 (기존 것들은 뒤로 밀림)
            hotspot.order = index
            for h in self.hotspots:
                if h.order >= index:
                    h.order += 1
            self.hotspots.append(hotspot)
        
    def remove_hotspot(self, hotspot_id: str) -> bool:
        """핫스팟 제거 및 순서 재배치"""
        removed_order = -1
        target_idx = -1
        for i, h in enumerate(self.hotspots):
            if h.id == hotspot_id:
                removed_order = h.order
                target_idx = i
                break
        
        if target_idx != -1:
            self.hotspots.pop(target_idx)
            # 순서 재정렬 (빈자리 채우기)
            for h in self.hotspots:
                if h.order > removed_order:
                    h.order -= 1
            return True
        return False
    
    def find_hotspot_by_id(self, hotspot_id: str) -> Hotspot | None:
        """ID로 핫스팟 찾기"""
        for h in self.hotspots:
            if h.id == hotspot_id:
                return h
        return None
    
    def get_ordered_hotspots(self) -> list[Hotspot]:
        """순서대로 정렬된 핫스팟 목록 반환"""
        return sorted(self.hotspots, key=lambda h: h.order)
    
    def get_next_hotspot(self, current_id: str) -> Hotspot | None:
        """다음 핫스팟 반환"""
        ordered = self.get_ordered_hotspots()
        for i, h in enumerate(ordered):
            if h.id == current_id and i + 1 < len(ordered):
                return ordered[i + 1]
        return None
    
    def get_previous_hotspot(self, current_id: str) -> Hotspot | None:
        """이전 핫스팟 반환"""
        ordered = self.get_ordered_hotspots()
        for i, h in enumerate(ordered):
            if h.id == current_id and i > 0:
                return ordered[i - 1]
        return None
    
    def to_dict(self) -> dict[str, Any]:
        """딕셔너리로 변환 (JSON 직렬화용)"""
        return {
            "id": self.id,
            "name": self.name,
            "image_path": self.image_path,
            "pptx_path": self.pptx_path,
            "hotspots": [h.to_dict() for h in self.hotspots],
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ScoreSheet:
        """딕셔너리에서 생성 (JSON 역직렬화용)"""
        hotspots = [Hotspot.from_dict(h) for h in data.get("hotspots", [])]
        return cls(
            id=data["id"],
            name=data["name"],
            image_path=data.get("image_path", ""),
            pptx_path=data.get("pptx_path", ""),
            hotspots=hotspots,
        )
