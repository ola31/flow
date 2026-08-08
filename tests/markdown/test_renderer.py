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
    # Red dominates after cover-scaling 4x4 red image to the output canvas.
    assert pixel.red() > 200
    assert pixel.green() < 50
    assert pixel.blue() < 50


def test_render_3_line_slide_uses_3plus_background(qapp, tmp_path: Path) -> None:
    spec = SongSpec(
        title="T",
        frontmatter=Frontmatter(
            background="#112233",
            background_3plus="#445566",
            background_4plus="#778899",
        ),
        slides=[
            Slide(
                main="one\ntwo\nthree",
                sub_override=None,
                section_sub_default=None,
            )
        ],
    )
    img = render_slide(spec, spec.slides[0], song_dir=tmp_path)
    pixel = img.pixelColor(10, 10)
    assert (pixel.red(), pixel.green(), pixel.blue()) == (0x44, 0x55, 0x66)


def test_render_4_line_slide_uses_4plus_background(qapp, tmp_path: Path) -> None:
    spec = SongSpec(
        title="T",
        frontmatter=Frontmatter(
            background="#112233",
            background_3plus="#445566",
            background_4plus="#778899",
        ),
        slides=[
            Slide(
                main="one\ntwo\nthree\nfour",
                sub_override=None,
                section_sub_default=None,
            )
        ],
    )
    img = render_slide(spec, spec.slides[0], song_dir=tmp_path)
    pixel = img.pixelColor(10, 10)
    assert (pixel.red(), pixel.green(), pixel.blue()) == (0x77, 0x88, 0x99)


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


def test_resolve_font_maps_static_pretendard_to_variable() -> None:
    from flow.services.markdown.renderer import resolve_font
    assert resolve_font("Pretendard Medium", 400) == ("Pretendard Variable", 500)
    assert resolve_font("Pretendard Light", 700) == ("Pretendard Variable", 300)
    assert resolve_font("Pretendard Bold", 100) == ("Pretendard Variable", 700)
    assert resolve_font("Pretendard", 500) == ("Pretendard Variable", 400)


def test_resolve_font_passes_through_other_fonts() -> None:
    from flow.services.markdown.renderer import resolve_font
    assert resolve_font("Noto Sans KR", 500) == ("Noto Sans KR", 500)
    assert resolve_font("Pretendard Variable", 500) == ("Pretendard Variable", 500)


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


def test_effective_background_is_public():
    from flow.services.markdown import effective_background, parse, resolve_attrs
    spec = parse("---\n---\n\n# 곡\n\n한 줄 가사\n")
    slide = spec.slides[0]
    attrs = resolve_attrs(spec, slide)
    bg = effective_background(spec, slide, attrs)
    assert bg == spec.frontmatter.background  # 1줄이므로 기본 배경


def _ink_rows(img: QImage) -> tuple[int, int]:
    """본문 가사가 그려진 세로 범위 (첫 행, 마지막 행).

    슬라이드 하단에는 보조 텍스트가 늘 함께 그려지므로, 잉크가 있는
    구간을 묶은 뒤 맨 아래 덩어리(보조 텍스트)를 빼고 본문만 잰다.
    """
    rows = []
    for y in range(img.height()):
        for x in range(0, img.width(), 3):  # 3px 간격이면 충분히 잡힌다
            c = img.pixelColor(x, y)
            if c.red() > 60 or c.green() > 60 or c.blue() > 60:
                rows.append(y)
                break

    bands: list[list[int]] = []
    for y in rows:
        if bands and y - bands[-1][1] <= 2:
            bands[-1][1] = y
        else:
            bands.append([y, y])

    main = bands[:-1]  # 마지막 덩어리는 하단 보조 텍스트
    if not main:
        return -1, -1
    return main[0][0], main[-1][1]


def _render(main: str, **fm_kw) -> QImage:
    fm = Frontmatter(background="#000000", **fm_kw)
    slide = Slide(main=main, sub_override=None, section_sub_default=None)
    spec = SongSpec(title="T", frontmatter=fm, slides=[slide])
    return render_slide(spec, slide, song_dir=Path("."))


class TestSingleLineIsLifted:
    """한 줄 가사가 두 줄 기준의 '아랫줄' 자리에 놓여 아래로 치우치던 문제.

    아래 정렬(anchor=bottom)이라 줄 수가 적을수록 아래로 몰린다 —
    한 줄은 반 줄만큼 올려 두 줄이 차지했을 영역의 가운데에 오게 한다.
    """

    def test_single_line_sits_above_the_two_line_bottom(self, qapp) -> None:
        one_top, one_bottom = _ink_rows(_render("한 줄"))
        _, two_bottom = _ink_rows(_render("첫 줄\n둘째 줄"))

        assert one_top >= 0 and two_bottom >= 0
        assert one_bottom < two_bottom, "한 줄이 두 줄짜리의 아랫줄보다 위여야 한다"

    def test_single_line_lands_near_the_two_line_middle(self, qapp) -> None:
        one_top, one_bottom = _ink_rows(_render("한 줄"))
        two_top, two_bottom = _ink_rows(_render("첫 줄\n둘째 줄"))

        one_mid = (one_top + one_bottom) / 2
        two_mid = (two_top + two_bottom) / 2
        # 두 줄 블록의 세로 가운데 근처 — 한 줄 높이의 절반 안쪽
        assert abs(one_mid - two_mid) < (one_bottom - one_top + 1)

    def test_lift_zero_restores_the_old_position(self, qapp) -> None:
        _, lifted = _ink_rows(_render("한 줄"))
        _, unlifted = _ink_rows(_render("한 줄", single_line_lift=0.0))

        assert lifted < unlifted

    def test_two_line_slide_is_unchanged_by_the_lift(self, qapp) -> None:
        a = _ink_rows(_render("첫 줄\n둘째 줄"))
        b = _ink_rows(_render("첫 줄\n둘째 줄", single_line_lift=0.0))

        assert a == b
