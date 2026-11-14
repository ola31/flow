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


def test_apply_patches_edit_prefers_the_saved_seat_when_text_repeats() -> None:
    """같은 후렴이 두 번 나오는 곡에서 뒤쪽을 고치면 뒤쪽이 바뀌어야 한다.

    해시부터 찾으면 첫 일치(앞쪽)에 붙어, 고친 자리는 그대로고 엉뚱한
    자리가 바뀐다.
    """
    spec = _make_spec("후렴", "둘째 줄", "후렴")
    patch = SlidePatch(
        id="p1",
        type=PatchType.EDIT,
        patched_main="후렴 (수정)",
        slide_hash=slide_hash("후렴"),
        slide_index=2,
        created_at="t",
        created_during="live",
    )
    result = apply_patches(spec, [patch])
    assert [s.main for s in result.slides] == ["후렴", "둘째 줄", "후렴 (수정)"]


def test_apply_patches_edit_follows_the_slide_when_it_moved() -> None:
    """자리의 글이 바뀌었으면(앞에 슬라이드가 끼어듦) 해시로 옮겨간 자리를
    찾는다."""
    spec = _make_spec("새로 끼어든 줄", "원본 1", "원본 2")
    patch = SlidePatch(
        id="p1",
        type=PatchType.EDIT,
        patched_main="패치된 본문",
        slide_hash=slide_hash("원본 2"),
        slide_index=1,  # 저장 당시 자리 — 지금은 '원본 1'이 있다
        created_at="t",
        created_during="live",
    )
    result = apply_patches(spec, [patch])
    assert [s.main for s in result.slides] == [
        "새로 끼어든 줄", "원본 1", "패치된 본문"
    ]


def test_edit_patches_for_slide_uses_the_same_resolution() -> None:
    from flow.services.markdown import edit_patches_for_slide

    spec = _make_spec("후렴", "둘째 줄", "후렴")
    patch = SlidePatch(
        id="p1",
        type=PatchType.EDIT,
        patched_main="후렴 (수정)",
        slide_hash=slide_hash("후렴"),
        slide_index=2,
        created_at="t",
        created_during="live",
    )
    assert edit_patches_for_slide([patch], spec, 2) == [patch]
    assert edit_patches_for_slide([patch], spec, 0) == []



def test_repeated_edits_stay_on_the_same_duplicate_and_revert_together() -> None:
    from dataclasses import replace

    from flow.services.markdown import edit_patches_for_slide

    spec = _make_spec("chorus", "verse", "chorus")
    first = SlidePatch(
        id="first", type=PatchType.EDIT, patched_main="edit 1",
        slide_hash=slide_hash("chorus"), slide_index=2,
        created_at="t1", created_during="live",
    )
    second = replace(first, id="second", patched_main="edit 2", created_at="t2")
    patches = [first, second]

    result = apply_patches(spec, patches)
    assert [s.main for s in result.slides] == ["chorus", "verse", "edit 2"]
    assert [s.main for s in spec.slides] == ["chorus", "verse", "chorus"]
    assert edit_patches_for_slide(patches, spec, 0) == []
    stale = edit_patches_for_slide(patches, spec, 2)
    assert stale == patches
    remaining = [p for p in patches if p not in stale]
    assert apply_patches(spec, remaining) == spec


def test_edit_target_ignores_text_introduced_by_an_earlier_patch() -> None:
    from dataclasses import replace

    spec = _make_spec("first", "target")
    first = SlidePatch(
        id="first", type=PatchType.EDIT, patched_main="target",
        slide_hash=slide_hash("first"), slide_index=0,
        created_at="t1", created_during="live",
    )
    # The target moved from its saved seat 0 to seat 1 in the source.
    moved = replace(
        first, id="moved", patched_main="corrected",
        slide_hash=slide_hash("target"), created_at="t2",
    )
    result = apply_patches(spec, [first, moved])
    assert [s.main for s in result.slides] == ["target", "corrected"]
