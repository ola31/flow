import json
from pathlib import Path
import os

class ConfigService:
    """애플리케이션 설정 관리 (최근 프로젝트 등)"""
    
    def __init__(self):
        self._config_dir = Path.home() / ".flow"
        self._config_file = self._config_dir / "config.json"
        self._config = {
            "recent_projects": []
        }
        self.load()

    def load(self):
        """설정 파일 로드"""
        if self._config_file.exists():
            try:
                with open(self._config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._config.update(data)
            except Exception as e:
                print(f"[Config] 설정 로드 실패: {e}")

    def save(self):
        """설정 파일 저장"""
        self._config_dir.mkdir(parents=True, exist_ok=True)
        try:
            with open(self._config_file, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"[Config] 설정 저장 실패: {e}")

    def get_recent_projects(self) -> list[str]:
        """최근 프로젝트 경로 목록 반환 (존재하는 파일만)"""
        recent = self._config.get("recent_projects", [])
        # 실제로 존재하는 파일만 필터링
        valid_recent = [p for p in recent if Path(p).exists()]
        if len(valid_recent) != len(recent):
            self._config["recent_projects"] = valid_recent
            self.save()
        return valid_recent

    def add_recent_project(self, path: str):
        """최근 프로젝트 목록에 추가"""
        path = str(Path(path).resolve())
        recent = self._config.get("recent_projects", [])
        if path in recent:
            recent.remove(path)
        recent.insert(0, path)
        # 최대 10개까지 유지
        self._config["recent_projects"] = recent[:10]
        self.save()

    def remove_recent_project(self, path: str):
        """최근 프로젝트 목록에서 제거"""
        recent = self._config.get("recent_projects", [])
        if path in recent:
            recent.remove(path)
            self.save()
