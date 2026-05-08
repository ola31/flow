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
        ptype = PatchType(raw["type"])
        return cls(
            id=raw["id"],
            type=ptype,
            patched_main=raw["patched_main"],
            slide_hash=raw.get("slide_hash"),
            slide_index=raw.get("slide_index"),
            created_at=raw["created_at"],
            created_during=raw["created_during"],
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
