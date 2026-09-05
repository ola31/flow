"""라이브 중 곡을 넘길 때 '긴급 수정' 게이트가 따라오는지.

게이트는 곡의 슬라이드 형식(markdown일 때만 허용)으로 정해지는데, 예전에는
라이브 진입 시점에 한 번만 정해졌다. PPT 곡에서 라이브를 시작하면 그 뒤
마크다운 곡으로 넘어가도 '긴급 수정'이 세션 내내 나오지 않았다.
"""

from __future__ import annotations

import json
from pathlib import Path

from flow.domain.hotspot import Hotspot
from flow.domain.project import Project
from flow.domain.score_sheet import ScoreSheet
from flow.domain.song import Song
from flow.domain.workspace import Workspace
from flow.repository.project_repository import ProjectRepository


def _seed(workspace: Workspace, name: str, kind: str) -> Path:
    from PySide6.QtGui import QColor, QImage

    song_dir = workspace.library_song_dir(name)
    (song_dir / "sheets").mkdir(parents=True, exist_ok=True)
    image = song_dir / "sheets" / "p1.png"
    canvas = QImage(64, 64, QImage.Format.Format_RGB32)
    canvas.fill(QColor("#333333"))
    canvas.save(str(image))

    sheet = ScoreSheet(name=f"{name}_1", image_path=str(image))
    sheet.hotspots.append(Hotspot(x=10, y=10, order=0))
    (song_dir / "song.json").write_text(
        json.dumps({"name": name, "sheets": [sheet.to_dict()]}, ensure_ascii=False),
        encoding="utf-8",
    )
    if kind == "markdown":
        (song_dir / "slides.md").write_text(
            "# 곡\n\n첫 줄\n\n둘째 줄\n", encoding="utf-8"
        )
    else:
        (song_dir / "slides.pptx").write_bytes(b"fake")
    return song_dir


def _window_with_ppt_then_markdown(tmp_path: Path):
    from flow.ui.main_window import MainWindow

    ws = Workspace.create(tmp_path / "ws")
    _seed(ws, "피피티곡", "pptx")
    _seed(ws, "마크다운곡", "markdown")

    mw = MainWindow(workspace=ws)
    mw._project = Project(name="셋")
    mw._project_path = ProjectRepository(ws.projects_dir).save_to_workspace(
        mw._project, ws
    )
    for i, name in enumerate(("피피티곡", "마크다운곡")):
        song = Song.load_from_workspace(ws, "셋", name, order=i)
        assert song is not None
        mw._project.selected_songs.append(song)
    mw._song_list.set_project(mw._project)
    return mw


def test_gate_opens_when_live_moves_onto_a_markdown_song(qapp, tmp_path):
    mw = _window_with_ppt_then_markdown(tmp_path)
    try:
        ppt_sheet, md_sheet = mw._project.all_score_sheets

        mw._on_song_selected(ppt_sheet)
        mw._enter_live()
        assert mw._canvas._live_emergency_enabled is False

        mw._on_song_selected(md_sheet)

        assert mw._canvas._live_emergency_enabled is True
        assert mw._slide_preview._live_emergency_enabled is True
    finally:
        mw._exit_live()
        mw.close()


def test_gate_closes_when_live_moves_onto_a_pptx_song(qapp, tmp_path):
    """반대 방향도 따라와야 한다 — 안 그러면 못 쓰는 메뉴가 남는다."""
    mw = _window_with_ppt_then_markdown(tmp_path)
    try:
        ppt_sheet, md_sheet = mw._project.all_score_sheets

        mw._on_song_selected(md_sheet)
        mw._enter_live()
        assert mw._canvas._live_emergency_enabled is True

        mw._on_song_selected(ppt_sheet)

        assert mw._canvas._live_emergency_enabled is False
        assert mw._slide_preview._live_emergency_enabled is False
    finally:
        mw._exit_live()
        mw.close()
