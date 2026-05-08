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
