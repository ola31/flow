"""곡 편집 모드에서 프로젝트로 복귀할 때의 슬라이드 재로딩 범위.

복귀할 때 파일이 바뀔 수 있는 건 방금 편집한 곡뿐이다. 셋리스트 전체를
다시 세면 곡마다 슬라이드 파일을 두 번(메타데이터 + LOAD_SINGLE) 파싱해서,
곡이 많을수록 복귀가 통째로 다시 로딩되는 것처럼 보인다.

곡은 마크다운 슬라이드로 심는다 — 가짜 .pptx를 심으면 변환 워커가 실패
신호를 올리고, 그 핸들러의 모달 알림이 헤드리스 실행을 붙잡는다.
"""

from __future__ import annotations

import json
from pathlib import Path

from flow.domain.project import Project
from flow.domain.score_sheet import ScoreSheet
from flow.domain.song import Song
from flow.domain.workspace import Workspace
from flow.repository.project_repository import ProjectRepository


def _seed_library_song(workspace: Workspace, name: str) -> Path:
    song_dir = workspace.library_song_dir(name)
    song_dir.mkdir(parents=True, exist_ok=True)
    sheet = ScoreSheet(name=f"{name}_sheet")
    (song_dir / "song.json").write_text(
        json.dumps({"name": name, "sheets": [sheet.to_dict()]}, ensure_ascii=False),
        encoding="utf-8",
    )
    (song_dir / "slides.md").write_text(
        f"# {name}\n\n첫 슬라이드\n\n둘째 슬라이드\n", encoding="utf-8"
    )
    (song_dir / "sheets").mkdir(exist_ok=True)
    return song_dir


def _main_window_with_setlist(tmp_path: Path):
    """곡 두 개짜리 셋리스트를 가진 MainWindow (슬라이드 카운트 채워둠)."""
    from flow.ui.main_window import MainWindow

    ws = Workspace.create(tmp_path / "ws")
    _seed_library_song(ws, "곡A")
    _seed_library_song(ws, "곡B")

    mw = MainWindow(workspace=ws)
    mw._project = Project(name="셋")
    mw._project_path = ProjectRepository(ws.projects_dir).save_to_workspace(
        mw._project, ws
    )

    for i, name in enumerate(("곡A", "곡B")):
        song = Song.load_from_workspace(ws, "셋", name, order=i)
        assert song is not None
        # 프로젝트를 열 때 SlideManager가 채워두는 값
        song.set_slide_count(5 + i)
        mw._project.selected_songs.append(song)

    return mw


def test_return_recounts_only_the_edited_song(qapp, tmp_path):
    mw = _main_window_with_setlist(tmp_path)
    try:
        edited, untouched = mw._project.selected_songs

        calls: list[tuple[list, dict]] = []
        mw._slide_manager.load_songs = lambda songs, **kw: calls.append(
            ([(s.name, s.get_slide_count()) for s in songs], kw)
        )

        mw._enter_song_edit_mode(edited)
        assert mw._is_standalone is True

        calls.clear()
        mw._exit_song_edit_mode()

        assert mw._is_standalone is False
        # 복귀는 load_songs를 정확히 한 번 부른다 — 이 호출의 완료 신호가
        # 진입 때 localize한 핫스팟 인덱스를 다시 globalize한다.
        assert len(calls) == 1
        counts, kwargs = calls[0]
        assert kwargs.get("skip_counted") is True
        # 편집한 곡만 0으로 비워 다시 세게 하고, 나머지는 센 값을 재사용
        assert dict(counts) == {edited.name: 0, untouched.name: 6}
    finally:
        mw.close()


def test_return_binds_manager_to_parent_project_songs(qapp, tmp_path):
    """편집 중 SlideManager는 standalone 곡 객체를 들고 있다 — 복귀하면
    부모 프로젝트의 곡 객체로 다시 묶여야 오프셋이 맞는다."""
    mw = _main_window_with_setlist(tmp_path)
    try:
        parent_songs = list(mw._project.selected_songs)

        mw._enter_song_edit_mode(parent_songs[0])
        assert [s.name for s in mw._slide_manager._songs] == ["곡A"]

        mw._exit_song_edit_mode()

        assert [id(s) for s in mw._slide_manager._songs] == [
            id(s) for s in parent_songs
        ]
    finally:
        mw.close()
