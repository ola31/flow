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
        """프로젝트 저장 (새 구조 및 레거시 구조 모두 지원)"""
        if file_path:
            file_path = Path(file_path).resolve()
            file_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            self.base_path.mkdir(parents=True, exist_ok=True)
            file_path = (self.base_path / f"{project.id}.json").resolve()

        project_dir = file_path.parent

        # 새 구조 감지: selected_songs가 있으면 새 구조로 저장
        if project.selected_songs:
            self._save_new_structure(project, file_path, project_dir)
        else:
            # 레거시 구조로 저장
            self._save_legacy_structure(project, file_path, project_dir)

        return file_path

    def _save_new_structure(
        self, project: Project, file_path: Path, project_dir: Path
    ) -> None:
        """새 구조로 저장 (곡별 폴더)"""
        songs_dir = project_dir / "songs"
        songs_dir.mkdir(exist_ok=True)

        # 1. 각 곡별 song.json 저장
        selected_songs_data = []
        for song in project.selected_songs:
            song_dir = project_dir / song.folder
            song_dir.mkdir(parents=True, exist_ok=True)

            # song.json 저장 (다중 시트 지원)
            song_data = {
                "name": song.name,
                "sheets": [s.to_dict() for s in song.score_sheets],
            }

            song_json_path = song_dir / "song.json"
            with open(song_json_path, "w", encoding="utf-8-sig") as f:
                json.dump(song_data, f, ensure_ascii=False, indent=2)

            # project.json에 저장할 곡 정보
            selected_songs_data.append(
                {"name": song.name, "order": song.order, "folder": str(song.folder)}
            )

        # 2. project.json 저장
        project_data = {
            "id": project.id,
            "name": project.name,
            "selected_songs": selected_songs_data,
            "song_order": project.song_order,
            "current_sheet_index": project.current_sheet_index,
            "current_verse_index": project.current_verse_index,
        }

        with open(file_path, "w", encoding="utf-8-sig") as f:
            json.dump(project_data, f, ensure_ascii=False, indent=2)

    def _save_legacy_structure(
        self, project: Project, file_path: Path, project_dir: Path
    ) -> None:
        """레거시 구조로 저장 (단일 JSON)"""
        data = project.to_dict()

        # PPT 경로 처리
        if data.get("pptx_path"):
            data["pptx_path"] = self._try_make_relative(data["pptx_path"], project_dir)

        # 각 악보 이미지 경로 처리
        for sheet_data in data.get("score_sheets", []):
            if sheet_data.get("image_path"):
                sheet_data["image_path"] = self._try_make_relative(
                    sheet_data["image_path"], project_dir
                )

        with open(file_path, "w", encoding="utf-8-sig") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

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
        """프로젝트 로드 (새 구조 및 레거시 구조 자동 감지)"""
        file_path = Path(file_path).resolve()
        project_dir = file_path.parent

        with open(file_path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)

        # 새 구조 감지: selected_songs 필드 존재 여부
        if "selected_songs" in data:
            return self._load_new_structure(data, project_dir)
        else:
            return self._load_legacy_structure(data, project_dir)

    def _load_new_structure(self, data: dict[str, Any], project_dir: Path) -> Project:
        """새 구조 로드 (곡별 폴더)"""
        from flow.domain.song import Song
        from flow.domain.score_sheet import ScoreSheet

        # 1. 각 곡 로드
        selected_songs = []
        for song_info in data.get("selected_songs", []):
            song_folder = project_dir / song_info["folder"]
            song_json_path = song_folder / "song.json"

            if not song_json_path.exists():
                print(f"⚠️  곡 파일 없음: {song_json_path}")
                continue

            # song.json 로드
            with open(song_json_path, "r", encoding="utf-8-sig") as f:
                song_data = json.load(f)

            # ScoreSheet 목록 복원 (다중 시트 호환)
            score_sheets = []
            if "sheets" in song_data:
                score_sheets = [ScoreSheet.from_dict(s) for s in song_data["sheets"]]
            elif "sheet" in song_data and song_data["sheet"]:
                # 레거시 단일 시트 호환
                score_sheets = [ScoreSheet.from_dict(song_data["sheet"])]

            # Song 객체 생성 (프로젝트 경로 포함)
            song = Song(
                name=song_info["name"],
                folder=Path(song_info["folder"]),
                score_sheets=score_sheets,
                order=song_info.get("order", 0),
                project_dir=project_dir,
            )
            selected_songs.append(song)

        # 2. Project 객체 생성
        project = Project(
            id=data["id"],
            name=data["name"],
            selected_songs=selected_songs,
            song_order=data.get("song_order", []),
            current_sheet_index=data.get("current_sheet_index", 0),
            current_verse_index=data.get("current_verse_index", 0),
        )

        return project

    def _load_legacy_structure(
        self, data: dict[str, Any], project_dir: Path
    ) -> Project:
        """레거시 구조 로드 (단일 JSON)"""
        # 상대 경로들을 절대 경로로 복구
        if data.get("pptx_path"):
            data["pptx_path"] = self._resolve_path(data["pptx_path"], project_dir)

        for sheet_data in data.get("score_sheets", []):
            if sheet_data.get("image_path"):
                sheet_data["image_path"] = self._resolve_path(
                    sheet_data["image_path"], project_dir
                )

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

        # [NEW] 3. sheet <-> sheets 폴더명 불일치 및 서브폴더 검색 강화
        filename = p.name
        # 3.1 명시적인 폴더명 교체 시도
        alt_path_str = path_str
        if "sheets/" in alt_path_str:
            alt_path_str = alt_path_str.replace("sheets/", "sheet/")
        elif "sheet/" in alt_path_str:
            alt_path_str = alt_path_str.replace("sheet/", "sheets/")

        if alt_path_str != path_str:
            alt_abs_p = (project_dir / Path(alt_path_str)).resolve()
            if alt_abs_p.exists():
                return str(alt_abs_p)

        # 3.2 서브폴더(sheet, sheets) 직접 확인
        for sub in ["sheet", "sheets"]:
            sub_p = (project_dir / sub / filename).resolve()
            if sub_p.exists():
                return str(sub_p)

        # 4. 그래도 없으면 원래 경로 반환 (UI에서 '찾을 수 없음' 표시용)
        return str(p)

    def load_standalone_song(self, song_dir: Path | str) -> Project:
        """단일 곡 폴더를 가상 프로젝트로 로드"""
        song_dir = Path(song_dir).resolve()
        song_json_path = song_dir / "song.json"

        if not song_json_path.exists():
            raise FileNotFoundError(f"song.json이 없습니다: {song_dir}")

        # 1. song.json 로드
        with open(song_json_path, "r", encoding="utf-8-sig") as f:
            song_data = json.load(f)

        from flow.domain.song import Song
        from flow.domain.score_sheet import ScoreSheet

        # ScoreSheet 목록 복원
        score_sheets = []
        if "sheets" in song_data:
            score_sheets = [ScoreSheet.from_dict(s) for s in song_data["sheets"]]
        elif "sheet" in song_data and song_data["sheet"]:
            score_sheets = [ScoreSheet.from_dict(song_data["sheet"])]

        if not score_sheets:
            score_sheets.append(ScoreSheet(name=song_data.get("name", song_dir.name)))

        # 2. Song 객체 생성
        # 단독 편집이므로 곡 폴더 자체를 기준으로 상대 경로 설정
        song = Song(
            name=song_data.get("name", song_dir.name),
            folder=Path("."),  # 현재 폴더가 곡 폴더임
            score_sheets=score_sheets,
            project_dir=song_dir,
        )

        # 3. 가상 Project 객체 생성
        project = Project(
            name=f"[곡 편집] {song.name}", selected_songs=[song], current_sheet_index=0
        )

        return project

    def save_standalone_song(self, project: Project) -> None:
        """가상 프로젝트에서 단일 곡 정보만 해당 폴더에 저장"""
        if not project.selected_songs:
            return

        song = project.selected_songs[0]
        # Song.project_dir이 실제 곡 폴더 경로임 (load_standalone_song 참고)
        song_dir = song.project_dir
        song_json_path = song_dir / "song.json"

        song_data = {
            "name": song.name,
            "sheets": [s.to_dict() for s in song.score_sheets],
        }

        with open(song_json_path, "w", encoding="utf-8-sig") as f:
            json.dump(song_data, f, ensure_ascii=False, indent=2)

    def create_standalone_song(self, song_dir: Path | str, name: str) -> Project:
        """새로운 곡 폴더 및 기본 song.json 생성"""
        song_dir = Path(song_dir).resolve()
        if song_dir.exists():
            raise FileExistsError(f"폴더가 이미 존재합니다: {song_dir}")

        song_dir.mkdir(parents=True)

        from flow.domain.score_sheet import ScoreSheet

        initial_sheet = ScoreSheet(name=name)

        song_data = {"name": name, "sheets": [initial_sheet.to_dict()]}

        song_json_path = song_dir / "song.json"
        with open(song_json_path, "w", encoding="utf-8-sig") as f:
            json.dump(song_data, f, ensure_ascii=False, indent=2)

        return self.load_standalone_song(song_dir)

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
