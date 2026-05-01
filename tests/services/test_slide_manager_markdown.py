from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEventLoop, QTimer

from flow.services.slide_manager import SlideManager


def test_load_pptx_with_md_path_uses_markdown_converter(qapp, tmp_path: Path) -> None:
    md = tmp_path / "slides.md"
    md.write_text("# T\n\n가사 1\n\n가사 2\n", encoding="utf-8")

    sm = SlideManager()

    finished: list[int] = []
    sm.load_finished.connect(lambda count: finished.append(count))

    sm.load_pptx(md)

    # Wait for worker to finish via Qt event loop (signals are queued cross-thread)
    loop = QEventLoop()
    sm.load_finished.connect(loop.quit)
    QTimer.singleShot(5000, loop.quit)
    if not finished:
        loop.exec()

    assert finished, "load_finished signal never fired"
    assert finished[0] == 2
