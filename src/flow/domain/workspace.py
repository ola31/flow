"""Workspace 도메인 모델

Flow 워크스페이스: library/(공용 곡)와 projects/(셋리스트) 폴더를 갖는
루트 컨테이너. 위치는 자유, PC당 여러 개 존재 가능.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Workspace:
    """Flow 워크스페이스

    Attributes:
        root: 워크스페이스 루트 폴더 (library/, projects/ 포함)
    """

    root: Path

    @property
    def library_dir(self) -> Path:
        """공용 곡 라이브러리 경로"""
        return self.root / "library"

    @property
    def projects_dir(self) -> Path:
        """프로젝트 폴더들의 부모 경로"""
        return self.root / "projects"

    @property
    def name(self) -> str:
        """워크스페이스 이름 (루트 폴더명)"""
        return self.root.name

    def is_valid(self) -> bool:
        """유효한 워크스페이스인지 확인 (library/, projects/ 존재)"""
        return (
            self.root.exists()
            and self.library_dir.exists()
            and self.projects_dir.exists()
        )

    def library_song_dir(self, song_name: str) -> Path:
        """library 내의 특정 곡 폴더 경로"""
        return self.library_dir / song_name

    def project_dir(self, project_name: str) -> Path:
        """projects 내의 특정 프로젝트 폴더 경로"""
        return self.projects_dir / project_name

    @classmethod
    def create(cls, root: Path | str) -> Workspace:
        """새 워크스페이스 초기화 (library/, projects/ 폴더 생성)"""
        root = Path(root).resolve()
        ws = cls(root=root)
        ws.library_dir.mkdir(parents=True, exist_ok=True)
        ws.projects_dir.mkdir(parents=True, exist_ok=True)
        return ws

    @classmethod
    def open(cls, root: Path | str) -> Workspace:
        """기존 워크스페이스 열기 (유효성 검사)"""
        root = Path(root).resolve()
        ws = cls(root=root)
        if not ws.is_valid():
            raise ValueError(
                f"유효한 워크스페이스가 아닙니다 (library/ 또는 projects/ 없음): {root}"
            )
        return ws

    def list_projects(self) -> list[Path]:
        """projects/ 안의 프로젝트 폴더 목록 (project.json 존재하는 것만)"""
        if not self.projects_dir.exists():
            return []
        return sorted(
            p for p in self.projects_dir.iterdir()
            if p.is_dir() and (p / "project.json").exists()
        )

    def list_library_songs(self) -> list[Path]:
        """library/ 안의 곡 폴더 목록 (song.json 존재하는 것만)"""
        if not self.library_dir.exists():
            return []
        return sorted(
            p for p in self.library_dir.iterdir()
            if p.is_dir() and (p / "song.json").exists()
        )

    def resolve_song_folder(self, project_name: str, song_name: str) -> Path | None:
        """곡 폴더 경로 해석 (local → library 우선순위)

        Returns:
            우선순위에 따라 찾은 곡 폴더 경로, 없으면 None
        """
        # 1. 로컬 오버라이드 (projects/{name}/songs/{song})
        local = self.project_dir(project_name) / "songs" / song_name
        if (local / "song.json").exists():
            return local

        # 2. 공용 라이브러리 (library/{song})
        lib = self.library_song_dir(song_name)
        if (lib / "song.json").exists():
            return lib

        return None
