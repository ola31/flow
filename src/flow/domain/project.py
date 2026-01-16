"""Project(프로젝트) 도메인 모델

여러 시트를 관리하는 프로젝트 루트 엔티티.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from flow.domain.score_sheet import ScoreSheet


@dataclass
class Project:
    """프로젝트 (예배 세션)
    
    Attributes:
        name: 프로젝트 이름
        score_sheets: 시트 목록
        current_sheet_index: 현재 선택된 시트 인덱스
        id: 고유 식별자 (자동 생성)
    """
    
    name: str
    pptx_path: str = ""
    score_sheets: list[ScoreSheet] = field(default_factory=list)
    current_sheet_index: int = 0
    current_verse_index: int = 0 # 0=1절, 1=2절, 2=3절, 3=4절, 4=5절, 5=후렴
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    def add_score_sheet(self, sheet: ScoreSheet) -> None:
        """시트 추가"""
        self.score_sheets.append(sheet)
    
    def remove_score_sheet(self, sheet_id: str) -> bool:
        """시트 제거"""
        for i, s in enumerate(self.score_sheets):
            if s.id == sheet_id:
                self.score_sheets.pop(i)
                # 현재 인덱스 조정
                if self.current_sheet_index >= len(self.score_sheets):
                    self.current_sheet_index = max(0, len(self.score_sheets) - 1)
                return True
        return False
    
    def find_score_sheet_by_id(self, sheet_id: str) -> ScoreSheet | None:
        """ID로 시트 찾기"""
        for s in self.score_sheets:
            if s.id == sheet_id:
                return s
        return None
    
    def move_score_sheet(self, sheet_id: str, new_index: int) -> bool:
        """시트 순서 변경"""
        for i, s in enumerate(self.score_sheets):
            if s.id == sheet_id:
                sheet = self.score_sheets.pop(i)
                new_index = max(0, min(new_index, len(self.score_sheets)))
                self.score_sheets.insert(new_index, sheet)
                return True
        return False
    
    def get_current_score_sheet(self) -> ScoreSheet | None:
        """현재 시트 반환"""
        if 0 <= self.current_sheet_index < len(self.score_sheets):
            return self.score_sheets[self.current_sheet_index]
        return None
    
    def next_score_sheet(self) -> bool:
        """다음 시트로 이동"""
        if self.current_sheet_index + 1 < len(self.score_sheets):
            self.current_sheet_index += 1
            return True
        return False
    
    def previous_score_sheet(self) -> bool:
        """이전 시트로 이동"""
        if self.current_sheet_index > 0:
            self.current_sheet_index -= 1
            return True
        return False
    
    def to_dict(self) -> dict[str, Any]:
        """딕셔너리로 변환 (JSON 직렬화용)"""
        return {
            "id": self.id,
            "name": self.name,
            "pptx_path": self.pptx_path,
            "current_sheet_index": self.current_sheet_index,
            "current_verse_index": self.current_verse_index,
            "score_sheets": [s.to_dict() for s in self.score_sheets],
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Project:
        """딕셔너리에서 생성 (JSON 역직렬화용)"""
        score_sheets = [ScoreSheet.from_dict(s) for s in data.get("score_sheets", [])]
        return cls(
            id=data["id"],
            name=data["name"],
            pptx_path=data.get("pptx_path", ""),
            score_sheets=score_sheets,
            current_sheet_index=data.get("current_sheet_index", 0),
            current_verse_index=data.get("current_verse_index", 0),
        )
