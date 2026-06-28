# tests/services/test_apply_patches_to_text.py
"""apply_patches_to_text rewrites a slides.md to embed all patches."""
from __future__ import annotations

import pytest

from flow.services.markdown import (
    PatchType,
    SlidePatch,
    apply_patches_to_text,
    slide_hash,
)


def test_apply_edit_replaces_slide_body() -> None:
    src = "# t\n\n원본 1\n\n원본 2\n"
    patch = SlidePatch(
        id="p1",
        type=PatchType.EDIT,
        patched_main="고친 1",
        slide_hash=slide_hash("원본 1"),
        slide_index=0,
        created_at="t",
        created_during="live",
    )
    out = apply_patches_to_text(src, [patch])
    assert "고친 1" in out
    assert "원본 1" not in out
    assert "원본 2" in out


def test_apply_append_adds_blank_separated_block() -> None:
    src = "# t\n\n원본 1\n"
    patch = SlidePatch(
        id="p1",
        type=PatchType.APPEND,
        patched_main="추가된",
        slide_hash=None,
        slide_index=None,
        created_at="t",
        created_during="live",
    )
    out = apply_patches_to_text(src, [patch])
    assert out.endswith("추가된\n")
    assert "원본 1" in out
