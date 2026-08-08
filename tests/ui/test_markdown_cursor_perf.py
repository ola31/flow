"""마크다운 에디터 커서 이동 — 프리뷰 렌더는 커서가 멈춘 뒤에.

방향키를 누르고 있으면 슬라이드 경계를 넘을 때마다 메인 프리뷰를 즉시
풀 렌더(회당 ~50ms, 배경 스케일이 대부분)해서 커서가 끊겼다. 중간
슬라이드의 프리뷰는 어차피 보이지도 않는다.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtGui import QTextCursor

from flow.ui.editor.markdown_editor import MarkdownEditor


def _doc(tmp_path: Path, slides: int = 12) -> Path:
    md = tmp_path / "slides.md"
    lines = ["---", "main_size: 56", "---", ""]
    for i in range(slides):
        lines += [f"## {i + 1}절", "", f"가사 {i}", ""]
    md.write_text("\n".join(lines), encoding="utf-8")
    return md


@pytest.fixture
def editor(qtbot, tmp_path):
    ed = MarkdownEditor(_doc(tmp_path))
    qtbot.addWidget(ed)
    ed.resize(900, 700)
    ed.show()
    qtbot.waitExposed(ed)
    qtbot.wait(150)  # 최초 렌더 소화
    return ed


def _spy(editor, monkeypatch) -> list[int]:
    calls: list[int] = []
    monkeypatch.setattr(
        editor, "_render_main_preview", lambda idx: calls.append(idx)
    )
    return calls


def _move_down(editor, times: int) -> None:
    """이벤트 루프로 돌아가지 않고 연속 이동 — 방향키를 누르고 있는 상태."""
    editor._text_edit.moveCursor(QTextCursor.MoveOperation.Start)
    for _ in range(times):
        editor._text_edit.moveCursor(QTextCursor.MoveOperation.Down)


def test_rapid_moves_do_not_render_each_slide(editor, qtbot, monkeypatch):
    calls = _spy(editor, monkeypatch)

    _move_down(editor, 20)  # 여러 슬라이드를 빠르게 가로지름

    assert calls == [], (
        f"이동 중 프리뷰를 {len(calls)}번 렌더 — 커서가 끊긴다"
    )


def test_render_happens_after_cursor_settles(editor, qtbot, monkeypatch):
    calls = _spy(editor, monkeypatch)

    _move_down(editor, 20)
    qtbot.wait(editor._PREVIEW_DEBOUNCE_MS + 250)

    expected = editor._slide_index_at_line(
        editor._text_edit.textCursor().blockNumber()
    )
    assert calls and calls[-1] == expected, "멈춘 위치의 슬라이드가 렌더돼야 한다"


def test_thumbnail_highlight_follows_immediately(editor, qtbot, monkeypatch):
    """프리뷰는 미뤄도 썸네일 선택 표시는 즉시 따라가야 한다."""
    _spy(editor, monkeypatch)

    _move_down(editor, 12)

    expected = editor._slide_index_at_line(
        editor._text_edit.textCursor().blockNumber()
    )
    assert editor._thumbs.currentRow() == expected
