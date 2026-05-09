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

    apply_fired: list = []
    close_fired: list = []
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

    apply_fired: list = []
    close_fired: list = []
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

    close_fired: list = []
    panel.close_requested.connect(lambda: close_fired.append(True))

    panel.attempt_close()
    assert not close_fired  # dialog cancelled → stay open


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


def test_out_of_range_initial_index_clips_to_last_slide(qtbot, tmp_path: Path) -> None:
    """Defense in depth: a stale/global index must not crash the panel."""
    spec = _make_spec("원본 1", "원본 2")
    panel = EmergencyPatchPanel(spec=spec, song_dir=tmp_path, initial_index=99)
    qtbot.addWidget(panel)
    # Should clip to the last valid slide rather than IndexError
    assert panel.current_text() == "원본 2"


def test_negative_initial_index_clips_to_first_slide(qtbot, tmp_path: Path) -> None:
    spec = _make_spec("원본 1", "원본 2")
    panel = EmergencyPatchPanel(spec=spec, song_dir=tmp_path, initial_index=-3)
    qtbot.addWidget(panel)
    assert panel.current_text() == "원본 1"


def test_empty_spec_with_index_falls_back_to_add_mode(qtbot, tmp_path: Path) -> None:
    """If a song somehow has zero slides, opening in edit mode should
    degrade to add mode rather than crash."""
    spec = SongSpec(title="t", frontmatter=Frontmatter(), slides=[])
    panel = EmergencyPatchPanel(spec=spec, song_dir=tmp_path, initial_index=0)
    qtbot.addWidget(panel)
    assert panel.is_add_mode()


def test_set_active_changes_panel_stylesheet(qtbot, tmp_path: Path) -> None:
    """Visual focus indicator: ACCENT left bar appears/disappears."""
    spec = _make_spec("원본 1")
    panel = EmergencyPatchPanel(spec=spec, song_dir=tmp_path, initial_index=0)
    qtbot.addWidget(panel)

    panel.set_active(True)
    active_qss = panel.styleSheet()
    panel.set_active(False)
    inactive_qss = panel.styleSheet()

    assert active_qss != inactive_qss
    # Active state must reference the ACCENT token; inactive must not.
    from flow.ui import styles
    assert styles.ACCENT.lower() in active_qss.lower()
    assert styles.ACCENT.lower() not in inactive_qss.lower()


def test_cancel_button_invokes_attempt_close(qtbot, tmp_path: Path) -> None:
    spec = _make_spec("원본 1")
    panel = EmergencyPatchPanel(spec=spec, song_dir=tmp_path, initial_index=0)
    qtbot.addWidget(panel)
    # No pending edits → cancel should fire close_requested immediately.
    with qtbot.waitSignal(panel.close_requested, timeout=1000):
        panel._cancel_btn.click()


def test_song_nav_signals_exist() -> None:
    assert hasattr(EmergencyPatchPanel, "prev_song_requested")
    assert hasattr(EmergencyPatchPanel, "next_song_requested")


def test_song_nav_buttons_emit_signals(qtbot, tmp_path: Path) -> None:
    spec = _make_spec("원본 1")
    panel = EmergencyPatchPanel(spec=spec, song_dir=tmp_path, initial_index=0)
    qtbot.addWidget(panel)
    with qtbot.waitSignal(panel.next_song_requested, timeout=1000):
        panel._next_song_btn.click()
    with qtbot.waitSignal(panel.prev_song_requested, timeout=1000):
        panel._prev_song_btn.click()


def test_set_song_nav_enabled_toggles_buttons(qtbot, tmp_path: Path) -> None:
    spec = _make_spec("원본 1")
    panel = EmergencyPatchPanel(spec=spec, song_dir=tmp_path, initial_index=0)
    qtbot.addWidget(panel)
    panel.set_song_nav_enabled(False, False)
    assert not panel._prev_song_btn.isEnabled()
    assert not panel._next_song_btn.isEnabled()
    panel.set_song_nav_enabled(True, True)
    assert panel._prev_song_btn.isEnabled()
    assert panel._next_song_btn.isEnabled()
