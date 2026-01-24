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
    score_sheets: list[ScoreSheet] = field(default_factory=list)  # 악보 목록 (다중 페이지 지원)
    slides_path: Optional[Path] = None  # slides.pptx 경로
    sheets_dir: Optional[Path] = None  # sheets/ 폴더 경로
    order: int = 0  # 예배 순서
    project_dir: Optional[Path] = None # 프로젝트 베이스 경로 (절대 경로 해결용)
    
    @property
    def score_sheet(self) -> ScoreSheet | None:
        """하위 호환성을 위한 첫 번째 시트 반환"""
        return self.score_sheets[0] if self.score_sheets else None
    
    # 런타임 정보 (로드 후 설정)
    _slide_count: int = field(default=0, init=False, repr=False)
    
    def __post_init__(self):
        """폴더 경로 기반으로 기본값 설정 (필드가 None인 경우)"""
        if self.folder:
            if self.slides_path is None:
                self.slides_path = self.folder / "slides.pptx"
            if self.sheets_dir is None:
                self.sheets_dir = self.folder / "sheets"

    def _resolve_abs(self, p: Path) -> Path:
        """project_dir을 기준으로 절대 경로 반환"""
        if p.is_absolute(): return p
        if self.project_dir: return (self.project_dir / p).resolve()
        return p.resolve()

    @property
    def abs_slides_path(self) -> Path:
        """슬라이드 파일의 절대 경로"""
        p = self.slides_path or (self.folder / "slides.pptx")
        return self._resolve_abs(p)

    @property
    def abs_sheets_dir(self) -> Path:
        """악보 폴더의 절대 경로"""
        p = self.sheets_dir or (self.folder / "sheets")
        # [기존 로직 유지] sheet vs sheets 감지
        sheets_plural = self._resolve_abs(p)
        sheet_singular = self._resolve_abs(self.folder / "sheet")
        if sheet_singular.exists() and not sheets_plural.exists():
            return sheet_singular
        return sheets_plural

    @property
    def has_slides(self) -> bool:
        """슬라이드 파일이 존재하는지 확인 (절대 경로 기준)"""
        return self.abs_slides_path.exists()
    
    @property
    def has_sheets(self) -> bool:
        """악보 폴더가 존재하는지 확인 (절대 경로 기준)"""
        return self.abs_sheets_dir.exists()

    def get_slide_count(self) -> int:
        """이 곡의 슬라이드 개수 반환"""
        return self._slide_count
    
    def set_slide_count(self, count: int):
        """슬라이드 개수 설정 (SlideManager가 PPT 로드 후 호출)"""
        self._slide_count = count

    def shift_indices(self, offset: int) -> None:
        """이 곡의 모든 시트의 모든 핫스팟 인덱스 이동"""
        for sheet in self.score_sheets:
            for h in sheet.hotspots:
                h.shift_indices(offset)
