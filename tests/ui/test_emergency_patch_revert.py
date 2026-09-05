"""'원본으로 되돌리기'는 .md 원문으로 되돌려야 한다.

패널에는 이미 적용된 패치가 반영된 spec이 들어온다. 그걸 원본으로 삼으면
한 번 적용한 뒤에는 되돌리기를 눌러도 같은 글이 다시 채워져 버튼이 아무
일도 하지 않는 것처럼 보인다.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from flow.services.markdown import (
    PatchStore,
    PatchType,
    SlidePatch,
    apply_patches,
    parse,
    slide_hash,
)

_MD = "# 바다\n\n푸른 바다가 보이네\n\n노을이 물든다\n"


@pytest.fixture
def song_dir(tmp_path: Path) -> Path:
    folder = tmp_path / "songs" / "테스트곡"
    folder.mkdir(parents=True)
    (folder / "slides.md").write_text(_MD, encoding="utf-8")
    return folder


def _store_with_edit(song_dir: Path, index: int, text: str) -> PatchStore:
    spec = parse((song_dir / "slides.md").read_text(encoding="utf-8"))
    store = PatchStore(song_dir / ".patches.json")
    store.add(
        SlidePatch(
            id=str(uuid.uuid4()),
            type=PatchType.EDIT,
            patched_main=text,
            slide_hash=slide_hash(spec.slides[index].main),
            slide_index=index,
            created_at="2026-08-16T00:00:00+00:00",
            created_during="live",
        )
    )
    store.save()
    return store


def _panel(qtbot, song_dir: Path, index: int):
    """main_window가 패널을 여는 것과 같은 방식으로 만든다."""
    from flow.ui.live.emergency_patch_panel import EmergencyPatchPanel

    spec = parse((song_dir / "slides.md").read_text(encoding="utf-8"))
    store = PatchStore(song_dir / ".patches.json")
    panel = EmergencyPatchPanel(
        spec=apply_patches(spec, store.patches),
        original_spec=spec,
        song_dir=song_dir,
        initial_index=index,
    )
    qtbot.addWidget(panel)
    return panel


def test_revert_restores_the_md_text_not_the_applied_patch(qtbot, song_dir):
    _store_with_edit(song_dir, 0, "긴급히 고친 줄")
    panel = _panel(qtbot, song_dir, 0)
    assert panel.current_text() == "긴급히 고친 줄"  # 패치가 반영된 상태로 열림

    panel.revert_current()

    assert panel.current_text() == "푸른 바다가 보이네"


def test_revert_leaves_a_change_to_apply(qtbot, song_dir):
    """되돌린 결과는 적용 대상이어야 한다 — 아니면 패치가 그대로 남는다."""
    _store_with_edit(song_dir, 0, "긴급히 고친 줄")
    panel = _panel(qtbot, song_dir, 0)

    panel.revert_current()

    assert panel.has_pending_changes() is True
    payloads: list = []
    panel.applied.connect(payloads.append)
    panel.apply_now()
    # Qt 시그널을 거치며 튜플이 리스트가 되므로 값으로 비교한다
    assert payloads
    assert [list(item) for item in payloads[0]] == [[0, "푸른 바다가 보이네"]]


def test_revert_without_any_patch_discards_typing(qtbot, song_dir):
    """패치가 없을 때는 이 세션에 친 글만 버린다 (원래 동작)."""
    panel = _panel(qtbot, song_dir, 1)
    panel.set_text("잘못 친 글")

    panel.revert_current()

    assert panel.current_text() == "노을이 물든다"
    assert panel.has_pending_changes() is False


def test_applying_a_revert_removes_the_patch_instead_of_stacking_one(
    qapp, song_dir, tmp_path
):
    """되돌린 뒤 적용하면 .patches.json에서 그 슬라이드 패치가 사라져야 한다."""
    from flow.services.markdown import edit_patches_for_slide

    _store_with_edit(song_dir, 0, "긴급히 고친 줄")
    spec = parse((song_dir / "slides.md").read_text(encoding="utf-8"))
    store = PatchStore(song_dir / ".patches.json")
    assert len(store.patches) == 1

    # main_window._on_patch_applied 가 하는 일: 원본과 같으면 걷어낸다
    stale = edit_patches_for_slide(store.patches, spec, 0)
    assert len(stale) == 1
    for patch in stale:
        store.remove(patch.id)
    store.save()

    reloaded = PatchStore(song_dir / ".patches.json")
    assert reloaded.patches == []
    assert apply_patches(spec, reloaded.patches).slides[0].main == "푸른 바다가 보이네"


def test_end_to_end_revert_through_main_window(qapp, tmp_path):
    """패널 열기 → 되돌리기 → 적용 이 실제로 패치를 걷어내는지."""
    import json

    from flow.domain.project import Project
    from flow.domain.score_sheet import ScoreSheet
    from flow.domain.song import Song
    from flow.domain.workspace import Workspace
    from flow.repository.project_repository import ProjectRepository
    from flow.ui.main_window import MainWindow

    ws = Workspace.create(tmp_path / "ws")
    song_dir = ws.library_song_dir("마크다운곡")
    (song_dir / "sheets").mkdir(parents=True, exist_ok=True)
    (song_dir / "slides.md").write_text(_MD, encoding="utf-8")
    sheet = ScoreSheet(name="p1")
    (song_dir / "song.json").write_text(
        json.dumps({"name": "마크다운곡", "sheets": [sheet.to_dict()]},
                   ensure_ascii=False),
        encoding="utf-8",
    )
    _store_with_edit(song_dir, 0, "긴급히 고친 줄")

    mw = MainWindow(workspace=ws)
    try:
        mw._project = Project(name="셋")
        mw._project_path = ProjectRepository(ws.projects_dir).save_to_workspace(
            mw._project, ws
        )
        song = Song.load_from_workspace(ws, "셋", "마크다운곡", order=0)
        mw._project.selected_songs.append(song)

        mw._is_live = True
        mw._open_emergency_patch_panel(song=song, initial_index=0)
        panel = mw._patch_panel
        assert panel is not None
        assert panel.current_text() == "긴급히 고친 줄"

        panel.revert_current()
        assert panel.current_text() == "푸른 바다가 보이네"
        panel.apply_now()

        store = PatchStore(song_dir / ".patches.json")
        assert store.patches == []
        spec = parse((song_dir / "slides.md").read_text(encoding="utf-8"))
        assert apply_patches(spec, store.patches).slides[0].main == "푸른 바다가 보이네"
    finally:
        mw._close_emergency_patch_panel()
        mw._is_live = False
        mw.close()
