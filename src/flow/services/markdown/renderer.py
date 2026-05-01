"""Markdown song renderer — SongSpec + Slide → QImage."""
from __future__ import annotations

import logging
import re
from pathlib import Path

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter

from flow.services.markdown.parser import ResolvedAttrs, Slide, SongSpec, resolve_attrs

logger = logging.getLogger(__name__)


def _pt_to_px(
    pt: float,
    *,
    slide_inches: tuple[float, float],
    resolution: tuple[int, int],
) -> float:
    """Convert pt to pixels using the canvas physical size & output resolution.

    1pt = 1/72 inch. DPI = resolution_height / slide_inches_height.
    px = pt * DPI / 72.
    """
    _, inches_h = slide_inches
    _, res_h = resolution
    dpi = res_h / inches_h
    return pt * dpi / 72


# Layout constants (proportions of slide canvas)
_MAIN_TOP = 0.363
_MAIN_HEIGHT = 0.296   # 36.3% → 65.9%
_SUB_TOP = 0.897
_SUB_HEIGHT = 0.083    # 89.7% → 98.0%
_SUB_LEFT = 0.27
_SUB_WIDTH = 0.46


def render_slide(spec: SongSpec, slide: Slide, *, song_dir: Path) -> QImage:
    """Render a single slide into a QImage at the resolution from frontmatter."""
    width, height = spec.frontmatter.resolution
    img = QImage(width, height, QImage.Format.Format_RGB32)

    attrs = resolve_attrs(spec, slide)
    painter = QPainter(img)
    try:
        _draw_background(painter, img, attrs.background, song_dir)
        _draw_main_text(painter, img, slide.main, attrs, spec.frontmatter)
        _draw_sub_text(painter, img, attrs.sub_text, attrs, spec.frontmatter)
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


def _draw_main_text(
    painter: QPainter,
    target: QImage,
    text: str,
    attrs: ResolvedAttrs,
    fm,
) -> None:
    if not text:
        return
    w, h = target.width(), target.height()
    box = QRect(
        0,
        int(h * _MAIN_TOP),
        w,
        int(h * _MAIN_HEIGHT),
    )
    px = _pt_to_px(
        attrs.main_size, slide_inches=fm.slide_inches, resolution=fm.resolution
    )
    font = QFont(attrs.main_font)
    font.setPixelSize(max(1, int(px)))
    painter.setFont(font)
    painter.setPen(QColor(attrs.main_color))
    painter.drawText(
        box,
        int(Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap),
        text,
    )


def _draw_sub_text(
    painter: QPainter,
    target: QImage,
    text: str,
    attrs: ResolvedAttrs,
    fm,
) -> None:
    if not text:
        return
    w, h = target.width(), target.height()
    box = QRect(
        int(w * _SUB_LEFT),
        int(h * _SUB_TOP),
        int(w * _SUB_WIDTH),
        int(h * _SUB_HEIGHT),
    )
    px = _pt_to_px(
        attrs.sub_size, slide_inches=fm.slide_inches, resolution=fm.resolution
    )
    font = QFont(attrs.sub_font)
    font.setPixelSize(max(1, int(px)))
    painter.setFont(font)
    painter.setPen(QColor(attrs.sub_color))
    painter.drawText(
        box,
        int(Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap),
        text,
    )


def render_all(spec: SongSpec, *, song_dir: Path) -> list[QImage]:
    """Render every slide in the spec."""
    return [render_slide(spec, s, song_dir=song_dir) for s in spec.slides]
