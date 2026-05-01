from __future__ import annotations

import pytest

from flow.services.markdown.parser import parse


def test_empty_file_yields_zero_slides() -> None:
    spec = parse("")
    assert spec.title == ""
    assert spec.slides == []


def test_just_title_yields_zero_slides() -> None:
    spec = parse("# 어떤 곡\n")
    assert spec.title == "어떤 곡"
    assert spec.slides == []


def test_frontmatter_parses_known_fields() -> None:
    text = """\
---
main_size: 56
main_color: "#FFFFFF"
sub_size: 18
background: "bg.jpg"
slide_inches: "13.333x7.5"
resolution: "1920x1080"
---

# T

가사
"""
    spec = parse(text)
    assert spec.frontmatter.main_size == 56
    assert spec.frontmatter.main_color == "#FFFFFF"
    assert spec.frontmatter.sub_size == 18
    assert spec.frontmatter.background == "bg.jpg"
    assert spec.frontmatter.slide_inches == (13.333, 7.5)
    assert spec.frontmatter.resolution == (1920, 1080)


def test_frontmatter_defaults_when_missing() -> None:
    spec = parse("# T\n\n가사\n")
    fm = spec.frontmatter
    assert fm.main_font == "Pretendard Variable"
    assert fm.main_size == 56
    assert fm.main_color == "#FFFFFF"
    assert fm.sub_font == "Pretendard Variable"
    assert fm.sub_size == 18
    assert fm.sub_color == "#CCCCCC"
    assert fm.background == "#000000"
    assert fm.slide_inches == (13.333, 7.5)
    assert fm.resolution == (1920, 1080)


def test_frontmatter_invalid_value_falls_back_to_default(
    caplog: pytest.LogCaptureFixture,
) -> None:
    text = """\
---
main_size: "not a number"
slide_inches: "garbage"
---

# T
"""
    spec = parse(text)
    # Invalid values fall back to defaults
    assert spec.frontmatter.main_size == 56
    assert spec.frontmatter.slide_inches == (13.333, 7.5)
