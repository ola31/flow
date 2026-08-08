"""악보 이미지 교체 — 핫스팟·매핑을 유지한 채 그림만 바꾼다.

기존에는 교체 수단이 없어 삭제 후 재추가해야 했고, 그러면 그 시트의
핫스팟과 슬라이드 매핑이 통째로 사라졌다.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QFileDialog

from flow.domain.hotspot import Hotspot
from flow.domain.project import Project
from flow.domain.score_sheet import ScoreSheet
from flow.domain.song import Song
from flow.ui.editor.song_list_widget import SongListWidget, _PageCard


def _img(path: Path, color: str, w: int = 100, h: int = 100) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = QImage(w, h, QImage.Format.Format_RGB32)
    img.fill(QColor(color))
    img.save(str(path))
    return path


class _MainWindowStub:
    def __init__(self, project_path: Path):
        self._project_path = project_path
        self._is_live = False
        self.dirty = False

    def _mark_dirty(self):
        self.dirty = True

    def statusBar(self):  # noqa: N802 — Qt 이름 규약 흉내
        class _Bar:
            def showMessage(self, *a):  # noqa: N802
                pass

        return _Bar()


@pytest.fixture
def widget(qtbot, tmp_path):
    song_dir = tmp_path / "song_a"
    _img(song_dir / "sheets" / "old.png", "#ff0000", 100, 100)
    sheet = ScoreSheet(
        name="1장",
        image_path="sheets/old.png",
        hotspots=[Hotspot(x=50, y=40, slide_index=3, lyric="가사")],
    )
    song = Song(
        name="song_a", folder=song_dir, project_dir=tmp_path,
        score_sheets=[sheet],
    )
    w = SongListWidget()
    qtbot.addWidget(w)
    w.set_main_window(_MainWindowStub(song_dir))
    w.set_standalone(True)
    project = Project(name="[곡 편집] song_a")
    project.selected_songs = [song]
    w.set_project(project)
    return w, song, sheet


def _pick(monkeypatch, path: Path) -> None:
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName",
        staticmethod(lambda *a, **k: (str(path), "")),
    )


class TestMenuEntry:
    def test_page_card_offers_replace_image(self, qtbot):
        card = _PageCard(ScoreSheet(name="p", image_path="a.png"), 1, active=False)
        qtbot.addWidget(card)

        labels = [a.text() for a in card._build_context_menu().actions()]

        assert "이미지 교체" in labels

    def test_action_emits_signal(self, qtbot):
        sheet = ScoreSheet(name="p", image_path="a.png")
        card = _PageCard(sheet, 1, active=False)
        qtbot.addWidget(card)
        seen = []
        card.replace_image_requested.connect(seen.append)

        act = next(
            a for a in card._build_context_menu().actions()
            if a.text() == "이미지 교체"
        )
        act.trigger()

        assert seen == [sheet]


class TestReplaceKeepsHotspots:
    def test_image_path_points_to_the_new_file(
        self, widget, tmp_path, monkeypatch
    ):
        w, song, sheet = widget
        _pick(monkeypatch, _img(tmp_path / "inbox" / "new.png", "#0000ff"))

        w._replace_sheet_image(sheet)

        assert sheet.image_path == "sheets/new.png"
        saved = QImage(str(tmp_path / "song_a" / sheet.image_path))
        assert saved.pixelColor(10, 10).name() == "#0000ff"

    def test_hotspots_and_mappings_survive(self, widget, tmp_path, monkeypatch):
        w, song, sheet = widget
        _pick(monkeypatch, _img(tmp_path / "inbox" / "new.png", "#0000ff"))

        w._replace_sheet_image(sheet)

        assert len(sheet.hotspots) == 1
        assert sheet.hotspots[0].slide_index == 3
        assert sheet.hotspots[0].lyric == "가사"

    def test_same_size_leaves_coordinates_untouched(
        self, widget, tmp_path, monkeypatch
    ):
        w, song, sheet = widget
        _pick(monkeypatch, _img(tmp_path / "inbox" / "new.png", "#0000ff", 100, 100))

        w._replace_sheet_image(sheet)

        assert (sheet.hotspots[0].x, sheet.hotspots[0].y) == (50, 40)

    def test_different_size_rescales_coordinates(
        self, widget, tmp_path, monkeypatch
    ):
        """핫스팟은 이미지 픽셀 좌표라, 크기가 바뀌면 비례 보정해야
        같은 자리(가사 위)에 남는다."""
        w, song, sheet = widget
        _pick(
            monkeypatch,
            _img(tmp_path / "inbox" / "new.png", "#0000ff", 200, 300),
        )

        w._replace_sheet_image(sheet)

        assert (sheet.hotspots[0].x, sheet.hotspots[0].y) == (100, 120)

    def test_old_file_is_kept(self, widget, tmp_path, monkeypatch):
        w, song, sheet = widget
        _pick(monkeypatch, _img(tmp_path / "inbox" / "new.png", "#0000ff"))

        w._replace_sheet_image(sheet)

        assert (tmp_path / "song_a" / "sheets" / "old.png").exists()

    def test_canvas_is_told_to_refresh(self, widget, tmp_path, monkeypatch):
        w, song, sheet = widget
        _pick(monkeypatch, _img(tmp_path / "inbox" / "new.png", "#0000ff"))
        seen = []
        w.song_selected.connect(seen.append)

        w._replace_sheet_image(sheet)

        assert seen == [sheet], "교체 후 캔버스가 새 이미지를 다시 읽어야 한다"

    def test_cancelled_dialog_changes_nothing(
        self, widget, tmp_path, monkeypatch
    ):
        w, song, sheet = widget
        monkeypatch.setattr(
            QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: ("", ""))
        )

        w._replace_sheet_image(sheet)

        assert sheet.image_path == "sheets/old.png"
        assert (sheet.hotspots[0].x, sheet.hotspots[0].y) == (50, 40)

    def test_live_mode_blocks_replacement(self, widget, tmp_path, monkeypatch):
        w, song, sheet = widget
        w._main_window._is_live = True
        _pick(monkeypatch, _img(tmp_path / "inbox" / "new.png", "#0000ff"))

        w._replace_sheet_image(sheet)

        assert sheet.image_path == "sheets/old.png"
