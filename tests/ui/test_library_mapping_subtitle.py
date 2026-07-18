"""라이브러리 카드 부제 — 매핑에 문제가 있을 때만 경고 꼬리.

완료된 곡은 기존 "PPT · 악보 N장" 그대로, 매핑이 없거나 일부만 매핑된
곡만 "· 매핑 없음"/"· 매핑 m/N"이 붙는다. 악보나 슬라이드가 없는 곡은
원인 경고가 이미 부제에 있으므로 매핑 꼬리를 생략한다.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from flow.ui.screens.library_screen import LibraryScreen


def _make_song_dir(tmp_path: Path, name: str, *, hotspots, slides=True) -> Path:
    d = tmp_path / name
    (d / "sheets").mkdir(parents=True)
    (d / "sheets" / "page1.png").touch()
    if slides:
        (d / "slides.pptx").touch()
    data = {"name": name, "sheets": [{"name": "page1", "hotspots": hotspots}]}
    with open(d / "song.json", "w", encoding="utf-8-sig") as f:
        json.dump(data, f, ensure_ascii=False)
    return d


@pytest.fixture
def screen(qtbot):
    sc = LibraryScreen()
    qtbot.addWidget(sc)
    return sc


class TestMappingSubtitleTail:
    def test_complete_mapping_no_tail(self, screen, tmp_path):
        d = _make_song_dir(tmp_path, "song_a", hotspots=[{"slide_index": 0}])
        assert "매핑" not in screen._build_subtitle(d)

    def test_zero_hotspots_shows_missing(self, screen, tmp_path):
        d = _make_song_dir(tmp_path, "song_b", hotspots=[])
        assert screen._build_subtitle(d).endswith("· 매핑 없음")

    def test_unmapped_hotspots_show_missing(self, screen, tmp_path):
        d = _make_song_dir(tmp_path, "song_c", hotspots=[{"slide_index": -1}])
        assert screen._build_subtitle(d).endswith("· 매핑 없음")

    def test_partial_mapping_shows_ratio(self, screen, tmp_path):
        d = _make_song_dir(
            tmp_path, "song_d",
            hotspots=[{"slide_index": 0}, {"slide_index": -1}],
        )
        assert screen._build_subtitle(d).endswith("· 매핑 1/2")

    def test_slide_mappings_dict_counts_as_mapped(self, screen, tmp_path):
        d = _make_song_dir(
            tmp_path, "song_e",
            hotspots=[{"slide_index": -1, "slide_mappings": {"0": 3}}],
        )
        assert "매핑" not in screen._build_subtitle(d)

    def test_no_slides_suppresses_mapping_tail(self, screen, tmp_path):
        d = _make_song_dir(tmp_path, "song_f", hotspots=[], slides=False)
        subtitle = screen._build_subtitle(d)
        assert "슬라이드 없음" in subtitle
        assert "매핑" not in subtitle
