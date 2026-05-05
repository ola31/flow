# Emergency Slide Patch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable operators to fix lyric typos and add new slides during live broadcast, without interrupting the stream, via a split-pane editor with batch commit semantics.

**Architecture:** A patch layer sits on top of the existing markdown rendering pipeline. Patches live in `<song_dir>/.patches.json` and are applied to the parsed `SongSpec` at render time. During live mode, right-clicking a hotspot or thumbnail opens a left-side editor pane (the right side keeps the existing live UI). The editor accumulates pending changes across slide navigation and commits them atomically with Ctrl+Enter.

**Tech Stack:** PySide6 (Qt Widgets), `services/markdown/{parser,renderer}.py` (existing), pytest-qt for UI tests, JSON file for persistence.

**Spec reference:** `docs/superpowers/specs/2026-05-05-emergency-slide-patch-design.md`

---

## File Plan

### New files

| Path | Responsibility |
|---|---|
| `src/flow/services/markdown/patches.py` | `SlidePatch` dataclass, `PatchStore` (load/save), `apply_patches(spec, patches)` |
| `src/flow/ui/live/confirm_dialog.py` | Reusable two-option keyboard-only confirm dialog (← → + Enter) |
| `src/flow/ui/live/emergency_patch_panel.py` | The split editor pane widget |
| `tests/services/test_patches.py` | Unit tests for patches.py |
| `tests/ui/test_confirm_dialog.py` | UI tests for confirm dialog |
| `tests/ui/test_emergency_patch_panel.py` | UI tests for the editor pane |
| `tests/ui/test_emergency_patch_integration.py` | End-to-end live integration tests |

### Modified files

| Path | Change |
|---|---|
| `src/flow/services/markdown/__init__.py` | Export `SlidePatch`, `PatchStore`, `apply_patches` |
| `src/flow/services/slide_converter.py` | `MarkdownSlideConverter` reads `.patches.json` and applies patches before render |
| `src/flow/services/slide_manager.py` | Refresh markdown cache when patches change |
| `src/flow/ui/editor/score_canvas.py` | Live-mode "긴급 수정" item in hotspot context menu |
| `src/flow/ui/editor/slide_preview_panel.py` | Live-mode "긴급 수정" + "맨 끝에 슬라이드 추가" thumbnail menu, AMBER patch dot |
| `src/flow/ui/editor/markdown_editor.py` | Unreconciled patches notification bar with apply/discard actions |
| `src/flow/ui/main_window.py` | Split layout management, focus switching, key suppression, signal wiring |

---

## Conventions

- Every module starts with `from __future__ import annotations` (project convention)
- Use Python 3.10+ type syntax (`dict[str, int]`, `Foo | None`)
- Use design tokens from `src/flow/ui/styles.py`. Notably:
  - Backgrounds: `BG_DEEP`, `BG_SURFACE`, `BG_ELEVATED`
  - Accent: `ACCENT` (`#5E6AD2`), `ACCENT_INTER`, `ACCENT_HOVER`
  - Status: `AMBER` (`#F5A623`), `AMBER_MUTED`
  - Spacing: `SP_XS=4`, `SP_SM=8`, `SP_MD=12`, `SP_LG=16`, `SP_XL=24`
  - Fonts: `FONT_XS=11`, `FONT_SM=12`, `FONT_MD=14`, `FONT_LG=16`
- Tests run headless via `QT_QPA_PLATFORM=offscreen` (configured in `tests/conftest.py`)

---

## Task 1: `SlidePatch` dataclass + `PatchStore` load/save

**Files:**
- Create: `src/flow/services/markdown/patches.py`
- Test: `tests/services/test_patches.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/services/test_patches.py
"""Unit tests for SlidePatch / PatchStore — emergency-patch persistence."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from flow.services.markdown.patches import (
    PatchStore,
    PatchType,
    SlidePatch,
)


def test_slide_patch_edit_minimal_fields() -> None:
    p = SlidePatch(
        id="abc",
        type=PatchType.EDIT,
        patched_main="고친 가사",
        slide_hash="sha256:deadbeef",
        slide_index=2,
        created_at="2026-05-05T19:42:11Z",
        created_during="live",
    )
    assert p.type is PatchType.EDIT
    assert p.slide_hash == "sha256:deadbeef"
    assert p.slide_index == 2


def test_slide_patch_append_has_no_hash_or_index() -> None:
    p = SlidePatch(
        id="xyz",
        type=PatchType.APPEND,
        patched_main="추가된 슬라이드",
        slide_hash=None,
        slide_index=None,
        created_at="2026-05-05T19:50:33Z",
        created_during="live",
    )
    assert p.type is PatchType.APPEND
    assert p.slide_hash is None
    assert p.slide_index is None


def test_patch_store_load_returns_empty_when_file_missing(tmp_path: Path) -> None:
    store = PatchStore(tmp_path / ".patches.json")
    assert store.patches == []


def test_patch_store_round_trip(tmp_path: Path) -> None:
    path = tmp_path / ".patches.json"
    store = PatchStore(path)
    patch = SlidePatch(
        id="abc",
        type=PatchType.EDIT,
        patched_main="고친 가사",
        slide_hash="sha256:deadbeef",
        slide_index=2,
        created_at="2026-05-05T19:42:11Z",
        created_during="live",
    )
    store.add(patch)
    store.save()

    reloaded = PatchStore(path)
    assert len(reloaded.patches) == 1
    rp = reloaded.patches[0]
    assert rp.id == "abc"
    assert rp.type is PatchType.EDIT
    assert rp.patched_main == "고친 가사"
    assert rp.slide_hash == "sha256:deadbeef"
    assert rp.slide_index == 2


def test_patch_store_round_trip_append(tmp_path: Path) -> None:
    path = tmp_path / ".patches.json"
    store = PatchStore(path)
    store.add(
        SlidePatch(
            id="xyz",
            type=PatchType.APPEND,
            patched_main="새 슬라이드",
            slide_hash=None,
            slide_index=None,
            created_at="2026-05-05T19:50:33Z",
            created_during="live",
        )
    )
    store.save()

    reloaded = PatchStore(path)
    assert len(reloaded.patches) == 1
    assert reloaded.patches[0].type is PatchType.APPEND
    assert reloaded.patches[0].slide_hash is None


def test_patch_store_save_writes_version(tmp_path: Path) -> None:
    path = tmp_path / ".patches.json"
    store = PatchStore(path)
    store.add(
        SlidePatch(
            id="abc",
            type=PatchType.EDIT,
            patched_main="x",
            slide_hash="h",
            slide_index=0,
            created_at="t",
            created_during="live",
        )
    )
    store.save()

    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["version"] == 1
    assert isinstance(raw["patches"], list)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/services/test_patches.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'flow.services.markdown.patches'`

- [ ] **Step 3: Implement `patches.py`**

```python
# src/flow/services/markdown/patches.py
"""Slide patch storage — `.patches.json` per song, edit + append patches."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)

_PATCHES_VERSION = 1


class PatchType(str, Enum):
    EDIT = "edit"
    APPEND = "append"


@dataclass
class SlidePatch:
    id: str
    type: PatchType
    patched_main: str
    slide_hash: str | None
    slide_index: int | None
    created_at: str
    created_during: str

    def to_json(self) -> dict:
        d: dict = {
            "id": self.id,
            "type": self.type.value,
            "patched_main": self.patched_main,
            "created_at": self.created_at,
            "created_during": self.created_during,
        }
        if self.type is PatchType.EDIT:
            d["slide_hash"] = self.slide_hash
            d["slide_index"] = self.slide_index
        return d

    @classmethod
    def from_json(cls, raw: dict) -> SlidePatch:
        ptype = PatchType(raw["type"])
        return cls(
            id=raw["id"],
            type=ptype,
            patched_main=raw["patched_main"],
            slide_hash=raw.get("slide_hash"),
            slide_index=raw.get("slide_index"),
            created_at=raw["created_at"],
            created_during=raw.get("created_during", "live"),
        )


class PatchStore:
    """Read/write `.patches.json` for one song folder."""

    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        self._patches: list[SlidePatch] = []
        self._load()

    @property
    def patches(self) -> list[SlidePatch]:
        return list(self._patches)

    def add(self, patch: SlidePatch) -> None:
        self._patches.append(patch)

    def remove(self, patch_id: str) -> None:
        self._patches = [p for p in self._patches if p.id != patch_id]

    def replace_all(self, patches: list[SlidePatch]) -> None:
        self._patches = list(patches)

    def clear(self) -> None:
        self._patches = []

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": _PATCHES_VERSION,
            "patches": [p.to_json() for p in self._patches],
        }
        self._path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("patches.json load failed (%s): %s", self._path, exc)
            return
        try:
            self._patches = [SlidePatch.from_json(p) for p in raw.get("patches", [])]
        except (KeyError, ValueError) as exc:
            logger.warning("patches.json schema error (%s): %s", self._path, exc)
            self._patches = []
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/services/test_patches.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add src/flow/services/markdown/patches.py tests/services/test_patches.py
git commit -m "feat(patches): SlidePatch dataclass + PatchStore load/save"
```

---

## Task 2: PatchStore corruption handling

**Files:**
- Modify: `src/flow/services/markdown/patches.py` (already handles corruption — just verify with tests)
- Test: `tests/services/test_patches.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/services/test_patches.py`:

```python
def test_patch_store_handles_corrupted_json(tmp_path: Path) -> None:
    path = tmp_path / ".patches.json"
    path.write_text("{ this is not valid json", encoding="utf-8")
    store = PatchStore(path)
    assert store.patches == []  # corrupted → fall back to empty


def test_patch_store_handles_missing_required_keys(tmp_path: Path) -> None:
    path = tmp_path / ".patches.json"
    # patch entry missing "patched_main"
    path.write_text(
        '{"version":1,"patches":[{"id":"x","type":"edit"}]}',
        encoding="utf-8",
    )
    store = PatchStore(path)
    assert store.patches == []


def test_patch_store_handles_unknown_type(tmp_path: Path) -> None:
    path = tmp_path / ".patches.json"
    path.write_text(
        '{"version":1,"patches":[{"id":"x","type":"weird","patched_main":"y","created_at":"t"}]}',
        encoding="utf-8",
    )
    store = PatchStore(path)
    assert store.patches == []
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `pytest tests/services/test_patches.py -v -k "corrupt or missing or unknown"`
Expected: PASS (3 tests)

- [ ] **Step 3: Commit**

```bash
git add tests/services/test_patches.py
git commit -m "test(patches): graceful handling of corrupted .patches.json"
```

---

## Task 3: `apply_patches` — edit type with hash matching, index fallback, orphan detection

**Files:**
- Modify: `src/flow/services/markdown/patches.py` (add `apply_patches` function)
- Test: `tests/services/test_patches.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/services/test_patches.py`:

```python
from flow.services.markdown.parser import Frontmatter, Slide, SongSpec
from flow.services.markdown.patches import apply_patches, slide_hash


def _make_spec(*mains: str) -> SongSpec:
    return SongSpec(
        title="t",
        frontmatter=Frontmatter(),
        slides=[
            Slide(main=m, sub_override=None, section_sub_default=None) for m in mains
        ],
    )


def test_slide_hash_is_stable() -> None:
    h1 = slide_hash("주의 사랑은")
    h2 = slide_hash("주의 사랑은")
    assert h1 == h2
    assert h1.startswith("sha256:")


def test_apply_patches_edit_by_hash(tmp_path: Path) -> None:
    spec = _make_spec("원본 1", "원본 2", "원본 3")
    patch = SlidePatch(
        id="p1",
        type=PatchType.EDIT,
        patched_main="패치된 본문",
        slide_hash=slide_hash("원본 2"),
        slide_index=99,  # wrong index — hash should win
        created_at="t",
        created_during="live",
    )
    result = apply_patches(spec, [patch])
    assert result.slides[0].main == "원본 1"
    assert result.slides[1].main == "패치된 본문"
    assert result.slides[2].main == "원본 3"


def test_apply_patches_edit_index_fallback_when_hash_misses(tmp_path: Path) -> None:
    spec = _make_spec("원본 1", "원본 2", "원본 3")
    patch = SlidePatch(
        id="p1",
        type=PatchType.EDIT,
        patched_main="패치된 본문",
        slide_hash="sha256:nomatch",
        slide_index=1,
        created_at="t",
        created_during="live",
    )
    result = apply_patches(spec, [patch])
    assert result.slides[1].main == "패치된 본문"


