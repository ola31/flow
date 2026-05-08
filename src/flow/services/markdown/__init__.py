"""Markdown-based slide source — parser + renderer + patches."""
from __future__ import annotations

from flow.services.markdown.parser import (
    Frontmatter,
    ResolvedAttrs,
    Slide,
    SongSpec,
    parse,
    resolve_attrs,
)
from flow.services.markdown.patches import (
    PatchStore,
    PatchType,
    SlidePatch,
    apply_patches,
    slide_hash,
)
from flow.services.markdown.renderer import render_all, render_slide

__all__ = [
    "Frontmatter",
    "PatchStore",
    "PatchType",
    "ResolvedAttrs",
    "Slide",
    "SlidePatch",
    "SongSpec",
    "apply_patches",
    "parse",
    "render_all",
    "render_slide",
    "resolve_attrs",
    "slide_hash",
]
