"""악보 이미지 여러 장 동시 추가.

한 곡에 악보 5~6장을 넣는 게 흔한데 한 번에 한 장씩만 고를 수 있으면
파일 대화상자를 그만큼 다시 열어야 한다. 여러 장을 고르면 이름을
장마다 묻지 않고 파일명에서 자동으로 짓는다.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QFileDialog, QInputDialog

from flow.domain.project import Project
from flow.domain.song import Song
from flow.ui.editor.song_list_widget import SongListWidget


class _FakeMainWindow:
    def __init__(self, project_path: Path):
        self._project_path = project_path
        self._is_live = False
        self.dirty = False
        self._messages: list[str] = []

    def _mark_dirty(self):
        self.dirty = True

    def statusBar(self):  # noqa: N802 — Qt 이름 규약을 흉내
        outer = self

        class _Bar:
            def showMessage(self, msg, _timeout=0):  # noqa: N802
                outer._messages.append(msg)

        return _Bar()


@pytest.fixture
def env(qtbot, tmp_path):
    song_dir = tmp_path / "songs" / "곡A"
    song_dir.mkdir(parents=True)
    src_dir = tmp_path / "scans"
    src_dir.mkdir()
    sources = []
    for name in ("page2.png", "page1.png", "page3.png"):
        p = src_dir / name
        p.write_bytes(b"\x89PNG fake")
        sources.append(str(p))

    song = Song(name="곡A", folder=Path("songs/곡A"), project_dir=tmp_path)
    widget = SongListWidget()
    qtbot.addWidget(widget)
    project = Project(name="p")
    project.selected_songs = [song]
    widget.set_project(project)
    widget.set_main_window(_FakeMainWindow(tmp_path / "project.json"))
    return widget, song, sources, tmp_path


def _patch_dialog(monkeypatch, paths: list[str]):
    monkeypatch.setattr(
        QFileDialog, "getOpenFileNames", staticmethod(lambda *a, **k: (paths, ""))
    )


class TestMultiSheetAdd:
    def test_all_selected_images_are_added(self, env, monkeypatch):
        widget, song, sources, tmp_path = env
        _patch_dialog(monkeypatch, sources)

        widget._set_song_image(song)

        assert len(song.score_sheets) == 3
        for name in ("page1.png", "page2.png", "page3.png"):
            assert (tmp_path / "songs" / "곡A" / "sheets" / name).exists()

    def test_names_are_sorted_by_filename(self, env, monkeypatch):
        widget, song, sources, _ = env
        _patch_dialog(monkeypatch, sources)  # page2, page1, page3 순으로 선택

        widget._set_song_image(song)

        assert [s.image_path for s in song.score_sheets] == [
            "sheets/page1.png",
            "sheets/page2.png",
            "sheets/page3.png",
        ]

    def test_multi_select_does_not_prompt_for_names(self, env, monkeypatch):
        widget, song, sources, _ = env
        _patch_dialog(monkeypatch, sources)
        prompted = []
        monkeypatch.setattr(
            QInputDialog,
            "getText",
            staticmethod(lambda *a, **k: (prompted.append(1), ("x", True))[1]),
        )

        widget._set_song_image(song)

        assert prompted == [], "여러 장 선택 시 장마다 이름을 묻지 않는다"
        assert [s.name for s in song.score_sheets] == [
            "곡A - page1", "곡A - page2", "곡A - page3"
        ]

    def test_single_select_still_prompts_for_name(self, env, monkeypatch):
        widget, song, sources, _ = env
        _patch_dialog(monkeypatch, sources[:1])
        monkeypatch.setattr(
            QInputDialog,
            "getText",
            staticmethod(lambda *a, **k: ("내가 지은 이름", True)),
        )

        widget._set_song_image(song)

        assert [s.name for s in song.score_sheets] == ["내가 지은 이름"]

    def test_cancelled_dialog_adds_nothing(self, env, monkeypatch):
        widget, song, _sources, _ = env
        _patch_dialog(monkeypatch, [])

        widget._set_song_image(song)

        assert song.score_sheets == []
