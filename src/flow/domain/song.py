"""곡(Song) 도메인 모델"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .score_sheet import ScoreSheet


@dataclass
class Song:
    """
    곡 정보를 담는 도메인 모델
    
    각 곡은 독립적인 폴더를 가지며, 슬라이드(PPT)와 악보(Sheet)를 포함합니다.
    """
    name: str  # 곡 이름 (예: "주님의_기쁨")
    folder: Path  # 곡 폴더 경로 (예: songs/주님의_기쁨)
    score_sheet: ScoreSheet  # 악보 + 핫스팟 매핑
    slides_path: Optional[Path] = None  # slides.pptx 경로
    sheets_dir: Optional[Path] = None  # sheets/ 폴더 경로
    order: int = 0  # 예배 순서
    
    # 런타임 정보 (로드 후 설정)
    _slide_count: int = field(default=0, init=False, repr=False)
    
    def __post_init__(self):
        """폴더 경로 기반으로 기본값 설정"""
        if self.slides_path is None and self.folder:
            self.slides_path = self.folder / "slides.pptx"
        
        if self.sheets_dir is None and self.folder:
            self.sheets_dir = self.folder / "sheets"
    
    def get_slide_count(self) -> int:
        """이 곡의 슬라이드 개수 반환"""
        return self._slide_count
    
    def set_slide_count(self, count: int):
        """슬라이드 개수 설정 (SlideManager가 PPT 로드 후 호출)"""
        self._slide_count = count
    
    @property
    def has_slides(self) -> bool:
        """슬라이드 파일이 존재하는지 확인"""
        return self.slides_path and self.slides_path.exists()
    
    @property
    def has_sheets(self) -> bool:
        """악보 폴더가 존재하는지 확인"""
        return self.sheets_dir and self.sheets_dir.exists()

    def shift_indices(self, offset: int) -> None:
        """이 곡의 모든 핫스팟 인덱스 이동"""
        if self.score_sheet:
            for h in self.score_sheet.hotspots:
                h.shift_indices(offset)
