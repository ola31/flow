from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QImage

from flow.services.slide_converter import MarkdownSlideConverter


def test_get_slide_count(qapp, tmp_path: Path) -> None:
    md = tmp_path / "slides.md"
    md.write_text("# T\n\n가사 1\n\n가사 2\n", encoding="utf-8")

    conv = MarkdownSlideConverter()
    assert conv.get_slide_count(md) == 2


def test_convert_slide_returns_qimage(qapp, tmp_path: Path) -> None:
    md = tmp_path / "slides.md"
    md.write_text("# T\n\n가사 1\n\n가사 2\n", encoding="utf-8")

    conv = MarkdownSlideConverter()
    img = conv.convert_slide(md, 0)
    assert isinstance(img, QImage)
    assert img.width() == 1920
    assert img.height() == 1080


def test_caching_avoids_reparse(qapp, tmp_path: Path) -> None:
    md = tmp_path / "slides.md"
    md.write_text("# T\n\n가사 1\n", encoding="utf-8")
    conv = MarkdownSlideConverter()
    img1 = conv.convert_slide(md, 0)
    img2 = conv.convert_slide(md, 0)
    # Same identity from cache
    assert img1 is img2


def test_invalidate_cache_forces_rerender(qapp, tmp_path: Path) -> None:
    md = tmp_path / "slides.md"
    md.write_text("# T\n\n가사 1\n", encoding="utf-8")
    conv = MarkdownSlideConverter()
    img1 = conv.convert_slide(md, 0)
    conv.invalidate_cache(md)
    img2 = conv.convert_slide(md, 0)
    # Different objects after invalidation
    assert img1 is not img2


def test_get_engine_name() -> None:
    assert MarkdownSlideConverter().get_engine_name() == "Markdown"
