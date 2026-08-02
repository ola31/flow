"""Workspace 도메인 모델

Flow 워크스페이스: library/(공용 곡)와 projects/(셋리스트) 폴더를 갖는
루트 컨테이너. 위치는 자유, PC당 여러 개 존재 가능.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

# 루트를 표시하는 마커 파일. 이게 있으면 어느 하위 폴더에서 시작하든 위로
# 거슬러 올라가 워크스페이스를 찾을 수 있다 (.git·.idea·.obsidian과 같은 방식).
# 없이 구조(library/ + projects/)만 보면 사용자가 library/를 골랐을 때
# 그것이 워크스페이스 안인지 밖인지 구분할 수 없다.
MARKER_NAME = ".flow-workspace"

# 마커까지 거슬러 올라갈 최대 깊이 — 무한 루프 방지용 상한
_MAX_WALK_UP = 32


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

    @property
    def marker_path(self) -> Path:
        """워크스페이스 루트임을 표시하는 파일 경로"""
        return self.root / MARKER_NAME

    def is_valid(self) -> bool:
        """유효한 워크스페이스인지 확인 (library/, projects/ 존재)

        마커 파일은 요구하지 않는다 — 마커 도입 이전에 만든 워크스페이스도
        그대로 열려야 한다. 마커는 '루트 찾기'를 위한 것이지 유효성 조건이
        아니다.
        """
        return (
            self.root.exists()
            and self.library_dir.exists()
            and self.projects_dir.exists()
        )

    def write_marker(self) -> None:
        """마커 파일을 만든다 (이미 있으면 그대로 둔다).

        내용은 최소한으로 — 지금은 형식 버전만 담는다. 나중에 워크스페이스
        이름 같은 설정을 여기에 얹을 수 있다.
        """
        if self.marker_path.exists():
            return
        try:
            self.marker_path.write_text(
                json.dumps({"version": 1}, indent=2) + "\n", encoding="utf-8"
            )
        except OSError:
            pass  # 읽기 전용 매체 등 — 마커가 없어도 구조 판정으로 동작한다

    @classmethod
    def find_root(cls, start: Path | str) -> Path | None:
        """주어진 경로에서 위로 올라가며 워크스페이스 루트를 찾는다.

        곡 폴더나 library/를 골라도 워크스페이스를 찾아내기 위한 것.
        마커가 있으면 그것을 우선하고, 없으면 구조(library/ + projects/)로
        판정해 마커 이전 워크스페이스도 인식한다.

        Returns:
            찾은 루트 경로, 없으면 None
        """
        path = Path(start).resolve()
        for _ in range(_MAX_WALK_UP):
            if (path / MARKER_NAME).exists() and cls(root=path).is_valid():
                return path
            if cls(root=path).is_valid():
                return path
            if path.parent == path:
                break
            path = path.parent
        return None

    def library_song_dir(self, song_name: str) -> Path:
        """library 내의 특정 곡 폴더 경로"""
        return self.library_dir / song_name

    def project_dir(self, project_name: str) -> Path:
        """projects 내의 특정 프로젝트 폴더 경로"""
        return self.projects_dir / project_name

    @classmethod
    def create(cls, root: Path | str) -> Workspace:
        """새 워크스페이스 초기화 (library/, projects/ 폴더 + 마커 생성)"""
        root = Path(root).resolve()
        ws = cls(root=root)
        ws.library_dir.mkdir(parents=True, exist_ok=True)
        ws.projects_dir.mkdir(parents=True, exist_ok=True)
        ws.write_marker()
        return ws

    @classmethod
    def open(cls, root: Path | str) -> Workspace:
        """기존 워크스페이스 열기 (유효성 검사)

        마커가 없는 예전 워크스페이스는 여는 김에 마커를 남긴다 — 다음부터는
        하위 폴더를 골라도 루트를 찾을 수 있다.
        """
        root = Path(root).resolve()
        ws = cls(root=root)
        if not ws.is_valid():
            raise ValueError(
                f"유효한 워크스페이스가 아닙니다 (library/ 또는 projects/ 없음): {root}"
            )
        ws.write_marker()
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
