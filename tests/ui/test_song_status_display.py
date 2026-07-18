"""셋리스트 카드 상태 표시 — 정상은 조용히, 문제만 앰버 경고.

초록 라벨("악보·PPT·매핑 N개 완료")이 모든 카드에 상시 붙어 조잡했고,
핫스팟이 0개인 곡은 오히려 아무 표시가 없었다. 문제가 있는 곡만
경고를 보여주고, 형식(PPT/마크다운) 태그는 선택된 카드에만 표시한다.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from flow.domain.hotspot import Hotspot
from flow.domain.score_sheet import ScoreSheet
from flow.domain.song import Song
from flow.ui.editor.song_list_widget import _SongCard


def _hotspot(mapped: bool) -> Hotspot:
    return Hotspot(x=10, y=10, slide_index=0 if mapped else -1)


def _song(
    tmp_path: Path, *, sheets=True, slides=True, md=False, hotspots=()
) -> Song:
    song_dir = tmp_path / "song_a"
    song_dir.mkdir(exist_ok=True)
    if slides:
        (song_dir / "slides.pptx").touch()
    if md:
        (song_dir / "slides.md").write_text("# page", encoding="utf-8")
    sheet = ScoreSheet(
        name="page1",
        image_path="page1.png" if sheets else "",
        hotspots=list(hotspots),
    )
    return Song(
        name="song_a",
        folder=Path("song_a"),
        score_sheets=[sheet],
        project_dir=tmp_path,
    )


@pytest.fixture
def make_card(qtbot):
    def _make(song):
        card = _SongCard(song, position=1)
        qtbot.addWidget(card)
        return card

    return _make


class TestWarningOnlyStatusRow:
    def test_complete_song_hides_status_row(self, make_card, tmp_path):
        song = _song(tmp_path, hotspots=[_hotspot(True), _hotspot(True)])
        card = make_card(song)
        assert card._status_widget.isHidden()

    def test_zero_hotspots_shows_mapping_missing(self, make_card, tmp_path):
        song = _song(tmp_path, hotspots=[])
        card = make_card(song)
        assert not card._status_widget.isHidden()
        assert card._lbl_warnings.text() == "매핑 없음"

    def test_unmapped_hotspots_show_mapping_missing(self, make_card, tmp_path):
        song = _song(tmp_path, hotspots=[_hotspot(False), _hotspot(False)])
        card = make_card(song)
        assert card._lbl_warnings.text() == "매핑 없음"

    def test_partial_mapping_shows_ratio(self, make_card, tmp_path):
        song = _song(tmp_path, hotspots=[_hotspot(True), _hotspot(False)])
        card = make_card(song)
        assert card._lbl_warnings.text() == "매핑 1/2"

    def test_no_slides_suppresses_mapping_warning(self, make_card, tmp_path):
        song = _song(tmp_path, slides=False, hotspots=[])
        card = make_card(song)
        assert card._lbl_warnings.text() == "슬라이드 없음"

    def test_no_sheets_suppresses_mapping_warning(self, make_card, tmp_path):
        song = _song(tmp_path, sheets=False, hotspots=[])
        card = make_card(song)
        assert card._lbl_warnings.text() == "악보 없음"
