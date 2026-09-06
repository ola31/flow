"""패치 바 동작(원본에 반영 / 폐기) 이후 화면과 세션 상태.

두 버튼 모두 곡이 그려지는 내용을 바꾼다. 그런데 반영은 load_file로
텍스트를 갈아끼우면서 세션의 '바뀜' 표시까지 지웠고, load_file은 미리보기를
다시 그리지 않았다 — 그래서 눌러도 아무 일이 없는 것처럼 보였고, 편집기를
나가도 main_window가 "수정 없음"으로 보고 슬라이드 재로딩을 건너뛰었다.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from flow.services.markdown import PatchStore, PatchType, SlidePatch, parse, slide_hash

_MD = "---\n---\n\n# 바다\n\n푸른 바다가 보이네\n\n노을이 물든다\n"


@pytest.fixture
def song_dir(tmp_path: Path) -> Path:
    folder = tmp_path / "songs" / "테스트곡"
    folder.mkdir(parents=True)
    (folder / "slides.md").write_text(_MD, encoding="utf-8")
    return folder


def _add_patch(song_dir: Path, index: int, text: str) -> None:
    spec = parse((song_dir / "slides.md").read_text(encoding="utf-8"))
    store = PatchStore(song_dir / ".patches.json")
    store.add(
        SlidePatch(
            id="p1",
            type=PatchType.EDIT,
            patched_main=text,
            slide_hash=slide_hash(spec.slides[index].main),
            slide_index=index,
            created_at="2026-09-06T00:00:00+00:00",
            created_during="live",
        )
    )
    store.save()


def _editor(qtbot, song_dir: Path):
    from flow.ui.editor.markdown_editor import MarkdownEditor

    editor = MarkdownEditor(song_dir / "slides.md")
    qtbot.addWidget(editor)
    return editor


def test_apply_to_source_writes_patch_into_the_md(qtbot, song_dir):
    _add_patch(song_dir, 1, "노을이 붉게 물든다")
    editor = _editor(qtbot, song_dir)

    editor._on_patches_apply_to_source()

    text = (song_dir / "slides.md").read_text(encoding="utf-8")
    assert "노을이 붉게 물든다" in text
    assert text.startswith("---\n---\n")  # 빈 프론트매터 보존
    assert PatchStore(song_dir / ".patches.json").patches == []


def test_apply_to_source_shows_the_new_text_in_the_editor(qtbot, song_dir):
    _add_patch(song_dir, 1, "노을이 붉게 물든다")
    editor = _editor(qtbot, song_dir)

    editor._on_patches_apply_to_source()

    assert "노을이 붉게 물든다" in editor.text()


def test_apply_to_source_re_renders_the_preview(qtbot, song_dir, monkeypatch):
    """미리보기를 다시 그리지 않으면 반영 전 슬라이드가 그대로 남는다."""
    _add_patch(song_dir, 1, "노을이 붉게 물든다")
    editor = _editor(qtbot, song_dir)

    calls: list[int] = []
    monkeypatch.setattr(editor, "_render_preview", lambda: calls.append(1))

    editor._on_patches_apply_to_source()

    assert calls, "load_file이 미리보기를 다시 그려야 한다"


def test_apply_to_source_marks_the_session_changed(qtbot, song_dir):
    """나갈 때 main_window가 슬라이드를 다시 세도록 하는 표시."""
    _add_patch(song_dir, 1, "노을이 붉게 물든다")
    editor = _editor(qtbot, song_dir)

    editor._on_patches_apply_to_source()

    assert editor.content_changed() is True


def test_discard_marks_the_session_changed(qtbot, song_dir):
    """.md는 그대로여도 패치가 사라지면 곡은 다르게 그려진다."""
    _add_patch(song_dir, 1, "노을이 붉게 물든다")
    editor = _editor(qtbot, song_dir)

    editor._on_patches_discard()

    assert PatchStore(song_dir / ".patches.json").patches == []
    assert editor.content_changed() is True


def test_untouched_editor_stays_unchanged(qtbot, song_dir):
    """아무것도 안 했으면 나갈 때 재로딩도 없어야 한다 (기존 동작)."""
    editor = _editor(qtbot, song_dir)

    assert editor.content_changed() is False
