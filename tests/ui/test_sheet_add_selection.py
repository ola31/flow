"""악보를 추가하면 캔버스가 새 악보로 따라와야 한다.

select_sheet_by_id는 인덱스와 카드 강조만 바꾸고 song_selected를 쏘지
않아서, 악보를 추가해도 캔버스는 이전 악보를 계속 보여줬다 —
"새로 추가한 이미지 대신 기존 이미지가 뜬다".
"""
from __future__ import annotations

from pathlib import Path

import pytest

from flow.domain.project import Project
from flow.domain.score_sheet import ScoreSheet
from flow.domain.song import Song
from flow.ui.editor.song_list_widget import SongListWidget


class _MainWindowStub:
    def __init__(self, project_path: Path):
        self._project_path = project_path
        self._is_live = False

    def _mark_dirty(self):
        pass

    def statusBar(self):  # noqa: N802 — Qt 이름 규약 흉내
        class _Bar:
            def showMessage(self, *a):  # noqa: N802
                pass

        return _Bar()


@pytest.fixture
def widget(qtbot, tmp_path):
    song = Song(
        name="song_a",
        folder=tmp_path / "song_a",
        project_dir=tmp_path,
        score_sheets=[
            ScoreSheet(name="1장", image_path="sheets/a.png"),
            ScoreSheet(name="2장", image_path="sheets/b.png"),
        ],
    )
    w = SongListWidget()
    qtbot.addWidget(w)
    w.set_main_window(_MainWindowStub(tmp_path / "song_a"))
    w.set_standalone(True)
    project = Project(name="[곡 편집] song_a")
    project.selected_songs = [song]
    w.set_project(project)
    return w, song


def test_select_sheet_by_id_notifies_listeners(widget):
    w, song = widget
    seen = []
    w.song_selected.connect(seen.append)

    w.select_sheet_by_id(song.score_sheets[1].id)

    assert seen == [song.score_sheets[1]], (
        "선택을 알리지 않으면 캔버스가 옛 악보를 계속 표시한다"
    )


def test_select_sheet_by_id_still_updates_index(widget):
    w, song = widget

    w.select_sheet_by_id(song.score_sheets[1].id)

    assert w._project.current_sheet_index == 1


def test_unknown_sheet_id_does_not_notify(widget):
    w, _song = widget
    seen = []
    w.song_selected.connect(seen.append)

    w.select_sheet_by_id("존재하지-않는-id")

    assert seen == []
