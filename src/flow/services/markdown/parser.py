"""Markdown song parser — frontmatter + slide structure to SongSpec."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

import yaml

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Frontmatter:
    main_font: str = "Pretendard Variable"
    main_size: int = 56
    main_color: str = "#FFFFFF"
    sub_font: str = "Pretendard Variable"
    sub_size: int = 18
    sub_color: str = "#CCCCCC"
    background: str = "#000000"
    slide_inches: tuple[float, float] = (13.333, 7.5)
    resolution: tuple[int, int] = (1920, 1080)


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


def _parse_str(v: Any, default: str) -> str:
    return v if isinstance(v, str) else default


def _build_frontmatter(raw: dict[str, Any] | None) -> Frontmatter:
    if not raw:
        return Frontmatter()
    d = Frontmatter()
    return Frontmatter(
        main_font=_parse_str(raw.get("main_font"), d.main_font),
        main_size=_parse_int(raw.get("main_size"), d.main_size),
        main_color=_parse_str(raw.get("main_color"), d.main_color),
        sub_font=_parse_str(raw.get("sub_font"), d.sub_font),
        sub_size=_parse_int(raw.get("sub_size"), d.sub_size),
        sub_color=_parse_str(raw.get("sub_color"), d.sub_color),
        background=_parse_str(raw.get("background"), d.background),
        slide_inches=_parse_inches(raw.get("slide_inches"), d.slide_inches),
        resolution=_parse_resolution(raw.get("resolution"), d.resolution),
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
