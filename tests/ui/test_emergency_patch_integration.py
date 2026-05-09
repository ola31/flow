# tests/ui/test_emergency_patch_integration.py
"""End-to-end: emergency patch flow updates .patches.json and converter sees it."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest


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
    """Translate payload like main_window does → .patches.json."""
    from flow.services.markdown import (
        PatchStore,
        PatchType,
        SlidePatch,
        parse,
        slide_hash,
    )

    md = song_dir / "slides.md"
    spec = parse(md.read_text(encoding="utf-8"))

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


def test_round_trip_via_converter(qtbot, song_dir: Path, qapp) -> None:
    """After saving patches, MarkdownSlideConverter exposes the new slide count."""
    from flow.services.markdown import (
        PatchStore,
        PatchType,
        SlidePatch,
        parse,
        slide_hash,
    )
    from flow.services.slide_converter import MarkdownSlideConverter

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


def test_panel_applied_signal_payload_shape(qtbot, song_dir: Path, qapp) -> None:
    """The EmergencyPatchPanel emits payload that main_window expects."""
    from flow.services.markdown import Frontmatter, Slide, SongSpec
    from flow.ui.live.emergency_patch_panel import EmergencyPatchPanel

    spec = SongSpec(
        title="t",
        frontmatter=Frontmatter(),
        slides=[
            Slide(main="원본 1", sub_override=None, section_sub_default=None),
            Slide(main="원본 2", sub_override=None, section_sub_default=None),
        ],
    )

    panel = EmergencyPatchPanel(spec=spec, song_dir=song_dir, initial_index=0)
    qtbot.addWidget(panel)

    panel.set_text("고친 1")
    panel.go_next()
    panel.set_text("고친 2")

    with qtbot.waitSignal(panel.applied, timeout=1000) as blocker:
        panel.apply_now()

    payload = blocker.args[0]
    keys_to_text = dict(payload)
    # Both edits surfaced; types match what main_window expects
    assert keys_to_text[0] == "고친 1"
    assert keys_to_text[1] == "고친 2"
    assert all(isinstance(k, int) for k in keys_to_text.keys())
