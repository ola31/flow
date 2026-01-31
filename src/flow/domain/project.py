"""Project(프로젝트) 도메인 모델

여러 시트를 관리하는 프로젝트 루트 엔티티.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

from flow.domain.score_sheet import ScoreSheet

if TYPE_CHECKING:
    from flow.domain.song import Song


@dataclass
class Project:
    """프로젝트 (예배 세션)

    Attributes:
        name: 프로젝트 이름
        score_sheets: 시트 목록 (레거시, 하위 호환용)
        selected_songs: 선택된 곡 목록 (새 구조)
        current_sheet_index: 현재 선택된 시트 인덱스
        id: 고유 식별자 (자동 생성)
    """

    name: str
    pptx_path: str = ""
    score_sheets: list[ScoreSheet] = field(default_factory=list)
    selected_songs: list["Song"] = field(default_factory=list)  # 새 구조
    song_order: list[str] = field(default_factory=list)  # 모든 곡의 순서 (이름 목록)
    current_sheet_index: int = 0
    current_verse_index: int = 0  # 0=1절, 1=2절, 2=3절, 3=4절, 4=5절, 5=후렴
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    @property
    def all_score_sheets(self) -> list[ScoreSheet]:
        """모든 시트 목록 (이미지가 있는 유효한 시트만 반환)"""
        # [주의] image_path가 존재하고 비어있지 않은 것만 유효 시트로 간주
        if self.selected_songs:
            all_sheets = []
            for song in self.selected_songs:
                all_sheets.extend(
                    [
                        s
                        for s in song.score_sheets
                        if s.image_path and str(s.image_path).strip()
                    ]
                )
            return all_sheets
        return [
            s for s in self.score_sheets if s.image_path and str(s.image_path).strip()
        ]

    def add_score_sheet(self, sheet: ScoreSheet) -> None:
        """시트 추가"""
        if self.selected_songs:
            # 새 구조에서는 곡을 추가해야 함 (여기서는 하위 호환을 위해 유지)
            pass
        self.score_sheets.append(sheet)

    def remove_score_sheet(self, sheet_id: str) -> bool:
        """시트 제거 (곡 내부 시트 목록에서 제거)"""
        if self.selected_songs:
            for song in self.selected_songs:
                for i, s in enumerate(song.score_sheets):
                    if s.id == sheet_id:
                        song.score_sheets.pop(i)
                        # 곡 자체가 통째로 삭제되는 것은 별도 로직(SongListWidget)에서 처리
                        return True
        else:
            for i, s in enumerate(self.score_sheets):
                if s.id == sheet_id:
                    self.score_sheets.pop(i)
                    return True
        return False

    def find_score_sheet_by_id(self, sheet_id: str) -> ScoreSheet | None:
        """ID로 시트 찾기"""
        for s in self.all_score_sheets:
            if s.id == sheet_id:
                return s
        return None

    def move_score_sheet(self, sheet_id: str, new_index: int) -> bool:
        """시트 순서 변경 (프로젝트 전체 순서 기준)"""
        # [주의] 다중 곡/다중 시트 구조에서 '전체 인덱스' 이동은 복잡하므로
        # 여기서는 레거시 구조 대응만 유지하거나, 곡별 이동으로 제한하는 것이 안전함.
        # 현재는 SongListWidget에서 곡 단위 이동을 처리함.
        if not self.selected_songs:
            sheets = self.score_sheets
            for i, s in enumerate(sheets):
                if s.id == sheet_id:
                    item = self.score_sheets.pop(i)
                    new_index = max(0, min(new_index, len(self.score_sheets)))
                    self.score_sheets.insert(new_index, item)
                    return True
        return False

    def ensure_unique_ids(self) -> bool:
        """모든 시트와 핫스팟의 ID 중복을 체크하고 필요시 재생성 (복사된 폴더 대응)"""
        seen_ids = set()
        changed = False

        for song in self.selected_songs:
            for sheet in song.score_sheets:
                # 1. 시트 ID 체크
                if sheet.id in seen_ids:
                    sheet.id = str(uuid.uuid4())
                    changed = True
                seen_ids.add(sheet.id)

                # 2. 핫스팟 ID 체크
                for hotspot in sheet.hotspots:
                    if hotspot.id in seen_ids:
                        hotspot.id = str(uuid.uuid4())
                        changed = True
                    seen_ids.add(hotspot.id)

        return changed

    def get_current_score_sheet(self) -> ScoreSheet | None:
        """현재 시트 반환"""
        sheets = self.all_score_sheets
        if 0 <= self.current_sheet_index < len(sheets):
            return sheets[self.current_sheet_index]
        return None

    def next_score_sheet(self) -> bool:
        """다음 시트로 이동"""
        if self.current_sheet_index + 1 < len(self.all_score_sheets):
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
            "song_order": self.song_order,
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
            song_order=data.get("song_order", []),
            current_sheet_index=data.get("current_sheet_index", 0),
            current_verse_index=data.get("current_verse_index", 0),
        )
