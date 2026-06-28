"""Markdown-based slide source — parser + renderer + patches."""
from __future__ import annotations

from flow.services.markdown.parser import (
    Frontmatter,
    ResolvedAttrs,
    Slide,
    SongSpec,
    lyric_snippet,
    parse,
    read_song_lyrics,
    resolve_attrs,
    strip_frontmatter,
)
from flow.services.markdown.patches import (
    PatchStore,
    PatchType,
    SlidePatch,
    apply_patches,
    apply_patches_to_text,
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
    "apply_patches_to_text",
    "lyric_snippet",
    "parse",
    "read_song_lyrics",
    "render_all",
    "render_slide",
    "resolve_attrs",
    "slide_hash",
    "strip_frontmatter",
]
