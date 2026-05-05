# Markdown Slide Format Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a markdown-based slide source (`slides.md`) that Flow renders directly via Qt, plus an in-app split-view editor with syntax highlighting, frontmatter form, and live preview.

**Architecture:** Pure-Qt parser + renderer in `src/flow/services/markdown/`. New `MarkdownSlideConverter` plugs into `slide_converter.py`. SlideManager dispatches by file extension (`.md` → markdown, `.pptx` → existing PPT path). UI editor at `src/flow/ui/editor/markdown_editor.py` opens for markdown songs from the existing edit-button entry; PPT songs continue to launch external apps unchanged.

**Tech Stack:** Python 3.10+, PySide6 (QPainter, QImage, QPlainTextEdit, QSyntaxHighlighter), PyYAML (new dep, for frontmatter parsing). No PowerPoint/LibreOffice dependency for the markdown path.

**Spec:** `docs/superpowers/specs/2026-05-01-markdown-slide-format-design.md`

---

## File Structure

**New files:**
```
src/flow/services/markdown/
├── __init__.py              # public exports
├── parser.py                # SongSpec, Slide, Frontmatter dataclasses + parse() + resolve_attrs()
└── renderer.py              # MarkdownRenderer (SongSpec + song_dir → list[QImage])

src/flow/ui/editor/
├── markdown_editor.py              # MarkdownEditor split-view widget
├── markdown_highlighter.py         # QSyntaxHighlighter for markdown
└── markdown_frontmatter_dialog.py  # Frontmatter form modal

tests/markdown/
├── __init__.py
├── test_parser.py
├── test_renderer.py
└── test_converter.py        # MarkdownSlideConverter integration

tests/ui/
├── test_markdown_editor.py
├── test_markdown_highlighter.py
└── test_markdown_frontmatter_dialog.py
```

**Modified files:**
- `pyproject.toml` — add `pyyaml` dependency
- `src/flow/services/slide_converter.py` — add `MarkdownSlideConverter` class, dispatch in `create_slide_converter`
- `src/flow/services/slide_manager.py` — extension-based converter dispatch in `load_pptx`
- `src/flow/domain/song.py` — `markdown_path`, `has_markdown`, `slide_source`
- `src/flow/ui/editor/song_list_widget.py` — edit button opens MarkdownEditor for markdown songs
- `src/flow/ui/main_window.py` — wire MarkdownEditor entry (or related screen)

**Boundaries:**
- `parser.py` knows markdown syntax + YAML frontmatter only. No Qt, no rendering.
- `renderer.py` knows Qt + drawing only. Takes a parsed SongSpec.
- `slide_converter.py` integrates the markdown engine into the existing converter abstraction.
- UI editor files don't know markdown internals beyond what parser exposes — they edit text and call save → reparse → rerender.

---

## Task 1: Add PyYAML dependency

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add pyyaml to dependencies**

In `pyproject.toml`, change:

```toml
dependencies = [
    "PySide6>=6.4.0",
    "python-pptx",
    "watchdog",
    "pywin32; platform_system == 'Windows'",
    "pdf2image",
    "pymupdf",
]
```

to:

```toml
dependencies = [
    "PySide6>=6.4.0",
    "python-pptx",
    "watchdog",
    "pywin32; platform_system == 'Windows'",
    "pdf2image",
    "pymupdf",
    "pyyaml>=6.0",
]
```

- [ ] **Step 2: Install the new dep**

Run: `pip install -e ".[dev]"`
Expected: pyyaml installed without errors.

- [ ] **Step 3: Verify import works**

Run: `python -c "import yaml; print(yaml.__version__)"`
Expected: prints version number.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "deps: add pyyaml for markdown frontmatter parsing"
```

---

## Task 2: Parser data model + frontmatter parsing

**Files:**
- Create: `src/flow/services/markdown/__init__.py`
- Create: `src/flow/services/markdown/parser.py`
- Create: `tests/markdown/__init__.py`
- Create: `tests/markdown/test_parser.py`

- [ ] **Step 1: Empty package init files**

```python
# src/flow/services/markdown/__init__.py
"""Markdown-based slide source — parser + renderer."""
from __future__ import annotations
```

```python
# tests/markdown/__init__.py
```

- [ ] **Step 2: Write failing tests for data model + frontmatter**

```python
# tests/markdown/test_parser.py
from __future__ import annotations

from pathlib import Path

import pytest

from flow.services.markdown.parser import (
    Frontmatter,
    Slide,
    SongSpec,
    parse,
)


def test_empty_file_yields_zero_slides() -> None:
    spec = parse("")
    assert spec.title == ""
    assert spec.slides == []


def test_just_title_yields_zero_slides() -> None:
    spec = parse("# 어떤 곡\n")
    assert spec.title == "어떤 곡"
    assert spec.slides == []


def test_frontmatter_parses_known_fields() -> None:
    text = """\
---
main_size: 56
main_color: "#FFFFFF"
sub_size: 18
background: "bg.jpg"
slide_inches: "13.333x7.5"
resolution: "1920x1080"
---

# T

가사
"""
    spec = parse(text)
    assert spec.frontmatter.main_size == 56
    assert spec.frontmatter.main_color == "#FFFFFF"
    assert spec.frontmatter.sub_size == 18
    assert spec.frontmatter.background == "bg.jpg"
    assert spec.frontmatter.slide_inches == (13.333, 7.5)
    assert spec.frontmatter.resolution == (1920, 1080)


def test_frontmatter_defaults_when_missing() -> None:
    spec = parse("# T\n\n가사\n")
    fm = spec.frontmatter
    assert fm.main_font == "Pretendard Variable"
    assert fm.main_size == 56
    assert fm.main_color == "#FFFFFF"
    assert fm.sub_font == "Pretendard Variable"
    assert fm.sub_size == 18
    assert fm.sub_color == "#CCCCCC"
    assert fm.background == "#000000"
    assert fm.slide_inches == (13.333, 7.5)
    assert fm.resolution == (1920, 1080)


def test_frontmatter_invalid_value_falls_back_to_default(caplog: pytest.LogCaptureFixture) -> None:
    text = """\
---
main_size: "not a number"
slide_inches: "garbage"
---

# T
"""
    spec = parse(text)
    # Invalid values fall back to defaults
    assert spec.frontmatter.main_size == 56
    assert spec.frontmatter.slide_inches == (13.333, 7.5)
```

- [ ] **Step 3: Run tests — expect failure**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/markdown/test_parser.py -v`
Expected: All FAIL with `ModuleNotFoundError`.

- [ ] **Step 4: Implement parser data model + frontmatter**

```python
# src/flow/services/markdown/parser.py
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
    main: str                               # raw main text (multi-line)
    sub_override: str | None                # > sub text, if present on the slide
    section_sub_default: str | None         # ## X :: Y, if the slide is in such a section
    overrides: dict[str, Any] = field(default_factory=dict)  # {key: val} per-slide attrs


@dataclass(frozen=True)
class SongSpec:
    title: str                              # # Title (defaults to "")
    frontmatter: Frontmatter
    slides: list[Slide]


_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)


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
    return SongSpec(title=title, frontmatter=fm, slides=[])


def _extract_title(body: str) -> str:
    for line in body.splitlines():
        if line.startswith("# ") and not line.startswith("## "):
            return line[2:].strip()
    return ""
```

- [ ] **Step 5: Run tests — expect pass**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/markdown/test_parser.py -v`
Expected: All 5 PASS.

- [ ] **Step 6: Verify ruff clean**

Run: `ruff check src/flow/services/markdown/ tests/markdown/`
Expected: All checks passed!

- [ ] **Step 7: Commit**

```bash
git add src/flow/services/markdown/__init__.py src/flow/services/markdown/parser.py tests/markdown/
git commit -m "feat(markdown): parser data model + frontmatter parsing"
```

---

## Task 3: Parser — slide block splitting

**Files:**
- Modify: `src/flow/services/markdown/parser.py`
- Modify: `tests/markdown/test_parser.py`

- [ ] **Step 1: Append failing tests**

```python
# Append to tests/markdown/test_parser.py


def test_two_slide_blocks() -> None:
    spec = parse("# T\n\n첫 슬라이드\n\n둘째 슬라이드\n")
    assert len(spec.slides) == 2
    assert spec.slides[0].main == "첫 슬라이드"
    assert spec.slides[1].main == "둘째 슬라이드"


