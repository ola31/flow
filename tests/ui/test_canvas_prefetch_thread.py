"""프리페치 스레드가 캔버스를 소유하면 안 된다.

스레드 클로저가 마지막 참조를 들면 Thread.run의 `del self._target`이
QWidget인 캔버스를 워커 스레드에서 파괴한다 — Qt에서 정의되지 않은
동작이고, 같은 계열의 프리워밍 스레드 문제가 실제 segfault를 냈다.
"""
from __future__ import annotations

import gc
import threading

import pytest
from PySide6.QtGui import QColor, QImage

from flow.ui.editor.score_canvas import ScoreCanvas


@pytest.fixture
def big_images(tmp_path) -> list[str]:
    """디코드가 오래 걸릴 만큼 큰 이미지 — 스레드가 도는 동안 참조가 끊긴다."""
    paths = []
    for i in range(6):
        p = tmp_path / f"big_{i}.png"
        img = QImage(1600, 1600, QImage.Format.Format_RGB32)
        img.fill(QColor("#334455"))
        img.save(str(p))
        paths.append(str(p))
    return paths


def test_canvas_is_not_destroyed_on_the_worker_thread(qtbot, big_images):
    destroyed_in: dict[str, str] = {}

    class _Tracked(ScoreCanvas):
        def __del__(self):
            destroyed_in["thread"] = threading.current_thread().name

    canvas = _Tracked()
    canvas.prefetch_images(big_images)
    del canvas  # 테스트 teardown처럼 참조를 즉시 버린다
    gc.collect()

    qtbot.waitUntil(lambda: "thread" in destroyed_in, timeout=8000)

    assert destroyed_in["thread"] == "MainThread", (
        f"캔버스가 {destroyed_in['thread']}에서 파괴됨 — "
        "QWidget을 GUI 스레드 밖에서 파괴하면 안 된다"
    )


def test_prefetch_still_caches(qtbot, big_images):
    canvas = ScoreCanvas()
    qtbot.addWidget(canvas)

    canvas.prefetch_images(big_images[:2])

    qtbot.waitUntil(
        lambda: canvas._cache_key(big_images[0]) in canvas._pixmap_cache,
        timeout=8000,
    )
