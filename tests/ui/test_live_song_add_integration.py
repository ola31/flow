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


def test_exit_live_unmounts_song_add_panel(live_mw):
    """Fix 1: _exit_live must tear down the song-add panel when it is open."""
    mw, ws, project, path = live_mw
    mw._open_live_song_add_panel()
    assert isinstance(mw._live_side_panel, LiveSongAddPanel)
    mw._exit_live()
    assert mw._live_side_panel is None


def test_patch_open_blocked_while_song_add_panel_open(live_mw, tmp_path):
    """Fix 2: opening the patch panel while song-add is open must be a no-op."""
    mw, ws, project, path = live_mw
    mw._open_live_song_add_panel()
    assert isinstance(mw._live_side_panel, LiveSongAddPanel)
    before = mw._live_side_panel

    # Create a minimal markdown file so _open_emergency_patch_panel can read
    # past the file-I/O step (without Fix 2, it would succeed and replace the
    # slot; with Fix 2, the _live_side_panel guard fires before any file I/O).
    song_md = tmp_path / "test_song" / "slides.md"
    song_md.parent.mkdir(parents=True, exist_ok=True)
    song_md.write_text("# 테스트\n\n슬라이드 1\n", encoding="utf-8")

    class _MockSong:
        name = "test_song"
        markdown_path = song_md

    try:
        mw._open_emergency_patch_panel(song=_MockSong(), initial_index=None)
    except Exception:
        pass

    # The slot must still hold the original LiveSongAddPanel.
    assert mw._live_side_panel is before
    assert isinstance(mw._live_side_panel, LiveSongAddPanel)


def test_normal_add_reloads_slides_via_songs_changed(live_mw, monkeypatch):
    """일반(비라이브) 곡 추가는 _on_songs_changed를 거쳐 슬라이드 미리보기를
    즉시 갱신해야 한다 (재열기 없이도 슬라이드가 떠야 함)."""
    mw, ws, project, path = live_mw
    calls = []
    monkeypatch.setattr(mw, "_on_songs_changed", lambda: calls.append(1))

    mw._song_list._add_existing_song("새노래", "library")  # 기본 reload_slides=True

    assert calls == [1]
    assert any(s.name == "새노래" for s in project.selected_songs)


def test_live_add_skips_songs_changed(live_mw, monkeypatch):
    """라이브 추가(reload_slides=False)는 송출 무중단을 위해 _on_songs_changed를
    호출하지 않는다."""
    mw, ws, project, path = live_mw
    calls = []
    monkeypatch.setattr(mw, "_on_songs_changed", lambda: calls.append(1))

    mw._song_list._add_existing_song("새노래", "library", reload_slides=False)

    assert calls == []