def test_multiline_main_text() -> None:
    spec = parse("# T\n\n첫 줄\n둘째 줄\n셋째 줄\n")
    assert len(spec.slides) == 1
    assert spec.slides[0].main == "첫 줄\n둘째 줄\n셋째 줄"


def test_section_header_does_not_become_slide() -> None:
    spec = parse("# T\n\n## 1절\n\n가사\n")
    assert len(spec.slides) == 1
    assert spec.slides[0].main == "가사"


def test_multiple_blank_lines_treated_as_one_separator() -> None:
    spec = parse("# T\n\n첫\n\n\n\n둘째\n")
    assert len(spec.slides) == 2


def test_title_line_not_part_of_first_slide() -> None:
    spec = parse("# 어떤 곡\n\n첫 가사\n")
    assert len(spec.slides) == 1
    assert spec.slides[0].main == "첫 가사"
```

- [ ] **Step 2: Run new tests — expect failure**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/markdown/test_parser.py::test_two_slide_blocks -v`
Expected: FAIL (slides list is empty).

- [ ] **Step 3: Implement slide block splitting**

Replace the `parse()` function and add helper:

```python
# Replace parse() with:
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
    """Split body into slide blocks separated by blank lines.

    Lines starting with '#' (title or sections) are skipped — they delimit
    sections but aren't slide content. Each remaining non-blank block of
    consecutive lines becomes one slide.
    """
    slides: list[Slide] = []
    current_lines: list[str] = []

    def flush() -> None:
        if not current_lines:
            return
        main = "\n".join(current_lines).rstrip()
        if main:
            slides.append(Slide(main=main, sub_override=None, section_sub_default=None))
        current_lines.clear()

    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            flush()
            continue
        if not stripped:
            flush()
            continue
        current_lines.append(line)

    flush()
    return slides
```

- [ ] **Step 4: Run all parser tests — expect pass**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/markdown/test_parser.py -v`
Expected: All PASS (10 tests).

- [ ] **Step 5: Commit**

```bash
git add src/flow/services/markdown/parser.py tests/markdown/test_parser.py
git commit -m "feat(markdown): split body into slide blocks separated by blank lines"
```

---

## Task 4: Parser — sub override (`>`) and section sub default (`::`)

**Files:**
- Modify: `src/flow/services/markdown/parser.py`
- Modify: `tests/markdown/test_parser.py`

- [ ] **Step 1: Append failing tests**

```python
# Append to tests/markdown/test_parser.py


def test_sub_override_attached_to_slide() -> None:
    text = "# T\n\n첫 슬라이드\n둘째 줄\n> sub for slide\n"
    spec = parse(text)
    assert len(spec.slides) == 1
    assert spec.slides[0].main == "첫 슬라이드\n둘째 줄"
    assert spec.slides[0].sub_override == "sub for slide"


def test_sub_override_only_when_last_line() -> None:
    """A `>` line in the middle of a slide is just main text, not sub override."""
    text = "# T\n\n첫 줄\n> middle quote\n셋째 줄\n"
    spec = parse(text)
    assert len(spec.slides) == 1
    assert spec.slides[0].main == "첫 줄\n> middle quote\n셋째 줄"
    assert spec.slides[0].sub_override is None


def test_section_sub_default_applies_to_following_slides() -> None:
    text = """\
# T

## 1절 :: 어떤 곡 1절

첫 슬라이드

다음 슬라이드

## 후렴

후렴 슬라이드
"""
    spec = parse(text)
    assert len(spec.slides) == 3
    assert spec.slides[0].section_sub_default == "어떤 곡 1절"
    assert spec.slides[1].section_sub_default == "어떤 곡 1절"
    assert spec.slides[2].section_sub_default is None  # ## 후렴 has no ::


def test_section_without_double_colon_clears_default() -> None:
    text = """\
# T

## 1절 :: 어떤 곡 1절

첫

## 후렴

둘째
"""
    spec = parse(text)
    assert spec.slides[0].section_sub_default == "어떤 곡 1절"
    assert spec.slides[1].section_sub_default is None
```

- [ ] **Step 2: Run — expect failure**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/markdown/test_parser.py -v`
Expected: 4 new tests FAIL.

- [ ] **Step 3: Implement sub override + section sub default**

Replace `_parse_slides()` with:

```python
def _parse_slides(body: str) -> list[Slide]:
    """Split body into slide blocks. Track section sub default and per-slide sub override."""
    slides: list[Slide] = []
    current_lines: list[str] = []
    current_section_default: str | None = None

    def flush() -> None:
        nonlocal current_lines
        if not current_lines:
            return
        sub_override: str | None = None
        if current_lines[-1].lstrip().startswith("> "):
            sub_override = current_lines[-1].lstrip()[2:].strip()
            current_lines = current_lines[:-1]
        main = "\n".join(current_lines).rstrip()
        if main or sub_override:
            slides.append(Slide(
                main=main,
                sub_override=sub_override,
                section_sub_default=current_section_default,
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
```

- [ ] **Step 4: Run — expect pass**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/markdown/test_parser.py -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add src/flow/services/markdown/parser.py tests/markdown/test_parser.py
git commit -m "feat(markdown): sub override (>) and section sub default (::)"
```

---

## Task 5: Parser — slide override `{...}`

**Files:**
- Modify: `src/flow/services/markdown/parser.py`
- Modify: `tests/markdown/test_parser.py`

- [ ] **Step 1: Append failing tests**

```python
# Append to tests/markdown/test_parser.py


def test_slide_override_first_line_parsed() -> None:
    text = "# T\n\n{main_size: 72, main_color: \"#FFD700\"}\n강조 슬라이드\n"
    spec = parse(text)
    assert len(spec.slides) == 1
    assert spec.slides[0].main == "강조 슬라이드"
    assert spec.slides[0].overrides == {
        "main_size": 72,
        "main_color": "#FFD700",
    }


def test_slide_override_must_be_first_line() -> None:
    text = "# T\n\n첫 줄\n{main_size: 72}\n둘째 줄\n"
    spec = parse(text)
    assert spec.slides[0].overrides == {}
    assert "{main_size: 72}" in spec.slides[0].main


def test_slide_override_invalid_yaml_ignored(caplog: pytest.LogCaptureFixture) -> None:
    text = "# T\n\n{not valid yaml\n가사\n"
    spec = parse(text)
    assert spec.slides[0].overrides == {}
    # Should still parse rest of slide normally
    assert "가사" in spec.slides[0].main


def test_slide_override_with_sub() -> None:
    text = "# T\n\n{main_size: 72}\n강조\n> custom sub\n"
    spec = parse(text)
    assert spec.slides[0].overrides == {"main_size": 72}
    assert spec.slides[0].main == "강조"
    assert spec.slides[0].sub_override == "custom sub"
```

- [ ] **Step 2: Run — expect failure**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/markdown/test_parser.py -v`
Expected: 4 new tests FAIL.

- [ ] **Step 3: Implement slide override parsing**

Replace `_parse_slides()` body that handles flush — extract override parsing helper, then update flush:

```python
_OVERRIDE_RE = re.compile(r"\A\{(.+)\}\s*\Z")


def _parse_overrides(line: str) -> dict[str, Any] | None:
    """Parse `{key: val, ...}` line. Return dict on success, None if not an override block."""
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


def _parse_slides(body: str) -> list[Slide]:
    """Split body into slide blocks. Track section sub default, sub override, slide override."""
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
```

- [ ] **Step 4: Run — expect pass**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/markdown/test_parser.py -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add src/flow/services/markdown/parser.py tests/markdown/test_parser.py
git commit -m "feat(markdown): per-slide attribute override via {key: val}"
```

---

## Task 6: Attribute cascade resolver

**Files:**
- Modify: `src/flow/services/markdown/parser.py`
- Modify: `tests/markdown/test_parser.py`

- [ ] **Step 1: Append failing tests**

```python
# Append to tests/markdown/test_parser.py


from flow.services.markdown.parser import resolve_attrs


def test_resolve_uses_frontmatter_when_no_overrides() -> None:
    spec = parse("# T\n\n가사\n")
    attrs = resolve_attrs(spec, spec.slides[0])
    assert attrs.main_font == spec.frontmatter.main_font
    assert attrs.main_size == spec.frontmatter.main_size
    assert attrs.main_color == spec.frontmatter.main_color
    assert attrs.background == spec.frontmatter.background
    assert attrs.sub_text == "T"  # falls back to title


