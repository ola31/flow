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
background_3plus: "bg_3.jpg"
background_4plus: "bg_4.jpg"
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
    assert spec.frontmatter.background_3plus == "bg_3.jpg"
    assert spec.frontmatter.background_4plus == "bg_4.jpg"
    assert spec.frontmatter.slide_inches == (13.333, 7.5)
    assert spec.frontmatter.resolution == (1920, 1080)


def test_empty_frontmatter_not_treated_as_slide() -> None:
    """빈 frontmatter(--- 바로 아래 ---)가 '---' 텍스트 슬라이드가 되면 안 된다."""
    text = "---\n---\n\n# 제목\n\n첫 가사\n"
    spec = parse(text)
    assert spec.title == "제목"
    assert [s.main for s in spec.slides] == ["첫 가사"]


def test_blank_line_only_frontmatter_not_treated_as_slide() -> None:
    text = "---\n\n---\n\n# 제목\n\n첫 가사\n"
    spec = parse(text)
    assert spec.title == "제목"
    assert [s.main for s in spec.slides] == ["첫 가사"]


def test_strip_frontmatter_handles_empty_block() -> None:
    from flow.services.markdown.parser import strip_frontmatter

    assert strip_frontmatter("---\n---\n가사\n") == "가사\n"


def test_frontmatter_defaults_when_missing() -> None:
    spec = parse("# T\n\n가사\n")
    fm = spec.frontmatter
    assert fm.main_font == "Pretendard Variable"
    assert fm.main_size == 38
    assert fm.main_weight == 500
    assert fm.main_color == "#F0F0F0"
    assert fm.sub_font == "Pretendard Variable"
    assert fm.sub_size == 20
    assert fm.sub_weight == 300
    assert fm.sub_color == "#F0F0F0"
    assert fm.background == "@app/default_bg.jpg"
    assert fm.background_3plus == "@app/default_bg_3plus.jpg"
    assert fm.background_4plus == "@app/default_bg_4plus.jpg"
    assert fm.slide_inches == (11.024, 6.201)
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
    assert spec.frontmatter.main_size == 38
    assert spec.frontmatter.slide_inches == (11.024, 6.201)


def test_two_slide_blocks() -> None:
    spec = parse("# T\n\n첫 슬라이드\n\n둘째 슬라이드\n")
    assert len(spec.slides) == 2
    assert spec.slides[0].main == "첫 슬라이드"
    assert spec.slides[1].main == "둘째 슬라이드"


def test_multiline_main_text() -> None:
    spec = parse("# T\n\n첫 줄\n둘째 줄\n셋째 줄\n")
    assert len(spec.slides) == 1
    assert spec.slides[0].main == "첫 줄\n둘째 줄\n셋째 줄"


def test_section_header_does_not_become_slide() -> None:
    spec = parse("# T\n\n## 1절\n\n가사\n")
    assert len(spec.slides) == 1
    assert spec.slides[0].main == "가사"


def test_multiple_blank_lines_treated_as_one_separator() -> None:
    spec = parse("# T\n\n첫\n\n\n\n둘째\n")
    assert len(spec.slides) == 2


def test_title_line_not_part_of_first_slide() -> None:
    spec = parse("# 어떤 곡\n\n첫 가사\n")
    assert len(spec.slides) == 1
    assert spec.slides[0].main == "첫 가사"


def test_sub_override_attached_to_slide() -> None:
    text = "# T\n\n첫 슬라이드\n둘째 줄\n> sub for slide\n"
    spec = parse(text)
    assert len(spec.slides) == 1
    assert spec.slides[0].main == "첫 슬라이드\n둘째 줄"
    assert spec.slides[0].sub_override == "sub for slide"


def test_sub_override_only_when_last_line() -> None:
    """A `>` line in the middle of a slide is just main text, not sub override."""
    text = "# T\n\n첫 줄\n> middle quote\n셋째 줄\n"
    spec = parse(text)
    assert len(spec.slides) == 1
    assert spec.slides[0].main == "첫 줄\n> middle quote\n셋째 줄"
    assert spec.slides[0].sub_override is None


