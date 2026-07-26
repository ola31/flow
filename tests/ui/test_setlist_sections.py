"""셋리스트 구간(오전/오후) 구분.

한 프로젝트 안에서 곡을 구간으로 묶어 보여준다. 구간은 표시용이라
라이브 방향키 탐색은 구간을 가로질러 전체를 순서대로 훑는다.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from flow.domain.project import Project
from flow.domain.song import Song
from flow.domain.workspace import Workspace
from flow.repository.project_repository import ProjectRepository
from flow.ui.editor.song_list_widget import (
    SongListWidget,
    _SectionHeader,
    _SongCard,
)


class _FakeMainWindow:
    def __init__(self, project_path: Path):
        self._project_path = project_path
        self._is_live = False
        self.dirty = False

    def _mark_dirty(self):
        self.dirty = True


def _song(name: str, section: str = "") -> Song:
    return Song(name=name, folder=Path(f"songs/{name}"), section=section)


@pytest.fixture
def widget(qtbot, tmp_path):
    w = SongListWidget()
    qtbot.addWidget(w)
    w.set_main_window(_FakeMainWindow(tmp_path / "project.json"))
    return w


def _rows(widget) -> list[str]:
    """레이아웃 순서대로 머리글/곡 이름을 납작하게 나열."""
    out = []
    for i in range(widget._cards_layout.count()):
        w = widget._cards_layout.itemAt(i).widget()
        if isinstance(w, _SectionHeader):
            out.append(f"# {w._title}")
        elif isinstance(w, _SongCard):
            out.append(w._song.name)
    return out


class TestSectionHeaders:
    def test_no_headers_when_no_section_set(self, widget):
        p = Project(name="p")
        p.selected_songs = [_song("곡A"), _song("곡B")]

        widget.set_project(p)

        assert _rows(widget) == ["곡A", "곡B"]

    def test_header_per_section_group(self, widget):
        p = Project(name="p")
        p.selected_songs = [
            _song("곡A", "오전"),
            _song("곡B", "오전"),
            _song("곡C", "오후"),
        ]

        widget.set_project(p)

        assert _rows(widget) == ["# 오전", "곡A", "곡B", "# 오후", "곡C"]

    def test_unassigned_songs_get_their_own_header(self, widget):
        p = Project(name="p")
        p.selected_songs = [_song("곡A"), _song("곡B", "오후")]

        widget.set_project(p)

        assert _rows(widget) == ["# 구간 없음", "곡A", "# 오후", "곡B"]

    def test_header_shows_song_count(self, widget):
        from PySide6.QtWidgets import QLabel

        p = Project(name="p")
        p.selected_songs = [
            _song("곡A", "오전"), _song("곡B", "오전"), _song("곡C", "오후"),
        ]

        widget.set_project(p)

        headers = [
            widget._cards_layout.itemAt(i).widget()
            for i in range(widget._cards_layout.count())
            if isinstance(widget._cards_layout.itemAt(i).widget(), _SectionHeader)
        ]
        assert [h._title for h in headers] == ["오전", "오후"]
        counts = [
            [lbl.text() for lbl in h.findChildren(QLabel)][1] for h in headers
        ]
        assert counts == ["2곡", "1곡"]

    def test_headers_cleared_on_refresh(self, widget):
        p = Project(name="p")
        p.selected_songs = [_song("곡A", "오전")]
        widget.set_project(p)

        widget.refresh_list()
        widget.refresh_list()

        assert _rows(widget) == ["# 오전", "곡A"]


class TestSectionPersistence:
    """구간은 프로젝트 소유 — project.json에 저장되고 song.json에는 없다."""

    def test_roundtrip_through_workspace(self, tmp_path):
        ws = Workspace.create(tmp_path / "ws")
        repo = ProjectRepository(ws.projects_dir)
        project = Project(name="주간")
        s1 = Song(name="곡A", folder=ws.library_song_dir("곡A"), section="오전")
        s2 = Song(name="곡B", folder=ws.library_song_dir("곡B"), section="오후")
        s1.source = s2.source = "library"
        project.selected_songs = [s1, s2]
        project.song_order = ["곡A", "곡B"]

        repo.save_to_workspace(project, ws)
        loaded = repo.load_from_workspace(ws, "주간")

        assert [s.section for s in loaded.selected_songs] == ["오전", "오후"]

    def test_section_not_written_to_song_json(self, tmp_path):
        ws = Workspace.create(tmp_path / "ws")
        repo = ProjectRepository(ws.projects_dir)
        project = Project(name="주간")
        song = Song(
            name="곡A", folder=ws.library_song_dir("곡A"), section="오전"
        )
        song.source = "library"
        project.selected_songs = [song]

        repo.save_to_workspace(project, ws)

        data = json.loads(
            (ws.library_song_dir("곡A") / "song.json").read_text(
                encoding="utf-8-sig"
            )
        )
        assert "section" not in data

    def test_missing_section_defaults_to_empty(self, tmp_path):
        """구간이 없던 기존 project.json도 그대로 열린다."""
        ws = Workspace.create(tmp_path / "ws")
        repo = ProjectRepository(ws.projects_dir)
        d = ws.library_song_dir("곡A")
        d.mkdir(parents=True)
        (d / "song.json").write_text(
            json.dumps({"name": "곡A", "sheets": []}), encoding="utf-8-sig"
        )
        pdir = ws.project_dir("옛프로젝트")
        pdir.mkdir(parents=True)
        (pdir / "project.json").write_text(
            json.dumps({
                "id": "x", "name": "옛프로젝트",
                "selected_songs": [{"name": "곡A", "order": 0}],
                "song_order": ["곡A"],
            }),
            encoding="utf-8-sig",
        )

        loaded = repo.load_from_workspace(ws, "옛프로젝트")

        assert loaded.selected_songs[0].section == ""


class TestSetSectionAction:
    def test_menu_offers_section_action(self, qtbot):
        card = _SongCard(_song("곡A"), 1)
        qtbot.addWidget(card)

        labels = [a.text() for a in card._build_context_menu().actions()]

        assert "구간 지정" in labels

    def test_menu_says_change_when_already_set(self, qtbot):
        card = _SongCard(_song("곡A", "오전"), 1)
        qtbot.addWidget(card)

        labels = [a.text() for a in card._build_context_menu().actions()]

        assert "구간 변경" in labels

    def test_action_emits_signal(self, qtbot):
        song = _song("곡A")
        card = _SongCard(song, 1)
        qtbot.addWidget(card)
        received = []
        card.set_section_requested.connect(received.append)

        next(
            a for a in card._build_context_menu().actions() if a.text() == "구간 지정"
        ).trigger()

        assert received == [song]
