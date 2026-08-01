"""셋리스트에 같은 곡을 여러 번 넣기 (오전·오후에 같은 곡을 부르는 경우).

두 자리는 같은 곡이므로 악보·핫스팟·매핑을 공유하고, 구간(section)처럼
'이 자리'에만 해당하는 값만 따로 갖는다.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from flow.domain.hotspot import Hotspot
from flow.domain.project import Project
from flow.domain.score_sheet import ScoreSheet
from flow.domain.song import Song
from flow.domain.workspace import Workspace
from flow.repository.project_repository import ProjectRepository
from flow.ui.editor.song_list_widget import SongListWidget, _SongCard


def _song(name: str = "곡A", sheets: int = 1) -> Song:
    return Song(
        name=name,
        folder=Path(f"songs/{name}"),
        score_sheets=[
            ScoreSheet(name=f"{name}_p{i}", image_path=f"sheets/p{i}.png")
            for i in range(sheets)
        ],
    )


class TestDuplicateReference:
    def test_shares_score_sheets(self):
        song = _song()
        dup = song.duplicate_reference("오후")

        assert dup.score_sheets is song.score_sheets  # 같은 리스트 객체
        assert dup.name == song.name
        assert dup.section == "오후"
        assert song.section == ""

    def test_mapping_edit_is_visible_from_both(self):
        song = _song()
        dup = song.duplicate_reference()
        h = Hotspot(x=1, y=1)

        song.score_sheets[0].hotspots.append(h)
        h.set_slide_index(4, verse_index=0)

        assert dup.score_sheets[0].hotspots[0] is h
        assert dup.score_sheets[0].hotspots[0].get_slide_index(0) == 4

    def test_sheet_added_later_shows_in_both(self):
        song = _song()
        dup = song.duplicate_reference()

        song.score_sheets.append(ScoreSheet(name="p2", image_path="sheets/p2.png"))

        assert len(dup.score_sheets) == 2


class TestProjectOccurrences:
    def test_second_add_creates_an_occurrence(self):
        p = Project(name="p")
        song = _song()

        p.add_song_occurrence(song, "오전")
        p.add_song_occurrence(song, "오후")

        assert len(p.selected_songs) == 2
        assert [s.section for s in p.selected_songs] == ["오전", "오후"]
        assert p.selected_songs[0].score_sheets is p.selected_songs[1].score_sheets
        assert p.song_order == ["곡A"]  # 곡 자체는 한 번만

    def test_occurrences_of(self):
        p = Project(name="p")
        p.add_song_occurrence(_song("A"))
        p.add_song_occurrence(_song("B"))
        p.add_song_occurrence(p.selected_songs[0])

        assert p.occurrences_of("A") == [0, 2]
        assert p.occurrences_of("B") == [1]

    def test_remove_occurrence_keeps_the_other(self):
        p = Project(name="p")
        song = _song()
        p.add_song_occurrence(song, "오전")
        p.add_song_occurrence(song, "오후")

        p.remove_occurrence(0)

        assert len(p.selected_songs) == 1
        assert p.selected_songs[0].section == "오후"
        assert p.song_order == ["곡A"]  # 아직 남아 있으므로 유지

    def test_removing_last_occurrence_drops_from_order(self):
        p = Project(name="p")
        song = _song()
        p.add_song_occurrence(song)
        p.add_song_occurrence(song)

        p.remove_occurrence(0)
        p.remove_occurrence(0)

        assert p.selected_songs == []
        assert p.song_order == []

    def test_remove_out_of_range_is_noop(self):
        p = Project(name="p")
        p.add_song_occurrence(_song())

        assert p.remove_occurrence(5) is None
        assert len(p.selected_songs) == 1

    def test_all_score_sheets_lists_each_occurrence(self):
        p = Project(name="p")
        song = _song(sheets=2)
        p.add_song_occurrence(song)
        p.add_song_occurrence(song)

        # 두 자리를 오가려면 시트도 자리마다 세어야 한다
        assert len(p.all_score_sheets) == 4

    def test_ensure_unique_ids_does_not_touch_shared_sheets(self):
        """두 번째 등장을 '중복 ID'로 보고 새로 발급하면 매핑이 끊긴다."""
        p = Project(name="p")
        song = _song()
        h = Hotspot(x=1, y=1)
        song.score_sheets[0].hotspots.append(h)
        p.add_song_occurrence(song)
        p.add_song_occurrence(song)
        sheet_id, hotspot_id = song.score_sheets[0].id, h.id

        changed = p.ensure_unique_ids()

        assert changed is False
        assert song.score_sheets[0].id == sheet_id
        assert h.id == hotspot_id


class TestPersistence:
    def _seed(self, ws: Workspace, name: str) -> None:
        d = ws.library_song_dir(name)
        d.mkdir(parents=True, exist_ok=True)
        (d / "song.json").write_text(
            json.dumps({
                "name": name,
                "sheets": [ScoreSheet(name=f"{name}_p", image_path="s.png").to_dict()],
            }),
            encoding="utf-8-sig",
        )

    def test_roundtrip_keeps_both_occurrences_and_sections(self, tmp_path):
        ws = Workspace.create(tmp_path / "ws")
        self._seed(ws, "곡A")
        repo = ProjectRepository(ws.projects_dir)

        project = Project(name="주간")
        song = Song.load_from_workspace(ws, "주간", "곡A")
        song.source = "library"
        project.add_song_occurrence(song, "오전")
        project.add_song_occurrence(song, "오후")
        repo.save_to_workspace(project, ws)

        loaded = repo.load_from_workspace(ws, "주간")

        assert [s.name for s in loaded.selected_songs] == ["곡A", "곡A"]
        assert [s.section for s in loaded.selected_songs] == ["오전", "오후"]

    def test_loaded_occurrences_share_sheets(self, tmp_path):
        """따로 로드하면 ID가 겹치는 별개 객체가 두 벌 생겨 저장이 충돌한다."""
        ws = Workspace.create(tmp_path / "ws")
        self._seed(ws, "곡A")
        repo = ProjectRepository(ws.projects_dir)
        project = Project(name="주간")
        song = Song.load_from_workspace(ws, "주간", "곡A")
        song.source = "library"
        project.add_song_occurrence(song, "오전")
        project.add_song_occurrence(song, "오후")
        repo.save_to_workspace(project, ws)

        loaded = repo.load_from_workspace(ws, "주간")

        a, b = loaded.selected_songs
        assert a.score_sheets is b.score_sheets


class TestSlideOffsetsWithDuplicates:
    def test_offset_counted_once(self, qapp):
        """등장할 때마다 오프셋을 더하면 전체 장수가 부풀고 매핑이 밀린다."""
        from unittest.mock import MagicMock

        from flow.services.slide_manager import SlideManager

        mgr = SlideManager(converter=MagicMock())
        try:
            song = _song()
            song.slides_path = Path("x.pptx")
            song.set_slide_count(5)
            other = _song("곡B")
            other.set_slide_count(3)
            # slide_source를 pptx로 고정
            for s in (song, other):
                type(s).slide_source = property(lambda self: "pptx")

            mgr._songs = [song, song.duplicate_reference(), other]
            mgr._slide_offsets = {}
            mgr._recalculate_offsets()

            assert mgr._slide_offsets["곡A"] == 0
            assert mgr._slide_offsets["곡B"] == 5
            assert mgr._total_slide_count == 8  # 5 + 3, 곡A를 두 번 세지 않음
        finally:
            del type(song).slide_source
            mgr.shutdown()


class _FakeMainWindow:
    def __init__(self, project_path: Path):
        from PySide6.QtWidgets import QWidget

        self._project_path = project_path
        self._is_live = False
        self.dirty = False
        self._canvas = QWidget()

    def _mark_dirty(self):
        self.dirty = True


@pytest.fixture
def widget(qtbot, tmp_path):
    w = SongListWidget()
    qtbot.addWidget(w)
    w.set_main_window(_FakeMainWindow(tmp_path / "project.json"))
    return w


def _cards(widget) -> list[_SongCard]:
    return [
        widget._cards_layout.itemAt(i).widget()
        for i in range(widget._cards_layout.count())
        if isinstance(widget._cards_layout.itemAt(i).widget(), _SongCard)
    ]


class TestSetlistUiWithDuplicates:
    def _project(self, widget):
        p = Project(name="p")
        song = _song(sheets=1)
        p.add_song_occurrence(song, "오전")
        p.add_song_occurrence(song, "오후")
        widget.set_project(p)
        return p

    def test_renders_a_card_per_occurrence(self, widget):
        self._project(widget)

        assert len(_cards(widget)) == 2

    def test_clicking_second_occurrence_selects_it(self, widget):
        p = self._project(widget)
        sheet = p.selected_songs[1].score_sheets[0]

        widget._on_sheet_selected_direct(sheet, 1)

        assert p.current_sheet_index == 1  # 첫 등장(0)이 아니라 두 번째
        selected = [c._is_selected for c in _cards(widget)]
        assert selected == [False, True]

    def test_clicking_first_occurrence_selects_it(self, widget):
        p = self._project(widget)
        sheet = p.selected_songs[0].score_sheets[0]

        widget._on_sheet_selected_direct(sheet, 0)

        assert p.current_sheet_index == 0
        assert [c._is_selected for c in _cards(widget)] == [True, False]


class TestIndexShiftWithSharedSheets:
    """전역/로컬 인덱스 변환은 시트 객체마다 한 번씩만.

    같은 곡이 두 번 들어가면 두 등장이 같은 시트 객체를 공유하므로,
    곡 단위로 돌리면 오프셋이 두 번 더해져 매핑이 통째로 어긋난다.
    """

    def _main_window(self, qtbot, offsets):
        from flow.ui.main_window import MainWindow

        mw = MainWindow()
        qtbot.addWidget(mw)
        mw._slide_manager.get_song_offset = lambda name: offsets.get(name, 0)
        return mw

    def test_shared_sheet_shifted_once(self, qtbot):
        mw = self._main_window(qtbot, {"곡A": 10})
        try:
            p = Project(name="p")
            song = _song()
            h = Hotspot(x=1, y=1)
            h.set_slide_index(2, verse_index=0)
            song.score_sheets[0].hotspots.append(h)
            p.add_song_occurrence(song, "오전")
            p.add_song_occurrence(song, "오후")
            mw._project = p

            mw._globalize_project_indices()

            assert h.get_slide_index(0) == 12  # 2 + 10, 22가 아니다
        finally:
            mw._slide_manager.shutdown()
            mw._clear_dirty()
            mw.close()

    def test_globalize_then_localize_round_trips(self, qtbot):
        mw = self._main_window(qtbot, {"곡A": 7})
        try:
            p = Project(name="p")
            song = _song()
            h = Hotspot(x=1, y=1)
            h.set_slide_index(3, verse_index=0)
            song.score_sheets[0].hotspots.append(h)
            p.add_song_occurrence(song)
            p.add_song_occurrence(song)
            mw._project = p

            mw._globalize_project_indices()
            mw._localize_project_indices()

            assert h.get_slide_index(0) == 3
        finally:
            mw._slide_manager.shutdown()
            mw._clear_dirty()
            mw.close()


class TestIndexShiftIsIdempotent:
    """전역화/로컬화는 상태를 추적해 두 번 적용되지 않아야 한다.

    실제 손상 사례: 곡을 추가하면 _on_songs_changed가 저장(내부에서
    localize→save→globalize) 뒤 다시 localize한다. 3단계의 globalize는
    _on_songs_metadata_finished가 담당하는데 화면 전환 중이면 조용히
    빠져나간다 — 그러면 로컬인 값을 다시 로컬화해 매핑이 음수가 되고,
    그대로 song.json에 저장돼 곡 전체의 매핑이 사라진다.
    """

    def _mw(self, qtbot, offset):
        from flow.ui.main_window import MainWindow

        mw = MainWindow()
        qtbot.addWidget(mw)
        mw._slide_manager.get_song_offset = lambda name: offset
        return mw

    def _project_with_mapping(self, mw, index=2):
        p = Project(name="p")
        song = _song()
        h = Hotspot(x=1, y=1)
        h.set_slide_index(index, verse_index=0)
        song.score_sheets[0].hotspots.append(h)
        p.add_song_occurrence(song)
        mw._project = p
        return h

    def test_double_localize_does_not_go_negative(self, qtbot):
        mw = self._mw(qtbot, 80)
        try:
            h = self._project_with_mapping(mw)
            mw._globalize_project_indices()
            assert h.get_slide_index(0) == 82

            mw._localize_project_indices()
            mw._localize_project_indices()  # 두 번째는 무시돼야 한다

            assert h.get_slide_index(0) == 2
        finally:
            mw._slide_manager.shutdown()
            mw._clear_dirty()
            mw.close()

    def test_double_globalize_does_not_double_shift(self, qtbot):
        mw = self._mw(qtbot, 80)
        try:
            h = self._project_with_mapping(mw)

            mw._globalize_project_indices()
            mw._globalize_project_indices()

            assert h.get_slide_index(0) == 82
        finally:
            mw._slide_manager.shutdown()
            mw._clear_dirty()
            mw.close()

    def test_new_project_starts_local(self, qtbot):
        mw = self._mw(qtbot, 80)
        try:
            self._project_with_mapping(mw)
            mw._globalize_project_indices()
            assert mw._indices_globalized is True

            # 프로젝트를 새로 물리면 디스크에서 온 로컬 인덱스다
            h = self._project_with_mapping(mw)
            assert mw._indices_globalized is False

            mw._localize_project_indices()  # 로컬을 또 로컬화하지 않는다

            assert h.get_slide_index(0) == 2
        finally:
            mw._slide_manager.shutdown()
            mw._clear_dirty()
            mw.close()

    def test_shift_refuses_to_produce_negative(self, qtbot):
        """상태 추적이 어긋나도 매핑이 음수로 저장되지는 않게 하는 안전망."""
        mw = self._mw(qtbot, 80)
        try:
            h = self._project_with_mapping(mw)
            mw._indices_globalized = True  # 어긋난 상태를 강제

            mw._localize_project_indices()

            assert h.get_slide_index(0) == 2  # 건드리지 않는다
        finally:
            mw._slide_manager.shutdown()
            mw._clear_dirty()
            mw.close()
