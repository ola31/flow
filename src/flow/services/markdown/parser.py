"""Markdown song parser — frontmatter + slide structure to SongSpec."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


def strip_frontmatter(text: str) -> str:
    """선두 `--- ... ---` frontmatter 블록을 제거한 본문(가사)을 반환한다."""
    return _FRONTMATTER_RE.sub("", text, count=1)


def read_song_lyrics(song_dir: Path) -> str:
    """곡 폴더의 slides.md에서 frontmatter를 제외한 가사 본문을 반환한다.

    slides.md가 없거나 읽기 실패 시 빈 문자열. 원문 대소문자를 유지하므로
    검색용으로 쓸 때는 호출 측에서 lower()한다.
    """
    md = Path(song_dir) / "slides.md"
    if not md.exists():
        return ""
    try:
        return strip_frontmatter(md.read_text(encoding="utf-8"))
    except OSError:
        return ""


def lyric_snippet(lyrics: str, query: str, max_len: int = 40) -> str:
    """가사에서 query(소문자)가 포함된 첫 줄을 잘라 반환한다(없으면 "").

    매칭 위치 주변으로 잘라 검색어가 보이도록 하며, 마크다운 제목/절 기호(`#`)는
    앞부분에서 제거한다. query는 소문자로 전달한다.
    """
    if not query or not lyrics:
        return ""
    low = lyrics.lower()
    idx = low.find(query)
    if idx < 0:
        return ""
    start = lyrics.rfind("\n", 0, idx) + 1
    end = lyrics.find("\n", idx)
    if end < 0:
        end = len(lyrics)
    line = lyrics[start:end].lstrip("# ").strip()
    if len(line) <= max_len:
        return line
    pos = line.lower().find(query)
    head = max(0, pos - max_len // 3)
    snippet = line[head:head + max_len]
    return ("…" if head > 0 else "") + snippet + "…"


@dataclass(frozen=True)
class Frontmatter:
    # Font family: variable 폰트의 family name. weight axis 는 main_weight 로 제어.
    main_font: str = "Pretendard Variable"
    main_size: int = 38
    main_weight: int = 500              # 500 = Medium
    main_color: str = "#F0F0F0"
    sub_font: str = "Pretendard Variable"
    sub_size: int = 20
    sub_weight: int = 300               # 300 = Light
    sub_color: str = "#F0F0F0"
    background: str = "@app/default_bg.jpg"
    # Auto-applied backgrounds for longer lyric slides.
    background_3plus: str = "@app/default_bg_3plus.jpg"
    background_4plus: str = "@app/default_bg_4plus.jpg"
    slide_inches: tuple[float, float] = (11.024, 6.201)  # 28 × 15.75 cm (16:9)
    resolution: tuple[int, int] = (1920, 1080)
    line_spacing: float = 1.3              # multiplier (1–2 line slides)
    para_spacing: float = 10.0             # pt — extra space before each paragraph
    text_anchor: str = "bottom"            # "center" | "bottom"
    text_bottom_pct: float = 0.659         # baseline fraction (anchor=bottom, 1–2 line)
    line_spacing_3plus: float = 1.5        # multiplier (3+ line slides — PPT 2_기본값)
    text_bottom_pct_3plus: float = 0.736   # baseline fraction (3+ line slides)
    line_spacing_4plus: float = 1.42       # multiplier (4+ line slides)
    text_bottom_pct_4plus: float = 0.796   # baseline fraction (4+ line slides)
    multiline_threshold: int = 3           # line count that triggers _3plus values
    multiline_4plus_threshold: int = 4     # line count that triggers _4plus values


@dataclass(frozen=True)
class Slide:
    main: str                        # raw main text (multi-line)
    sub_override: str | None         # > sub text, if present on the slide
    section_sub_default: str | None  # ## X :: Y, if slide is in such a section
    overrides: dict[str, Any] = field(default_factory=dict)  # per-slide attrs


@dataclass(frozen=True)
class SongSpec:
    title: str                              # # Title (defaults to "")
    frontmatter: Frontmatter
    slides: list[Slide]


_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_OVERRIDE_RE = re.compile(r"\A\{(.+)\}\s*\Z")

# Effective default resolution when frontmatter omits it.
# Synced to ConfigService.get_output_resolution() via set_default_resolution()
# at app startup so PPT- and markdown-sourced slides share the same target.
_default_resolution: tuple[int, int] = (1920, 1080)


def set_default_resolution(resolution: tuple[int, int]) -> None:
    """Override the default resolution used when frontmatter omits `resolution`."""
    global _default_resolution
    _default_resolution = (int(resolution[0]), int(resolution[1]))


def _parse_overrides(line: str) -> dict[str, Any] | None:
    """Parse `{key: val, ...}` line. Return dict on success, None otherwise."""
    m = _OVERRIDE_RE.match(line.strip())
    if not m:
        return None
    inner = "{" + m.group(1) + "}"
    try:
        result = yaml.safe_load(inner)
    except yaml.YAMLError as exc:
        logger.warning("slide override parse error: %s", exc)
        return None
    if not isinstance(result, dict):
        return None
    return result


def _parse_inches(s: Any, default: tuple[float, float]) -> tuple[float, float]:
    if not isinstance(s, str):
        return default
    m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*x\s*(\d+(?:\.\d+)?)\s*", s)
    if not m:
        return default
    return (float(m.group(1)), float(m.group(2)))


def _parse_resolution(s: Any, default: tuple[int, int]) -> tuple[int, int]:
    if not isinstance(s, str):
        return default
    m = re.fullmatch(r"\s*(\d+)\s*x\s*(\d+)\s*", s)
    if not m:
        return default
    return (int(m.group(1)), int(m.group(2)))


def _parse_int(v: Any, default: int) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _parse_float(v: Any, default: float) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _parse_str(v: Any, default: str) -> str:
    return v if isinstance(v, str) else default


def _build_frontmatter(raw: dict[str, Any] | None) -> Frontmatter:
    if not raw:
        return Frontmatter(resolution=_default_resolution)
    d = Frontmatter(resolution=_default_resolution)
    return Frontmatter(
        main_font=_parse_str(raw.get("main_font"), d.main_font),
        main_size=_parse_int(raw.get("main_size"), d.main_size),
        main_weight=_parse_int(raw.get("main_weight"), d.main_weight),
        main_color=_parse_str(raw.get("main_color"), d.main_color),
        sub_font=_parse_str(raw.get("sub_font"), d.sub_font),
        sub_size=_parse_int(raw.get("sub_size"), d.sub_size),
        sub_weight=_parse_int(raw.get("sub_weight"), d.sub_weight),
        sub_color=_parse_str(raw.get("sub_color"), d.sub_color),
        background=_parse_str(raw.get("background"), d.background),
        background_3plus=_parse_str(raw.get("background_3plus"), d.background_3plus),
        background_4plus=_parse_str(raw.get("background_4plus"), d.background_4plus),
        slide_inches=_parse_inches(raw.get("slide_inches"), d.slide_inches),
        resolution=_parse_resolution(raw.get("resolution"), d.resolution),
        line_spacing=_parse_float(raw.get("line_spacing"), d.line_spacing),
        para_spacing=_parse_float(raw.get("para_spacing"), d.para_spacing),
        text_anchor=_parse_str(raw.get("text_anchor"), d.text_anchor),
        text_bottom_pct=_parse_float(raw.get("text_bottom_pct"), d.text_bottom_pct),
        line_spacing_3plus=_parse_float(
            raw.get("line_spacing_3plus"), d.line_spacing_3plus
        ),
        text_bottom_pct_3plus=_parse_float(
            raw.get("text_bottom_pct_3plus"), d.text_bottom_pct_3plus
        ),
        line_spacing_4plus=_parse_float(
            raw.get("line_spacing_4plus"), d.line_spacing_4plus
        ),
        text_bottom_pct_4plus=_parse_float(
            raw.get("text_bottom_pct_4plus"), d.text_bottom_pct_4plus
        ),
        multiline_threshold=_parse_int(
            raw.get("multiline_threshold"), d.multiline_threshold
        ),
        multiline_4plus_threshold=_parse_int(
            raw.get("multiline_4plus_threshold"), d.multiline_4plus_threshold
        ),
    )


def parse(text: str) -> SongSpec:
    """Parse markdown song text into a SongSpec."""
    fm_raw: dict[str, Any] | None = None
    body = text

    m = _FRONTMATTER_RE.match(text)
    if m:
        try:
            fm_raw = yaml.safe_load(m.group(1)) or {}
            if not isinstance(fm_raw, dict):
                logger.warning("frontmatter must be a mapping; ignoring")
                fm_raw = None
        except yaml.YAMLError as exc:
            logger.warning("frontmatter parse error: %s", exc)
            fm_raw = None
        body = text[m.end():]

    fm = _build_frontmatter(fm_raw)
    title = _extract_title(body)
    slides = _parse_slides(body)
    return SongSpec(title=title, frontmatter=fm, slides=slides)


def _parse_slides(body: str) -> list[Slide]:
    """Split body into slide blocks.

    Tracks section sub default (:: syntax), per-slide sub override (> syntax),
    and per-slide attribute overrides ({key: val} on the first line).
    """
    slides: list[Slide] = []
    current_lines: list[str] = []
    current_section_default: str | None = None

    def flush() -> None:
        nonlocal current_lines
        if not current_lines:
            return
        # First line may be {key: val} override
        overrides: dict[str, Any] = {}
        if current_lines:
            parsed = _parse_overrides(current_lines[0])
            if parsed is not None:
                overrides = parsed
                current_lines = current_lines[1:]
        # Last non-empty line may be > sub override
        sub_override: str | None = None
        if current_lines and current_lines[-1].lstrip().startswith("> "):
            sub_override = current_lines[-1].lstrip()[2:].strip()
            current_lines = current_lines[:-1]
        main = "\n".join(current_lines).rstrip()
        if main or sub_override or overrides:
            slides.append(Slide(
                main=main,
                sub_override=sub_override,
                section_sub_default=current_section_default,
                overrides=overrides,
            ))
        current_lines = []

    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("# ") and not stripped.startswith("## "):
            flush()
            continue
        if stripped.startswith("## "):
            flush()
            section_text = stripped[3:].strip()
            if "::" in section_text:
                current_section_default = section_text.split("::", 1)[1].strip()
            else:
                current_section_default = None
            continue
        if not stripped:
            flush()
            continue
        current_lines.append(line)

    flush()
    return slides


def _extract_title(body: str) -> str:
    for line in body.splitlines():
        if line.startswith("# ") and not line.startswith("## "):
            return line[2:].strip()
    return ""


@dataclass(frozen=True)
class ResolvedAttrs:
    """Final attributes for a slide after cascading frontmatter + overrides."""

    main_font: str
    main_size: int
    main_weight: int
    main_color: str
    sub_font: str
    sub_size: int
    sub_weight: int
    sub_color: str
    background: str
    sub_text: str  # already-resolved sub text (override > section default > title)


def resolve_attrs(spec: SongSpec, slide: Slide) -> ResolvedAttrs:
    """Cascade slide overrides over frontmatter; resolve sub_text by priority."""
    fm = spec.frontmatter
    o = slide.overrides

    def get_str(key: str, default: str) -> str:
        v = o.get(key)
        return v if isinstance(v, str) else default

    def get_int(key: str, default: int) -> int:
        try:
            v = o.get(key)
            return int(v) if v is not None else default
        except (TypeError, ValueError):
            return default

    if slide.sub_override is not None:
        sub_text = slide.sub_override
    elif slide.section_sub_default is not None:
        sub_text = slide.section_sub_default
    else:
        sub_text = spec.title

    return ResolvedAttrs(
        main_font=get_str("main_font", fm.main_font),
        main_size=get_int("main_size", fm.main_size),
        main_weight=get_int("main_weight", fm.main_weight),
        main_color=get_str("main_color", fm.main_color),
        sub_font=get_str("sub_font", fm.sub_font),
        sub_size=get_int("sub_size", fm.sub_size),
        sub_weight=get_int("sub_weight", fm.sub_weight),
        sub_color=get_str("sub_color", fm.sub_color),
        background=get_str("background", fm.background),
        sub_text=sub_text,
    )
