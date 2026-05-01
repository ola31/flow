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


def test_render_returns_qimage_at_resolution(qapp, tmp_path: Path) -> None:
    spec = _make_spec()
    img = render_slide(spec, spec.slides[0], song_dir=tmp_path)
    assert isinstance(img, QImage)
    assert img.width() == 1920
    assert img.height() == 1080


def test_render_solid_color_background(qapp, tmp_path: Path) -> None:
    spec = _make_spec(background="#112233")
    img = render_slide(spec, spec.slides[0], song_dir=tmp_path)
    pixel = img.pixelColor(10, 10)
    assert pixel.red() == 0x11
    assert pixel.green() == 0x22
    assert pixel.blue() == 0x33


def test_render_image_background_used_when_file_exists(
    qapp, tmp_path: Path
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
    qapp, tmp_path: Path, caplog: pytest.LogCaptureFixture,
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


def test_render_main_text_visible_in_main_box(qapp, tmp_path: Path) -> None:
    """Main text region (top 36.3%, height 30%) should differ from background."""
    spec = SongSpec(
        title="T",
        frontmatter=Frontmatter(
            background="#000000",
            main_color="#FFFFFF",
            main_size=72,
        ),
        slides=[Slide(main="ABCDEFG", sub_override=None, section_sub_default=None)],
    )
    img = render_slide(spec, spec.slides[0], song_dir=tmp_path)
    width, height = img.width(), img.height()
    main_y_start = int(height * 0.36)
    main_y_end = int(height * 0.66)
    found_text_pixel = False
    for y in range(main_y_start, main_y_end, 10):
        for x in range(int(width * 0.3), int(width * 0.7), 20):
            p = img.pixelColor(x, y)
            if p.red() > 200 and p.green() > 200 and p.blue() > 200:
                found_text_pixel = True
                break
        if found_text_pixel:
            break
    assert found_text_pixel, "main text not visible in expected region"


def test_render_sub_text_visible_in_sub_box(qapp, tmp_path: Path) -> None:
    """Sub text region (top 89.7%, height 8%) should differ from background."""
    spec = SongSpec(
        title="SUBTITLE",
        frontmatter=Frontmatter(
            background="#000000",
            sub_color="#CCCCCC",
            sub_size=32,
        ),
        slides=[Slide(main="main", sub_override=None, section_sub_default=None)],
    )
    img = render_slide(spec, spec.slides[0], song_dir=tmp_path)
    width, height = img.width(), img.height()
    found = False
    for y in range(int(height * 0.90), int(height * 0.97), 2):
        for x in range(int(width * 0.30), int(width * 0.70), 5):
            p = img.pixelColor(x, y)
            if p.red() > 100 and p.green() > 100 and p.blue() > 100:
                found = True
                break
        if found:
            break
    assert found, "sub text not visible in expected region"


def test_pt_to_pixel_conversion() -> None:
    """At slide_inches=(13.333, 7.5), resolution=(1920, 1080):
    DPI = 1080 / 7.5 = 144. So 72pt = 1in = 144px.
    """
    from flow.services.markdown.renderer import _pt_to_px
    px = _pt_to_px(72, slide_inches=(13.333, 7.5), resolution=(1920, 1080))
    assert px == pytest.approx(144, abs=1)


def test_pt_to_pixel_with_smaller_canvas() -> None:
    """At smaller canvas (e.g. user PPT 11.02×6.20), DPI is higher.
    DPI = 1080 / 6.20 ≈ 174.
    """
    from flow.services.markdown.renderer import _pt_to_px
    px = _pt_to_px(72, slide_inches=(11.02, 6.20), resolution=(1920, 1080))
    assert px == pytest.approx(174, abs=1)


def test_render_all_returns_one_image_per_slide(qapp, tmp_path: Path) -> None:
    from flow.services.markdown.parser import parse
    from flow.services.markdown.renderer import render_all

    text = """\
# T

가사 1

가사 2

가사 3
"""
    spec = parse(text)
    images = render_all(spec, song_dir=tmp_path)
    assert len(images) == 3
    assert all(isinstance(img, QImage) for img in images)
