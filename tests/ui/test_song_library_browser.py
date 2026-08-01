from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtWidgets import QPushButton

from flow.ui.editor.song_list_widget import _LibrarySongCard

_INFO = {
    "name": "곡A", "sheet_count": 1, "has_ppt": False, "has_md": True,
    "total_hotspots": 0, "mapped_hotspots": 0,
}


def _search(browser, qtbot, text: str) -> None:
    """검색어 입력 후 디바운스 렌더 완료까지 대기."""
    browser._search.setText(text)
    qtbot.waitUntil(lambda: not browser._filter_timer.isActive(), timeout=2000)


def test_card_added_state_still_allows_adding_again(qtbot):
    """같은 곡을 오전·오후에 각각 부를 수 있어야 한다 — 배지로 알리되
    버튼은 계속 열어 둔다 (셋리스트에 한 번 더 들어간다)."""
    card = _LibrarySongCard(_INFO, workspace_mode=True, added=True)
    qtbot.addWidget(card)
    add_buttons = [
        b for b in card.findChildren(QPushButton)
        if b.text() in ("참조", "복사")
    ]
    assert add_buttons, "참조/복사 버튼이 있어야 함"
    assert all(b.isEnabled() for b in add_buttons)
    from PySide6.QtWidgets import QLabel
    labels = [lbl.text() for lbl in card.findChildren(QLabel)]
    assert any("이미 추가" in t for t in labels)


def test_card_set_added_toggles_badge_only(qtbot):
    card = _LibrarySongCard(_INFO, workspace_mode=True, added=False)
    qtbot.addWidget(card)
    add_buttons = [
        b for b in card.findChildren(QPushButton)
        if b.text() in ("참조", "복사")
    ]
    assert all(b.isEnabled() for b in add_buttons)

    card.set_added(True)

    assert card._added is True
    assert card._added_badge.isVisibleTo(card)
    assert all(b.isEnabled() for b in add_buttons)  # 다시 넣을 수 있다


# ─── Task 2: SongLibraryBrowser tests ────────────────────────────────────────


from flow.ui.editor.song_list_widget import SongLibraryBrowser  # noqa: E402


def _make_library(tmp_path: Path, names: list[str]) -> Path:
    lib = tmp_path / "library"
    lib.mkdir()
    for n in names:
        d = lib / n
        d.mkdir()
        (d / "song.json").write_text(
            json.dumps({"name": n, "sheets": []}), encoding="utf-8"
        )
    return lib


class _FakeWorkspace:
    def __init__(self, lib_dir: Path):
        self.library_dir = lib_dir


def test_browser_shows_all_songs_included_marked(qtbot, tmp_path):
    lib = _make_library(tmp_path, ["곡A", "곡B"])
    ws = _FakeWorkspace(lib)
    browser = SongLibraryBrowser(
        songs_dir=tmp_path, included_names={"곡A"}, workspace=ws
    )
    qtbot.addWidget(browser)
    cards = {c._name: c for c in browser._cards}
    assert set(cards) == {"곡A", "곡B"}
    assert cards["곡A"]._added is True
    assert cards["곡B"]._added is False


def test_browser_marks_added(qtbot, tmp_path):
    lib = _make_library(tmp_path, ["곡A"])
    ws = _FakeWorkspace(lib)
    browser = SongLibraryBrowser(songs_dir=tmp_path, included_names=set(), workspace=ws)
    qtbot.addWidget(browser)
    browser.mark_added("곡A")
    assert browser._cards[0]._added is True


def test_browser_filter(qtbot, tmp_path):
    lib = _make_library(tmp_path, ["바다", "하늘"])
    ws = _FakeWorkspace(lib)
    browser = SongLibraryBrowser(songs_dir=tmp_path, included_names=set(), workspace=ws)
    qtbot.addWidget(browser)
    _search(browser, qtbot, "바다")
    names = [c._name for c in browser._cards]
    assert names == ["바다"]


def _make_md_song(lib: Path, name: str, slides_md: str) -> None:
    d = lib / name
    d.mkdir()
    (d / "song.json").write_text(
        json.dumps({"name": name, "sheets": []}), encoding="utf-8"
    )
    (d / "slides.md").write_text(slides_md, encoding="utf-8")


def test_browser_filter_matches_markdown_lyrics(qtbot, tmp_path):
    lib = tmp_path / "library"
    lib.mkdir()
    _make_md_song(
        lib, "첫째곡",
        '---\nmain_size: 56\nbackground: "#000000"\n---\n\n'
        "# 첫째곡\n\n푸른 바다가 보이네\n",
    )
    _make_md_song(lib, "둘째곡", "---\n---\n\n# 둘째곡\n\n노을이 물든다\n")
    ws = _FakeWorkspace(lib)
    browser = SongLibraryBrowser(songs_dir=tmp_path, included_names=set(), workspace=ws)
    qtbot.addWidget(browser)

    # 제목엔 없고 가사에만 있는 단어로 검색 → 해당 곡이 잡힘
    _search(browser, qtbot, "바다")
    assert [c._name for c in browser._cards] == ["첫째곡"]

    # frontmatter 설정값(background)은 검색에 걸리지 않음
    _search(browser, qtbot, "background")
    assert browser._cards == []

    # 제목 검색은 그대로 동작
    _search(browser, qtbot, "둘째")
    assert [c._name for c in browser._cards] == ["둘째곡"]


def test_browser_shows_lyric_snippet_for_lyric_match(qtbot, tmp_path):
    lib = tmp_path / "library"
    lib.mkdir()
    _make_md_song(lib, "곡A", "---\n---\n\n# 곡A\n\n푸른 바다가 보이네\n노을이 물든다\n")
    ws = _FakeWorkspace(lib)
    browser = SongLibraryBrowser(songs_dir=tmp_path, included_names=set(), workspace=ws)
    qtbot.addWidget(browser)

    # 가사로 매칭 → 매칭된 가사 줄이 카드에 표시됨
    _search(browser, qtbot, "바다")
    assert "바다가 보이네" in browser._cards[0]._match_snippet

    # 제목으로 매칭 → 스니펫 없음
    _search(browser, qtbot, "곡A")
    assert browser._cards[0]._match_snippet == ""

    # 검색어 없음 → 스니펫 없음
    browser._search.setText("")
    assert browser._cards[0]._match_snippet == ""
