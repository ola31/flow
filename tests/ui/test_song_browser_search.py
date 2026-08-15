"""곡 추가 브라우저 검색 — 타이핑은 디스크를 건드리지 않고, 디바운스는
라이브러리 화면과 같은 상수를 쓴다.

_filter가 키 입력마다 song_lyrics()를 부르면 곡당 slides.md를 stat 한다
(140곡이면 키당 140회). 스캔 때 담아 둔 소문자 가사만 훑으면 된다.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from flow.ui.editor import song_list_widget as slw
from flow.ui.editor.song_list_widget import SongLibraryBrowser
from flow.ui.screens._browser_widgets import SEARCH_DEBOUNCE_MS


def _library(tmp_path: Path) -> Path:
    for name, lyric in (
        ("song_alpha", "바다 위의 노을"),
        ("song_beta", "하늘을 나는 새"),
    ):
        d = tmp_path / name
        d.mkdir(parents=True)
        with open(d / "song.json", "w", encoding="utf-8-sig") as f:
            json.dump({"name": name, "sheets": []}, f, ensure_ascii=False)
        (d / "slides.md").write_text(f"# p\n{lyric}\n", encoding="utf-8")
    return tmp_path


@pytest.fixture
def browser(qtbot, tmp_path):
    b = SongLibraryBrowser(_library(tmp_path), set())
    qtbot.addWidget(b)
    return b


def test_typing_does_not_read_lyrics_from_disk(browser, monkeypatch):
    calls = []
    orig = slw.song_lyrics if hasattr(slw, "song_lyrics") else None

    import flow.services.song_index as si

    real = si.song_lyrics

    def counted(p):
        calls.append(p)
        return real(p)

    monkeypatch.setattr(si, "song_lyrics", counted)
    if orig is not None:
        monkeypatch.setattr(slw, "song_lyrics", counted)

    browser._filter("노을")

    assert calls == [], f"검색 한 번에 가사 파일 조회 {len(calls)}회"


def test_lyric_search_still_matches(browser):
    browser._filter("노을")

    names = [c._name for c in browser._cards]
    assert names == ["song_alpha"]


def test_title_search_still_matches(browser):
    browser._filter("beta")

    assert [c._name for c in browser._cards] == ["song_beta"]


def test_debounce_uses_the_shared_constant(browser):
    assert browser._filter_timer.interval() == SEARCH_DEBOUNCE_MS


class TestSwitcherSearch:
    """편집 화면 좌측 곡 전환 목록도 같은 규칙을 따른다."""

    def _switcher(self, qtbot, tmp_path):
        from flow.ui.editor.song_list_widget import _LibrarySongSwitcher

        sw = _LibrarySongSwitcher(_library(tmp_path), "song_beta")
        qtbot.addWidget(sw)
        return sw

    def test_typing_does_not_read_lyrics_from_disk(
        self, qtbot, tmp_path, monkeypatch
    ):
        sw = self._switcher(qtbot, tmp_path)
        import flow.services.song_index as si

        calls = []
        real = si.song_lyrics
        monkeypatch.setattr(
            si, "song_lyrics", lambda p: (calls.append(p), real(p))[1]
        )

        sw._filter("노을")

        assert calls == [], f"검색 한 번에 가사 파일 조회 {len(calls)}회"

    def test_lyric_search_still_matches_with_snippet(self, qtbot, tmp_path):
        sw = self._switcher(qtbot, tmp_path)

        sw._filter("노을")

        visible = [r for r in sw._rows if not r.isHidden()]
        assert [r._name for r in visible] == ["song_alpha"]
        assert "노을" in visible[0]._snippet

    def test_search_is_debounced_with_the_shared_constant(self, qtbot, tmp_path):
        sw = self._switcher(qtbot, tmp_path)

        assert sw._filter_timer.interval() == SEARCH_DEBOUNCE_MS