def test_resolve_slide_override_wins() -> None:
    text = "# T\n\n{main_size: 72, main_color: \"#FFD700\"}\n강조\n"
    spec = parse(text)
    attrs = resolve_attrs(spec, spec.slides[0])
    assert attrs.main_size == 72
    assert attrs.main_color == "#FFD700"
    # sub_size/font fall through to frontmatter
    assert attrs.sub_size == spec.frontmatter.sub_size


def test_resolve_sub_text_priority() -> None:
    text = """\
# 곡 제목

## 1절 :: 곡 제목 1절

기본
> 직접 적은 sub

기본만
"""
    spec = parse(text)
    # First slide has > override
    attrs0 = resolve_attrs(spec, spec.slides[0])
    assert attrs0.sub_text == "직접 적은 sub"
    # Second slide uses section default
    attrs1 = resolve_attrs(spec, spec.slides[1])
    assert attrs1.sub_text == "곡 제목 1절"


def test_resolve_sub_text_falls_back_to_title() -> None:
    text = "# 곡 제목\n\n가사\n"
    spec = parse(text)
    attrs = resolve_attrs(spec, spec.slides[0])
    assert attrs.sub_text == "곡 제목"


def test_resolve_sub_text_empty_when_no_title() -> None:
    text = "가사\n"
    spec = parse(text)
    attrs = resolve_attrs(spec, spec.slides[0])
    assert attrs.sub_text == ""
```

- [ ] **Step 2: Run — expect failure**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/markdown/test_parser.py -v`
Expected: 5 new tests FAIL with `ImportError`.

- [ ] **Step 3: Implement resolve_attrs**

Append to `src/flow/services/markdown/parser.py`:

```python
@dataclass(frozen=True)
class ResolvedAttrs:
    """Final attributes for a slide after cascading frontmatter + overrides."""

    main_font: str
    main_size: int
    main_color: str
    sub_font: str
    sub_size: int
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
        main_color=get_str("main_color", fm.main_color),
        sub_font=get_str("sub_font", fm.sub_font),
        sub_size=get_int("sub_size", fm.sub_size),
        sub_color=get_str("sub_color", fm.sub_color),
        background=get_str("background", fm.background),
        sub_text=sub_text,
    )
```

- [ ] **Step 4: Run — expect pass**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/markdown/test_parser.py -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add src/flow/services/markdown/parser.py tests/markdown/test_parser.py
git commit -m "feat(markdown): attribute cascade resolver"
```

---

## Task 7: Renderer — canvas + background

**Files:**
- Create: `src/flow/services/markdown/renderer.py`
- Create: `tests/markdown/test_renderer.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/markdown/test_renderer.py
from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtGui import QImage

from flow.services.markdown.parser import (
    Frontmatter,
    Slide,
    SongSpec,
)
from flow.services.markdown.renderer import render_slide


def _make_spec(background: str = "#000000") -> SongSpec:
    fm = Frontmatter(background=background)
    slides = [Slide(main="hi", sub_override=None, section_sub_default=None)]
    return SongSpec(title="T", frontmatter=fm, slides=slides)


def test_render_returns_qimage_at_resolution(qapp_args, tmp_path: Path) -> None:
    spec = _make_spec()
    img = render_slide(spec, spec.slides[0], song_dir=tmp_path)
    assert isinstance(img, QImage)
    assert img.width() == 1920
    assert img.height() == 1080


def test_render_solid_color_background(qapp_args, tmp_path: Path) -> None:
    spec = _make_spec(background="#112233")
    img = render_slide(spec, spec.slides[0], song_dir=tmp_path)
    pixel = img.pixelColor(10, 10)
    assert pixel.red() == 0x11
    assert pixel.green() == 0x22
    assert pixel.blue() == 0x33


def test_render_image_background_used_when_file_exists(qapp_args, tmp_path: Path) -> None:
    # Create a tiny red 4x4 PNG as the background
    bg = QImage(4, 4, QImage.Format.Format_RGB32)
    bg.fill(0xFFFF0000)  # ARGB: opaque red
    bg_path = tmp_path / "bg.png"
    assert bg.save(str(bg_path))

    spec = SongSpec(
        title="T",
        frontmatter=Frontmatter(background="bg.png"),
        slides=[Slide(main="hi", sub_override=None, section_sub_default=None)],
    )
    img = render_slide(spec, spec.slides[0], song_dir=tmp_path)
    pixel = img.pixelColor(10, 10)
    # Red dominates after cover-scaling 4x4 red image to 1920x1080
    assert pixel.red() > 200
    assert pixel.green() < 50
    assert pixel.blue() < 50


def test_render_missing_image_falls_back_to_default_color(
    qapp_args, tmp_path: Path, caplog: pytest.LogCaptureFixture,
) -> None:
    spec = SongSpec(
        title="T",
        frontmatter=Frontmatter(background="missing.jpg"),
        slides=[Slide(main="hi", sub_override=None, section_sub_default=None)],
    )
    img = render_slide(spec, spec.slides[0], song_dir=tmp_path)
    # Falls back to black (default color for missing-image path)
    pixel = img.pixelColor(10, 10)
    assert pixel.red() == 0 and pixel.green() == 0 and pixel.blue() == 0
```

- [ ] **Step 2: Run — expect failure**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/markdown/test_renderer.py -v`
Expected: All FAIL with `ImportError`.

- [ ] **Step 3: Implement renderer skeleton + background**

```python
# src/flow/services/markdown/renderer.py
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

    img_path = (song_dir / background) if not Path(background).is_absolute() else Path(background)
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
```

- [ ] **Step 4: Run — expect pass**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/markdown/test_renderer.py -v`
Expected: All 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/flow/services/markdown/renderer.py tests/markdown/test_renderer.py
git commit -m "feat(markdown): renderer canvas + background (color + image cover)"
```

---

## Task 8: Renderer — pt → pixel + text rendering

**Files:**
- Modify: `src/flow/services/markdown/renderer.py`
- Modify: `tests/markdown/test_renderer.py`

- [ ] **Step 1: Append failing tests**

```python
# Append to tests/markdown/test_renderer.py


def test_render_main_text_visible_in_main_box(qapp_args, tmp_path: Path) -> None:
    """Main text region (top 36.3%, height 30%) should differ from background."""
    spec = SongSpec(
        title="T",
        frontmatter=Frontmatter(
            background="#000000",
            main_color="#FFFFFF",
            main_size=72,
        ),
        slides=[Slide(main="ABCDEFG", sub_override=None, section_sub_default=None)],
    )
    img = render_slide(spec, spec.slides[0], song_dir=tmp_path)
    # Sample several pixels in the main text region (rows ~36-66% × cols ~30-70%)
    width, height = img.width(), img.height()
    main_y_start = int(height * 0.36)
    main_y_end = int(height * 0.66)
    found_text_pixel = False
    for y in range(main_y_start, main_y_end, 10):
        for x in range(int(width * 0.3), int(width * 0.7), 20):
            p = img.pixelColor(x, y)
            if p.red() > 200 and p.green() > 200 and p.blue() > 200:
                found_text_pixel = True
                break
        if found_text_pixel:
            break
    assert found_text_pixel, "main text not visible in expected region"


def test_render_sub_text_visible_in_sub_box(qapp_args, tmp_path: Path) -> None:
    """Sub text region (top 89.7%, height 8%) should differ from background."""
    spec = SongSpec(
        title="SUBTITLE",
        frontmatter=Frontmatter(
            background="#000000",
            sub_color="#CCCCCC",
            sub_size=32,
        ),
        slides=[Slide(main="main", sub_override=None, section_sub_default=None)],
    )
    img = render_slide(spec, spec.slides[0], song_dir=tmp_path)
    width, height = img.width(), img.height()
    # Sub region: rows 89.7-98%
    found = False
    for y in range(int(height * 0.90), int(height * 0.97), 2):
        for x in range(int(width * 0.30), int(width * 0.70), 5):
            p = img.pixelColor(x, y)
            if p.red() > 100 and p.green() > 100 and p.blue() > 100:
                found = True
                break
        if found:
            break
    assert found, "sub text not visible in expected region"


def test_pt_to_pixel_conversion() -> None:
    """At slide_inches=(13.333, 7.5), resolution=(1920, 1080):
    DPI = 1080 / 7.5 = 144. So 72pt = 1in = 144px.
    """
    from flow.services.markdown.renderer import _pt_to_px
    px = _pt_to_px(72, slide_inches=(13.333, 7.5), resolution=(1920, 1080))
    assert px == pytest.approx(144, abs=1)


def test_pt_to_pixel_with_smaller_canvas() -> None:
    """At smaller canvas (e.g. user PPT 11.02×6.20), DPI is higher.
    DPI = 1080 / 6.20 ≈ 174.
    """
    from flow.services.markdown.renderer import _pt_to_px
    px = _pt_to_px(72, slide_inches=(11.02, 6.20), resolution=(1920, 1080))
    assert px == pytest.approx(174, abs=1)
```

