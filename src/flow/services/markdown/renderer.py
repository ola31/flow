"""Markdown song renderer — SongSpec + Slide → QImage."""
from __future__ import annotations

import logging
import re
import sys
from pathlib import Path

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetricsF,
    QImage,
    QPainter,
    QTextBlockFormat,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
)

from flow.services.markdown.parser import ResolvedAttrs, Slide, SongSpec, resolve_attrs

logger = logging.getLogger(__name__)

_APP_ASSET_PREFIX = "@app/"

# Pretendard static family name → variable font 의 weight 값.
# 사용자가 `Pretendard Medium` 같은 익숙한 이름을 쓰면 시스템에 그 static
# 폰트가 없어도 번들된 PretendardVariable.ttf 의 해당 weight 로 자동 매핑된다.
_PRETENDARD_WEIGHT_MAP: dict[str, int] = {
    "Pretendard Thin": 100,
    "Pretendard ExtraLight": 200,
    "Pretendard Light": 300,
    "Pretendard": 400,
    "Pretendard Regular": 400,
    "Pretendard Medium": 500,
    "Pretendard SemiBold": 600,
    "Pretendard Bold": 700,
    "Pretendard ExtraBold": 800,
    "Pretendard Black": 900,
}


def resolve_font(name: str, weight: int) -> tuple[str, int]:
    """Map static Pretendard names to ('Pretendard Variable', implied weight).

    For non-Pretendard fonts, return inputs unchanged. The implied weight from
    the static name takes precedence over `weight` since the user's intent is
    expressed by the family name.
    """
    if name in _PRETENDARD_WEIGHT_MAP:
        return ("Pretendard Variable", _PRETENDARD_WEIGHT_MAP[name])
    return (name, weight)


def _app_assets_dir() -> Path:
    """Resolve the bundled assets dir (handles PyInstaller frozen + dev mode)."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "assets"  # type: ignore[attr-defined]
    # repo root: src/flow/services/markdown/renderer.py → parents[3] is repo root
    return Path(__file__).resolve().parents[4] / "assets"


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
# Main text is centered around slide midpoint (50%) — height computed dynamically.
_SUB_TOP = 0.897
_SUB_HEIGHT = 0.083    # 89.7% → 98.0%
_SUB_LEFT = 0.27
_SUB_WIDTH = 0.46


def render_slide(spec: SongSpec, slide: Slide, *, song_dir: Path) -> QImage:
    """Render a single slide into a QImage at the resolution from frontmatter."""
    width, height = spec.frontmatter.resolution
    img = QImage(width, height, QImage.Format.Format_RGB32)

    attrs = resolve_attrs(spec, slide)
    background = effective_background(spec, slide, attrs)
    painter = QPainter(img)
    try:
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        _draw_background(painter, img, background, song_dir)
        _draw_main_text(painter, img, slide.main, attrs, spec.frontmatter)
        _draw_sub_text(painter, img, attrs.sub_text, attrs, spec.frontmatter)
    finally:
        painter.end()
    return img


def effective_background(spec: SongSpec, slide: Slide, attrs: ResolvedAttrs) -> str:
    """Pick background.

    Slide override wins; otherwise longer slides use long-line backgrounds.
    """
    if "background" in slide.overrides:
        return attrs.background
    n_lines = len(slide.main.split("\n")) if slide.main else 0
    fm = spec.frontmatter
    if n_lines >= fm.multiline_4plus_threshold and fm.background_4plus:
        return fm.background_4plus
    if n_lines >= fm.multiline_threshold and fm.background_3plus:
        return fm.background_3plus
    return attrs.background


def _draw_background(
    painter: QPainter, target: QImage, background: str, song_dir: Path
) -> None:
    """Background can be a hex color, app asset (`@app/<name>`), or image path."""
    if _is_color(background):
        painter.fillRect(target.rect(), QColor(background))
        return

    if background.startswith(_APP_ASSET_PREFIX):
        img_path = _app_assets_dir() / background[len(_APP_ASSET_PREFIX):]
    else:
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
    """Draw main text via QTextDocument so we can control line + paragraph spacing.

    Each newline becomes a separate paragraph. Spacing between paragraphs adds
    `fm.para_spacing` pt; line height inside a paragraph is `fm.line_spacing`× the
    font's natural height. Vertical placement is either centered around mid-slide
    or anchored to `fm.text_bottom_pct` of slide height (PPT-style bottom anchor).
    """
    if not text:
        return
    w, h = target.width(), target.height()
    px = _pt_to_px(
        attrs.main_size, slide_inches=fm.slide_inches, resolution=fm.resolution
    )
    para_px = _pt_to_px(
        fm.para_spacing, slide_inches=fm.slide_inches, resolution=fm.resolution
    )
    lines = text.split("\n")
    if len(lines) >= fm.multiline_4plus_threshold:
        line_spacing = fm.line_spacing_4plus
        text_bottom_pct = fm.text_bottom_pct_4plus
    elif len(lines) >= fm.multiline_threshold:
        line_spacing = fm.line_spacing_3plus
        text_bottom_pct = fm.text_bottom_pct_3plus
    else:
        line_spacing = fm.line_spacing
        text_bottom_pct = fm.text_bottom_pct
    family, eff_weight = resolve_font(attrs.main_font, attrs.main_weight)
    font = QFont(family)
    font.setPixelSize(max(1, int(px)))
    # Variable 폰트의 weight axis 를 명시 — "Pretendard Variable" + weight=500 →
    # Pretendard Medium 모양으로 렌더링됨. static font name 의존을 제거.
    font.setWeight(QFont.Weight(eff_weight))

    doc = QTextDocument()
    doc.setDefaultFont(font)
    doc.setTextWidth(w)
    doc.setDocumentMargin(0)

    cf = QTextCharFormat()
    cf.setForeground(QColor(attrs.main_color))

    cursor = QTextCursor(doc)
    for i, line in enumerate(lines):
        bf = QTextBlockFormat()
        bf.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        bf.setLineHeight(
            line_spacing * 100,
            int(QTextBlockFormat.LineHeightTypes.ProportionalHeight.value),
        )
        if i > 0:
            bf.setTopMargin(para_px)
            cursor.insertBlock(bf)
        else:
            cursor.setBlockFormat(bf)
        cursor.setCharFormat(cf)
        cursor.insertText(line)

    doc_h = doc.size().height()
    # Qt ProportionalHeight splits extra leading above/below each line, so the
    # first line carries only HALF the (line_spacing - 1) leading at its top.
    # Subtract that from doc_h before bottom-anchoring to match PPT's behavior.
    natural_lh = QFontMetricsF(font).height()
    first_line_leading = natural_lh * max(0.0, line_spacing - 1.0) * 0.7
    if fm.text_anchor == "bottom":
        y = h * text_bottom_pct - doc_h + first_line_leading
    else:
        y = (h - doc_h) / 2 + first_line_leading / 2
    y = round(y)

    painter.save()
    painter.translate(0, y)
    doc.drawContents(painter)
    painter.restore()


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
    family, eff_weight = resolve_font(attrs.sub_font, attrs.sub_weight)
    font = QFont(family)
    font.setPixelSize(max(1, int(px)))
    font.setWeight(QFont.Weight(eff_weight))
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
