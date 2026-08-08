"""악보 이미지 추가 — 같은 파일명이어도 기존 악보를 파괴하지 않는다.

기존에는 sheets/ 안 같은 이름 파일을 말없이 덮어써서, 원래 악보 이미지가
사라지고 두 시트가 같은 경로를 가리켰다. 게다가 캔버스 픽스맵 캐시가
경로만 키로 써서 파일이 바뀌어도 옛 이미지가 계속 표시됐다.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QFileDialog, QInputDialog

from flow.domain.project import Project
from flow.domain.score_sheet import ScoreSheet
from flow.domain.song import Song
from flow.ui.editor.score_canvas import ScoreCanvas
from flow.ui.editor.song_list_widget import SongListWidget


def _img(path: Path, color: str) -> Path:
    img = QImage(40, 40, QImage.Format.Format_RGB32)
    img.fill(QColor(color))
    img.save(str(path))
    return path


class _MainWindowStub:
    def __init__(self, project_path: Path):
        self._project_path = project_path
        self._is_live = False

    def _mark_dirty(self):
        pass

    def statusBar(self):  # noqa: N802 — Qt 이름 규약 흉내
        class _Bar:
            def showMessage(self, *a):  # noqa: N802
                pass

        return _Bar()


@pytest.fixture
def song_widget(qtbot, tmp_path):
    song_dir = tmp_path / "song_a"
    (song_dir / "sheets").mkdir(parents=True)
    _img(song_dir / "sheets" / "scan.png", "#ff0000")  # 기존 악보(빨강)

    song = Song(
        name="song_a",
        folder=song_dir,
        project_dir=tmp_path,
        score_sheets=[ScoreSheet(name="기존악보", image_path="sheets/scan.png")],
    )
    widget = SongListWidget()
    qtbot.addWidget(widget)
    widget.set_main_window(_MainWindowStub(song_dir))
    widget.set_standalone(True)
    project = Project(name="[곡 편집] song_a")
    project.selected_songs = [song]
    widget.set_project(project)
    return widget, song


def _pick(monkeypatch, paths: list[Path]) -> None:
    monkeypatch.setattr(
        QFileDialog, "getOpenFileNames",
        staticmethod(lambda *a, **k: ([str(p) for p in paths], "")),
    )
    monkeypatch.setattr(
        QInputDialog, "getText",
        staticmethod(lambda *a, **k: ("새 악보", True)),
    )


class TestNameCollision:
    def test_existing_sheet_image_is_not_overwritten(
        self, song_widget, tmp_path, monkeypatch
    ):
        widget, song = song_widget
        (tmp_path / "다운로드").mkdir(exist_ok=True)
        _img(tmp_path / "다운로드" / "scan.png", "#0000ff")
        _pick(monkeypatch, [tmp_path / "다운로드" / "scan.png"])

        widget._set_song_image(song)

        kept = QImage(str(tmp_path / "song_a" / "sheets" / "scan.png"))
        assert kept.pixelColor(20, 20).name() == "#ff0000", (
            "기존 악보 이미지가 덮어써짐 — 데이터 손실"
        )

    def test_added_sheet_gets_its_own_path(
        self, song_widget, tmp_path, monkeypatch
    ):
        widget, song = song_widget
        (tmp_path / "다운로드").mkdir(exist_ok=True)
        _img(tmp_path / "다운로드" / "scan.png", "#0000ff")
        _pick(monkeypatch, [tmp_path / "다운로드" / "scan.png"])

        widget._set_song_image(song)

        paths = [s.image_path for s in song.score_sheets]
        assert len(paths) == len(set(paths)), f"시트 경로가 중복됨: {paths}"

    def test_added_image_content_is_the_new_one(
        self, song_widget, tmp_path, monkeypatch
    ):
        widget, song = song_widget
        (tmp_path / "다운로드").mkdir(exist_ok=True)
        _img(tmp_path / "다운로드" / "scan.png", "#0000ff")
        _pick(monkeypatch, [tmp_path / "다운로드" / "scan.png"])

        widget._set_song_image(song)

        added = song.score_sheets[-1]
        saved = QImage(str(tmp_path / "song_a" / added.image_path))
        assert saved.pixelColor(20, 20).name() == "#0000ff"

    def test_identical_file_is_not_duplicated(
        self, song_widget, tmp_path, monkeypatch
    ):
        """같은 내용의 파일을 다시 고르면 사본을 만들지 않는다."""
        widget, song = song_widget
        (tmp_path / "다운로드").mkdir(exist_ok=True)
        _img(tmp_path / "다운로드" / "scan.png", "#ff0000")  # 내용 동일
        _pick(monkeypatch, [tmp_path / "다운로드" / "scan.png"])

        widget._set_song_image(song)

        files = list((tmp_path / "song_a" / "sheets").iterdir())
        assert len(files) == 1, f"동일 내용인데 사본 생성됨: {files}"


class TestCanvasCacheHonoursFileChange:
    def test_replaced_file_shows_new_image(self, qtbot, tmp_path):
        """파일이 교체되면 캔버스는 새 이미지를 보여야 한다.

        캐시 키가 경로뿐이면 곡 폴더에서 악보를 바꿔치기해도 앱을 껐다
        켜기 전까지 옛 이미지가 남는다.
        """
        song_dir = tmp_path / "song_a"
        (song_dir / "sheets").mkdir(parents=True)
        target = _img(song_dir / "sheets" / "p1.png", "#ff0000")

        canvas = ScoreCanvas()
        qtbot.addWidget(canvas)
        sheet = ScoreSheet(name="p1", image_path="sheets/p1.png")
        canvas.set_score_sheet(sheet, str(song_dir))
        assert canvas._pixmap.toImage().pixelColor(20, 20).name() == "#ff0000"

        import os
        import time

        time.sleep(0.01)
        _img(target, "#0000ff")
        os.utime(target)  # mtime 갱신 보장

        canvas.set_score_sheet(sheet, str(song_dir))

        assert canvas._pixmap.toImage().pixelColor(20, 20).name() == "#0000ff"
