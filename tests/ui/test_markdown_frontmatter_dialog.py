from __future__ import annotations

from flow.ui.editor.markdown_frontmatter_dialog import (
    FrontmatterDialog,
    SlideSizePicker,
    apply_frontmatter_to_text,
    extract_raw_frontmatter,
)


def test_apply_to_text_replaces_existing_frontmatter() -> None:
    original = """\
---
main_size: 56
---

# T

가사
"""
    new = apply_frontmatter_to_text(original, {"main_size": 72})
    assert "main_size: 72" in new
    assert "# T" in new
    assert "가사" in new


def test_apply_to_text_inserts_when_no_frontmatter() -> None:
    original = "# T\n\n가사\n"
    new = apply_frontmatter_to_text(original, {"main_size": 72})
    assert new.startswith("---\n")
    assert "main_size: 72" in new
    assert "# T" in new


def test_apply_to_text_strips_when_raw_is_empty() -> None:
    original = "---\nmain_size: 56\n---\n\n# T\n"
    new = apply_frontmatter_to_text(original, {})
    assert not new.startswith("---")
    assert "# T" in new


def test_apply_to_text_writes_only_given_keys() -> None:
    """Should not expand frontmatter with system defaults."""
    new = apply_frontmatter_to_text("# T\n", {"main_size": 56})
    assert "main_size: 56" in new
    assert "main_font" not in new
    assert "background" not in new


def test_extract_raw_frontmatter_returns_only_explicit_keys() -> None:
    text = "---\nmain_size: 56\nbackground: '#000'\n---\n\n# T\n"
    raw = extract_raw_frontmatter(text)
    assert raw == {"main_size": 56, "background": "#000"}


def test_extract_raw_frontmatter_empty_when_missing() -> None:
    assert extract_raw_frontmatter("# T\n") == {}


def test_slide_size_picker_matches_preset(qtbot) -> None:
    p = SlideSizePicker()
    qtbot.addWidget(p)
    p.set_value("11.024 x 6.201")  # spaces should normalize
    assert p.value() == "11.024x6.201"


def test_slide_size_picker_falls_back_to_custom(qtbot) -> None:
    p = SlideSizePicker()
    qtbot.addWidget(p)
    p.set_value("12x9")
    assert p.value() == "12x9"


def test_dialog_skips_slide_size_when_default_and_not_originally_set(qtbot) -> None:
    dlg = FrontmatterDialog(original_raw={})
    qtbot.addWidget(dlg)
    assert "slide_inches" not in dlg.result_raw()


def test_dialog_writes_slide_size_when_originally_present(qtbot) -> None:
    dlg = FrontmatterDialog(original_raw={"slide_inches": "11.024x6.201"})
    qtbot.addWidget(dlg)
    out = dlg.result_raw()
    assert out["slide_inches"] == "11.024x6.201"
