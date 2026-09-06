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


def test_empty_frontmatter_block_survives() -> None:
    """--- 다음 줄이 바로 ---인 빈 블록도 보존해야 한다.

    라이브러리 곡이 대부분 이 형태라, 못 잡으면 '원본에 반영'을 누를 때마다
    그 두 줄이 조용히 사라진다.
    """
    src = "---\n---\n\n# t\n\n원본 1\n"
    assert apply_patches_to_text(src, []) == src


def test_frontmatter_with_settings_survives() -> None:
    src = '---\nmain_size: 56\nbackground: "#000000"\n---\n\n# t\n\n원본 1\n'
    out = apply_patches_to_text(src, [])
    assert out.startswith('---\nmain_size: 56\nbackground: "#000000"\n---\n\n')
    assert out == src


def test_patch_applies_under_an_empty_frontmatter() -> None:
    src = "---\n---\n\n# t\n\n원본 1\n\n원본 2\n"
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
    assert out.startswith("---\n---\n\n# t\n")
    assert "고친 1" in out and "원본 1" not in out
