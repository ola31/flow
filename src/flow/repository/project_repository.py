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
    
    def save(self, project: Project) -> Path:
        """프로젝트를 JSON 파일로 저장
        
        Args:
            project: 저장할 프로젝트
            
        Returns:
            저장된 파일 경로
        """
        # 디렉토리 생성
        self.base_path.mkdir(parents=True, exist_ok=True)
        
        # 파일 경로 생성 (프로젝트 ID 사용)
        file_path = self.base_path / f"{project.id}.json"
        
        # JSON 저장
        data = project.to_dict()
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return file_path
    
    def load(self, file_path: Path | str) -> Project:
        """JSON 파일에서 프로젝트 로드
        
        Args:
            file_path: 로드할 파일 경로
            
        Returns:
            로드된 프로젝트
            
        Raises:
            FileNotFoundError: 파일이 없을 경우
            json.JSONDecodeError: JSON 파싱 에러
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"Project file not found: {file_path}")
        
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        return Project.from_dict(data)
    
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
