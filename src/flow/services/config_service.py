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
        """최근 프로젝트 경로 목록 반환 (존재하는 파일만 표시하지만 목록에서 강제 삭제는 자제)"""
        self.load() # 최신 상태 로드
        recent = self._config.get("recent_projects", [])
        # 노출할 때는 존재하는 것만 리턴하되, 원본 데이터(self._config)는 보존하여 
        # 일시적인 네트워크 드라이브 단절 등으로 인한 데이터 유실 방지
        valid_recent = [p for p in recent if Path(p).exists()]
        return valid_recent

    def add_recent_project(self, path: str):
        """최근 프로젝트 목록에 추가"""
        if not path:
            return
            
        # 1. 먼저 문자열 수준에서 정규화 (백슬래시 -> 슬래시)
        # 윈도우에서 복사한 경로가 리눅스 환경으로 넘어왔을 때를 대비
        clean_path = str(path).replace("\\", "/")
        
        # 2. 절대 경로화 및 표준 포맷(POSIX) 변환
        try:
            path_obj = Path(clean_path).resolve()
            path_str = path_obj.as_posix()
        except Exception:
            path_str = clean_path
            path_obj = Path(path_str)
            
        # 3. 파일이 실제로 존재할 때만 추가
        if not path_obj.exists():
            return

        self.load() # 다른 인스턴스에서 추가했을 수 있으므로 먼저 로드
        recent = self._config.get("recent_projects", [])
        
        # 중복 제거 (대소문자 구분 없이 체크하여 윈도우/리눅스 포괄 대응)
        cleaned_recent = [p for p in recent if p.lower() != path_str.lower()]
        
        # 목록 맨 앞에 추가
        cleaned_recent.insert(0, path_str)
        
        # 최대 10개까지 유지 및 저장
        self._config["recent_projects"] = cleaned_recent[:10]
        self.save()

    def remove_recent_project(self, path: str):
        """최근 프로젝트 목록에서 제거"""
        self.load()
        recent = self._config.get("recent_projects", [])
        
        # 대소문자 구분 없이 제거
        new_recent = [p for p in recent if p.lower() != path.lower()]
        
        if len(new_recent) != len(recent):
            self._config["recent_projects"] = new_recent
            self.save()