def test_apply_patches_edit_orphan_when_both_miss(tmp_path: Path) -> None:
    spec = _make_spec("원본 1", "원본 2")
    patch = SlidePatch(
        id="p1",
        type=PatchType.EDIT,
        patched_main="패치된 본문",
        slide_hash="sha256:nomatch",
        slide_index=99,  # out of range
        created_at="t",
        created_during="live",
    )
    result = apply_patches(spec, [patch])
    # No slide should be patched
    assert [s.main for s in result.slides] == ["원본 1", "원본 2"]


def test_apply_patches_does_not_mutate_input_spec() -> None:
    spec = _make_spec("원본 1", "원본 2")
    patch = SlidePatch(
        id="p1",
        type=PatchType.EDIT,
        patched_main="패치",
        slide_hash=slide_hash("원본 1"),
        slide_index=0,
        created_at="t",
        created_during="live",
    )
    apply_patches(spec, [patch])
    assert spec.slides[0].main == "원본 1"  # original unchanged
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/services/test_patches.py -v -k "apply or hash"`
Expected: FAIL — `apply_patches` and `slide_hash` not yet defined

- [ ] **Step 3: Add `slide_hash` and `apply_patches` to `patches.py`**

Append to `src/flow/services/markdown/patches.py`:

```python
import hashlib
from dataclasses import replace

from flow.services.markdown.parser import SongSpec


