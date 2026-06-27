from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtWidgets import QPushButton

from flow.ui.editor.song_list_widget import _LibrarySongCard

_INFO = {
    "name": "곡A", "sheet_count": 1, "has_ppt": False, "has_md": True,
    "total_hotspots": 0, "mapped_hotspots": 0,
}


def test_card_added_state_disables_add_buttons(qtbot):
    card = _LibrarySongCard(_INFO, workspace_mode=True, added=True)
    qtbot.addWidget(card)
    add_buttons = [
        b for b in card.findChildren(QPushButton)
        if b.text() in ("참조", "복사")
    ]
    assert add_buttons, "참조/복사 버튼이 있어야 함"
    assert all(not b.isEnabled() for b in add_buttons)
    from PySide6.QtWidgets import QLabel
    labels = [lbl.text() for lbl in card.findChildren(QLabel)]
    assert any("이미 추가" in t for t in labels)


def test_card_set_added_toggles_state(qtbot):
    card = _LibrarySongCard(_INFO, workspace_mode=True, added=False)
    qtbot.addWidget(card)
    add_buttons = [
        b for b in card.findChildren(QPushButton)
        if b.text() in ("참조", "복사")
    ]
    assert all(b.isEnabled() for b in add_buttons)
    card.set_added(True)
    assert all(not b.isEnabled() for b in add_buttons)


# ─── Task 2: SongLibraryBrowser tests ────────────────────────────────────────


from flow.ui.editor.song_list_widget import SongLibraryBrowser  # noqa: E402


def _make_library(tmp_path: Path, names: list[str]) -> Path:
    lib = tmp_path / "library"
    lib.mkdir()
    for n in names:
        d = lib / n
        d.mkdir()
        (d / "song.json").write_text(json.dumps({"name": n, "sheets": []}), encoding="utf-8")
    return lib


class _FakeWorkspace:
    def __init__(self, lib_dir: Path):
        self.library_dir = lib_dir


def test_browser_shows_all_songs_included_marked(qtbot, tmp_path):
    lib = _make_library(tmp_path, ["곡A", "곡B"])
    ws = _FakeWorkspace(lib)
    browser = SongLibraryBrowser(songs_dir=tmp_path, included_names={"곡A"}, workspace=ws)
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
    lib = _make_library(tmp_path, ["사랑", "은혜"])
    ws = _FakeWorkspace(lib)
    browser = SongLibraryBrowser(songs_dir=tmp_path, included_names=set(), workspace=ws)
    qtbot.addWidget(browser)
    browser._search.setText("사랑")
    names = [c._name for c in browser._cards]
    assert names == ["사랑"]
