from __future__ import annotations

from pathlib import Path

from flow.domain.song import Song


def test_markdown_path_default(tmp_path: Path) -> None:
    folder = tmp_path / "song1"
    folder.mkdir()
    song = Song(name="song1", folder=folder, project_dir=tmp_path)
    assert song.markdown_path == folder / "slides.md"


def test_has_markdown_true(tmp_path: Path) -> None:
    folder = tmp_path / "song1"
    folder.mkdir()
    (folder / "slides.md").write_text("# T", encoding="utf-8")
    song = Song(name="song1", folder=folder, project_dir=tmp_path)
    assert song.has_markdown is True


def test_has_markdown_false(tmp_path: Path) -> None:
    folder = tmp_path / "song1"
    folder.mkdir()
    song = Song(name="song1", folder=folder, project_dir=tmp_path)
    assert song.has_markdown is False


def test_slide_source_markdown_wins_when_both_exist(tmp_path: Path) -> None:
    folder = tmp_path / "song1"
    folder.mkdir()
    (folder / "slides.md").write_text("# T", encoding="utf-8")
    (folder / "slides.pptx").write_bytes(b"fake")
    song = Song(name="song1", folder=folder, project_dir=tmp_path)
    assert song.slide_source == "markdown"


def test_slide_source_pptx_when_only_pptx(tmp_path: Path) -> None:
    folder = tmp_path / "song1"
    folder.mkdir()
    (folder / "slides.pptx").write_bytes(b"fake")
    song = Song(name="song1", folder=folder, project_dir=tmp_path)
    assert song.slide_source == "pptx"


def test_slide_source_none_when_neither(tmp_path: Path) -> None:
    folder = tmp_path / "song1"
    folder.mkdir()
    song = Song(name="song1", folder=folder, project_dir=tmp_path)
    assert song.slide_source == "none"
