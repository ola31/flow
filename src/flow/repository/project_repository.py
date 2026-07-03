"""프로젝트 저장소 (Repository)

프로젝트 데이터의 JSON 파일 저장/로드 담당.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, TYPE_CHECKING

from flow.domain.project import Project

if TYPE_CHECKING:
    from flow.domain.workspace import Workspace


class ProjectRepository:
    """프로젝트 저장소

    프로젝트를 JSON 파일로 저장하고 로드합니다.

    Attributes:
        base_path: 프로젝트 파일을 저장할 기본 디렉토리
    """

    def __init__(self, base_path: Path | str) -> None:
        self.base_path = Path(base_path)

    def save(self, project: Project, file_path: Path | str | None = None) -> Path:
        if file_path:
            file_path = Path(file_path).resolve()
            file_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            self.base_path.mkdir(parents=True, exist_ok=True)
            file_path = (self.base_path / f"{project.id}.json").resolve()

        project_dir = file_path.parent
        self._save_new_structure(project, file_path, project_dir)

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
                "show_sheet_names": song.show_sheet_names,
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

    def load(self, file_path: Path | str) -> Project:
        file_path = Path(file_path).resolve()
        project_dir = file_path.parent

        with open(file_path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)

        if "selected_songs" not in data:
            raise ValueError(
                f"지원하지 않는 프로젝트 형식입니다: {file_path}\n"
                "selected_songs 필드가 필요합니다."
            )

        return self._load_new_structure(data, project_dir)

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
                show_sheet_names=song_data.get("show_sheet_names", False),
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

    # ==== Workspace-aware methods ====

    def save_to_workspace(
        self,
        project: Project,
        workspace: "Workspace",
    ) -> Path:
        """워크스페이스 구조로 프로젝트 저장

        - project.json: workspace/projects/{name}/project.json
        - library 곡: library/{name}/song.json에 저장 (참조만)
        - local 곡: projects/{name}/songs/{song}/song.json에 저장

        Returns:
            저장된 project.json 경로
        """
        project_dir = workspace.project_dir(project.name)
        project_dir.mkdir(parents=True, exist_ok=True)
        file_path = project_dir / "project.json"

        selected_songs_data: list[dict[str, Any]] = []
        for song in project.selected_songs:
            source = getattr(song, "source", "local")

            if source == "library":
                # 라이브러리에 저장 (공용)
                target_dir = workspace.library_song_dir(song.name)
            else:
                # 로컬 오버라이드 (이 프로젝트 전용)
                target_dir = project_dir / "songs" / song.name

            target_dir.mkdir(parents=True, exist_ok=True)
            song_json = target_dir / "song.json"
            song_data = {
                "name": song.name,
                "sheets": [s.to_dict() for s in song.score_sheets],
                "show_sheet_names": song.show_sheet_names,
            }
            with open(song_json, "w", encoding="utf-8-sig") as f:
                json.dump(song_data, f, ensure_ascii=False, indent=2)

            selected_songs_data.append(
                {
                    "name": song.name,
                    "order": song.order,
                    "source": source,
                }
            )

        project_data = {
            "id": project.id,
            "name": project.name,
            "selected_songs": selected_songs_data,
            "song_order": project.song_order,
            "current_sheet_index": project.current_sheet_index,
            "current_verse_index": project.current_verse_index,
            "workspace_version": 1,
        }

        with open(file_path, "w", encoding="utf-8-sig") as f:
            json.dump(project_data, f, ensure_ascii=False, indent=2)

        return file_path

    def load_from_workspace(
        self,
        workspace: "Workspace",
        project_name: str,
    ) -> Project:
        """워크스페이스에서 프로젝트 로드 (local → library 우선순위)"""
        from flow.domain.song import Song

        file_path = workspace.project_dir(project_name) / "project.json"
        if not file_path.exists():
            raise FileNotFoundError(
                f"프로젝트 파일이 없습니다: {file_path}"
            )

        with open(file_path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)

        if "selected_songs" not in data:
            raise ValueError(
                f"지원하지 않는 프로젝트 형식입니다: {file_path}"
            )

        selected_songs = []
        for song_info in data.get("selected_songs", []):
            song_name = song_info["name"]
            order = song_info.get("order", 0)

            song = Song.load_from_workspace(
                workspace, project_name, song_name, order=order
            )
            if song is None:
                print(f"⚠️  곡을 찾을 수 없음: {song_name}")
                continue
            selected_songs.append(song)

        return Project(
            id=data["id"],
            name=data["name"],
            selected_songs=selected_songs,
            song_order=data.get("song_order", []),
            current_sheet_index=data.get("current_sheet_index", 0),
            current_verse_index=data.get("current_verse_index", 0),
        )

    def list_workspace_projects(self, workspace: "Workspace") -> list[str]:
        """워크스페이스의 프로젝트 이름 목록"""
        return [p.name for p in workspace.list_projects()]

    def delete_workspace_project(
        self, workspace: "Workspace", project_name: str
    ) -> bool:
        """워크스페이스에서 프로젝트 삭제 (폴더 전체 제거)"""
        project_dir = workspace.project_dir(project_name)
        if not project_dir.exists():
            return False
        shutil.rmtree(project_dir)
        return True

    def clone_workspace_project(
        self,
        workspace: "Workspace",
        source_name: str,
        new_name: str,
    ) -> Path:
        """워크스페이스 내 프로젝트 복제

        project.json과 로컬 songs/만 복사 (library 참조는 그대로 유지).

        Returns:
            복제된 project.json 경로
        """
        src_dir = workspace.project_dir(source_name)
        dst_dir = workspace.project_dir(new_name)

        if not src_dir.exists():
            raise FileNotFoundError(f"원본 프로젝트가 없습니다: {src_dir}")
        if dst_dir.exists():
            raise FileExistsError(f"이미 존재하는 이름입니다: {dst_dir}")

        shutil.copytree(src_dir, dst_dir)

        # project.json의 이름과 id 업데이트
        import uuid
        dst_file = dst_dir / "project.json"
        with open(dst_file, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        data["id"] = str(uuid.uuid4())
        data["name"] = new_name
        with open(dst_file, "w", encoding="utf-8-sig") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return dst_file

    # ==== Legacy methods ====

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
            show_sheet_names=song_data.get("show_sheet_names", False),
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
            "show_sheet_names": song.show_sheet_names,
        }

        with open(song_json_path, "w", encoding="utf-8-sig") as f:
            json.dump(song_data, f, ensure_ascii=False, indent=2)

    def init_song_folder(self, song_dir: Path | str, name: str) -> None:
        song_dir = Path(song_dir).resolve()
        if song_dir.exists():
            raise FileExistsError(f"폴더가 이미 존재합니다: {song_dir}")

        song_dir.mkdir(parents=True)
        (song_dir / "sheets").mkdir(exist_ok=True)

        song_data = {"name": name, "sheets": []}

        song_json_path = song_dir / "song.json"
        with open(song_json_path, "w", encoding="utf-8-sig") as f:
            json.dump(song_data, f, ensure_ascii=False, indent=2)

    def create_standalone_song(self, song_dir: Path | str, name: str) -> Project:
        self.init_song_folder(song_dir, name)
        return self.load_standalone_song(song_dir)

    def import_song_folder(self, project_dir: Path, src_folder: Path | str) -> str:
        """외부 곡 폴더를 프로젝트의 songs/ 폴더로 복사하고 곡 이름을 반환"""
        src = Path(src_folder).resolve()
        project_dir = Path(project_dir).resolve()
        songs_dir = project_dir / "songs"
        songs_dir.mkdir(exist_ok=True)

        if not (src / "song.json").exists():
            raise ValueError(f"유효한 곡 폴더가 아닙니다 (song.json 없음): {src}")

        dest = songs_dir / src.name
        if dest.exists():
            shutil.rmtree(dest)

        shutil.copytree(src, dest)
        return src.name

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
