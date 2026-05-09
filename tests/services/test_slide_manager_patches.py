"""SlideManager exposes a hook to invalidate the markdown cache after patch."""
from __future__ import annotations

from pathlib import Path

import pytest

from flow.services.slide_manager import SlideManager


def test_invalidate_markdown_cache_clears_internal_state(tmp_path: Path, qapp) -> None:
    md = tmp_path / "slides.md"
    md.write_text("# t\n\n원본\n", encoding="utf-8")

    sm = SlideManager()
    try:
        # Prime the cache
        sm._markdown_converter._slides_for(md)
        assert md.resolve() in sm._markdown_converter._cache

        sm.invalidate_markdown_cache(md)
        assert md.resolve() not in sm._markdown_converter._cache
    finally:
        sm.shutdown()
