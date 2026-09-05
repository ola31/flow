# src/flow/services/markdown/patches.py
"""Slide patch storage — `.patches.json` per song, edit + append patches."""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path

from flow.services.markdown.parser import SongSpec

logger = logging.getLogger(__name__)

_PATCHES_VERSION = 1


class PatchType(str, Enum):
    EDIT = "edit"
    APPEND = "append"


@dataclass(frozen=True)
class SlidePatch:
    id: str
    type: PatchType
    patched_main: str
    slide_hash: str | None
    slide_index: int | None
    created_at: str
    created_during: str

    def to_json(self) -> dict[str, object]:
        d: dict[str, object] = {
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
    def from_json(cls, raw: dict[str, object]) -> SlidePatch:
        ptype = PatchType(str(raw["type"]))
        slide_hash_val = raw.get("slide_hash")
        slide_index_val = raw.get("slide_index")
        return cls(
            id=str(raw["id"]),
            type=ptype,
            patched_main=str(raw["patched_main"]),
            slide_hash=str(slide_hash_val) if slide_hash_val is not None else None,
            slide_index=int(slide_index_val) if slide_index_val is not None else None,  # type: ignore[call-overload]
            created_at=str(raw["created_at"]),
            created_during=str(raw["created_during"]),
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


def slide_hash(main: str) -> str:
    """Hash a slide's main body for patch-matching. Stable for identical text."""
    digest = hashlib.sha256(main.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


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


def edit_patches_for_slide(
    patches: list[SlidePatch], spec: SongSpec, index: int
) -> list[SlidePatch]:
    """`index` 번째 원본 슬라이드를 겨냥하는 EDIT 패치들.

    되돌리기가 기존 패치를 걷어낼 때 쓴다. apply_patches의 매칭 규칙과
    같은 두 갈래를 본다 — 원문 해시가 같거나, slide_index가 그 자리를
    가리키거나.
    """
    if not (0 <= index < len(spec.slides)):
        return []
    target_hash = slide_hash(spec.slides[index].main)
    return [
        p
        for p in patches
        if p.type is PatchType.EDIT
        and (p.slide_hash == target_hash or p.slide_index == index)
    ]


def _find_edit_target(slides: list, patch: SlidePatch) -> int | None:
    if patch.slide_hash is not None:
        for i, s in enumerate(slides):
            if slide_hash(s.main) == patch.slide_hash:
                return i
    if patch.slide_index is not None and 0 <= patch.slide_index < len(slides):
        return patch.slide_index
    return None


def apply_patches_to_text(text: str, patches: list[SlidePatch]) -> str:
    """Apply patches by re-parsing text, applying patches at SongSpec level,
    and re-emitting markdown. Preserves frontmatter and title."""
    import re

    from flow.services.markdown.parser import parse

    spec = parse(text)
    patched = apply_patches(spec, patches)

    lines: list[str] = []
    if spec.title:
        lines.append(f"# {spec.title}")
        lines.append("")
    for slide in patched.slides:
        lines.append(slide.main.rstrip("\n"))
        lines.append("")
    out = "\n".join(lines).rstrip() + "\n"

    # Preserve original frontmatter block if present
    m = re.match(r"\A(---\s*\n.*?\n---\s*\n)", text, flags=re.DOTALL)
    if m:
        out = m.group(1) + out
    return out
