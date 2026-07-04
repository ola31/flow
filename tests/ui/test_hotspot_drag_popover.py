"""핫스팟 드래그 중 팝오버 표시 억제 테스트

press 즉시 팝오버가 뜨면 드래그로 위치를 옮길 때 화면을 가린다.
팝오버는 release 시점에, 실제로 드래그(이동)가 없었을 때만 떠야 한다.
"""
from __future__ import annotations

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QMouseEvent

from flow.domain.hotspot import Hotspot
from flow.domain.score_sheet import ScoreSheet
from flow.ui.editor.score_canvas import ScoreCanvas


def _mouse_event(event_type, x: float, y: float) -> QMouseEvent:
    return QMouseEvent(
        event_type,
        QPointF(x, y),
        QPointF(x, y),  # globalPos — deprecated 5-인자 오버로드 회피
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )


@pytest.fixture
def canvas(qtbot):
    c = ScoreCanvas()
    qtbot.addWidget(c)
    c.setFixedSize(800, 600)
    c.show()

    sheet = ScoreSheet(name="page_one")
    hotspot = Hotspot(x=100, y=100)
    hotspot.set_slide_index(1, verse_index=0)
    sheet.hotspots.append(hotspot)
    # 픽스맵 없이 좌표 항등 변환을 쓰도록 시트만 직접 주입
    c._score_sheet = sheet
    c._hotspot = hotspot
    return c


class TestPopoverDeferredToRelease:
    def test_press_alone_does_not_show_popover(self, canvas):
        canvas.mousePressEvent(
            _mouse_event(QMouseEvent.Type.MouseButtonPress, 100, 100)
        )

        assert not canvas._popover.isVisible()

    def test_clean_click_shows_popover_on_release(self, canvas):
        canvas.mousePressEvent(
            _mouse_event(QMouseEvent.Type.MouseButtonPress, 100, 100)
        )
        canvas.mouseReleaseEvent(
            _mouse_event(QMouseEvent.Type.MouseButtonRelease, 100, 100)
        )

        assert canvas._popover.isVisible()

    def test_drag_moves_hotspot_without_popover(self, canvas):
        sheet = canvas._score_sheet
        hotspot = sheet.hotspots[0]

        canvas.mousePressEvent(
            _mouse_event(QMouseEvent.Type.MouseButtonPress, 100, 100)
        )
        canvas.mouseMoveEvent(_mouse_event(QMouseEvent.Type.MouseMove, 160, 130))
        canvas.mouseReleaseEvent(
            _mouse_event(QMouseEvent.Type.MouseButtonRelease, 160, 130)
        )

        assert (hotspot.x, hotspot.y) == (160, 130)
        assert not canvas._popover.isVisible()

    def test_drag_emits_hotspot_moved(self, canvas):
        moved = []
        canvas.hotspot_moved.connect(lambda h, old, new: moved.append((old, new)))

        canvas.mousePressEvent(
            _mouse_event(QMouseEvent.Type.MouseButtonPress, 100, 100)
        )
        canvas.mouseMoveEvent(_mouse_event(QMouseEvent.Type.MouseMove, 160, 130))
        canvas.mouseReleaseEvent(
            _mouse_event(QMouseEvent.Type.MouseButtonRelease, 160, 130)
        )

        assert moved == [((100, 100), (160, 130))]