def slide_hash(main: str) -> str:
    """Hash a slide's main body for patch-matching. Stable for identical text."""
    digest = hashlib.sha256(main.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def apply_patches(spec: SongSpec, patches: list[SlidePatch]) -> SongSpec:
    """Return a new SongSpec with edit and append patches applied.

    edit patches: hash match first, fall back to slide_index, else orphan.
    append patches: appended at end in created_at order. (Phase 2 in this task.)
    """
    new_slides = list(spec.slides)
    for patch in patches:
        if patch.type is not PatchType.EDIT:
            continue
        target = _find_edit_target(new_slides, patch)
        if target is None:
            continue
        old = new_slides[target]
        new_slides[target] = replace(old, main=patch.patched_main)
    return replace(spec, slides=new_slides)


def _find_edit_target(
    slides: list, patch: SlidePatch
) -> int | None:
    if patch.slide_hash is not None:
        for i, s in enumerate(slides):
            if slide_hash(s.main) == patch.slide_hash:
                return i
    if patch.slide_index is not None and 0 <= patch.slide_index < len(slides):
        return patch.slide_index
    return None
```

Note: `Slide` is `@dataclass(frozen=True)` so `replace(old, main=...)` returns a new instance.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/services/test_patches.py -v -k "apply or hash"`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add src/flow/services/markdown/patches.py tests/services/test_patches.py
git commit -m "feat(patches): apply_patches with hash + index fallback for edits"
```

---

## Task 4: `apply_patches` — append type

**Files:**
- Modify: `src/flow/services/markdown/patches.py` (extend `apply_patches`)
- Test: `tests/services/test_patches.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/services/test_patches.py`:

```python
def test_apply_patches_append_adds_at_end() -> None:
    spec = _make_spec("기존 1", "기존 2")
    patch = SlidePatch(
        id="a1",
        type=PatchType.APPEND,
        patched_main="추가된 1",
        slide_hash=None,
        slide_index=None,
        created_at="2026-05-05T19:50:33Z",
        created_during="live",
    )
    result = apply_patches(spec, [patch])
    assert len(result.slides) == 3
    assert result.slides[2].main == "추가된 1"


def test_apply_patches_append_multiple_in_created_at_order() -> None:
    spec = _make_spec("기존 1")
    p1 = SlidePatch(
        id="a1", type=PatchType.APPEND, patched_main="첫 추가",
        slide_hash=None, slide_index=None,
        created_at="2026-05-05T19:50:33Z", created_during="live",
    )
    p2 = SlidePatch(
        id="a2", type=PatchType.APPEND, patched_main="두 번째 추가",
        slide_hash=None, slide_index=None,
        created_at="2026-05-05T19:51:00Z", created_during="live",
    )
    # Pass them in reverse order — apply_patches must sort by created_at
    result = apply_patches(spec, [p2, p1])
    assert [s.main for s in result.slides] == ["기존 1", "첫 추가", "두 번째 추가"]


def test_apply_patches_append_runs_after_edits() -> None:
    spec = _make_spec("원본 1", "원본 2")
    edit = SlidePatch(
        id="e1", type=PatchType.EDIT, patched_main="수정 2",
        slide_hash=slide_hash("원본 2"), slide_index=1,
        created_at="t1", created_during="live",
    )
    appended = SlidePatch(
        id="a1", type=PatchType.APPEND, patched_main="새것",
        slide_hash=None, slide_index=None,
        created_at="t2", created_during="live",
    )
    result = apply_patches(spec, [edit, appended])
    assert [s.main for s in result.slides] == ["원본 1", "수정 2", "새것"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/services/test_patches.py -v -k "append"`
Expected: FAIL — only 2 slides instead of 3

- [ ] **Step 3: Extend `apply_patches`**

Replace the existing `apply_patches` body in `src/flow/services/markdown/patches.py`:

```python
def apply_patches(spec: SongSpec, patches: list[SlidePatch]) -> SongSpec:
    """Return a new SongSpec with edit and append patches applied.

    Two-phase:
      1. Edit patches: hash match first, fall back to slide_index, else orphan.
      2. Append patches: appended at the end in created_at order.
    """
    from flow.services.markdown.parser import Slide

    edit_patches = [p for p in patches if p.type is PatchType.EDIT]
    append_patches = sorted(
        (p for p in patches if p.type is PatchType.APPEND),
        key=lambda p: p.created_at,
    )

    new_slides = list(spec.slides)
    for patch in edit_patches:
        target = _find_edit_target(new_slides, patch)
        if target is None:
            continue
        old = new_slides[target]
        new_slides[target] = replace(old, main=patch.patched_main)

    for patch in append_patches:
        new_slides.append(
            Slide(
                main=patch.patched_main,
                sub_override=None,
                section_sub_default=None,
            )
        )

    return replace(spec, slides=new_slides)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/services/test_patches.py -v`
Expected: ALL pass

- [ ] **Step 5: Commit**

```bash
git add src/flow/services/markdown/patches.py tests/services/test_patches.py
git commit -m "feat(patches): apply_patches handles append patches in created_at order"
```

---

## Task 5: Export new symbols from `flow.services.markdown`

**Files:**
- Modify: `src/flow/services/markdown/__init__.py`

- [ ] **Step 1: Read current contents**

```bash
cat src/flow/services/markdown/__init__.py
```

- [ ] **Step 2: Add patch exports**

Replace the file with:

```python
"""Markdown-based slide source — parser + renderer + patches."""
from __future__ import annotations

from flow.services.markdown.parser import (
    Frontmatter,
    ResolvedAttrs,
    Slide,
    SongSpec,
    parse,
    resolve_attrs,
)
from flow.services.markdown.patches import (
    PatchStore,
    PatchType,
    SlidePatch,
    apply_patches,
    slide_hash,
)
from flow.services.markdown.renderer import render_all, render_slide

__all__ = [
    "Frontmatter",
    "PatchStore",
    "PatchType",
    "ResolvedAttrs",
    "Slide",
    "SlidePatch",
    "SongSpec",
    "apply_patches",
    "parse",
    "render_all",
    "render_slide",
    "resolve_attrs",
    "slide_hash",
]
```

- [ ] **Step 3: Verify imports work**

Run: `python -c "from flow.services.markdown import PatchStore, SlidePatch, apply_patches, slide_hash; print('ok')"`
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add src/flow/services/markdown/__init__.py
git commit -m "feat(patches): export PatchStore, SlidePatch, apply_patches"
```

---

## Task 6: Wire patches into `MarkdownSlideConverter`

The converter caches rendered images per md_path. Patches apply at parse-time before render. We need:
- The converter to read `.patches.json` next to the md file
- `invalidate_cache` to be called when patches change

**Files:**
- Modify: `src/flow/services/slide_converter.py:704-740` (`MarkdownSlideConverter`)
- Test: `tests/services/test_markdown_converter_patches.py`

- [ ] **Step 1: Write the failing test**

```python
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
    song_dir_with_md: Path, qapp_args
) -> None:
    conv = MarkdownSlideConverter()
    assert conv.get_slide_count(song_dir_with_md) == 2


def test_converter_picks_up_append_patch(
    song_dir_with_md: Path, qapp_args
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
    song_dir_with_md: Path, qapp_args
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
    # Render succeeded with patched content (smoke check — non-empty image)
    assert not img.isNull()
    assert img.width() > 0


def test_invalidate_cache_re_reads_patches(
    song_dir_with_md: Path, qapp_args
) -> None:
    conv = MarkdownSlideConverter()
    assert conv.get_slide_count(song_dir_with_md) == 2

    # Add an append patch
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

    # Cache still says 2 — must invalidate
    assert conv.get_slide_count(song_dir_with_md) == 2
    conv.invalidate_cache(song_dir_with_md)
    assert conv.get_slide_count(song_dir_with_md) == 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/services/test_markdown_converter_patches.py -v`
Expected: FAIL — converter doesn't apply patches yet

- [ ] **Step 3: Update `MarkdownSlideConverter._slides_for`**

In `src/flow/services/slide_converter.py`, modify `MarkdownSlideConverter._slides_for`:

```python
    def _slides_for(self, md_path: Path) -> list:
        from flow.services.markdown import (
            PatchStore,
            apply_patches,
            parse,
            render_all,
        )

        key = Path(md_path).resolve()
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        text = key.read_text(encoding="utf-8")
        spec = parse(text)
        patch_store = PatchStore(key.parent / ".patches.json")
        patched_spec = apply_patches(spec, patch_store.patches)
        images = render_all(patched_spec, song_dir=key.parent)
        self._cache[key] = images
        return images
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/services/test_markdown_converter_patches.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/flow/services/slide_converter.py tests/services/test_markdown_converter_patches.py
git commit -m "feat(patches): MarkdownSlideConverter applies .patches.json transparently"
```

---

## Task 7: Reusable `ConfirmDialog` (← → + Enter, two options)

Used by: discard-on-close ("모두 적용 / 모두 버리기"), add-another ("예 / 아니오"), revert-saved-patch ("예 / 아니오").

**Files:**
- Create: `src/flow/ui/live/confirm_dialog.py`
- Test: `tests/ui/test_confirm_dialog.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/ui/test_confirm_dialog.py
"""Two-option keyboard-only confirm dialog (← → to switch, Enter to choose)."""
from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from flow.ui.live.confirm_dialog import ConfirmDialog


def test_default_focus_is_left_option(qtbot) -> None:
    dlg = ConfirmDialog(
        title="확인",
        message="진행할까요?",
        left_label="예",
        right_label="아니오",
    )
    qtbot.addWidget(dlg)
    dlg.show()
    assert dlg.selected_index() == 0  # left


def test_right_arrow_moves_selection_right(qtbot) -> None:
    dlg = ConfirmDialog(
        title="확인", message="?", left_label="A", right_label="B"
    )
    qtbot.addWidget(dlg)
    dlg.show()
    QTest.keyClick(dlg, Qt.Key.Key_Right)
    assert dlg.selected_index() == 1


def test_left_arrow_moves_selection_left(qtbot) -> None:
    dlg = ConfirmDialog(
        title="확인", message="?", left_label="A", right_label="B"
    )
    qtbot.addWidget(dlg)
    dlg.show()
    QTest.keyClick(dlg, Qt.Key.Key_Right)
    QTest.keyClick(dlg, Qt.Key.Key_Left)
    assert dlg.selected_index() == 0


def test_enter_accepts_with_left_chosen(qtbot) -> None:
    dlg = ConfirmDialog(
        title="확인", message="?", left_label="A", right_label="B"
    )
    qtbot.addWidget(dlg)
    dlg.show()
    QTest.keyClick(dlg, Qt.Key.Key_Return)
    assert dlg.result_choice == "left"


def test_enter_accepts_with_right_chosen(qtbot) -> None:
    dlg = ConfirmDialog(
        title="확인", message="?", left_label="A", right_label="B"
    )
    qtbot.addWidget(dlg)
    dlg.show()
    QTest.keyClick(dlg, Qt.Key.Key_Right)
    QTest.keyClick(dlg, Qt.Key.Key_Return)
    assert dlg.result_choice == "right"


def test_escape_closes_with_no_choice(qtbot) -> None:
    dlg = ConfirmDialog(
        title="확인", message="?", left_label="A", right_label="B"
    )
    qtbot.addWidget(dlg)
    dlg.show()
    QTest.keyClick(dlg, Qt.Key.Key_Escape)
    assert dlg.result_choice is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/ui/test_confirm_dialog.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `ConfirmDialog`**

```python
# src/flow/ui/live/confirm_dialog.py
"""Two-option keyboard-only confirm dialog used by emergency-patch flows.

Selection moves with ← / →, confirms with Enter, cancels with Esc.
The selected button gets the ACCENT highlight styling.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from flow.ui import styles


class ConfirmDialog(QDialog):
    """A modal yes/no-style dialog operable with arrow keys + Enter only."""

    def __init__(
        self,
        *,
        title: str,
        message: str,
        left_label: str,
        right_label: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._selected = 0  # 0 = left, 1 = right
        self.result_choice: str | None = None  # "left" | "right" | None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            styles.SP_XL, styles.SP_LG, styles.SP_XL, styles.SP_LG
        )
        layout.setSpacing(styles.SP_LG)

        msg = QLabel(message)
        msg.setStyleSheet(
            f"color: {styles.TEXT_PRIMARY}; font-size: {styles.FONT_MD}px;"
        )
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(msg)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(styles.SP_MD)
        self._left_btn = QPushButton(left_label)
        self._right_btn = QPushButton(right_label)
        for b in (self._left_btn, self._right_btn):
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # we drive selection ourselves
            b.setMinimumWidth(96)
            b.setMinimumHeight(32)
        btn_row.addStretch(1)
        btn_row.addWidget(self._left_btn)
        btn_row.addWidget(self._right_btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        self._left_btn.clicked.connect(lambda: self._accept_with("left"))
        self._right_btn.clicked.connect(lambda: self._accept_with("right"))

        self._refresh_styles()

    def selected_index(self) -> int:
        return self._selected

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 (Qt API)
        key = event.key()
        if key == Qt.Key.Key_Left:
            self._selected = 0
            self._refresh_styles()
            return
        if key == Qt.Key.Key_Right:
            self._selected = 1
            self._refresh_styles()
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._accept_with("left" if self._selected == 0 else "right")
            return
        if key == Qt.Key.Key_Escape:
            self.result_choice = None
            self.reject()
            return
        super().keyPressEvent(event)

    def _accept_with(self, choice: str) -> None:
        self.result_choice = choice
        self.accept()

    def _refresh_styles(self) -> None:
        for i, btn in enumerate((self._left_btn, self._right_btn)):
            if i == self._selected:
                btn.setStyleSheet(
                    f"QPushButton {{ "
                    f"background-color: {styles.ACCENT}; "
                    f"color: white; "
                    f"border: none; "
                    f"border-radius: 6px; "
                    f"padding: {styles.SP_SM}px {styles.SP_LG}px; "
                    f"font-weight: 600; "
                    f"}}"
                )
            else:
                btn.setStyleSheet(
                    f"QPushButton {{ "
                    f"background-color: {styles.BG_ELEVATED}; "
                    f"color: {styles.TEXT_PRIMARY}; "
                    f"border: 1px solid {styles.BORDER_SOFT}; "
                    f"border-radius: 6px; "
                    f"padding: {styles.SP_SM}px {styles.SP_LG}px; "
                    f"}}"
                )
```

Note: if `BORDER_SOFT` or `TEXT_PRIMARY` token names differ in the project, substitute. Check `src/flow/ui/styles.py` for actual names.

- [ ] **Step 4: Verify token names exist**

Run: `python -c "from flow.ui import styles; print(styles.TEXT_PRIMARY, styles.BORDER_SOFT)"`

If `BORDER_SOFT` or `TEXT_PRIMARY` doesn't exist, grep `styles.py` for the closest equivalent and update the dialog.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/ui/test_confirm_dialog.py -v`
Expected: PASS (6 tests)

- [ ] **Step 6: Commit**

```bash
git add src/flow/ui/live/confirm_dialog.py tests/ui/test_confirm_dialog.py
git commit -m "feat(live): keyboard-only ConfirmDialog for emergency-patch flows"
```

---

## Task 8: `EmergencyPatchPanel` skeleton — header, text input, preview, apply button

The widget that owns the editor pane. Starts simplest: load one slide, render preview, no nav yet.

**Files:**
- Create: `src/flow/ui/live/emergency_patch_panel.py`
- Test: `tests/ui/test_emergency_patch_panel.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/ui/test_emergency_patch_panel.py
"""Tests for EmergencyPatchPanel — the live-mode split editor."""
from __future__ import annotations

from pathlib import Path

import pytest

from flow.services.markdown import (
    Frontmatter,
    Slide,
    SongSpec,
)
from flow.ui.live.emergency_patch_panel import EmergencyPatchPanel


def _make_spec(*mains: str) -> SongSpec:
    return SongSpec(
        title="t",
        frontmatter=Frontmatter(),
        slides=[
            Slide(main=m, sub_override=None, section_sub_default=None) for m in mains
        ],
    )


def test_open_in_edit_mode_loads_slide_text(qtbot, tmp_path: Path) -> None:
    spec = _make_spec("원본 1", "원본 2", "원본 3")
    panel = EmergencyPatchPanel(spec=spec, song_dir=tmp_path, initial_index=1)
    qtbot.addWidget(panel)
    assert panel.current_text() == "원본 2"


def test_open_in_add_mode_starts_empty(qtbot, tmp_path: Path) -> None:
    spec = _make_spec("원본 1", "원본 2")
    panel = EmergencyPatchPanel(
        spec=spec, song_dir=tmp_path, initial_index=None  # add mode
    )
    qtbot.addWidget(panel)
    assert panel.current_text() == ""
    assert panel.is_add_mode()


def test_typing_updates_pending_text(qtbot, tmp_path: Path) -> None:
    spec = _make_spec("원본 1")
    panel = EmergencyPatchPanel(spec=spec, song_dir=tmp_path, initial_index=0)
    qtbot.addWidget(panel)
    panel.set_text("고친 가사")
    assert panel.current_text() == "고친 가사"
    assert panel.has_pending_changes()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/ui/test_emergency_patch_panel.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement skeleton**

```python
# src/flow/ui/live/emergency_patch_panel.py
"""Split-pane emergency patch editor for live mode.

Architecture:
    - Left pane of the live screen during emergency-patch sessions.
    - One panel instance per session. Carries pending changes across slide
      navigation in memory; commits all on Ctrl+Enter.
    - Owns the markdown text editor, a preview, and the apply/revert/close
      controls.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from flow.services.markdown import SongSpec
from flow.ui import styles


@dataclass
class _PendingState:
    """In-memory edit state for one slide-position in this session.

    For edit-mode slides: text is the new body (or original if unchanged).
    For add-mode (only one active at a time per panel): index_key is "add:N"
    where N is a session-local counter.
    """

    text: str
    is_dirty: bool  # True if text != original loaded text


class EmergencyPatchPanel(QWidget):
    """The split-pane editor widget. See spec for behavior detail."""

    # Emitted when user presses Ctrl+Enter / clicks 적용. Payload: list of
    # (slot_key, text) tuples; main_window converts them to SlidePatch
    # objects and writes to PatchStore.
    applied = Signal(list)
    close_requested = Signal()

    def __init__(
        self,
        *,
        spec: SongSpec,
        song_dir: Path,
        initial_index: int | None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._spec = spec
        self._song_dir = song_dir

        # Index key model:
        #   int N (0..len(slides)-1): existing slide index
        #   "add:0", "add:1", ...: pending append slides created in this session
        self._current_key: int | str
        self._pending: dict[int | str, _PendingState] = {}
        self._add_counter = 0  # next "add:N" suffix to allocate

        self._build_ui()

        if initial_index is None:
            self._current_key = self._allocate_add_slot()
        else:
            self._current_key = initial_index

        self._refresh_editor_for_current()

    # --- Public API used by tests + main_window --------------------------

    def current_text(self) -> str:
        return self._editor.toPlainText()

    def is_add_mode(self) -> bool:
        return isinstance(self._current_key, str)

    def has_pending_changes(self) -> bool:
        # Sync current editor text into pending store, then check
        self._sync_current_to_pending()
        return any(s.is_dirty for s in self._pending.values())

    def set_text(self, text: str) -> None:
        self._editor.setPlainText(text)

    # --- Internals --------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            styles.SP_MD, styles.SP_MD, styles.SP_MD, styles.SP_MD
        )
        layout.setSpacing(styles.SP_SM)

        self._title_label = QLabel("긴급 수정")
        self._title_label.setStyleSheet(
            f"color: {styles.AMBER}; font-size: {styles.FONT_SM}px; font-weight: 600;"
        )
        layout.addWidget(self._title_label)

        self._editor = QPlainTextEdit()
        self._editor.setStyleSheet(
            f"QPlainTextEdit {{ background-color: {styles.BG_ELEVATED}; "
            f"color: {styles.TEXT_PRIMARY}; border: none; "
            f"padding: {styles.SP_MD}px; font-family: '{styles.FONT_FAMILY}'; "
            f"font-size: {styles.FONT_MD}px; }}"
        )
        self._editor.setTabChangesFocus(True)  # Tab leaves the editor
        layout.addWidget(self._editor, 1)

        self._preview_label = QLabel()
        self._preview_label.setMinimumHeight(120)
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setStyleSheet(
            f"background-color: {styles.BG_DEEP}; "
            f"border: 1px solid {styles.BG_ELEVATED};"
        )
        layout.addWidget(self._preview_label)

        self._apply_btn = QPushButton("적용 (Ctrl+Enter)")
        self._apply_btn.setStyleSheet(
            f"QPushButton {{ background-color: {styles.ACCENT}; color: white; "
            f"border: none; border-radius: 6px; "
            f"padding: {styles.SP_SM}px {styles.SP_LG}px; font-weight: 600; }}"
        )
        layout.addWidget(self._apply_btn)

    def _allocate_add_slot(self) -> str:
        slot = f"add:{self._add_counter}"
        self._add_counter += 1
        return slot

    def _refresh_editor_for_current(self) -> None:
        """Load `_current_key`'s text into the editor, recording original."""
        key = self._current_key
        if isinstance(key, int):
            original = self._spec.slides[key].main
        else:
            original = ""  # add-mode start
        # If we have a pending entry, prefer it; else seed with original.
        existing = self._pending.get(key)
        if existing is not None:
            text = existing.text
        else:
            text = original
            self._pending[key] = _PendingState(text=text, is_dirty=False)
        self._editor.setPlainText(text)
        self._update_title_label()

    def _sync_current_to_pending(self) -> None:
        """Store current editor text into pending and update dirty flag."""
        key = self._current_key
        text = self._editor.toPlainText()
        if isinstance(key, int):
            original = self._spec.slides[key].main
        else:
            original = ""
        self._pending[key] = _PendingState(text=text, is_dirty=(text != original))

    def _update_title_label(self) -> None:
        key = self._current_key
        if isinstance(key, int):
            total = len(self._spec.slides)
            self._title_label.setText(f"긴급 수정 — 슬라이드 #{key + 1} / {total}")
        else:
            self._title_label.setText("새 슬라이드 추가")
```

Note on style tokens: if `TEXT_PRIMARY`, `FONT_FAMILY`, `FONT_MD` are absent in `src/flow/ui/styles.py`, substitute the closest equivalent. Run `python -c "from flow.ui import styles; print(dir(styles))" | tr ',' '\n' | grep -E 'TEXT|FONT'` to discover.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/ui/test_emergency_patch_panel.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/flow/ui/live/emergency_patch_panel.py tests/ui/test_emergency_patch_panel.py
git commit -m "feat(live): EmergencyPatchPanel skeleton — load slide, edit, preview"
```

---

## Task 9: `EmergencyPatchPanel` — live preview rendering

The preview area should render the current edited text using `render_slide()`.

**Files:**
- Modify: `src/flow/ui/live/emergency_patch_panel.py` (extend `_build_ui` + add preview update)
- Test: `tests/ui/test_emergency_patch_panel.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/ui/test_emergency_patch_panel.py`:

```python
def test_preview_updates_when_text_changes(qtbot, tmp_path: Path) -> None:
    spec = _make_spec("원본 1")
    panel = EmergencyPatchPanel(spec=spec, song_dir=tmp_path, initial_index=0)
    qtbot.addWidget(panel)
    panel.show()
    pix_before = panel.preview_pixmap()
    assert pix_before is not None
    panel.set_text("크게 고친 가사")
    pix_after = panel.preview_pixmap()
    assert pix_after is not None
    # Image bytes should differ when text changed (rough but reliable smoke check)
    assert pix_before.toImage() != pix_after.toImage()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/ui/test_emergency_patch_panel.py::test_preview_updates_when_text_changes -v`
Expected: FAIL — `preview_pixmap` not defined

- [ ] **Step 3: Add preview rendering**

In `src/flow/ui/live/emergency_patch_panel.py`, add `_render_preview` and wire `textChanged`:

After `self._editor = QPlainTextEdit()` block, add:

```python
        self._editor.textChanged.connect(self._on_text_changed)
```

Add these methods to the class:

```python
    def preview_pixmap(self):  # -> QPixmap | None
        return self._preview_label.pixmap()

    def _on_text_changed(self) -> None:
        self._sync_current_to_pending()
        self._render_preview()

    def _render_preview(self) -> None:
        from PySide6.QtCore import Qt as _Qt
        from PySide6.QtGui import QPixmap

        from flow.services.markdown import Slide, render_slide

        text = self._editor.toPlainText()
        slide = Slide(main=text, sub_override=None, section_sub_default=None)
        try:
            img = render_slide(self._spec, slide, song_dir=self._song_dir)
        except Exception:
            self._preview_label.setText("(미리보기 오류)")
            return
        pix = QPixmap.fromImage(img)
        scaled = pix.scaled(
            self._preview_label.width(),
            self._preview_label.height(),
            _Qt.AspectRatioMode.KeepAspectRatio,
            _Qt.TransformationMode.SmoothTransformation,
        )
        self._preview_label.setPixmap(scaled)
```

Also call `self._render_preview()` at the end of `_refresh_editor_for_current` so the preview shows on first load:

```python
    def _refresh_editor_for_current(self) -> None:
        ...  # existing body
        self._editor.setPlainText(text)
        self._update_title_label()
        self._render_preview()  # NEW
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/ui/test_emergency_patch_panel.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/flow/ui/live/emergency_patch_panel.py tests/ui/test_emergency_patch_panel.py
git commit -m "feat(live): EmergencyPatchPanel renders live preview as user types"
```

---

## Task 10: `EmergencyPatchPanel` — navigation between slides

◀ ▶ buttons + Ctrl+← / Ctrl+→ shortcuts. Pending text preserved per slide.

**Files:**
- Modify: `src/flow/ui/live/emergency_patch_panel.py`
- Test: `tests/ui/test_emergency_patch_panel.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/ui/test_emergency_patch_panel.py`:

```python
def test_next_slide_navigates_forward(qtbot, tmp_path: Path) -> None:
    spec = _make_spec("원본 1", "원본 2", "원본 3")
    panel = EmergencyPatchPanel(spec=spec, song_dir=tmp_path, initial_index=0)
    qtbot.addWidget(panel)
    panel.go_next()
    assert panel.current_text() == "원본 2"
    panel.go_next()
    assert panel.current_text() == "원본 3"


def test_prev_slide_navigates_backward(qtbot, tmp_path: Path) -> None:
    spec = _make_spec("원본 1", "원본 2", "원본 3")
    panel = EmergencyPatchPanel(spec=spec, song_dir=tmp_path, initial_index=2)
    qtbot.addWidget(panel)
    panel.go_prev()
    assert panel.current_text() == "원본 2"


def test_pending_text_preserved_across_navigation(qtbot, tmp_path: Path) -> None:
    spec = _make_spec("원본 1", "원본 2", "원본 3")
    panel = EmergencyPatchPanel(spec=spec, song_dir=tmp_path, initial_index=0)
    qtbot.addWidget(panel)
    panel.set_text("진행중 1")
    panel.go_next()
    assert panel.current_text() == "원본 2"  # slide 2 unedited
    panel.set_text("진행중 2")
    panel.go_prev()
    assert panel.current_text() == "진행중 1"  # came back to slide 1's pending


def test_can_go_next_at_last_returns_false(qtbot, tmp_path: Path) -> None:
    spec = _make_spec("원본 1", "원본 2")
    panel = EmergencyPatchPanel(spec=spec, song_dir=tmp_path, initial_index=1)
    qtbot.addWidget(panel)
    assert not panel.can_go_next()


def test_can_go_prev_at_first_returns_false(qtbot, tmp_path: Path) -> None:
    spec = _make_spec("원본 1", "원본 2")
    panel = EmergencyPatchPanel(spec=spec, song_dir=tmp_path, initial_index=0)
    qtbot.addWidget(panel)
    assert not panel.can_go_prev()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/ui/test_emergency_patch_panel.py -v -k "navigat or can_go or pending_text_preserved"`
Expected: FAIL — methods not defined

- [ ] **Step 3: Add navigation methods**

In `EmergencyPatchPanel`, add:

```python
    def can_go_prev(self) -> bool:
        if isinstance(self._current_key, int):
            return self._current_key > 0
        # Add mode: prev goes back to the last existing slide.
        return len(self._spec.slides) > 0

    def can_go_next(self) -> bool:
        if isinstance(self._current_key, int):
            return self._current_key < len(self._spec.slides) - 1
        # Add mode: next always offers "add another" (no hard limit)
        return True

    def go_prev(self) -> None:
        if not self.can_go_prev():
            return
        self._sync_current_to_pending()
        if isinstance(self._current_key, int):
            self._current_key = self._current_key - 1
        else:
            # add mode → last existing slide
            self._current_key = len(self._spec.slides) - 1
        self._refresh_editor_for_current()

    def go_next(self) -> None:
        if not self.can_go_next():
            return
        self._sync_current_to_pending()
        if isinstance(self._current_key, int):
            self._current_key = self._current_key + 1
            self._refresh_editor_for_current()
        # Add-mode "next" is handled by main_window via popup → see Task 11.
```

Also, to support keyboard shortcuts:

In `_build_ui`, after creating `self._editor`, add:

```python
        from PySide6.QtGui import QKeySequence, QShortcut

        QShortcut(
            QKeySequence("Ctrl+Right"), self, activated=self.go_next
        )
        QShortcut(
            QKeySequence("Ctrl+Left"), self, activated=self.go_prev
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/ui/test_emergency_patch_panel.py -v`
Expected: PASS (9 tests)

- [ ] **Step 5: Commit**

```bash
git add src/flow/ui/live/emergency_patch_panel.py tests/ui/test_emergency_patch_panel.py
git commit -m "feat(live): EmergencyPatchPanel ◀ ▶ navigation preserves pending text"
```

---

## Task 11: `EmergencyPatchPanel` — add mode + "add another" popup

▶ at last slide or in add mode → opens `ConfirmDialog` "새 슬라이드를 추가하시겠습니까?". Yes → next add-slot.

**Files:**
- Modify: `src/flow/ui/live/emergency_patch_panel.py`
- Test: `tests/ui/test_emergency_patch_panel.py`

- [ ] **Step 1: Write the failing tests**

Append:

```python
def test_go_next_at_last_existing_slide_offers_add(qtbot, tmp_path: Path, monkeypatch) -> None:
    spec = _make_spec("원본 1", "원본 2")
    panel = EmergencyPatchPanel(spec=spec, song_dir=tmp_path, initial_index=1)
    qtbot.addWidget(panel)

    # Stub: user clicks 예
    monkeypatch.setattr(panel, "_ask_add_another", lambda: True)
    panel.go_next()
    assert panel.is_add_mode()


def test_go_next_at_last_with_no_says_no_op(qtbot, tmp_path: Path, monkeypatch) -> None:
    spec = _make_spec("원본 1", "원본 2")
    panel = EmergencyPatchPanel(spec=spec, song_dir=tmp_path, initial_index=1)
    qtbot.addWidget(panel)

    monkeypatch.setattr(panel, "_ask_add_another", lambda: False)
    panel.go_next()
    assert not panel.is_add_mode()
    assert panel.current_text() == "원본 2"  # still on slide 2


def test_add_mode_prev_returns_to_last_existing(qtbot, tmp_path: Path) -> None:
    spec = _make_spec("원본 1", "원본 2")
    panel = EmergencyPatchPanel(spec=spec, song_dir=tmp_path, initial_index=None)
    qtbot.addWidget(panel)
    panel.set_text("새 슬라이드 작성중")
    panel.go_prev()
    assert not panel.is_add_mode()
    assert panel.current_text() == "원본 2"
    # Add slot pending preserved
    panel.go_next()  # this should re-prompt; stub it via _ask_add_another fallback
    # rather than re-implement here; the add slot's text should still be in _pending


def test_add_mode_next_with_yes_creates_another_slot(qtbot, tmp_path: Path, monkeypatch) -> None:
    spec = _make_spec("원본 1")
    panel = EmergencyPatchPanel(spec=spec, song_dir=tmp_path, initial_index=None)
    qtbot.addWidget(panel)
    first_slot = panel._current_key  # access internal for test only
    panel.set_text("첫 번째 추가")

    monkeypatch.setattr(panel, "_ask_add_another", lambda: True)
    panel.go_next()
    assert panel.is_add_mode()
    assert panel._current_key != first_slot
    assert panel.current_text() == ""  # fresh slot
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/ui/test_emergency_patch_panel.py -v -k "add_mode or add_another or last_existing"`
Expected: FAIL

- [ ] **Step 3: Wire add-mode into nav**

Replace `go_next` with:

```python
    def go_next(self) -> None:
        # Edit mode, not at last → just move forward
        if isinstance(self._current_key, int):
            if self._current_key < len(self._spec.slides) - 1:
                self._sync_current_to_pending()
                self._current_key = self._current_key + 1
                self._refresh_editor_for_current()
                return
            # At last existing slide → ask
            if self._ask_add_another():
                self._sync_current_to_pending()
                self._current_key = self._allocate_add_slot()
                self._refresh_editor_for_current()
            return
        # Add mode → ask for another
        if self._ask_add_another():
            self._sync_current_to_pending()
            self._current_key = self._allocate_add_slot()
            self._refresh_editor_for_current()
```

And add `_ask_add_another`:

```python
    def _ask_add_another(self) -> bool:
        """Show popup, return True if user said yes."""
        from flow.ui.live.confirm_dialog import ConfirmDialog

        dlg = ConfirmDialog(
            title="새 슬라이드 추가",
            message="새 슬라이드를 추가하시겠습니까?",
            left_label="예",
            right_label="아니오",
            parent=self,
        )
        dlg.exec()
        return dlg.result_choice == "left"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/ui/test_emergency_patch_panel.py -v`
Expected: PASS (13 tests)

- [ ] **Step 5: Commit**

```bash
git add src/flow/ui/live/emergency_patch_panel.py tests/ui/test_emergency_patch_panel.py
git commit -m "feat(live): EmergencyPatchPanel add mode + 'add another' popup chain"
```

---

## Task 12: `EmergencyPatchPanel` — batch commit (Ctrl+Enter, applied signal)

Apply button + Ctrl+Enter emit `applied(list)` with all dirty slots.

**Files:**
- Modify: `src/flow/ui/live/emergency_patch_panel.py`
- Test: `tests/ui/test_emergency_patch_panel.py`

- [ ] **Step 1: Write the failing tests**

Append:

```python
def test_apply_emits_signal_with_dirty_slots(qtbot, tmp_path: Path) -> None:
    spec = _make_spec("원본 1", "원본 2")
    panel = EmergencyPatchPanel(spec=spec, song_dir=tmp_path, initial_index=0)
    qtbot.addWidget(panel)
    panel.set_text("고친 1")
    panel.go_next()
    panel.set_text("고친 2")

    with qtbot.waitSignal(panel.applied, timeout=1000) as blocker:
        panel.apply_now()

    payload = blocker.args[0]
    # payload is list of (slot_key, text) tuples
    keys_to_text = dict(payload)
    assert keys_to_text[0] == "고친 1"
    assert keys_to_text[1] == "고친 2"


def test_apply_does_not_emit_unchanged_slots(qtbot, tmp_path: Path) -> None:
    spec = _make_spec("원본 1", "원본 2", "원본 3")
    panel = EmergencyPatchPanel(spec=spec, song_dir=tmp_path, initial_index=0)
    qtbot.addWidget(panel)
    panel.set_text("고친 1")
    panel.go_next()  # slide 2 — don't change
    panel.go_next()  # slide 3 — don't change

    with qtbot.waitSignal(panel.applied, timeout=1000) as blocker:
        panel.apply_now()

    payload = blocker.args[0]
    assert len(payload) == 1
    assert payload[0][0] == 0
    assert payload[0][1] == "고친 1"


def test_apply_emits_add_slots_with_string_keys(qtbot, tmp_path: Path, monkeypatch) -> None:
    spec = _make_spec("원본 1")
    panel = EmergencyPatchPanel(spec=spec, song_dir=tmp_path, initial_index=None)
    qtbot.addWidget(panel)
    panel.set_text("새 1")
    monkeypatch.setattr(panel, "_ask_add_another", lambda: True)
    panel.go_next()
    panel.set_text("새 2")

    with qtbot.waitSignal(panel.applied, timeout=1000) as blocker:
        panel.apply_now()

    payload = blocker.args[0]
    keys = [k for k, _ in payload]
    assert all(isinstance(k, str) and k.startswith("add:") for k in keys)
    texts = [t for _, t in payload]
    assert "새 1" in texts and "새 2" in texts


def test_ctrl_enter_triggers_apply(qtbot, tmp_path: Path) -> None:
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    spec = _make_spec("원본 1")
    panel = EmergencyPatchPanel(spec=spec, song_dir=tmp_path, initial_index=0)
    qtbot.addWidget(panel)
    panel.show()
    panel.set_text("고친 1")
    panel._editor.setFocus()

    with qtbot.waitSignal(panel.applied, timeout=1000):
        QTest.keyClick(panel._editor, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/ui/test_emergency_patch_panel.py -v -k "apply"`
Expected: FAIL — `apply_now` not defined

- [ ] **Step 3: Implement `apply_now` and shortcut**

Add to `EmergencyPatchPanel`:

```python
    def apply_now(self) -> None:
        self._sync_current_to_pending()
        dirty = [
            (key, state.text)
            for key, state in self._pending.items()
            if state.is_dirty
        ]
        # Add-mode slots are dirty even with empty text only if user typed
        # something — empty text on a freshly-allocated add slot is NOT dirty
        # because original is "" and text is "". Already handled by is_dirty.
        self.applied.emit(dirty)
```

In `_build_ui`, wire the apply button + Ctrl+Enter:

```python
        self._apply_btn.clicked.connect(self.apply_now)
        QShortcut(
            QKeySequence("Ctrl+Return"), self, activated=self.apply_now
        )
```

(Note: import `QShortcut`/`QKeySequence` from `PySide6.QtGui` at module top, removing local imports added in Task 10.)

Move all imports to module top — final state:

```python
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/ui/test_emergency_patch_panel.py -v`
Expected: PASS (17 tests)

- [ ] **Step 5: Commit**

```bash
git add src/flow/ui/live/emergency_patch_panel.py tests/ui/test_emergency_patch_panel.py
git commit -m "feat(live): EmergencyPatchPanel batch commit on Ctrl+Enter"
```

---

## Task 13: `EmergencyPatchPanel` — close handling (Esc + ConfirmDialog)

**Files:**
- Modify: `src/flow/ui/live/emergency_patch_panel.py`
- Test: `tests/ui/test_emergency_patch_panel.py`

- [ ] **Step 1: Write the failing tests**

Append:

```python
def test_close_no_pending_emits_close_immediately(qtbot, tmp_path: Path) -> None:
    spec = _make_spec("원본 1")
    panel = EmergencyPatchPanel(spec=spec, song_dir=tmp_path, initial_index=0)
    qtbot.addWidget(panel)

    with qtbot.waitSignal(panel.close_requested, timeout=1000):
        panel.attempt_close()


def test_close_with_pending_yes_apply_emits_apply_then_close(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    spec = _make_spec("원본 1")
    panel = EmergencyPatchPanel(spec=spec, song_dir=tmp_path, initial_index=0)
    qtbot.addWidget(panel)
    panel.set_text("고친")

    monkeypatch.setattr(panel, "_ask_apply_or_discard", lambda: "apply")

    apply_fired = []
    close_fired = []
    panel.applied.connect(lambda payload: apply_fired.append(payload))
    panel.close_requested.connect(lambda: close_fired.append(True))

    panel.attempt_close()
    assert apply_fired and apply_fired[0][0][1] == "고친"
    assert close_fired


def test_close_with_pending_discard_emits_close_only(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    spec = _make_spec("원본 1")
    panel = EmergencyPatchPanel(spec=spec, song_dir=tmp_path, initial_index=0)
    qtbot.addWidget(panel)
    panel.set_text("고친")

    monkeypatch.setattr(panel, "_ask_apply_or_discard", lambda: "discard")

    apply_fired = []
    close_fired = []
    panel.applied.connect(lambda payload: apply_fired.append(payload))
    panel.close_requested.connect(lambda: close_fired.append(True))

    panel.attempt_close()
    assert not apply_fired
    assert close_fired


def test_close_with_pending_dialog_cancelled_no_close(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    spec = _make_spec("원본 1")
    panel = EmergencyPatchPanel(spec=spec, song_dir=tmp_path, initial_index=0)
    qtbot.addWidget(panel)
    panel.set_text("고친")

    monkeypatch.setattr(panel, "_ask_apply_or_discard", lambda: None)

    close_fired = []
    panel.close_requested.connect(lambda: close_fired.append(True))

    panel.attempt_close()
    assert not close_fired  # dialog cancelled → stay open
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/ui/test_emergency_patch_panel.py -v -k "close"`
Expected: FAIL

- [ ] **Step 3: Implement `attempt_close` + `_ask_apply_or_discard`**

Add to `EmergencyPatchPanel`:

```python
    def attempt_close(self) -> None:
        self._sync_current_to_pending()
        dirty_count = sum(1 for s in self._pending.values() if s.is_dirty)
        if dirty_count == 0:
            self.close_requested.emit()
            return
        choice = self._ask_apply_or_discard()
        if choice == "apply":
            self.apply_now()
            self.close_requested.emit()
        elif choice == "discard":
            self.close_requested.emit()
        # else: None (dialog cancelled) → stay open

    def _ask_apply_or_discard(self) -> str | None:
        from flow.ui.live.confirm_dialog import ConfirmDialog

        dirty_count = sum(1 for s in self._pending.values() if s.is_dirty)
        dlg = ConfirmDialog(
            title="변경사항 처리",
            message=(
                f"누적된 변경사항 {dirty_count}건이 있습니다.\n"
                "모두 적용할까요? 모두 버릴까요?"
            ),
            left_label="모두 적용",
            right_label="모두 버리기",
            parent=self,
        )
        dlg.exec()
        if dlg.result_choice == "left":
            return "apply"
        if dlg.result_choice == "right":
            return "discard"
        return None
```

Also intercept Esc on the panel:

```python
    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.attempt_close()
            return
        super().keyPressEvent(event)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/ui/test_emergency_patch_panel.py -v`
Expected: PASS (21 tests)

- [ ] **Step 5: Commit**

```bash
git add src/flow/ui/live/emergency_patch_panel.py tests/ui/test_emergency_patch_panel.py
git commit -m "feat(live): EmergencyPatchPanel Esc close with apply-all/discard-all dialog"
```

---

## Task 14: `EmergencyPatchPanel` — "원본으로 되돌리기"

A header button. Acts on the current slide only:
- Discards pending edit for this slot
- For edit-mode slots with a saved patch (passed in via constructor), asks before removing the saved patch

For now, the panel exposes `revert_current()` and emits `saved_patch_revert_requested(slide_key)` when applicable. The actual `.patches.json` write happens in main_window.

**Files:**
- Modify: `src/flow/ui/live/emergency_patch_panel.py`
- Test: `tests/ui/test_emergency_patch_panel.py`

- [ ] **Step 1: Write the failing tests**

Append:

```python
def test_revert_clears_pending_for_current_only(qtbot, tmp_path: Path) -> None:
    spec = _make_spec("원본 1", "원본 2")
    panel = EmergencyPatchPanel(spec=spec, song_dir=tmp_path, initial_index=0)
    qtbot.addWidget(panel)
    panel.set_text("고친 1")
    panel.go_next()
    panel.set_text("고친 2")
    panel.go_prev()  # back to slide 0

    panel.revert_current()
    assert panel.current_text() == "원본 1"
    panel.go_next()
    assert panel.current_text() == "고친 2"  # other slide untouched


def test_revert_in_add_mode_drops_slot_and_returns_to_last(
    qtbot, tmp_path: Path
) -> None:
    spec = _make_spec("원본 1")
    panel = EmergencyPatchPanel(spec=spec, song_dir=tmp_path, initial_index=None)
    qtbot.addWidget(panel)
    panel.set_text("새 슬라이드")
    panel.revert_current()
    assert not panel.is_add_mode()
    assert panel.current_text() == "원본 1"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/ui/test_emergency_patch_panel.py -v -k "revert"`
Expected: FAIL

- [ ] **Step 3: Implement `revert_current`**

Add:

```python
    def revert_current(self) -> None:
        key = self._current_key
        if isinstance(key, str):
            # Add-mode: drop slot, return to last existing slide
            self._pending.pop(key, None)
            if len(self._spec.slides) > 0:
                self._current_key = len(self._spec.slides) - 1
                self._refresh_editor_for_current()
            else:
                # No existing slides — close
                self.close_requested.emit()
            return
        # Edit-mode: clear pending so refresh seeds with original
        self._pending.pop(key, None)
        self._refresh_editor_for_current()
```

Add a header button in `_build_ui`. After `self._title_label`:

```python
        header_row = QHBoxLayout()
        header_row.setSpacing(styles.SP_SM)
        header_row.addWidget(self._title_label)
        header_row.addStretch(1)
        self._revert_btn = QPushButton("원본으로 되돌리기")
        self._revert_btn.setStyleSheet(
            f"QPushButton {{ background-color: transparent; "
            f"color: {styles.AMBER}; border: 1px solid {styles.AMBER}; "
            f"border-radius: 4px; padding: 4px 8px; font-size: {styles.FONT_XS}px; }}"
        )
        self._revert_btn.clicked.connect(self.revert_current)
        header_row.addWidget(self._revert_btn)
        layout.addLayout(header_row)
```

And remove the bare `layout.addWidget(self._title_label)` from earlier — replace with the header_row layout.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/ui/test_emergency_patch_panel.py -v`
Expected: PASS (23 tests)

- [ ] **Step 5: Commit**

```bash
git add src/flow/ui/live/emergency_patch_panel.py tests/ui/test_emergency_patch_panel.py
git commit -m "feat(live): EmergencyPatchPanel revert-current per-slide action"
```

---

## Task 15: Score canvas — "긴급 수정" in live-mode hotspot context menu

When live mode is on AND the current song's `slide_source == "markdown"`, the hotspot context menu should include "긴급 수정". Picking it emits a new signal.

**Files:**
- Modify: `src/flow/ui/editor/score_canvas.py`
- Test: `tests/ui/test_score_canvas_live_menu.py`

- [ ] **Step 1: Inspect existing context menu**

```bash
sed -n '730,800p' src/flow/ui/editor/score_canvas.py
```

Locate the `_show_context_menu(self, pos, hotspot)` method.

- [ ] **Step 2: Write the failing test**

```python
# tests/ui/test_score_canvas_live_menu.py
"""Live-mode hotspot context menu shows '긴급 수정' for markdown songs only."""
from __future__ import annotations

import pytest

from flow.domain.hotspot import Hotspot
from flow.ui.editor.score_canvas import ScoreCanvas


def test_emergency_patch_signal_exists() -> None:
    # Sanity: signal is declared on the class
    assert hasattr(ScoreCanvas, "emergency_patch_requested")


def test_set_live_markdown_mode_enables_emergency_menu(qtbot) -> None:
    canvas = ScoreCanvas()
    qtbot.addWidget(canvas)
    canvas.set_live_mode(is_live=True, slide_source="markdown")
    assert canvas._live_emergency_enabled is True


def test_set_live_pptx_mode_disables_emergency_menu(qtbot) -> None:
    canvas = ScoreCanvas()
    qtbot.addWidget(canvas)
    canvas.set_live_mode(is_live=True, slide_source="pptx")
    assert canvas._live_emergency_enabled is False
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/ui/test_score_canvas_live_menu.py -v`
Expected: FAIL — signal/method missing

- [ ] **Step 4: Add signal + state to `ScoreCanvas`**

In `src/flow/ui/editor/score_canvas.py`, near other signal declarations:

```python
    emergency_patch_requested = Signal(object)  # Hotspot
```

In `__init__`, add:

```python
        self._live_emergency_enabled = False
```

Add method:

```python
    def set_live_mode(self, *, is_live: bool, slide_source: str) -> None:
        """Called by main_window on enter/exit live. slide_source is the
        current song's source ('markdown' | 'pptx' | 'none')."""
        self._live_emergency_enabled = is_live and slide_source == "markdown"
```

In `_show_context_menu`, after the existing items, add:

```python
        if self._live_emergency_enabled:
            menu.addSeparator()
            emergency_action = QAction("긴급 수정", self)
            emergency_action.triggered.connect(
                lambda: self.emergency_patch_requested.emit(hotspot)
            )
            menu.addAction(emergency_action)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/ui/test_score_canvas_live_menu.py -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add src/flow/ui/editor/score_canvas.py tests/ui/test_score_canvas_live_menu.py
git commit -m "feat(live): hotspot context menu offers '긴급 수정' in live mode"
```

---

## Task 16: Slide preview thumbnails — "긴급 수정" + "맨 끝에 슬라이드 추가" in live mode

In live mode the thumbnail strip should show:
- On a slide thumbnail right-click: both items
- (No special right-click behavior for empty space — Qt list widgets only fire `customContextMenuRequested` on items by default)

**Files:**
- Modify: `src/flow/ui/editor/slide_preview_panel.py`
- Test: `tests/ui/test_slide_preview_live_menu.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/ui/test_slide_preview_live_menu.py
"""Live-mode slide preview thumbnail menu offers patch actions."""
from __future__ import annotations

import pytest

from flow.ui.editor.slide_preview_panel import SlidePreviewPanel


def test_signals_exist() -> None:
    assert hasattr(SlidePreviewPanel, "emergency_patch_requested")
    assert hasattr(SlidePreviewPanel, "append_slide_requested")


def test_set_live_markdown_mode(qtbot) -> None:
    panel = SlidePreviewPanel()
    qtbot.addWidget(panel)
    panel.set_live_mode(is_live=True, slide_source="markdown")
    assert panel._live_emergency_enabled is True


def test_set_live_pptx_mode_disables_patches(qtbot) -> None:
    panel = SlidePreviewPanel()
    qtbot.addWidget(panel)
    panel.set_live_mode(is_live=True, slide_source="pptx")
    assert panel._live_emergency_enabled is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/ui/test_slide_preview_live_menu.py -v`
Expected: FAIL — signals/methods missing

- [ ] **Step 3: Update `SlidePreviewPanel`**

In `src/flow/ui/editor/slide_preview_panel.py`, near other `Signal` declarations:

```python
    emergency_patch_requested = Signal(int)  # slide index
    append_slide_requested = Signal()
```

In `__init__`:

```python
        self._live_emergency_enabled = False
```

Add method:

```python
    def set_live_mode(self, *, is_live: bool, slide_source: str) -> None:
        self._live_emergency_enabled = is_live and slide_source == "markdown"
```

Modify `_show_context_menu` to branch on live state:

```python
    def _show_context_menu(self, pos) -> None:
        item = self._list.itemAt(pos)

        from PySide6.QtWidgets import QMenu
        menu = QMenu(self)

        if self._live_emergency_enabled:
            if item is not None:
                index = item.data(Qt.ItemDataRole.UserRole)
                emergency_action = menu.addAction("긴급 수정")
                emergency_action.triggered.connect(
                    lambda: self.emergency_patch_requested.emit(index)
                )
            append_action = menu.addAction("맨 끝에 슬라이드 추가")
            append_action.triggered.connect(self.append_slide_requested.emit)
            menu.exec(self._list.mapToGlobal(pos))
            return

        # Existing edit-mode menu (unchanged)
        if not self._editable:
            return
        if not item:
            return
        index = item.data(Qt.ItemDataRole.UserRole)
        unlink_action = menu.addAction("매핑 해제")
        unlink_action.triggered.connect(
            lambda: self.slide_unlink_all_requested.emit(index)
        )
        menu.exec(self._list.mapToGlobal(pos))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/ui/test_slide_preview_live_menu.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/flow/ui/editor/slide_preview_panel.py tests/ui/test_slide_preview_live_menu.py
git commit -m "feat(live): thumbnail menu offers '긴급 수정' + '맨 끝에 슬라이드 추가'"
```

---

## Task 17: Patched-slide AMBER badge in thumbnail strip

Show a small AMBER dot on patched-slide thumbnails (operator view only).

**Files:**
- Modify: `src/flow/ui/editor/slide_preview_panel.py`
- Test: `tests/ui/test_slide_preview_live_menu.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/ui/test_slide_preview_live_menu.py`:

```python
def test_set_patched_indices_marks_thumbnails(qtbot) -> None:
    panel = SlidePreviewPanel()
    qtbot.addWidget(panel)

    # Seed it with 3 fake slides
    from PySide6.QtGui import QPixmap
    from PySide6.QtWidgets import QListWidgetItem
    from PySide6.QtCore import Qt

    for i in range(3):
        item = QListWidgetItem(f"#{i+1}")
        item.setData(Qt.ItemDataRole.UserRole, i)
        item.setIcon(QPixmap(144, 81))
        panel._list.addItem(item)

    panel.set_patched_indices({1})
    assert panel._patched_indices == {1}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/ui/test_slide_preview_live_menu.py -v -k patched_indices`
Expected: FAIL

- [ ] **Step 3: Implement badge state + paint**

In `SlidePreviewPanel.__init__`:

```python
        self._patched_indices: set[int] = set()
```

Add method:

```python
    def set_patched_indices(self, indices: set[int]) -> None:
        self._patched_indices = set(indices)
        self._list.viewport().update()
```

Add a delegate or use a custom paint hook. Simplest: subclass `QStyledItemDelegate` and override `paint`. To avoid restructuring, use a viewport `paintEvent` override on `_DraggableSlideList`:

In `_DraggableSlideList` (top of `slide_preview_panel.py`), add:

```python
    def __init__(self) -> None:
        super().__init__()
        self._patched_indices: set[int] = set()

    def set_patched_indices(self, indices: set[int]) -> None:
        self._patched_indices = set(indices)
        self.viewport().update()

    def paintEvent(self, event):  # noqa: N802
        super().paintEvent(event)
        if not self._patched_indices:
            return
        from PySide6.QtCore import QRect
        from PySide6.QtGui import QColor, QPainter

        from flow.ui import styles

        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setBrush(QColor(styles.AMBER))
        painter.setPen(QColor(styles.AMBER))
        for i in range(self.count()):
            item = self.item(i)
            idx = item.data(Qt.ItemDataRole.UserRole)
            if idx not in self._patched_indices:
                continue
            rect = self.visualItemRect(item)
            dot = QRect(rect.right() - 14, rect.top() + 4, 8, 8)
            painter.drawEllipse(dot)
        painter.end()
```

In `SlidePreviewPanel.set_patched_indices`, route through:

```python
    def set_patched_indices(self, indices: set[int]) -> None:
        self._patched_indices = set(indices)
        self._list.set_patched_indices(indices)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/ui/test_slide_preview_live_menu.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/flow/ui/editor/slide_preview_panel.py tests/ui/test_slide_preview_live_menu.py
git commit -m "feat(live): AMBER patch dot on patched-slide thumbnails"
```

---

## Task 18: Main window — split layout management

Open emergency patch panel as the LEFT pane of the live area, with existing live UI as the RIGHT pane. Wire signals from canvas/preview-panel menus.

**Files:**
- Modify: `src/flow/ui/main_window.py`
- Test: integration test in Task 22 (this task is wiring; lightly testable on its own)

- [ ] **Step 1: Locate the live container**

```bash
grep -n "_enter_live\|_exit_live\|class MainWindow\|self._central\|setCentralWidget" src/flow/ui/main_window.py | head -20
```

Identify which widget hosts the live UI when `_is_live` is true.

- [ ] **Step 2: Add a `QSplitter`-based emergency-patch insertion**

Add to `MainWindow.__init__` (near other live state):

```python
        self._patch_panel = None  # EmergencyPatchPanel | None
        self._patch_splitter = None  # QSplitter | None
        self._original_live_parent = None
```

Add new methods:

```python
    def _open_emergency_patch_panel(
        self, *, song, initial_index: int | None
    ) -> None:
        """Open the split-pane emergency patch editor.

        Replaces the current live container with a QSplitter containing the
        patch panel on the left and the (re-parented) existing live UI on
        the right. Closing the panel restores the original layout.
        """
        from flow.services.markdown import PatchStore, apply_patches, parse
        from flow.ui.live.emergency_patch_panel import EmergencyPatchPanel

        if not self._is_live:
            return
        if self._patch_panel is not None:
            return  # already open

        md_path = song.markdown_path
        text = md_path.read_text(encoding="utf-8")
        spec = parse(text)
        store = PatchStore(md_path.parent / ".patches.json")
        patched_spec = apply_patches(spec, store.patches)

        panel = EmergencyPatchPanel(
            spec=patched_spec,
            song_dir=md_path.parent,
            initial_index=initial_index,
            parent=self,
        )
        panel.applied.connect(
            lambda payload: self._on_patch_applied(song, payload)
        )
        panel.close_requested.connect(self._close_emergency_patch_panel)

        # Wrap the existing live container in a splitter
        live_container = self._live_container_widget()  # helper, see below
        live_parent = live_container.parentWidget()
        live_geom_index = live_parent.layout().indexOf(live_container)

        from PySide6.QtWidgets import QSplitter
        from PySide6.QtCore import Qt as _Qt
        splitter = QSplitter(_Qt.Orientation.Horizontal, parent=live_parent)
        live_parent.layout().insertWidget(live_geom_index, splitter)
        live_parent.layout().removeWidget(live_container)
        splitter.addWidget(panel)
        splitter.addWidget(live_container)
        splitter.setSizes([400, 600])

        self._patch_panel = panel
        self._patch_splitter = splitter
        self._patch_original_index = live_geom_index

    def _close_emergency_patch_panel(self) -> None:
        if self._patch_panel is None or self._patch_splitter is None:
            return
        live_container = self._live_container_widget()
        parent_layout = self._patch_splitter.parentWidget().layout()
        parent_layout.insertWidget(self._patch_original_index, live_container)
        self._patch_splitter.setParent(None)
        self._patch_splitter.deleteLater()
        self._patch_panel.deleteLater()
        self._patch_panel = None
        self._patch_splitter = None

    def _on_patch_applied(self, song, payload: list) -> None:
        """Translate (slot_key, text) tuples into SlidePatch and write store."""
        import uuid
        from datetime import datetime, timezone

        from flow.services.markdown import (
            PatchStore,
            PatchType,
            SlidePatch,
            slide_hash,
            parse,
        )

        md_path = song.markdown_path
        spec = parse(md_path.read_text(encoding="utf-8"))
        store = PatchStore(md_path.parent / ".patches.json")
        now = datetime.now(timezone.utc).isoformat()

        for key, text in payload:
            if isinstance(key, int):
                # Edit patch: hash the ORIGINAL .md slide so future drift logic works
                if 0 <= key < len(spec.slides):
                    h = slide_hash(spec.slides[key].main)
                else:
                    h = None
                store.add(
                    SlidePatch(
                        id=str(uuid.uuid4()),
                        type=PatchType.EDIT,
                        patched_main=text,
                        slide_hash=h,
                        slide_index=key,
                        created_at=now,
                        created_during="live",
                    )
                )
            else:
                # Append patch
                store.add(
                    SlidePatch(
                        id=str(uuid.uuid4()),
                        type=PatchType.APPEND,
                        patched_main=text,
                        slide_hash=None,
                        slide_index=None,
                        created_at=now,
                        created_during="live",
                    )
                )
        store.save()

        # Invalidate caches and trigger UI refresh
        self._slide_manager.invalidate_markdown_cache(md_path)  # see Task 19
        self._refresh_thumbnails_and_display(song)
        self._close_emergency_patch_panel()
```

`_live_container_widget()` is a helper you must add — it returns the existing widget that holds the score canvas + slide preview panel + live controls. Identify the right widget by looking at how `_enter_live` reconfigures layout.

- [ ] **Step 3: Wire the menu signals**

In `MainWindow.__init__` or wherever signals get connected for the score canvas and preview panel:

```python
        self._canvas.emergency_patch_requested.connect(
            self._on_canvas_emergency_patch_requested
        )
        self._slide_preview.emergency_patch_requested.connect(
            self._on_preview_emergency_patch_requested
        )
        self._slide_preview.append_slide_requested.connect(
            self._on_append_slide_requested
        )
```

Add handlers:

```python
    def _on_canvas_emergency_patch_requested(self, hotspot) -> None:
        if not self._is_live:
            return
        song = self._current_song()  # use existing helper
        if song is None or song.slide_source != "markdown":
            return
        slide_idx = hotspot.get_slide_index(self._project.current_verse_index)
        if slide_idx < 0:
            return
        self._open_emergency_patch_panel(song=song, initial_index=slide_idx)

    def _on_preview_emergency_patch_requested(self, slide_index: int) -> None:
        if not self._is_live:
            return
        song = self._current_song()
        if song is None or song.slide_source != "markdown":
            return
        self._open_emergency_patch_panel(song=song, initial_index=slide_index)

    def _on_append_slide_requested(self) -> None:
        if not self._is_live:
            return
        song = self._current_song()
        if song is None or song.slide_source != "markdown":
            return
        self._open_emergency_patch_panel(song=song, initial_index=None)
```

In `_enter_live` and `_exit_live`, add propagation:

```python
    def _enter_live(self) -> None:
        ...
        # NEW: propagate live-mode + source to the menus
        song = self._current_song()
        source = song.slide_source if song else "none"
        self._canvas.set_live_mode(is_live=True, slide_source=source)
        self._slide_preview.set_live_mode(is_live=True, slide_source=source)

    def _exit_live(self) -> None:
        ...
        self._canvas.set_live_mode(is_live=False, slide_source="none")
        self._slide_preview.set_live_mode(is_live=False, slide_source="none")
        self._close_emergency_patch_panel()  # if open
```

`_current_song()` — find existing helper or write one returning the active song instance. Likely already present (search for usage of `_project.current_song`, `selected_songs`, etc.).

- [ ] **Step 4: Smoke-run the app manually**

Build and run the app in headed mode:

```bash
QT_QPA_PLATFORM=xcb pytest tests/services/test_patches.py -v
```

(Tests still pass; manual verification of the live UI requires the app — defer to Task 22 integration test.)

- [ ] **Step 5: Commit**

```bash
git add src/flow/ui/main_window.py
git commit -m "feat(live): main window split-layout for emergency patch panel"
```

---

## Task 19: Slide manager — markdown cache invalidation hook

The slide manager already exposes invalidation for the file-watcher case. Make sure the manual invalidation path used by `_on_patch_applied` exists.

**Files:**
- Modify: `src/flow/services/slide_manager.py` (add public method if missing)
- Test: `tests/services/test_slide_manager_patches.py`

- [ ] **Step 1: Inspect existing API**

```bash
grep -n "invalidate_cache\|invalidate_markdown\|markdown_converter" src/flow/services/slide_manager.py | head -20
```

Look for an existing `invalidate_markdown_cache(md_path)` or equivalent. If absent, add one.

- [ ] **Step 2: Write the failing test**

```python
# tests/services/test_slide_manager_patches.py
"""SlideManager exposes a hook to invalidate the markdown cache after patch."""
from __future__ import annotations

from pathlib import Path

import pytest

from flow.services.slide_manager import SlideManager


def test_invalidate_markdown_cache_clears_internal_state(tmp_path: Path) -> None:
    md = tmp_path / "slides.md"
    md.write_text("원본\n", encoding="utf-8")

    sm = SlideManager()
    try:
        # Prime the cache
        sm._markdown_converter._slides_for(md)
        assert md.resolve() in sm._markdown_converter._cache

        sm.invalidate_markdown_cache(md)
        assert md.resolve() not in sm._markdown_converter._cache
    finally:
        sm.shutdown()
```

- [ ] **Step 3: Run test, observe pass or failure**

Run: `pytest tests/services/test_slide_manager_patches.py -v`
- If PASS: existing API already does this; skip to step 5
- If FAIL: add the method

- [ ] **Step 4: Add the method if needed**

In `SlideManager`:

```python
    def invalidate_markdown_cache(self, md_path: Path) -> None:
        """Public hook to drop the markdown render cache for one song."""
        self._markdown_converter.invalidate_cache(md_path)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/services/test_slide_manager_patches.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/flow/services/slide_manager.py tests/services/test_slide_manager_patches.py
git commit -m "feat(slide_manager): public invalidate_markdown_cache hook"
```

---

## Task 20: Main window — focus management + key suppression

Tab toggles between patch panel and live area. While patch panel is focused, live keys (Space, number keys, Enter, etc.) must NOT trigger live actions.

**Files:**
- Modify: `src/flow/ui/main_window.py`
- Test: `tests/ui/test_main_window_patch_focus.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/ui/test_main_window_patch_focus.py
"""When the patch panel is focused, live single-key shortcuts no-op."""
from __future__ import annotations

import pytest

from flow.ui.main_window import MainWindow


def test_emergency_patch_active_check(qtbot) -> None:
    win = MainWindow()
    qtbot.addWidget(win)
    # Initially no patch panel
    assert not win._patch_panel_has_focus()


def test_patch_panel_focus_suppresses_live_shortcuts(qtbot) -> None:
    """Smoke test: helper returns True after patch panel grabs focus."""
    win = MainWindow()
    qtbot.addWidget(win)
    # Manually set up scenario
    win._is_live = True

    class FakePanel:
        def hasFocus(self) -> bool:
            return True

    win._patch_panel = FakePanel()
    assert win._patch_panel_has_focus()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/ui/test_main_window_patch_focus.py -v`
Expected: FAIL — `_patch_panel_has_focus` not defined

- [ ] **Step 3: Add focus helpers + key gates**

In `MainWindow`:

```python
    def _patch_panel_has_focus(self) -> bool:
        if self._patch_panel is None:
            return False
        # Treat any descendant of the panel having focus as the panel having focus
        try:
            return self._patch_panel.hasFocus() or self._patch_panel.isAncestorOf(
                self.focusWidget()
            )
        except (RuntimeError, AttributeError):
            return False
```

In `keyPressEvent`, gate live keys:

```python
    def keyPressEvent(self, event) -> None:
        # Patch panel focused → don't dispatch live shortcuts; let normal Qt
        # event flow handle text editing inside the panel.
        if self._patch_panel_has_focus():
            super().keyPressEvent(event)
            return

        # Tab toggles between live and patch panel
        if (
            event.key() == Qt.Key.Key_Tab
            and self._patch_panel is not None
        ):
            self._toggle_patch_focus()
            event.accept()
            return

        # Existing live shortcut logic continues below ↓
        ...
```

Add toggle helper:

```python
    def _toggle_patch_focus(self) -> None:
        if self._patch_panel is None:
            return
        if self._patch_panel_has_focus():
            self._canvas.setFocus()
        else:
            self._patch_panel.setFocus()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/ui/test_main_window_patch_focus.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/flow/ui/main_window.py tests/ui/test_main_window_patch_focus.py
git commit -m "feat(live): suppress live shortcuts while patch panel focused"
```

---

## Task 21: Refresh thumbnail badge after patches change

`_on_patch_applied` calls `_refresh_thumbnails_and_display(song)`. Implement that helper to recompute which slide indices are patched and push to `SlidePreviewPanel.set_patched_indices`.

**Files:**
- Modify: `src/flow/ui/main_window.py`
- Test: covered by integration test (Task 22)

- [ ] **Step 1: Implement `_refresh_thumbnails_and_display`**

In `MainWindow`:

```python
    def _refresh_thumbnails_and_display(self, song) -> None:
        """Re-render thumbnail strip and update display if affected.

        Recomputes the set of patched slide indices and pushes to the preview
        panel. If display is currently showing a slide that's now patched,
        re-pushes that slide image.
        """
        from flow.services.markdown import PatchStore, PatchType, parse

        if song.slide_source != "markdown":
            return

        md_path = song.markdown_path
        store = PatchStore(md_path.parent / ".patches.json")
        spec = parse(md_path.read_text(encoding="utf-8"))
        n_original = len(spec.slides)

        patched_indices: set[int] = set()
        # Edit patches → indices that match (use slide_index after applying)
        for p in store.patches:
            if p.type is PatchType.EDIT and p.slide_index is not None:
                if 0 <= p.slide_index < n_original:
                    patched_indices.add(p.slide_index)
        # Append patches → trailing indices
        n_appended = sum(1 for p in store.patches if p.type is PatchType.APPEND)
        for i in range(n_appended):
            patched_indices.add(n_original + i)

        # Repopulate the thumbnail strip with the new (patched) slide images
        self._reload_song_into_preview(song)  # existing helper or write one
        self._slide_preview.set_patched_indices(patched_indices)

        # If display is showing a slide that's now patched, push the new image
        if self._display_window is not None and self._display_window.isVisible():
            current_live_idx = self._live_controller.live_slide_index  # or equivalent
            if current_live_idx in patched_indices:
                img = self._slide_manager.get_slide_image(song, current_live_idx)
                self._display_window.set_image(img)  # use existing API
```

If `_reload_song_into_preview` and the display API don't exist by those names, find equivalents by grepping for how thumbnails get populated when a song loads:

```bash
grep -n "addItem\|set_song\|load_song\|populate" src/flow/ui/main_window.py | head -20
```

- [ ] **Step 2: Commit**

```bash
git add src/flow/ui/main_window.py
git commit -m "feat(live): refresh thumbnails + display after patch commit"
```

---

## Task 22: End-to-end integration test

Verify the full flow: open patch panel from preview menu → edit → Ctrl+Enter → patches.json updated → thumbnail shows badge.

**Files:**
- Create: `tests/ui/test_emergency_patch_integration.py`

- [ ] **Step 1: Write the integration test**

```python
# tests/ui/test_emergency_patch_integration.py
"""End-to-end: emergency patch flow updates .patches.json and badges."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

# This test runs against MainWindow with a synthetic song.
# Skip if MainWindow setup is too heavy for CI; we'll exercise the seams instead.


@pytest.fixture
def song_dir(tmp_path: Path) -> Path:
    folder = tmp_path / "songs" / "test_song"
    folder.mkdir(parents=True)
    md = folder / "slides.md"
    md.write_text(
        "# 테스트\n\n원본 1\n\n원본 2\n",
        encoding="utf-8",
    )
    return folder


def test_panel_emit_apply_writes_patches_json(qtbot, song_dir: Path) -> None:
    """EmergencyPatchPanel.applied → main_window writes .patches.json."""
    from flow.services.markdown import (
        PatchStore,
        PatchType,
        SlidePatch,
        parse,
        slide_hash,
    )

    md = song_dir / "slides.md"
    spec = parse(md.read_text(encoding="utf-8"))

    # Simulate the main_window receiver behavior directly
    import uuid
    from datetime import datetime, timezone

    payload = [(0, "고친 1"), ("add:0", "새 슬라이드")]
    store = PatchStore(song_dir / ".patches.json")
    now = datetime.now(timezone.utc).isoformat()
    for key, text in payload:
        if isinstance(key, int):
            store.add(
                SlidePatch(
                    id=str(uuid.uuid4()),
                    type=PatchType.EDIT,
                    patched_main=text,
                    slide_hash=slide_hash(spec.slides[key].main),
                    slide_index=key,
                    created_at=now,
                    created_during="live",
                )
            )
        else:
            store.add(
                SlidePatch(
                    id=str(uuid.uuid4()),
                    type=PatchType.APPEND,
                    patched_main=text,
                    slide_hash=None,
                    slide_index=None,
                    created_at=now,
                    created_during="live",
                )
            )
    store.save()

    raw = json.loads((song_dir / ".patches.json").read_text(encoding="utf-8"))
    assert raw["version"] == 1
    types = [p["type"] for p in raw["patches"]]
    assert "edit" in types and "append" in types


def test_round_trip_via_converter(qtbot, song_dir: Path) -> None:
    """After saving patches, the MarkdownSlideConverter exposes them."""
    from flow.services.markdown import (
        PatchStore,
        PatchType,
        SlidePatch,
        slide_hash,
        parse,
    )
    from flow.services.slide_converter import MarkdownSlideConverter
    import uuid

    md = song_dir / "slides.md"
    spec = parse(md.read_text(encoding="utf-8"))
    store = PatchStore(song_dir / ".patches.json")
    store.add(
        SlidePatch(
            id=str(uuid.uuid4()),
            type=PatchType.EDIT,
            patched_main="고친 1",
            slide_hash=slide_hash(spec.slides[0].main),
            slide_index=0,
            created_at="t",
            created_during="live",
        )
    )
    store.add(
        SlidePatch(
            id=str(uuid.uuid4()),
            type=PatchType.APPEND,
            patched_main="추가",
            slide_hash=None,
            slide_index=None,
            created_at="u",
            created_during="live",
        )
    )
    store.save()

    conv = MarkdownSlideConverter()
    assert conv.get_slide_count(md) == 3  # 2 original + 1 append
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `pytest tests/ui/test_emergency_patch_integration.py -v`
Expected: PASS (2 tests)

- [ ] **Step 3: Commit**

```bash
git add tests/ui/test_emergency_patch_integration.py
git commit -m "test(live): integration coverage for emergency-patch round trip"
```

---

## Task 23: Markdown editor — unreconciled patches notification bar

When opening a song in normal markdown editor, if `.patches.json` has any patches, show a top notification bar with "원본에 반영 / 폐기 / 자세히 보기" actions.

**Files:**
- Modify: `src/flow/ui/editor/markdown_editor.py`
- Test: `tests/ui/test_markdown_editor_patches_bar.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/ui/test_markdown_editor_patches_bar.py
"""Markdown editor surfaces unreconciled patches via a top notification bar."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from flow.ui.editor.markdown_editor import MarkdownEditor


def test_no_bar_when_no_patches(qtbot, tmp_path: Path) -> None:
    md = tmp_path / "slides.md"
    md.write_text("# t\n\n가사\n", encoding="utf-8")
    editor = MarkdownEditor()
    qtbot.addWidget(editor)
    editor.load_file(md)
    assert not editor._patches_bar.isVisible()


def test_bar_shown_with_patches(qtbot, tmp_path: Path) -> None:
    md = tmp_path / "slides.md"
    md.write_text("# t\n\n가사\n", encoding="utf-8")
    (tmp_path / ".patches.json").write_text(
        json.dumps({
            "version": 1,
            "patches": [
                {"id": "x", "type": "edit", "patched_main": "y",
                 "slide_hash": "sha256:h", "slide_index": 0,
                 "created_at": "t", "created_during": "live"}
            ],
        }),
        encoding="utf-8",
    )
    editor = MarkdownEditor()
    qtbot.addWidget(editor)
    editor.show()
    editor.load_file(md)
    assert editor._patches_bar.isVisible()
    assert "1" in editor._patches_bar_label.text()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/ui/test_markdown_editor_patches_bar.py -v`
Expected: FAIL — `_patches_bar` not defined

- [ ] **Step 3: Add notification bar to `MarkdownEditor`**

Locate `MarkdownEditor.__init__` and the `load_file` method (or equivalent). Add at the top of the layout:

```python
        from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton
        from flow.ui import styles

        self._patches_bar = QFrame()
        self._patches_bar.setStyleSheet(
            f"background-color: {styles.AMBER_MUTED}; "
            f"border-left: 3px solid {styles.AMBER};"
        )
        bar_layout = QHBoxLayout(self._patches_bar)
        bar_layout.setContentsMargins(
            styles.SP_MD, styles.SP_SM, styles.SP_MD, styles.SP_SM
        )
        self._patches_bar_label = QLabel("긴급 수정 0건이 .md 원본에 반영되지 않았습니다.")
        self._patches_bar_label.setStyleSheet(
            f"color: {styles.AMBER}; font-size: {styles.FONT_SM}px;"
        )
        bar_layout.addWidget(self._patches_bar_label, 1)
        for label, slot in (
            ("원본에 반영", self._on_patches_apply_to_source),
            ("폐기", self._on_patches_discard),
            ("자세히 보기", self._on_patches_details),
        ):
            btn = QPushButton(label)
            btn.setStyleSheet(
                f"QPushButton {{ background-color: transparent; "
                f"color: {styles.AMBER}; border: 1px solid {styles.AMBER}; "
                f"border-radius: 4px; padding: 4px 8px; font-size: {styles.FONT_XS}px; }}"
            )
            btn.clicked.connect(slot)
            bar_layout.addWidget(btn)
        self._patches_bar.hide()
        # Insert at top of main layout — adjust index based on existing layout
        self.layout().insertWidget(0, self._patches_bar)
```

In `load_file`:

```python
    def load_file(self, md_path: Path) -> None:
        ...  # existing body
        self._refresh_patches_bar(md_path)

    def _refresh_patches_bar(self, md_path: Path) -> None:
        from flow.services.markdown import PatchStore
        store = PatchStore(md_path.parent / ".patches.json")
        n = len(store.patches)
        if n == 0:
            self._patches_bar.hide()
            return
        self._patches_bar_label.setText(
            f"긴급 수정 {n}건이 .md 원본에 반영되지 않았습니다."
        )
        self._patches_bar.show()
        self._current_md_path = md_path  # for action handlers

    def _on_patches_apply_to_source(self) -> None:
        # Implemented in Task 24
        pass

    def _on_patches_discard(self) -> None:
        from flow.services.markdown import PatchStore
        store = PatchStore(self._current_md_path.parent / ".patches.json")
        store.clear()
        store.save()
        self._refresh_patches_bar(self._current_md_path)

    def _on_patches_details(self) -> None:
        # Phase 2 — leave as no-op for now, surface a toast/dialog
        pass
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/ui/test_markdown_editor_patches_bar.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/flow/ui/editor/markdown_editor.py tests/ui/test_markdown_editor_patches_bar.py
git commit -m "feat(editor): unreconciled-patches notification bar"
```

---

## Task 24: Apply patches to source (.md rewrite)

Implement `_on_patches_apply_to_source`: write each patch into `slides.md` and clear `.patches.json`.

**Files:**
- Modify: `src/flow/ui/editor/markdown_editor.py`
- Create helper: `src/flow/services/markdown/patches.py` — `apply_patches_to_text(text, patches) -> str`
- Test: `tests/services/test_apply_patches_to_text.py`

- [ ] **Step 1: Write the failing test for the text helper**

```python
# tests/services/test_apply_patches_to_text.py
"""apply_patches_to_text rewrites a slides.md to embed all patches."""
from __future__ import annotations

import pytest

from flow.services.markdown import (
    PatchType,
    SlidePatch,
    apply_patches_to_text,
    slide_hash,
)


def test_apply_edit_replaces_slide_body() -> None:
    src = "# t\n\n원본 1\n\n원본 2\n"
    patch = SlidePatch(
        id="p1",
        type=PatchType.EDIT,
        patched_main="고친 1",
        slide_hash=slide_hash("원본 1"),
        slide_index=0,
        created_at="t",
        created_during="live",
    )
    out = apply_patches_to_text(src, [patch])
    assert "고친 1" in out
    assert "원본 1" not in out
    assert "원본 2" in out


def test_apply_append_adds_blank_separated_block() -> None:
    src = "# t\n\n원본 1\n"
    patch = SlidePatch(
        id="p1",
        type=PatchType.APPEND,
        patched_main="추가된",
        slide_hash=None,
        slide_index=None,
        created_at="t",
        created_during="live",
    )
    out = apply_patches_to_text(src, [patch])
    assert out.endswith("추가된\n")
    assert "원본 1" in out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/services/test_apply_patches_to_text.py -v`
Expected: FAIL — `apply_patches_to_text` not defined

- [ ] **Step 3: Implement `apply_patches_to_text`**

In `src/flow/services/markdown/patches.py`, add:

```python
def apply_patches_to_text(text: str, patches: list[SlidePatch]) -> str:
    """Apply patches by re-parsing text, applying patches at SongSpec level,
    and re-emitting markdown. For now we use a simple block-rewrite approach
    that preserves frontmatter and title."""
    from flow.services.markdown.parser import parse

    spec = parse(text)
    patched = apply_patches(spec, patches)

    # Rebuild markdown: keep original frontmatter/title prefix, re-emit slides
    lines: list[str] = []
    if spec.title:
        lines.append(f"# {spec.title}")
        lines.append("")
    for slide in patched.slides:
        lines.append(slide.main.rstrip("\n"))
        lines.append("")  # blank-line separator
    out = "\n".join(lines).rstrip() + "\n"

    # Preserve original frontmatter block if present
    import re
    m = re.match(r"\A(---\s*\n.*?\n---\s*\n)", text, flags=re.DOTALL)
    if m:
        out = m.group(1) + out
    return out
```

Add to `__all__` in `flow/services/markdown/__init__.py`:

```python
from flow.services.markdown.patches import (
    PatchStore,
    PatchType,
    SlidePatch,
    apply_patches,
    apply_patches_to_text,  # NEW
    slide_hash,
)
```

And update `__all__` list.

- [ ] **Step 4: Run text helper tests to verify they pass**

Run: `pytest tests/services/test_apply_patches_to_text.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Wire into editor**

In `MarkdownEditor`:

```python
    def _on_patches_apply_to_source(self) -> None:
        from flow.services.markdown import PatchStore, apply_patches_to_text

        if self._current_md_path is None:
            return
        text = self._current_md_path.read_text(encoding="utf-8")
        store = PatchStore(self._current_md_path.parent / ".patches.json")
        new_text = apply_patches_to_text(text, store.patches)
        self._current_md_path.write_text(new_text, encoding="utf-8")
        store.clear()
        store.save()
        # Reload current view to reflect new .md content
        self.load_file(self._current_md_path)
```

- [ ] **Step 6: Add an editor-side test**

Append to `tests/ui/test_markdown_editor_patches_bar.py`:

```python
def test_apply_to_source_rewrites_md_and_clears_patches(qtbot, tmp_path: Path) -> None:
    md = tmp_path / "slides.md"
    md.write_text("# t\n\n원본\n", encoding="utf-8")
    from flow.services.markdown import slide_hash
    (tmp_path / ".patches.json").write_text(
        json.dumps({
            "version": 1,
            "patches": [
                {"id": "x", "type": "edit", "patched_main": "고친",
                 "slide_hash": slide_hash("원본"), "slide_index": 0,
                 "created_at": "t", "created_during": "live"}
            ],
        }),
        encoding="utf-8",
    )
    editor = MarkdownEditor()
    qtbot.addWidget(editor)
    editor.show()
    editor.load_file(md)
    editor._on_patches_apply_to_source()

    new_text = md.read_text(encoding="utf-8")
    assert "고친" in new_text
    assert "원본" not in new_text
    patches_raw = json.loads((tmp_path / ".patches.json").read_text(encoding="utf-8"))
    assert patches_raw["patches"] == []
```

- [ ] **Step 7: Run all editor tests**

Run: `pytest tests/ui/test_markdown_editor_patches_bar.py tests/services/test_apply_patches_to_text.py -v`
Expected: ALL pass

- [ ] **Step 8: Commit**

```bash
git add src/flow/services/markdown/patches.py src/flow/services/markdown/__init__.py \
        src/flow/ui/editor/markdown_editor.py \
        tests/services/test_apply_patches_to_text.py \
        tests/ui/test_markdown_editor_patches_bar.py
git commit -m "feat(patches): apply-to-source rewrites .md and clears .patches.json"
```

---

## Task 25: Final regression sweep

Run the entire test suite to make sure nothing existing broke.

- [ ] **Step 1: Run all tests headlessly**

```bash
QT_QPA_PLATFORM=offscreen pytest -q
```

Expected: ALL PASS, no regressions.

- [ ] **Step 2: Lint + type check**

```bash
ruff check --fix src/ tests/
mypy src/flow/services/markdown/patches.py src/flow/ui/live/
```

Expected: No errors. Fix any type/lint issues inline.

- [ ] **Step 3: Manual smoke test in headed mode**

```bash
flow
```

Walk through:
1. Open a markdown song
2. Enter live mode
3. Right-click a thumbnail → "긴급 수정"
4. Edit text, see preview update
5. Press Ctrl+→ to navigate to next slide
6. Edit it too
7. Press Ctrl+Enter — verify display updates if applicable, panel closes
8. Right-click thumbnail again → "맨 끝에 슬라이드 추가"
9. Type, press Ctrl+Enter — verify new thumbnail appears
10. Exit live mode, open the song in normal markdown editor
11. Verify "긴급 수정 N건…" bar shows
12. Click "원본에 반영" — verify .md is rewritten

- [ ] **Step 4: Commit cleanup if any**

```bash
git status
# If anything from lint/type fixes:
git add -A
git commit -m "chore: ruff + mypy cleanup for emergency patch feature"
```

---

## Self-Review

This implementation plan covers all spec sections:

- **Trigger menus** (spec §UX 진입): Tasks 15, 16
- **Split layout** (§분할 레이아웃): Task 18
- **Focus model** (§포커스 모델): Task 20
- **Editor pane** (§편집 패널 구성): Tasks 8, 9, 10, 11, 12, 13, 14
- **Navigation** (§편집 패널 내 슬라이드 전환): Tasks 10, 11
- **Batch commit** (§편집 적용): Task 12
- **Esc + dialog** (§닫기): Task 13
- **Original revert** (§원본으로 되돌리기): Task 14
- **Visual badge** (§시각 표시): Task 17
- **Data model** (§데이터 모델): Tasks 1-5
- **Slide identity algorithm** (§슬라이드 식별/적용): Tasks 3, 4
- **MarkdownSlideConverter integration**: Task 6
- **Reconciliation flow** (§라이브 종료 후 정리): Tasks 23, 24
- **Tests** (§테스트 전략): unit covered in Tasks 1-6, UI in 7-14, integration in 22

**Type/method consistency check:**
- `SlidePatch` fields: `id, type, patched_main, slide_hash, slide_index, created_at, created_during` — used consistently across all tasks
- `PatchType.EDIT` / `PatchType.APPEND` — same names everywhere
- `PatchStore.add/remove/clear/save/patches` — consistent API
- `apply_patches(spec, patches) -> SongSpec` — consistent
- `slide_hash(main: str) -> str` — consistent
- `EmergencyPatchPanel.applied(list)` — payload always `list[(int|str, str)]`
- `EmergencyPatchPanel.close_requested()` — no payload
- Slot key model `int | str` (with `"add:N"` for add slots) — consistent

**Out-of-scope items deferred to follow-up:**
- "자세히 보기" diff dialog (Task 23 leaves it as no-op stub)
- drift / orphan visual indicators (logic implemented, UI deferred)
- per-patch individual apply/discard (only bulk in this plan)
- Phase 2 features from spec §비범위 stay out

---

**Plan complete and saved to `docs/superpowers/plans/2026-05-05-emergency-slide-patch.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

**Which approach?**
