"""Markdown song renderer — SongSpec + Slide → QImage."""
from __future__ import annotations

import logging
import re
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter

from flow.services.markdown.parser import Slide, SongSpec, resolve_attrs

logger = logging.getLogger(__name__)


def render_slide(spec: SongSpec, slide: Slide, *, song_dir: Path) -> QImage:
    """Render a single slide into a QImage at the resolution from frontmatter."""
    width, height = spec.frontmatter.resolution
    img = QImage(width, height, QImage.Format.Format_RGB32)

    attrs = resolve_attrs(spec, slide)
    painter = QPainter(img)
    try:
        _draw_background(painter, img, attrs.background, song_dir)
    finally:
        painter.end()
    return img


def _draw_background(
    painter: QPainter, target: QImage, background: str, song_dir: Path
) -> None:
    """Background can be a hex color or an image path (relative to song_dir)."""
    if _is_color(background):
        painter.fillRect(target.rect(), QColor(background))
        return

    bg_path = Path(background)
    img_path = bg_path if bg_path.is_absolute() else (song_dir / background)
    if not img_path.exists():
        logger.warning("background image not found: %s", img_path)
        painter.fillRect(target.rect(), QColor("#000000"))
        return

    bg = QImage(str(img_path))
    if bg.isNull():
        logger.warning("background image failed to load: %s", img_path)
        painter.fillRect(target.rect(), QColor("#000000"))
        return

    _draw_cover(painter, target, bg)


_HEX_COLOR_RE = re.compile(r"\A#[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?\Z")


def _is_color(s: str) -> bool:
    return bool(_HEX_COLOR_RE.match(s))


def _draw_cover(painter: QPainter, target: QImage, source: QImage) -> None:
    """Scale source to 'cover' target rect — fills entirely, may crop."""
    tw, th = target.width(), target.height()
    sw, sh = source.width(), source.height()
    if sw == 0 or sh == 0:
        return
    scale = max(tw / sw, th / sh)
    dw, dh = sw * scale, sh * scale
    dx = (tw - dw) / 2
    dy = (th - dh) / 2
    painter.drawImage(
        int(dx), int(dy), source.scaled(
            int(dw), int(dh),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    )