def test_section_sub_default_applies_to_following_slides() -> None:
    text = """\
# T

## 1절 :: 어떤 곡 1절

첫 슬라이드

다음 슬라이드

## 후렴

후렴 슬라이드
"""
    spec = parse(text)
    assert len(spec.slides) == 3
    assert spec.slides[0].section_sub_default == "어떤 곡 1절"
    assert spec.slides[1].section_sub_default == "어떤 곡 1절"
    assert spec.slides[2].section_sub_default is None  # ## 후렴 has no ::


def test_section_without_double_colon_clears_default() -> None:
    text = """\
# T

## 1절 :: 어떤 곡 1절

첫

## 후렴

둘째
"""
    spec = parse(text)
    assert spec.slides[0].section_sub_default == "어떤 곡 1절"
    assert spec.slides[1].section_sub_default is None


def test_slide_override_first_line_parsed() -> None:
    text = "# T\n\n{main_size: 72, main_color: \"#FFD700\"}\n강조 슬라이드\n"
    spec = parse(text)
    assert len(spec.slides) == 1
    assert spec.slides[0].main == "강조 슬라이드"
    assert spec.slides[0].overrides == {
        "main_size": 72,
        "main_color": "#FFD700",
    }


def test_slide_override_must_be_first_line() -> None:
    text = "# T\n\n첫 줄\n{main_size: 72}\n둘째 줄\n"
    spec = parse(text)
    assert spec.slides[0].overrides == {}
    assert "{main_size: 72}" in spec.slides[0].main


def test_slide_override_invalid_yaml_ignored(caplog: pytest.LogCaptureFixture) -> None:
    text = "# T\n\n{not valid yaml\n가사\n"
    spec = parse(text)
    assert spec.slides[0].overrides == {}
    # Should still parse rest of slide normally
    assert "가사" in spec.slides[0].main


def test_slide_override_with_sub() -> None:
    text = "# T\n\n{main_size: 72}\n강조\n> custom sub\n"
    spec = parse(text)
    assert spec.slides[0].overrides == {"main_size": 72}
    assert spec.slides[0].main == "강조"
    assert spec.slides[0].sub_override == "custom sub"


from flow.services.markdown.parser import resolve_attrs  # noqa: E402


def test_resolve_uses_frontmatter_when_no_overrides() -> None:
    spec = parse("# T\n\n가사\n")
    attrs = resolve_attrs(spec, spec.slides[0])
    assert attrs.main_font == spec.frontmatter.main_font
    assert attrs.main_size == spec.frontmatter.main_size
    assert attrs.main_color == spec.frontmatter.main_color
    assert attrs.background == spec.frontmatter.background
    assert attrs.sub_text == "T"  # falls back to title


def test_resolve_slide_override_wins() -> None:
    text = "# T\n\n{main_size: 72, main_color: \"#FFD700\"}\n강조\n"
    spec = parse(text)
    attrs = resolve_attrs(spec, spec.slides[0])
    assert attrs.main_size == 72
    assert attrs.main_color == "#FFD700"
    # sub_size/font fall through to frontmatter
    assert attrs.sub_size == spec.frontmatter.sub_size


def test_resolve_sub_text_priority() -> None:
    text = """\
# 곡 제목

## 1절 :: 곡 제목 1절

기본
> 직접 적은 sub

기본만
"""
    spec = parse(text)
    # First slide has > override
    attrs0 = resolve_attrs(spec, spec.slides[0])
    assert attrs0.sub_text == "직접 적은 sub"
    # Second slide uses section default
    attrs1 = resolve_attrs(spec, spec.slides[1])
    assert attrs1.sub_text == "곡 제목 1절"


def test_resolve_sub_text_falls_back_to_title() -> None:
    text = "# 곡 제목\n\n가사\n"
    spec = parse(text)
    attrs = resolve_attrs(spec, spec.slides[0])
    assert attrs.sub_text == "곡 제목"


def test_resolve_sub_text_empty_when_no_title() -> None:
    text = "가사\n"
    spec = parse(text)
    attrs = resolve_attrs(spec, spec.slides[0])
    assert attrs.sub_text == ""
