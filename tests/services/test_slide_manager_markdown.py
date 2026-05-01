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


def test_md_file_change_invalidates_markdown_cache(qapp, tmp_path: Path) -> None:
    """When the loaded .md file changes on disk, the cache for that file is
    invalidated so the next access re-renders fresh content."""
    md = tmp_path / "slides.md"
    md.write_text("# T\n\n가사 1\n", encoding="utf-8")

    sm = SlideManager()
    sm.load_pptx(md)

    # Wait for first load
    finished: list[int] = []
    sm.load_finished.connect(lambda count: finished.append(count))
    loop = QEventLoop()
    sm.load_finished.connect(loop.quit)
    QTimer.singleShot(5000, loop.quit)
    if not finished:
        loop.exec()

    # Cache should now hold one entry for this path
    key = md.resolve()
    assert key in sm._markdown_converter._cache

    # Start the file watcher so external edits trigger callback
    sm.start_watching()

    # Modify the file — watcher should detect and invalidate cache
    import time
    time.sleep(0.5)  # let watcher settle
    md.write_text("# T\n\n가사 1\n\n가사 2\n", encoding="utf-8")

    # Wait briefly for watcher event
    fired: list[bool] = []
    sm.file_changed.connect(lambda: fired.append(True))
    loop2 = QEventLoop()
    sm.file_changed.connect(loop2.quit)
    QTimer.singleShot(3000, loop2.quit)
    loop2.exec()

    assert fired, "file_changed didn't fire on .md modification"
    # Cache should be cleared by the watcher's callback
    assert key not in sm._markdown_converter._cache
