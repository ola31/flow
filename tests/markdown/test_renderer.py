# tests/markdown/test_renderer.py
from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtGui import QImage

from flow.services.markdown.parser import (
    Frontmatter,
    Slide,
    SongSpec,
)
from flow.services.markdown.renderer import render_slide


def _make_spec(background: str = "#000000") -> SongSpec:
    fm = Frontmatter(background=background)
    slides = [Slide(main="hi", sub_override=None, section_sub_default=None)]
    return SongSpec(title="T", frontmatter=fm, slides=slides)


def test_render_returns_qimage_at_resolution(qapp_args, tmp_path: Path) -> None:
    spec = _make_spec()
    img = render_slide(spec, spec.slides[0], song_dir=tmp_path)
    assert isinstance(img, QImage)
    assert img.width() == 1920
    assert img.height() == 1080


def test_render_solid_color_background(qapp_args, tmp_path: Path) -> None:
    spec = _make_spec(background="#112233")
    img = render_slide(spec, spec.slides[0], song_dir=tmp_path)
    pixel = img.pixelColor(10, 10)
    assert pixel.red() == 0x11
    assert pixel.green() == 0x22
    assert pixel.blue() == 0x33


def test_render_image_background_used_when_file_exists(
    qapp_args, tmp_path: Path
) -> None:
    # Create a tiny red 4x4 PNG as the background
    bg = QImage(4, 4, QImage.Format.Format_RGB32)
    bg.fill(0xFFFF0000)  # ARGB: opaque red
    bg_path = tmp_path / "bg.png"
    assert bg.save(str(bg_path))

    spec = SongSpec(
        title="T",
        frontmatter=Frontmatter(background="bg.png"),
        slides=[Slide(main="hi", sub_override=None, section_sub_default=None)],
    )
    img = render_slide(spec, spec.slides[0], song_dir=tmp_path)
    pixel = img.pixelColor(10, 10)
    # Red dominates after cover-scaling 4x4 red image to 1920x1080
    assert pixel.red() > 200
    assert pixel.green() < 50
    assert pixel.blue() < 50


def test_render_missing_image_falls_back_to_default_color(
    qapp_args, tmp_path: Path, caplog: pytest.LogCaptureFixture,
) -> None:
    spec = SongSpec(
        title="T",
        frontmatter=Frontmatter(background="missing.jpg"),
        slides=[Slide(main="hi", sub_override=None, section_sub_default=None)],
    )
    img = render_slide(spec, spec.slides[0], song_dir=tmp_path)
    # Falls back to black (default color for missing-image path)
    pixel = img.pixelColor(10, 10)
    assert pixel.red() == 0 and pixel.green() == 0 and pixel.blue() == 0
