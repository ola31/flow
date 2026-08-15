"""라이브러리 검색: 타이핑은 디스크를 건드리지 않는다.

검색어가 재구성 지문에 들어 있어 한 글자마다 전체 라이브러리를 다시
검증했다 — 140곡에서 stat 2400여 회 + 카드 전체 visibility 토글로
키 입력당 50~200ms가 멈췄다. 디스크 상태는 타이핑 사이에 바뀌지 않으므로
검색은 이미 읽어 둔 색인만 훑어야 한다.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from flow.ui.screens import library_screen as ls_mod
from flow.ui.screens.library_screen import LibraryScreen


class _FakeWorkspace:
    def __init__(self, lib: Path):
        self.library_dir = lib
        self.scans = 0

    def list_library_songs(self):
        self.scans += 1
        return sorted(
            d for d in self.library_dir.iterdir()
            if d.is_dir() and (d / "song.json").exists()
        )


def _make_library(tmp_path: Path) -> Path:
    lib = tmp_path / "library"
    for name, lyric in (
        ("song_alpha", "바다 위의 노을"),
        ("song_beta", "하늘을 나는 새"),
        ("song_gamma", "노을 지는 언덕"),
    ):
        d = lib / name
        d.mkdir(parents=True)
        with open(d / "song.json", "w", encoding="utf-8-sig") as f:
            json.dump({"name": name, "sheets": []}, f, ensure_ascii=False)
        (d / "slides.md").write_text(f"# p\n{lyric}\n", encoding="utf-8")
    return lib


@pytest.fixture
def screen(qtbot, tmp_path):
    sc = LibraryScreen()
    qtbot.addWidget(sc)
    ws = _FakeWorkspace(_make_library(tmp_path))
    sc.set_workspace(ws)
    return sc, ws


def _visible_titles(screen) -> list[str]:
    out = []
    for i in range(screen._cards_layout.count()):
        w = screen._cards_layout.itemAt(i).widget()
        if w is not None and not w.isHidden() and hasattr(w, "_path"):
            out.append(Path(w._path).name)
    return out


def _count_disk_calls(monkeypatch) -> dict:
    counts = {"info": 0, "lyrics": 0, "subtitle": 0}
    orig_info, orig_lyrics = ls_mod.song_info, ls_mod.song_lyrics

    def info(p):
        counts["info"] += 1
        return orig_info(p)

    def lyrics(p):
        counts["lyrics"] += 1
        return orig_lyrics(p)

    monkeypatch.setattr(ls_mod, "song_info", info)
    monkeypatch.setattr(ls_mod, "song_lyrics", lyrics)
    orig_sub = LibraryScreen._build_subtitle

    def sub(self, p):
        counts["subtitle"] += 1
        return orig_sub(self, p)

    monkeypatch.setattr(LibraryScreen, "_build_subtitle", sub)
    return counts


class TestTypingDoesNotTouchDisk:
    def test_search_change_does_not_rescan(self, screen, monkeypatch):
        sc, ws = screen
        counts = _count_disk_calls(monkeypatch)
        scans_before = ws.scans

        sc._on_search_changed("노을")

        assert ws.scans == scans_before, "검색인데 라이브러리를 다시 훑음"
        assert counts == {"info": 0, "lyrics": 0, "subtitle": 0}, (
            f"검색 한 번에 디스크 접근 {counts}"
        )

    def test_repeated_typing_stays_disk_free(self, screen, monkeypatch):
        sc, ws = screen
        counts = _count_disk_calls(monkeypatch)
        scans_before = ws.scans  # 픽스처의 최초 로드는 제외

        for q in ("노", "노을", "노을 ", "노을 지"):
            sc._on_search_changed(q)

        assert counts == {"info": 0, "lyrics": 0, "subtitle": 0}
        assert ws.scans == scans_before


class TestSearchStillWorks:
    def test_filters_by_title(self, screen):
        sc, _ = screen

        sc._on_search_changed("alpha")

        assert _visible_titles(sc) == ["song_alpha"]

    def test_filters_by_lyrics_with_snippet(self, screen):
        sc, _ = screen

        sc._on_search_changed("언덕")

        assert _visible_titles(sc) == ["song_gamma"]
        card = next(
            c for k, c in sc._cards.items() if k.endswith("song_gamma")
        )
        assert "언덕" in card._snippet_lbl.text()

    def test_clearing_shows_everything_again(self, screen):
        sc, _ = screen
        sc._on_search_changed("alpha")

        sc._on_search_changed("")

        assert len(_visible_titles(sc)) == 3

    def test_no_match_shows_empty_state(self, screen):
        sc, _ = screen

        sc._on_search_changed("존재하지않는가사")

        assert _visible_titles(sc) == []
        assert not sc._empty_lbl.isHidden()


class TestDiskChangesStillDetected:
    def test_new_song_appears_on_refresh(self, screen, tmp_path):
        sc, ws = screen
        d = tmp_path / "library" / "song_delta"
        d.mkdir()
        with open(d / "song.json", "w", encoding="utf-8-sig") as f:
            json.dump({"name": "song_delta", "sheets": []}, f)

        sc.refresh()

        assert "song_delta" in _visible_titles(sc)

    def test_edited_lyrics_are_searchable_after_refresh(self, screen, tmp_path):
        import time

        sc, _ = screen
        time.sleep(0.01)
        (tmp_path / "library" / "song_beta" / "slides.md").write_text(
            "# p\n새로운 가사 조각\n", encoding="utf-8"
        )

        sc.refresh()
        sc._on_search_changed("조각")

        assert _visible_titles(sc) == ["song_beta"]
