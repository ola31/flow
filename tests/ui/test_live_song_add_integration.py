from __future__ import annotations

from pathlib import Path

import pytest

from flow.domain.project import Project
from flow.domain.workspace import Workspace
from flow.repository.project_repository import ProjectRepository
from flow.ui.live.live_song_add_panel import LiveSongAddPanel
from flow.ui.main_window import MainWindow


def test_add_lib_button_enabled_during_live(qapp):
    mw = MainWindow()
    try:
        mw._set_project_editable(False)  # simulate live (edit disabled)
        assert mw._song_list._btn_add_lib.isEnabled()
        assert mw._song_list._btn_new_song.isEnabled() is False
    finally:
        mw.close()


# ── Integration fixtures ────────────────────────────────────────────────────


@pytest.fixture
def live_mw(qapp, tmp_path: Path):
    """Workspace with library song '새노래' + saved project, MainWindow live."""
    ws = Workspace.create(tmp_path / "ws")

    # Create library song "새노래" with a valid song.json
    song_dir = ws.library_song_dir("새노래")
    song_dir.mkdir(parents=True, exist_ok=True)
    (song_dir / "song.json").write_text(
        '{"name":"새노래","sheets":[]}', encoding="utf-8"
    )

    # Save an empty project to the workspace
    repo = ProjectRepository(ws.projects_dir)
    project = Project(name="공연")
    path = repo.save_to_workspace(project, ws)

    mw = MainWindow(workspace=ws)
    mw._project = project
    mw._project_path = path
    mw._is_standalone = False
    mw._is_live = True
    mw._song_list.set_project(project)
    yield mw, ws, project, path
    mw._slide_manager.shutdown()
    mw.close()


# ── Tests ───────────────────────────────────────────────────────────────────


def test_open_live_song_add_panel_mounts(live_mw):
    mw, ws, project, path = live_mw
    mw._open_live_song_add_panel()
    assert isinstance(mw._live_side_panel, LiveSongAddPanel)


def test_live_add_appends_and_saves_without_slide_reload(live_mw, monkeypatch):
    mw, ws, project, path = live_mw
    called = {"load_songs": 0}
    monkeypatch.setattr(
        mw._slide_manager,
        "load_songs",
        lambda *a, **k: called.__setitem__("load_songs", called["load_songs"] + 1),
    )
    mw._open_live_song_add_panel()
    mw._on_live_add_song_chosen("새노래", "library")
    assert any(s.name == "새노래" for s in project.selected_songs)
    saved = Path(path).read_text(encoding="utf-8")
    assert "새노래" in saved
    assert called["load_songs"] == 0


def test_live_add_blocked_when_other_panel_open(live_mw):
    mw, ws, project, path = live_mw
    from PySide6.QtWidgets import QWidget

    mw._live_side_panel = QWidget()  # simulate a patch panel occupying the slot
    mw._open_live_song_add_panel()
    assert not isinstance(mw._live_side_panel, LiveSongAddPanel)
