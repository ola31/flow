"""곡(Song) 도메인 모델"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from .score_sheet import ScoreSheet

if TYPE_CHECKING:
    from .workspace import Workspace


def detect_slides_file(song_dir: Path) -> Optional[Path]:
    """곡 폴더의 슬라이드 pptx 경로를 감지.

    규약 이름(slides.pptx)이 우선. 없으면 폴더 안의 *.pptx가 정확히
    1개일 때 그것을 슬라이드로 인식한다 (2개 이상이면 모호 → None).
    파일 관리자로 임의 이름의 pptx를 넣어도 동작하게 하는 완화 규칙.
    """
    default = song_dir / "slides.pptx"
    if default.exists():
        return default
    try:
        candidates = [f for f in song_dir.glob("*.pptx") if f.is_file()]
    except OSError:
        return None
    return candidates[0] if len(candidates) == 1 else None


@dataclass
class Song:
    """
    곡 정보를 담는 도메인 모델

    각 곡은 독립적인 폴더를 가지며, 슬라이드(PPT)와 악보(Sheet)를 포함합니다.
    """
    name: str  # 곡 이름 (예: "my_song")
    folder: Path  # 곡 폴더 경로 (상대 또는 절대)
    score_sheets: list[ScoreSheet] = field(default_factory=list)  # 악보 목록 (다중 페이지 지원)
    slides_path: Optional[Path] = None  # slides.pptx 경로
    sheets_dir: Optional[Path] = None  # sheets/ 폴더 경로
    order: int = 0  # 셋리스트 순서
    project_dir: Optional[Path] = None  # 프로젝트 베이스 경로 (절대 경로 해결용)
    source: str = "local"  # "library" | "local" — 워크스페이스 구조에서 곡 출처
    show_sheet_names: bool = False  # 셋리스트 탭에 P1, P2… 대신 시트 이름 표시
    # 셋리스트 안의 구간 이름 (예: "오전"/"오후"). 빈 문자열이면 구간 없음.
    # 프로젝트 소유 정보라 project.json에만 저장한다 — 같은 라이브러리 곡이
    # 프로젝트마다 다른 구간에 들어갈 수 있으므로 song.json에 넣으면 안 된다.
    section: str = ""
    
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
    def abs_folder(self) -> Path:
        """곡 폴더의 절대 경로"""
        return self._resolve_abs(self.folder)

    @property
    def abs_slides_path(self) -> Path:
        """슬라이드 파일의 절대 경로.

        규약 경로(slides.pptx)가 없으면 곡 폴더의 유일한 *.pptx를 자동
        감지한다 (detect_slides_file 규칙).
        """
        p = self.slides_path or (self.folder / "slides.pptx")
        resolved = self._resolve_abs(p)
        if resolved.exists():
            return resolved
        detected = detect_slides_file(self.abs_folder)
        return detected if detected is not None else resolved

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

    @property
    def markdown_path(self) -> Path:
        """slides.md absolute path."""
        return self._resolve_abs(self.folder / "slides.md")

    @property
    def has_markdown(self) -> bool:
        return self.markdown_path.exists()

    @property
    def slide_source(self) -> str:
        """One of: 'markdown', 'pptx', 'none'. markdown wins if both exist."""
        if self.has_markdown:
            return "markdown"
        if self.has_slides:
            return "pptx"
        return "none"

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

    @classmethod
    def load_from_workspace(
        cls,
        workspace: "Workspace",
        project_name: str,
        song_name: str,
        order: int = 0,
    ) -> Optional["Song"]:
        """워크스페이스에서 곡을 해석해 로드 (local → library 우선순위)

        Args:
            workspace: 워크스페이스 인스턴스
            project_name: 프로젝트 이름 (로컬 오버라이드 탐색용)
            song_name: 곡 이름
            order: 프로젝트 내 순서

        Returns:
            로드된 Song 또는 None (어디에도 없으면)
        """
        import json

        folder = workspace.resolve_song_folder(project_name, song_name)
        if folder is None:
            return None

        # source 판별: local 경로인지 library 경로인지
        local_path = workspace.project_dir(project_name) / "songs" / song_name
        source = "local" if folder == local_path else "library"

        # song.json 로드
        song_json = folder / "song.json"
        if not song_json.exists():
            return None

        with open(song_json, "r", encoding="utf-8-sig") as f:
            data = json.load(f)

        # ScoreSheet 목록 복원 (다중/단일 시트 호환)
        score_sheets: list[ScoreSheet] = []
        if "sheets" in data:
            score_sheets = [ScoreSheet.from_dict(s) for s in data["sheets"]]
        elif data.get("sheet"):
            score_sheets = [ScoreSheet.from_dict(data["sheet"])]

        # 절대 경로로 생성 (project_dir 불필요).
        # name은 요청된 폴더명을 그대로 쓴다 — song.json의 name과 폴더명이
        # 다른 곡(외부에서 가져온 곡 등)도 라이브러리 목록·셋리스트 순서·
        # 재열기 해석이 전부 같은 이름으로 일관되게 동작해야 한다.
        return cls(
            name=song_name,
            folder=folder.resolve(),
            score_sheets=score_sheets,
            order=order,
            source=source,
            show_sheet_names=data.get("show_sheet_names", False),
        )
