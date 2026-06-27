from __future__ import annotations

import json
from pathlib import Path

from flow.ui.live.live_song_add_panel import LiveSongAddPanel


class _FakeWorkspace:
    def __init__(self, lib_dir: Path):
        self.library_dir = lib_dir


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


def test_panel_forwards_song_chosen(qtbot, tmp_path):
    ws = _FakeWorkspace(_make_library(tmp_path, ["곡A"]))
    panel = LiveSongAddPanel(songs_dir=tmp_path, included_names=set(), workspace=ws)
    qtbot.addWidget(panel)
    got = []
    panel.song_chosen.connect(lambda n, s: got.append((n, s)))
    panel._browser.song_chosen.emit("곡A", "library")
    assert got == [("곡A", "library")]


def test_panel_focus_target_is_search(qtbot, tmp_path):
    ws = _FakeWorkspace(_make_library(tmp_path, ["곡A"]))
    panel = LiveSongAddPanel(songs_dir=tmp_path, included_names=set(), workspace=ws)
    qtbot.addWidget(panel)
    assert panel.focus_target() is panel._browser._search


def test_panel_close_button_emits(qtbot, tmp_path):
    ws = _FakeWorkspace(_make_library(tmp_path, ["곡A"]))
    panel = LiveSongAddPanel(songs_dir=tmp_path, included_names=set(), workspace=ws)
    qtbot.addWidget(panel)
    closed = []
    panel.close_requested.connect(lambda: closed.append(True))
    panel._btn_close.click()
    assert closed == [True]


def test_panel_mark_added_delegates(qtbot, tmp_path):
    ws = _FakeWorkspace(_make_library(tmp_path, ["곡A"]))
    panel = LiveSongAddPanel(songs_dir=tmp_path, included_names=set(), workspace=ws)
    qtbot.addWidget(panel)
    panel.mark_added("곡A")
    assert panel._browser._cards[0]._added is True


def test_panel_has_styled_background(qtbot, tmp_path):
    """Fix 3: WA_StyledBackground must be set so the active-highlight CSS renders."""
    from PySide6.QtCore import Qt

    ws = _FakeWorkspace(_make_library(tmp_path, ["곡A"]))
    panel = LiveSongAddPanel(songs_dir=tmp_path, included_names=set(), workspace=ws)
    qtbot.addWidget(panel)
    assert panel.testAttribute(Qt.WidgetAttribute.WA_StyledBackground)
