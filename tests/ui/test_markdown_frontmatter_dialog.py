from __future__ import annotations

from flow.services.markdown.parser import Frontmatter
from flow.ui.editor.markdown_frontmatter_dialog import (
    apply_frontmatter_to_text,
    parse_form_values,
)


def test_apply_to_text_replaces_existing_frontmatter() -> None:
    original = """\
---
main_size: 56
---

# T

가사
"""
    fm = Frontmatter(main_size=72)
    new = apply_frontmatter_to_text(original, fm)
    assert "main_size: 72" in new
    assert "# T" in new
    assert "가사" in new


def test_apply_to_text_inserts_when_no_frontmatter() -> None:
    original = "# T\n\n가사\n"
    fm = Frontmatter(main_size=72)
    new = apply_frontmatter_to_text(original, fm)
    assert new.startswith("---\n")
    assert "main_size: 72" in new
    assert "# T" in new


def test_parse_form_values_int() -> None:
    assert parse_form_values({"main_size": "72"}).main_size == 72
    assert parse_form_values({"main_size": "abc"}).main_size == 56