- [ ] **Step 2: Run — expect failure**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/markdown/test_renderer.py -v`
Expected: 4 new tests FAIL.

- [ ] **Step 3: Implement pt→pixel + text rendering**

In `src/flow/services/markdown/renderer.py`, add and update `render_slide`:

```python
# Add at module top
from PySide6.QtGui import QFont
from PySide6.QtCore import QRect


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
```

Replace the existing `render_slide()` body with the full version:

```python
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


def _draw_main_text(
    painter: QPainter,
    target: QImage,
    text: str,
    attrs,
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
    px = _pt_to_px(attrs.main_size, slide_inches=fm.slide_inches, resolution=fm.resolution)
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
    attrs,
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
    px = _pt_to_px(attrs.sub_size, slide_inches=fm.slide_inches, resolution=fm.resolution)
    font = QFont(attrs.sub_font)
    font.setPixelSize(max(1, int(px)))
    painter.setFont(font)
    painter.setPen(QColor(attrs.sub_color))
    painter.drawText(
        box,
        int(Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap),
        text,
    )
```

- [ ] **Step 4: Run — expect pass**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/markdown/test_renderer.py -v`
Expected: All PASS (8 tests).

- [ ] **Step 5: Commit**

```bash
git add src/flow/services/markdown/renderer.py tests/markdown/test_renderer.py
git commit -m "feat(markdown): pt→pixel conversion + main/sub text rendering"
```

---

## Task 9: render_all + module exports

**Files:**
- Modify: `src/flow/services/markdown/renderer.py`
- Modify: `src/flow/services/markdown/__init__.py`
- Modify: `tests/markdown/test_renderer.py`

- [ ] **Step 1: Append failing test**

```python
# Append to tests/markdown/test_renderer.py


def test_render_all_returns_one_image_per_slide(qapp_args, tmp_path: Path) -> None:
    from flow.services.markdown.parser import parse
    from flow.services.markdown.renderer import render_all

    text = """\
# T

가사 1

가사 2

가사 3
"""
    spec = parse(text)
    images = render_all(spec, song_dir=tmp_path)
    assert len(images) == 3
    assert all(isinstance(img, QImage) for img in images)
```

- [ ] **Step 2: Run — expect failure**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/markdown/test_renderer.py::test_render_all_returns_one_image_per_slide -v`
Expected: FAIL.

- [ ] **Step 3: Add render_all + exports**

Append to `src/flow/services/markdown/renderer.py`:

```python
def render_all(spec: SongSpec, *, song_dir: Path) -> list[QImage]:
    """Render every slide in the spec."""
    return [render_slide(spec, s, song_dir=song_dir) for s in spec.slides]
```

Replace `src/flow/services/markdown/__init__.py` with:

```python
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
```

- [ ] **Step 4: Run — expect pass**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/markdown/ -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add src/flow/services/markdown/renderer.py src/flow/services/markdown/__init__.py tests/markdown/test_renderer.py
git commit -m "feat(markdown): render_all + public API exports"
```

---

## Task 10: MarkdownSlideConverter

**Files:**
- Modify: `src/flow/services/slide_converter.py`
- Create: `tests/markdown/test_converter.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/markdown/test_converter.py
from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QImage

from flow.services.slide_converter import MarkdownSlideConverter


def test_get_slide_count(qapp_args, tmp_path: Path) -> None:
    md = tmp_path / "slides.md"
    md.write_text("# T\n\n가사 1\n\n가사 2\n", encoding="utf-8")

    conv = MarkdownSlideConverter()
    assert conv.get_slide_count(md) == 2


def test_convert_slide_returns_qimage(qapp_args, tmp_path: Path) -> None:
    md = tmp_path / "slides.md"
    md.write_text("# T\n\n가사 1\n\n가사 2\n", encoding="utf-8")

    conv = MarkdownSlideConverter()
    img = conv.convert_slide(md, 0)
    assert isinstance(img, QImage)
    assert img.width() == 1920
    assert img.height() == 1080


def test_caching_avoids_reparse(qapp_args, tmp_path: Path) -> None:
    md = tmp_path / "slides.md"
    md.write_text("# T\n\n가사 1\n", encoding="utf-8")
    conv = MarkdownSlideConverter()
    img1 = conv.convert_slide(md, 0)
    img2 = conv.convert_slide(md, 0)
    # Same identity from cache
    assert img1 is img2


def test_invalidate_cache_forces_rerender(qapp_args, tmp_path: Path) -> None:
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
```

- [ ] **Step 2: Run — expect failure**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/markdown/test_converter.py -v`
Expected: FAIL — `MarkdownSlideConverter` not in `slide_converter`.

- [ ] **Step 3: Add MarkdownSlideConverter to slide_converter.py**

Append to `src/flow/services/slide_converter.py` (after existing converter classes, before `create_slide_converter`):

```python
class MarkdownSlideConverter(SlideConverter):
    """Renders Flow markdown slide files to images using Qt only."""

    def __init__(self) -> None:
        self._cache: dict[Path, list] = {}

    def get_engine_name(self) -> str:
        return "Markdown"

    def get_slide_count(self, md_path: Path) -> int:
        return len(self._slides_for(md_path))

    def convert_slide(self, md_path: Path, index: int, status_callback=None) -> QImage:
        slides = self._slides_for(md_path)
        return slides[index]

    def invalidate_cache(self, md_path: Path) -> None:
        self._cache.pop(Path(md_path).resolve(), None)

    def clear_cache(self) -> None:
        self._cache.clear()

    def _slides_for(self, md_path: Path):
        from flow.services.markdown import parse, render_all

        key = Path(md_path).resolve()
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        text = key.read_text(encoding="utf-8")
        spec = parse(text)
        images = render_all(spec, song_dir=key.parent)
        self._cache[key] = images
        return images
```

- [ ] **Step 4: Run — expect pass**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/markdown/test_converter.py -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add src/flow/services/slide_converter.py tests/markdown/test_converter.py
git commit -m "feat(slide_converter): MarkdownSlideConverter with cache"
```

---

## Task 11: Song domain — markdown_path, has_markdown, slide_source

**Files:**
- Modify: `src/flow/domain/song.py`
- Create: `tests/domain/test_song_markdown.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/domain/test_song_markdown.py
from __future__ import annotations

from pathlib import Path

from flow.domain.song import Song


def test_markdown_path_default(tmp_path: Path) -> None:
    folder = tmp_path / "song1"
    folder.mkdir()
    song = Song(name="song1", folder=folder, project_dir=tmp_path)
    assert song.markdown_path == folder / "slides.md"


def test_has_markdown_true(tmp_path: Path) -> None:
    folder = tmp_path / "song1"
    folder.mkdir()
    (folder / "slides.md").write_text("# T", encoding="utf-8")
    song = Song(name="song1", folder=folder, project_dir=tmp_path)
    assert song.has_markdown is True


def test_has_markdown_false(tmp_path: Path) -> None:
    folder = tmp_path / "song1"
    folder.mkdir()
    song = Song(name="song1", folder=folder, project_dir=tmp_path)
    assert song.has_markdown is False


def test_slide_source_markdown_wins_when_both_exist(tmp_path: Path) -> None:
    folder = tmp_path / "song1"
    folder.mkdir()
    (folder / "slides.md").write_text("# T", encoding="utf-8")
    (folder / "slides.pptx").write_bytes(b"fake")
    song = Song(name="song1", folder=folder, project_dir=tmp_path)
    assert song.slide_source == "markdown"


def test_slide_source_pptx_when_only_pptx(tmp_path: Path) -> None:
    folder = tmp_path / "song1"
    folder.mkdir()
    (folder / "slides.pptx").write_bytes(b"fake")
    song = Song(name="song1", folder=folder, project_dir=tmp_path)
    assert song.slide_source == "pptx"


def test_slide_source_none_when_neither(tmp_path: Path) -> None:
    folder = tmp_path / "song1"
    folder.mkdir()
    song = Song(name="song1", folder=folder, project_dir=tmp_path)
    assert song.slide_source == "none"
```

- [ ] **Step 2: Run — expect failure**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/domain/test_song_markdown.py -v`
Expected: All FAIL — attributes don't exist.

- [ ] **Step 3: Add to Song domain**

In `src/flow/domain/song.py`, add (next to other path properties like `abs_slides_path`):

```python
@property
def markdown_path(self) -> Path:
    """slides.md absolute path."""
    return self._resolve_abs(self.folder / "slides.md")

@property
def has_markdown(self) -> bool:
    return self.markdown_path.exists()

@property
def slide_source(self) -> str:
    """One of: 'markdown', 'pptx', 'none'. markdown wins if both exist."""
    if self.has_markdown:
        return "markdown"
    if self.has_slides:
        return "pptx"
    return "none"
```

- [ ] **Step 4: Run — expect pass**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/domain/test_song_markdown.py -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add src/flow/domain/song.py tests/domain/test_song_markdown.py
git commit -m "feat(song): markdown_path, has_markdown, slide_source"
```

---

## Task 12: SlideManager dispatch by extension

**Files:**
- Modify: `src/flow/services/slide_manager.py`
- Modify: `src/flow/services/slide_converter.py` (verify create_slide_converter still works for both)
- Create: `tests/services/test_slide_manager_markdown.py`

- [ ] **Step 1: Read existing dispatch**

Read `src/flow/services/slide_manager.py` to find:
- The `__init__` constructor — currently creates `_converter` via `create_slide_converter()`
- Where `_converter.convert_slide(path, index)` is called inside `SlideWorker`
- Where `_converter.get_slide_count(path)` is called

Sketch: SlideManager currently holds ONE converter. We extend so it can hold both PPT-style converter (for `.pptx`) AND a `MarkdownSlideConverter` (for `.md`), and dispatch on the file extension.

- [ ] **Step 2: Write failing test**

```python
# tests/services/test_slide_manager_markdown.py
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from flow.services.slide_manager import SlideManager


def test_load_pptx_with_md_path_uses_markdown_converter(qapp_args, tmp_path: Path) -> None:
    md = tmp_path / "slides.md"
    md.write_text("# T\n\n가사 1\n\n가사 2\n", encoding="utf-8")

    sm = SlideManager()

    finished = []
    sm.load_finished.connect(lambda count: finished.append(count))

    sm.load_pptx(md)

    # Wait for SlideWorker to finish (file watcher / Qt event loop)
    from PySide6.QtCore import QEventLoop, QTimer
    loop = QEventLoop()
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    sm.load_finished.connect(loop.quit)
    timer.start(3000)
    if not finished:
        loop.exec()

    assert finished, "load_finished signal never fired"
    assert finished[0] == 2
```

- [ ] **Step 3: Run — expect failure**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/services/test_slide_manager_markdown.py -v`
Expected: FAIL — markdown path not handled.

- [ ] **Step 4: Add dispatch in SlideManager**

In `src/flow/services/slide_manager.py`:

1. Add markdown converter alongside existing converter. In `__init__`, after building `self._converter`:

```python
# Markdown converter is always available (no external deps)
from flow.services.slide_converter import MarkdownSlideConverter
self._markdown_converter = MarkdownSlideConverter()
```

2. Add a helper to pick the right converter:

```python
def _converter_for(self, path: Path):
    """Return the right converter for this file's extension."""
    if str(path).lower().endswith(".md"):
        return self._markdown_converter
    return self._converter
```

3. Update `SlideWorker` so it can be told which converter to use, OR (simpler) instantiate two workers and dispatch from SlideManager. The existing pattern uses ONE worker tied to ONE converter. Cleanest extension: hold two workers.

Replace the worker setup in `SlideManager.__init__`. Read existing init for `self._worker = SlideWorker(self._converter)` and change to:

```python
if self._converter is not None:
    self._worker = SlideWorker(self._converter)
    self._connect_worker(self._worker)
    self._worker.start()
else:
    self._worker = None

# Markdown worker uses the always-available markdown converter
self._markdown_worker = SlideWorker(self._markdown_converter)
self._connect_worker(self._markdown_worker)
self._markdown_worker.start()
```

4. Update `load_pptx` to dispatch:

Find the existing branch:
```python
self._pptx_path = p
self.load_started.emit()
self._worker.add_task(PPTTask(PPTTask.LOAD_SINGLE, p))
```

Replace with:
```python
self._pptx_path = p
self.load_started.emit()
worker = self._markdown_worker if str(p).lower().endswith(".md") else self._worker
if worker is None:
    self.engine_missing.emit()
    self.load_finished.emit(0)
    return
worker.add_task(PPTTask(PPTTask.LOAD_SINGLE, p))
```

Same pattern in `load_songs` and any other entry that adds a task — pick the right worker per-task.

5. Update `stop_workers`:

```python
def stop_workers(self):
    for worker in (self._worker, self._markdown_worker):
        if worker is not None:
            worker.stop()
            worker.wait()
```

- [ ] **Step 5: Run — expect pass**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/services/test_slide_manager_markdown.py tests/services/test_slide_manager.py -v`
Expected: New test PASSES; existing tests still pass (except pre-existing flaky `test_file_watcher_notifies_on_change`).

- [ ] **Step 6: Commit**

```bash
git add src/flow/services/slide_manager.py tests/services/test_slide_manager_markdown.py
git commit -m "feat(slide_manager): dispatch markdown vs pptx by file extension"
```

---

## Task 13: File watcher .md support + hot reload

**Files:**
- Modify: `src/flow/services/slide_manager.py`
- Modify: `tests/services/test_slide_manager_markdown.py`

The existing watcher watches `.pptx` for changes. Extend to also watch `.md`. On change → invalidate the markdown converter's cache → re-emit content so UI rerenders.

- [ ] **Step 1: Read existing watcher setup**

Find where SlideManager creates the watchdog `Observer` and how it filters events. Identify the handler.

- [ ] **Step 2: Append failing test**

```python
# Append to tests/services/test_slide_manager_markdown.py


def test_md_file_change_invalidates_markdown_cache(qapp_args, tmp_path: Path) -> None:
    md = tmp_path / "slides.md"
    md.write_text("# T\n\n가사 1\n", encoding="utf-8")

    sm = SlideManager()
    sm.load_pptx(md)

    # Wait for first load
    from PySide6.QtCore import QEventLoop, QTimer
    loop = QEventLoop()
    QTimer.singleShot(2000, loop.quit)
    sm.load_finished.connect(loop.quit)
    loop.exec()

    # Modify file
    md.write_text("# T\n\n가사 1\n\n가사 2\n", encoding="utf-8")

    # Wait for watcher to fire (file_changed signal exists for PPT — confirm same fires for md)
    fired = []
    sm.file_changed.connect(lambda *a: fired.append(True))
    loop2 = QEventLoop()
    QTimer.singleShot(3000, loop2.quit)
    sm.file_changed.connect(loop2.quit)
    loop2.exec()

    assert fired, "file_changed didn't fire for .md modification"
```

- [ ] **Step 3: Run — expect failure**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/services/test_slide_manager_markdown.py::test_md_file_change_invalidates_markdown_cache -v`
Expected: FAIL.

- [ ] **Step 4: Update watcher**

In `src/flow/services/slide_manager.py`, find the watchdog `FileSystemEventHandler` subclass. Update the handler to:
- Match `.md` files in addition to `.pptx`
- On change of `.md`, call `self._markdown_converter.invalidate_cache(path)` before emitting `file_changed`

Concrete change inside the handler's `on_modified`:

```python
def on_modified(self, event):
    if event.is_directory:
        return
    p = Path(event.src_path)
    suffix = p.suffix.lower()
    if suffix not in (".pptx", ".md"):
        return
    if self._slide_manager._pptx_path != p:
        return
    if self._slide_manager._watch_paused:
        return
    if suffix == ".md":
        self._slide_manager._markdown_converter.invalidate_cache(p)
    self._slide_manager.file_changed.emit(p)
```

(Adjust to actual handler shape — read it first.)

- [ ] **Step 5: Run — expect pass**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/services/test_slide_manager_markdown.py -v`
Expected: New test PASSES.

- [ ] **Step 6: Commit**

```bash
git add src/flow/services/slide_manager.py tests/services/test_slide_manager_markdown.py
git commit -m "feat(slide_manager): file watcher invalidates markdown cache on .md changes"
```

---

## Task 14: Markdown syntax highlighter

**Files:**
- Create: `src/flow/ui/editor/markdown_highlighter.py`
- Create: `tests/ui/test_markdown_highlighter.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/ui/test_markdown_highlighter.py
from __future__ import annotations

from PySide6.QtGui import QTextDocument

from flow.ui.editor.markdown_highlighter import MarkdownHighlighter


def test_highlighter_attaches_to_document(qapp_args) -> None:
    doc = QTextDocument()
    h = MarkdownHighlighter(doc)
    assert h.document() is doc


def test_highlighter_processes_text_without_error(qapp_args) -> None:
    doc = QTextDocument()
    MarkdownHighlighter(doc)
    doc.setPlainText("---\nmain_size: 56\n---\n\n# T\n\n## 1절 :: T 1절\n\n{main_size: 72}\n가사\n> sub\n")
    # If we got here without exception, syntax highlight ran without crashing
    assert doc.blockCount() > 0
```

- [ ] **Step 2: Run — expect failure**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/ui/test_markdown_highlighter.py -v`
Expected: FAIL — `MarkdownHighlighter` doesn't exist.

- [ ] **Step 3: Implement highlighter**

```python
# src/flow/ui/editor/markdown_highlighter.py
"""Syntax highlighter for markdown song files."""
from __future__ import annotations

import re

from PySide6.QtGui import (
    QColor,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextDocument,
)


class MarkdownHighlighter(QSyntaxHighlighter):
    """Highlights frontmatter, headers, sub override (>), slide override ({...})."""

    def __init__(self, document: QTextDocument) -> None:
        super().__init__(document)

        # Color palette — soft, not distracting
        self._fmt_frontmatter = self._format("#7DA0CA")  # blue
        self._fmt_header = self._format("#E5C07B", bold=True)  # gold
        self._fmt_section = self._format("#98C379")  # green
        self._fmt_section_sub = self._format("#56B6C2", italic=True)  # cyan, the part after ::
        self._fmt_sub_override = self._format("#56B6C2")  # cyan
        self._fmt_slide_override = self._format("#C678DD", italic=True)  # purple

        # State across blocks
        self._in_frontmatter = False

    def _format(self, color: str, bold: bool = False, italic: bool = False) -> QTextCharFormat:
        f = QTextCharFormat()
        f.setForeground(QColor(color))
        if bold:
            f.setFontWeight(700)
        if italic:
            f.setFontItalic(True)
        return f

    def highlightBlock(self, text: str) -> None:
        # Toggle frontmatter state on `---`
        if text.strip() == "---":
            # block-level formatting
            self.setFormat(0, len(text), self._fmt_frontmatter)
            # toggle: previousBlockState 0 = outside, 1 = inside
            prev = self.previousBlockState()
            self.setCurrentBlockState(1 if prev <= 0 else 0)
            return
        prev = self.previousBlockState()
        if prev == 1:
            # Inside frontmatter
            self.setFormat(0, len(text), self._fmt_frontmatter)
            self.setCurrentBlockState(1)
            return
        self.setCurrentBlockState(0)

        # Slide override: leading {...}
        m = re.match(r"\{[^}]*\}\s*$", text)
        if m:
            self.setFormat(0, len(text), self._fmt_slide_override)
            return

        # Header: # Title or ## Section
        if text.startswith("# ") and not text.startswith("## "):
            self.setFormat(0, len(text), self._fmt_header)
            return
        if text.startswith("## "):
            # Color the leading ## section, then ::sub-default in different color
            sep = text.find("::")
            if sep == -1:
                self.setFormat(0, len(text), self._fmt_section)
            else:
                self.setFormat(0, sep, self._fmt_section)
                self.setFormat(sep, len(text) - sep, self._fmt_section_sub)
            return

        # Sub override: leading >
        if text.lstrip().startswith("> "):
            self.setFormat(0, len(text), self._fmt_sub_override)
            return
```

- [ ] **Step 4: Run — expect pass**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/ui/test_markdown_highlighter.py -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add src/flow/ui/editor/markdown_highlighter.py tests/ui/test_markdown_highlighter.py
git commit -m "feat(editor): markdown syntax highlighter"
```

---

## Task 15: Frontmatter form dialog

**Files:**
- Create: `src/flow/ui/editor/markdown_frontmatter_dialog.py`
- Create: `tests/ui/test_markdown_frontmatter_dialog.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/ui/test_markdown_frontmatter_dialog.py
from __future__ import annotations

from flow.services.markdown.parser import Frontmatter
from flow.ui.editor.markdown_frontmatter_dialog import (
    apply_frontmatter_to_text,
    parse_form_values,
)


def test_apply_to_text_replaces_existing_frontmatter() -> None:
    original = """\
---
main_size: 56
---

# T

가사
"""
    fm = Frontmatter(main_size=72)
    new = apply_frontmatter_to_text(original, fm)
    # New frontmatter has main_size: 72 (and other defaults)
    assert "main_size: 72" in new
    # Body preserved
    assert "# T" in new
    assert "가사" in new


def test_apply_to_text_inserts_when_no_frontmatter() -> None:
    original = "# T\n\n가사\n"
    fm = Frontmatter(main_size=72)
    new = apply_frontmatter_to_text(original, fm)
    assert new.startswith("---\n")
    assert "main_size: 72" in new
    assert "# T" in new


def test_parse_form_values_int() -> None:
    assert parse_form_values({"main_size": "72"}).main_size == 72
    # Bad input → default
    assert parse_form_values({"main_size": "abc"}).main_size == 56
```

- [ ] **Step 2: Run — expect failure**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/ui/test_markdown_frontmatter_dialog.py -v`
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Implement the dialog + helpers**

```python
# src/flow/ui/editor/markdown_frontmatter_dialog.py
"""Frontmatter form modal — edit YAML frontmatter via form fields."""
from __future__ import annotations

import re
from dataclasses import asdict

import yaml
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QHBoxLayout,
    QVBoxLayout,
)

