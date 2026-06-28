# tests/services/test_markdown_converter_patches.py
"""MarkdownSlideConverter integrates `.patches.json` transparently."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from PySide6.QtGui import QImage

from flow.services.slide_converter import MarkdownSlideConverter


@pytest.fixture
def song_dir_with_md(tmp_path: Path) -> Path:
    """Create a minimal markdown song folder."""
    md = tmp_path / "slides.md"
    md.write_text(
        "# 테스트 곡\n\n"
        "원본 가사 1\n\n"
        "원본 가사 2\n",
        encoding="utf-8",
    )
    return md


def test_converter_returns_original_count_without_patches(
    song_dir_with_md: Path, qapp
) -> None:
    conv = MarkdownSlideConverter()
    assert conv.get_slide_count(song_dir_with_md) == 2


def test_converter_picks_up_append_patch(
    song_dir_with_md: Path, qapp
) -> None:
    patches_path = song_dir_with_md.parent / ".patches.json"
    patches_path.write_text(
        json.dumps(
            {
                "version": 1,
                "patches": [
                    {
                        "id": "a1",
                        "type": "append",
                        "patched_main": "추가된 슬라이드",
                        "created_at": "2026-05-05T19:50:00Z",
                        "created_during": "live",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    conv = MarkdownSlideConverter()
    assert conv.get_slide_count(song_dir_with_md) == 3


def test_converter_picks_up_edit_patch_by_hash(
    song_dir_with_md: Path, qapp
) -> None:
    from flow.services.markdown import slide_hash

    patches_path = song_dir_with_md.parent / ".patches.json"
    patches_path.write_text(
        json.dumps(
            {
                "version": 1,
                "patches": [
                    {
                        "id": "e1",
                        "type": "edit",
                        "patched_main": "고친 가사 1",
                        "slide_hash": slide_hash("원본 가사 1"),
                        "slide_index": 0,
                        "created_at": "2026-05-05T19:50:00Z",
                        "created_during": "live",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    conv = MarkdownSlideConverter()
    img: QImage = conv.convert_slide(song_dir_with_md, 0)
    assert not img.isNull()
    assert img.width() > 0


def test_cache_self_detects_patch_additions(
    song_dir_with_md: Path, qapp
) -> None:
    """The content-hash cache re-reads .patches.json and slides.md on
    each call, so additions are reflected immediately without an
    explicit invalidate call. (invalidate_cache stays available for
    memory cleanup.)"""
    conv = MarkdownSlideConverter()
    assert conv.get_slide_count(song_dir_with_md) == 2

    patches_path = song_dir_with_md.parent / ".patches.json"
    patches_path.write_text(
        json.dumps(
            {
                "version": 1,
                "patches": [
                    {
                        "id": "a1",
                        "type": "append",
                        "patched_main": "추가된",
                        "created_at": "2026-05-05T19:50:00Z",
                        "created_during": "live",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    # New count is reflected on the next call — no explicit invalidate
    # needed because the cache re-parses input on every request.
    assert conv.get_slide_count(song_dir_with_md) == 3


def test_unchanged_slide_returns_same_qimage_object(
    song_dir_with_md: Path, qapp
) -> None:
    """Per-content cache: same slide content → same QImage object.
    Lets downstream UI skip re-paints for unchanged thumbnails."""
    conv = MarkdownSlideConverter()
    img_first = conv.convert_slide(song_dir_with_md, 0)
    img_second = conv.convert_slide(song_dir_with_md, 0)
    assert img_first is img_second  # object identity, not just equal
