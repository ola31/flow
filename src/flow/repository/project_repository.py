"""프로젝트 저장소 (Repository)

프로젝트 데이터의 JSON 파일 저장/로드 담당.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from flow.domain.project import Project


class ProjectRepository:
    """프로젝트 저장소
    
    프로젝트를 JSON 파일로 저장하고 로드합니다.
    
    Attributes:
        base_path: 프로젝트 파일을 저장할 기본 디렉토리
    """
    
    def __init__(self, base_path: Path | str) -> None:
        self.base_path = Path(base_path)
    
    def save(self, project: Project, file_path: Path | str | None = None) -> Path:
        """프로젝트 저장 (상대 경로 변환 포함)"""
        if file_path:
            file_path = Path(file_path).resolve()
            file_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            self.base_path.mkdir(parents=True, exist_ok=True)
            file_path = (self.base_path / f"{project.id}.json").resolve()
        
        project_dir = file_path.parent
        
        # 딕셔너리 변환 시 경로들을 상대 경로로 시도
        data = project.to_dict()
        
        # PPT 경로 처리
        if data.get("pptx_path"):
            data["pptx_path"] = self._try_make_relative(data["pptx_path"], project_dir)
            
        # 각 악보 이미지 경로 처리
        for sheet_data in data.get("score_sheets", []):
            if sheet_data.get("image_path"):
                sheet_data["image_path"] = self._try_make_relative(sheet_data["image_path"], project_dir)
        
        with open(file_path, "w", encoding="utf-8-sig") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return file_path
    
    def _try_make_relative(self, path_str: str, base_dir: Path) -> str:
        """경로를 기준 디렉토리에 대한 상대 경로로 변환 시도"""
        try:
            p = Path(path_str).resolve()
            if base_dir in p.parents or p.parent == base_dir:
                return str(p.relative_to(base_dir))
        except Exception:
            pass
        return path_str

    def load(self, file_path: Path | str) -> Project:
        """프로젝트 로드 (경로 복구 로직 포함)"""
        file_path = Path(file_path).resolve()
        project_dir = file_path.parent
        
        with open(file_path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
            
        # 1. 딕셔너리 데이터의 상대 경로들을 절대 경로로 복구
        if data.get("pptx_path"):
            data["pptx_path"] = self._resolve_path(data["pptx_path"], project_dir)
            
        for sheet_data in data.get("score_sheets", []):
            if sheet_data.get("image_path"):
                sheet_data["image_path"] = self._resolve_path(sheet_data["image_path"], project_dir)
        
        return Project.from_dict(data)

    def _resolve_path(self, path_str: str, project_dir: Path) -> str:
        """상대 경로를 절대 경로로 복구하고, 파일이 없으면 주변 검색 시도"""
        p = Path(path_str)
        
        # 이미 절대 경로로 존재하면 그대로 유지
        if p.is_absolute() and p.exists():
            return str(p)
            
        # 1. 상대 경로인 경우 프로젝트 폴더 기반 확인
        abs_p = (project_dir / p).resolve()
        if abs_p.exists():
            return str(abs_p)
            
        # 2. 파일이 이동된 경우: 프로젝트 폴더 내에서 파일명만으로 검색 (Fallback)
        filename = p.name
        fallback_p = project_dir / filename
        if fallback_p.exists():
            return str(fallback_p)
            
        # 3. 그래도 없으면 원래 경로 반환 (UI에서 '찾을 수 없음' 표시용)
        return str(p)
    
    def list_projects(self) -> list[Path]:
        """저장된 프로젝트 파일 목록 반환"""
        if not self.base_path.exists():
            return []
        
        return list(self.base_path.glob("*.json"))
    
    def delete(self, file_path: Path | str) -> bool:
        """프로젝트 파일 삭제
        
        Returns:
            삭제 성공 여부
        """
        file_path = Path(file_path)
        
        if file_path.exists():
            file_path.unlink()
            return True
        return False