from flow.services.markdown.parser import Frontmatter, _build_frontmatter


_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def parse_form_values(values: dict[str, str]) -> Frontmatter:
    """Convert form string values back into a Frontmatter, falling back to defaults."""
    raw: dict[str, object] = {}
    for k, v in values.items():
        if v == "":
            continue
        raw[k] = v
    return _build_frontmatter(raw)


def _frontmatter_to_yaml(fm: Frontmatter) -> str:
    """Serialize a Frontmatter to YAML for embedding."""
    d = {
        "main_font": fm.main_font,
        "main_size": fm.main_size,
        "main_color": fm.main_color,
        "sub_font": fm.sub_font,
        "sub_size": fm.sub_size,
        "sub_color": fm.sub_color,
        "background": fm.background,
        "slide_inches": f"{fm.slide_inches[0]}x{fm.slide_inches[1]}",
        "resolution": f"{fm.resolution[0]}x{fm.resolution[1]}",
    }
    return yaml.safe_dump(d, allow_unicode=True, sort_keys=False).rstrip() + "\n"


def apply_frontmatter_to_text(text: str, fm: Frontmatter) -> str:
    """Replace or insert frontmatter block in markdown text."""
    yaml_body = _frontmatter_to_yaml(fm)
    block = f"---\n{yaml_body}---\n"
    m = _FRONTMATTER_RE.match(text)
    if m:
        return block + text[m.end():]
    return block + "\n" + text


