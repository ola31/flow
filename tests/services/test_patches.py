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
