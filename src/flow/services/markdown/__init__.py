"""Markdown-based slide source — parser + renderer."""
from __future__ import annotations

from flow.services.markdown.parser import (
    Frontmatter,
    ResolvedAttrs,
    Slide,
    SongSpec,
    parse,
    resolve_attrs,
)
from flow.services.markdown.renderer import render_all, render_slide

__all__ = [
    "Frontmatter",
    "ResolvedAttrs",
    "Slide",
    "SongSpec",
    "parse",
    "render_all",
    "render_slide",
    "resolve_attrs",
]