class FrontmatterDialog(QDialog):
    """Modal: edit frontmatter via form fields."""

    def __init__(self, current: Frontmatter, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Frontmatter 편집")
        self._fm = current
        self._inputs: dict[str, QLineEdit] = {}

        form = QFormLayout()
        for key, label in (
            ("main_font", "메인 폰트"),
            ("main_size", "메인 크기"),
            ("main_color", "메인 색"),
            ("sub_font", "서브 폰트"),
            ("sub_size", "서브 크기"),
            ("sub_color", "서브 색"),
            ("background", "배경"),
            ("slide_inches", "슬라이드 크기 (inch)"),
            ("resolution", "해상도 (px)"),
        ):
            le = QLineEdit(self._initial_value(key))
            self._inputs[key] = le
            form.addRow(label, le)

        layout = QVBoxLayout(self)
        layout.addLayout(form)

        buttons = QHBoxLayout()
        buttons.addStretch()
        ok = QPushButton("OK")
        cancel = QPushButton("취소")
        buttons.addWidget(cancel)
        buttons.addWidget(ok)
        layout.addLayout(buttons)
        ok.setDefault(True)
        ok.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)

    def _initial_value(self, key: str) -> str:
        v = getattr(self._fm, key)
        if isinstance(v, tuple):
            return f"{v[0]}x{v[1]}"
        return str(v)

    def result_frontmatter(self) -> Frontmatter:
        return parse_form_values({k: le.text() for k, le in self._inputs.items()})
