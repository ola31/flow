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


class TestFormatTagOnSelection:
    def test_tag_hidden_when_not_selected(self, make_card, tmp_path):
        song = _song(tmp_path, hotspots=[_hotspot(True)])
        card = make_card(song)
        assert card._fmt_tag.isHidden()

    def test_tag_visible_on_selected_ppt_song(self, make_card, tmp_path):
        song = _song(tmp_path, hotspots=[_hotspot(True)])
        card = make_card(song)
        card.set_selected(True, song.score_sheets[0].id)
        assert not card._fmt_tag.isHidden()
        assert card._fmt_tag.text() == "PPT"

    def test_markdown_song_shows_markdown_tag(self, make_card, tmp_path):
        song = _song(tmp_path, slides=False, md=True, hotspots=[_hotspot(True)])
        card = make_card(song)
        card.set_selected(True, song.score_sheets[0].id)
        assert card._fmt_tag.text() == "마크다운"

    def test_tag_hides_again_on_deselect(self, make_card, tmp_path):
        song = _song(tmp_path, hotspots=[_hotspot(True)])
        card = make_card(song)
        card.set_selected(True, song.score_sheets[0].id)
        card.set_selected(False)
        assert card._fmt_tag.isHidden()

    def test_no_tag_for_song_without_slides(self, make_card, tmp_path):
        song = _song(tmp_path, slides=False)
        card = make_card(song)
        card.set_selected(True, song.score_sheets[0].id)
        assert card._fmt_tag.isHidden()


class TestWarningColors:
    def test_mapping_missing_is_red(self, make_card, tmp_path):
        from flow.ui.styles import RED

        song = _song(tmp_path, hotspots=[])
        card = make_card(song)
        assert RED in card._lbl_warnings.styleSheet()

    def test_other_warnings_stay_amber(self, make_card, tmp_path):
        from flow.ui.styles import AMBER, RED

        song = _song(tmp_path, slides=False, hotspots=[])
        card = make_card(song)
        assert AMBER in card._lbl_warnings.styleSheet()
        assert RED not in card._lbl_warnings.styleSheet()


class TestLibraryAddPopupCard:
    """곡 추가 팝업(라이브 중 추가 패널 공용) 카드 — 빨간 경고만, 카운트 없음."""

    def _info(self, **over):
        base = {
            "name": "song_x",
            "sheet_count": 2,
            "has_ppt": True,
            "has_md": False,
            "total_hotspots": 2,
            "mapped_hotspots": 2,
        }
        base.update(over)
        return base

    def _texts(self, card):
        from PySide6.QtWidgets import QLabel

        return [lbl.text() for lbl in card.findChildren(QLabel)]

    def _make(self, qtbot, info):
        from flow.ui.editor.song_list_widget import _LibrarySongCard

        card = _LibrarySongCard(info)
        qtbot.addWidget(card)
        return card

    def test_complete_song_shows_no_status(self, qtbot):
        card = self._make(qtbot, self._info())
        texts = self._texts(card)
        assert "2/2" not in texts  # 완료 카운트 제거
        assert "악보 2장" not in texts
        assert "PPT" not in texts

    def test_partial_mapping_shows_no_count(self, qtbot):
        card = self._make(qtbot, self._info(mapped_hotspots=1))
        assert "1/2" not in self._texts(card)

    def test_unmapped_song_shows_red_warning(self, qtbot):
        from PySide6.QtWidgets import QLabel

        from flow.ui.styles import RED

        card = self._make(qtbot, self._info(mapped_hotspots=0))
        warn = [
            lbl for lbl in card.findChildren(QLabel)
            if lbl.text() == "매핑 없음"
        ]
        assert warn and RED in warn[0].styleSheet()

    def test_no_sheets_shows_red_and_suppresses_mapping(self, qtbot):
        card = self._make(
            qtbot, self._info(sheet_count=0, mapped_hotspots=0)
        )
        texts = self._texts(card)
        assert "악보 없음" in texts
        assert "매핑 없음" not in texts

    def test_no_slides_shows_red_and_suppresses_mapping(self, qtbot):
        card = self._make(
            qtbot, self._info(has_ppt=False, mapped_hotspots=0)
        )
        texts = self._texts(card)
        assert "슬라이드 없음" in texts
        assert "매핑 없음" not in texts