```

- [ ] **Step 4: Run — expect pass**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/ui/test_markdown_frontmatter_dialog.py -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add src/flow/ui/editor/markdown_frontmatter_dialog.py tests/ui/test_markdown_frontmatter_dialog.py
git commit -m "feat(editor): frontmatter form dialog + apply-to-text helper"
```

---

## Task 16: MarkdownEditor split-view widget

**Files:**
- Create: `src/flow/ui/editor/markdown_editor.py`
- Create: `tests/ui/test_markdown_editor.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/ui/test_markdown_editor.py
from __future__ import annotations

from pathlib import Path

from flow.ui.editor.markdown_editor import MarkdownEditor


def test_editor_loads_existing_file(qapp_args, tmp_path: Path) -> None:
    md = tmp_path / "slides.md"
    md.write_text("# T\n\n가사\n", encoding="utf-8")
    ed = MarkdownEditor(md)
    assert "가사" in ed.text()
    assert ed.is_dirty() is False


def test_editor_save_writes_file(qapp_args, tmp_path: Path) -> None:
    md = tmp_path / "slides.md"
    md.write_text("# T\n\n가사 1\n", encoding="utf-8")
    ed = MarkdownEditor(md)
    ed.set_text("# T\n\n가사 2\n")
    assert ed.is_dirty() is True
    ed.save()
    assert md.read_text(encoding="utf-8") == "# T\n\n가사 2\n"
    assert ed.is_dirty() is False


def test_editor_dirty_after_text_change(qapp_args, tmp_path: Path) -> None:
    md = tmp_path / "slides.md"
    md.write_text("# T\n", encoding="utf-8")
    ed = MarkdownEditor(md)
    ed.set_text("# X\n")
    assert ed.is_dirty() is True
```

- [ ] **Step 2: Run — expect failure**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/ui/test_markdown_editor.py -v`
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Implement MarkdownEditor**

```python
# src/flow/ui/editor/markdown_editor.py
"""Split-view markdown song editor with live preview."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from flow.services.markdown import parse, render_all
from flow.ui.editor.markdown_frontmatter_dialog import (
    FrontmatterDialog,
    apply_frontmatter_to_text,
)
from flow.ui.editor.markdown_highlighter import MarkdownHighlighter


class MarkdownEditor(QWidget):
    """Split-view editor: text on left, preview on right."""

    def __init__(self, md_path: Path, parent=None) -> None:
        super().__init__(parent)
        self._md_path = md_path
        self._original_text = (
            md_path.read_text(encoding="utf-8") if md_path.exists() else ""
        )

        # Toolbar
        toolbar = QToolBar()
        save_btn = QPushButton("저장 (Ctrl+S)")
        section_btn = QPushButton("섹션 추가")
        slide_btn = QPushButton("슬라이드 나누기")
        fm_btn = QPushButton("Frontmatter 편집")
        toolbar.addWidget(save_btn)
        toolbar.addWidget(section_btn)
        toolbar.addWidget(slide_btn)
        toolbar.addWidget(fm_btn)

        # Text editor (left)
        self._text_edit = QPlainTextEdit()
        self._text_edit.setPlainText(self._original_text)
        self._highlighter = MarkdownHighlighter(self._text_edit.document())

        # Preview (right): big preview + thumbnail list
        self._preview_label = QLabel("미리보기")
        self._preview_label.setMinimumSize(400, 225)
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thumbs = QListWidget()
        self._thumbs.setFlow(QListWidget.Flow.LeftToRight)
        self._thumbs.setFixedHeight(80)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(self._preview_label, 1)
        right_layout.addWidget(self._thumbs)

        # Split
        splitter = QSplitter()
        splitter.addWidget(self._text_edit)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)

        # Layout
        layout = QVBoxLayout(self)
        layout.addWidget(toolbar)
        layout.addWidget(splitter, 1)

        # Wire
        save_btn.clicked.connect(self.save)
        section_btn.clicked.connect(self._insert_section)
        slide_btn.clicked.connect(self._insert_slide_break)
        fm_btn.clicked.connect(self._open_frontmatter_dialog)
        self._text_edit.textChanged.connect(self._on_text_changed)
        self._text_edit.cursorPositionChanged.connect(self._on_cursor_moved)

        # Ctrl+S shortcut
        save_sc = QShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_S), self)
        save_sc.activated.connect(self.save)

        self._render_preview()

    # ── Public API ────────────────────────────────────────────────
    def text(self) -> str:
        return self._text_edit.toPlainText()

    def set_text(self, t: str) -> None:
        self._text_edit.setPlainText(t)

    def is_dirty(self) -> bool:
        return self.text() != self._original_text

    def save(self) -> None:
        text = self.text()
        self._md_path.write_text(text, encoding="utf-8")
        self._original_text = text
        self._render_preview()

    # ── Internals ─────────────────────────────────────────────────
    def _on_text_changed(self) -> None:
        # Could debounce + auto-rerender preview, but for v1 only on save
        pass

    def _on_cursor_moved(self) -> None:
        # Update which slide is shown in preview
        line_num = self._text_edit.textCursor().blockNumber()
        idx = self._slide_index_at_line(line_num)
        if 0 <= idx < self._thumbs.count():
            self._thumbs.setCurrentRow(idx)
            self._render_main_preview(idx)

    def _slide_index_at_line(self, line: int) -> int:
        """Map cursor line to slide index by re-parsing and counting blank-line blocks."""
        text = self.text()
        slides = parse(text).slides
        if not slides:
            return -1
        # Best-effort: count slide-block separators above cursor line
        running_idx = 0
        in_slide = False
        for i, raw in enumerate(text.splitlines()):
            stripped = raw.strip()
            if stripped.startswith("#"):
                if in_slide:
                    in_slide = False
                continue
            if not stripped:
                if in_slide:
                    running_idx += 1
                    in_slide = False
                continue
            if not in_slide:
                in_slide = True
            if i >= line:
                break
        return min(running_idx, len(slides) - 1)

    def _render_preview(self) -> None:
        """Re-parse + render all slides; populate thumbnails + main preview."""
        from PySide6.QtGui import QPixmap

        text = self.text()
        spec = parse(text)
        images = render_all(spec, song_dir=self._md_path.parent)
        self._thumbs.clear()
        for i, img in enumerate(images):
            item = QListWidgetItem(f"{i + 1}")
            pix = QPixmap.fromImage(img).scaled(
                100, 56, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            from PySide6.QtGui import QIcon
            item.setIcon(QIcon(pix))
            self._thumbs.addItem(item)
        if images:
            self._render_main_preview(0)

    def _render_main_preview(self, idx: int) -> None:
        from PySide6.QtGui import QPixmap

        text = self.text()
        spec = parse(text)
        if idx < 0 or idx >= len(spec.slides):
            return
        from flow.services.markdown import render_slide

        img = render_slide(spec, spec.slides[idx], song_dir=self._md_path.parent)
        pix = QPixmap.fromImage(img).scaled(
            self._preview_label.width(), self._preview_label.height(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._preview_label.setPixmap(pix)

    def _insert_section(self) -> None:
        cursor = self._text_edit.textCursor()
        cursor.insertText("\n## 새 섹션\n\n")

    def _insert_slide_break(self) -> None:
        cursor = self._text_edit.textCursor()
        cursor.insertText("\n\n")

    def _open_frontmatter_dialog(self) -> None:
        spec = parse(self.text())
        dlg = FrontmatterDialog(spec.frontmatter, parent=self)
        if dlg.exec() == FrontmatterDialog.DialogCode.Accepted:
            new_fm = dlg.result_frontmatter()
            new_text = apply_frontmatter_to_text(self.text(), new_fm)
            self._text_edit.setPlainText(new_text)
```

- [ ] **Step 4: Run — expect pass**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/ui/test_markdown_editor.py -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add src/flow/ui/editor/markdown_editor.py tests/ui/test_markdown_editor.py
git commit -m "feat(editor): MarkdownEditor split-view widget with live preview"
```

---

## Task 17: Edit button entry from song list

**Files:**
- Modify: `src/flow/ui/editor/song_list_widget.py`

The existing PPT edit button in `song_list_widget.py` opens the .pptx via `QDesktopServices.openUrl`. For markdown songs, route to the in-app `MarkdownEditor` instead.

- [ ] **Step 1: Read existing edit handler**

Find the edit handler around `song_list_widget.py:1455-1470` (per earlier conversation). It currently:
1. Pauses file watcher
2. Calls `QDesktopServices.openUrl(QUrl.fromLocalFile(str(pptx_path)))`
3. Warns on failure

- [ ] **Step 2: Update edit handler to dispatch by slide_source**

Modify the edit handler so that for `slide_source == "markdown"` songs, it opens `MarkdownEditor` as a modal dialog instead of calling QDesktopServices.

```python
# Wherever the edit handler is, replace:
url = QUrl.fromLocalFile(str(pptx_path))
if not QDesktopServices.openUrl(url):
    QMessageBox.warning(
        self,
        "열기 실패",
        f"PPT 파일을 여는 데 실패했습니다:\n{pptx_path}",
    )

# With:
if song.slide_source == "markdown":
    self._open_markdown_editor(song)
else:
    url = QUrl.fromLocalFile(str(pptx_path))
    if not QDesktopServices.openUrl(url):
        QMessageBox.warning(
            self,
            "열기 실패",
            f"PPT 파일을 여는 데 실패했습니다:\n{pptx_path}",
        )
```

Add `_open_markdown_editor` method:

```python
def _open_markdown_editor(self, song) -> None:
    from PySide6.QtWidgets import QDialog, QVBoxLayout
    from flow.ui.editor.markdown_editor import MarkdownEditor

    dlg = QDialog(self)
    dlg.setWindowTitle(f"마크다운 편집 — {song.name}")
    dlg.resize(1200, 800)
    layout = QVBoxLayout(dlg)
    editor = MarkdownEditor(song.markdown_path)
    layout.addWidget(editor)
    dlg.exec()
```

- [ ] **Step 3: Verify existing tests still pass**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/ -v`
Expected: existing baseline maintained.

- [ ] **Step 4: Commit**

```bash
git add src/flow/ui/editor/song_list_widget.py
git commit -m "feat(song_list): markdown songs open MarkdownEditor instead of OS shell"
```

---

## Task 18: New song format choice (PPT vs Markdown)

**Files:**
- Modify: wherever new-song creation lives (likely `song_list_widget.py` or `project_screen.py`)

When the user creates a new song, ask whether to start with a PPT slide stub or a markdown stub. If markdown: create `slides.md` with a starter template and immediately open the editor.

- [ ] **Step 1: Find new-song creation flow**

Run: `grep -rn "새 곡\|add_song\|새로 만들기\|create_song" src/flow/ui/ --include="*.py" | head -10`

Identify the entry point. Likely in `song_list_widget.py` or a screen-level handler.

- [ ] **Step 2: Add format choice to creation flow**

Wherever the song creation method lives, after the user names the song and the folder is created, add a format choice dialog:

```python
from PySide6.QtWidgets import QInputDialog

choice, ok = QInputDialog.getItem(
    self,
    "새 곡 형식",
    "어떤 형식으로 시작할까요?",
    ["마크다운 (텍스트)", "PowerPoint (PPT)"],
    0,
    False,
)
if not ok:
    # Folder created — user can fill in later via external tools
    return

if choice.startswith("마크다운"):
    template = """\
---
main_size: 56
sub_size: 18
background: "#000000"
---

# {name}

## 1절

첫 슬라이드 가사
""".format(name=song.name)
    song.markdown_path.write_text(template, encoding="utf-8")
    self._open_markdown_editor(song)
# else: PPT — user creates the .pptx via external tool as before
```

(Adapt to actual code shape — read it first.)

- [ ] **Step 3: Verify tests still pass**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/ -v`
Expected: baseline maintained (no new tests for this — manual UI verification).

- [ ] **Step 4: Commit**

```bash
git add src/flow/ui/editor/song_list_widget.py
git commit -m "feat(song_list): format choice (markdown/PPT) when creating new song"
```

---

## Task 19: Manual smoke test docs

**Files:**
- Create: `docs/superpowers/plans/2026-05-01-markdown-smoke-test.md`

- [ ] **Step 1: Write the doc**

```markdown
# Markdown Slide Format Smoke Test (manual)

**Setup:** Linux/Mac/Win — no PowerPoint or LibreOffice required.

## Steps

1. Open Flow, create a new project (or reuse one).
2. Add a new song. When prompted, choose **마크다운 (텍스트)**.
3. Editor opens with starter template. Verify:
   - ☐ Left pane shows markdown text (with syntax highlight: blue frontmatter, gold `# Title`, green `## section`)
   - ☐ Right pane shows preview + thumbnail strip below
4. Edit gradient: change title, add slides, add `> sub` overrides, add `{main_size: 80}` per-slide overrides.
5. Click **저장 (Ctrl+S)**. Verify:
   - ☐ File saved to disk
   - ☐ Preview re-renders to match
   - ☐ Tab dirty marker (if any) clears
6. Click **Frontmatter 편집**. Verify:
   - ☐ Form opens with current values
   - ☐ Change `main_size`, click OK
   - ☐ Frontmatter block updated, body preserved
7. Close editor. From the song list, click **편집** on the markdown song again. Verify:
   - ☐ Editor reopens with the saved content
8. Externally edit the `.md` file (with VS Code etc.). Save.
9. Verify in Flow:
   - ☐ Slide preview auto-updates
   - ☐ Live mode picks up the change

## Coexistence with PPT

10. In a song folder, place both `slides.md` and `slides.pptx`.
11. Verify Flow shows the markdown slides (not PPT).
12. Delete `slides.md`. Verify Flow falls back to PPT path.

## Failure modes

- Bad frontmatter (e.g. `main_size: "abc"`): edit triggers warning in console; defaults used; renderer doesn't crash.
- Missing background image (`background: "missing.jpg"`): falls back to black; warning logged.
- Empty `.md` file: 0 slides, no crash.
```

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/plans/2026-05-01-markdown-smoke-test.md
git commit -m "docs: manual smoke-test checklist for markdown slide format"
```

---

## Self-Review Notes

After all tasks complete:

```bash
QT_QPA_PLATFORM=offscreen pytest -v
```

Expected: 240 prior baseline + ~50 new tests (parser/renderer/converter/editor/highlighter/dialog).

**Spec coverage check:**
- ✅ Markdown format spec — Tasks 2-6
- ✅ Cascading attrs — Task 6
- ✅ Renderer (background + text + pt-px + layout) — Tasks 7-9
- ✅ MarkdownSlideConverter — Task 10
- ✅ Song domain — Task 11
- ✅ SlideManager dispatch — Task 12
- ✅ File watcher — Task 13
- ✅ Editor (highlighter + dialog + widget) — Tasks 14-16
- ✅ Edit button entry — Task 17
- ✅ New-song flow — Task 18
- ✅ Smoke test doc — Task 19

**Risks (from spec, unchanged):**
- Font rendering differs across OSes
- pt-to-pixel mapping assumes user calibrates `slide_inches` to match their existing PPT canvas
- Memory cache unbounded (may need LRU later)
- Watchdog event timing — gives empty file briefly on save (debounce as needed)
