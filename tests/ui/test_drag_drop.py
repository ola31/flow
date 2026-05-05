import pytest

from flow.ui.editor.slide_preview_panel import _DraggableSlideList, SLIDE_MIME_TYPE
from flow.ui.editor.score_canvas import ScoreCanvas


class SignalSpy:
    def __init__(self, signal):
        self.called = False
        self.args = None
        signal.connect(self.callback)

    def callback(self, *args):
        self.called = True
        self.args = args


@pytest.fixture
def canvas(qapp):
    return ScoreCanvas()


@pytest.fixture
def drag_list(qapp):
    return _DraggableSlideList()


class TestDraggableSlideList:
    def test_creation(self, drag_list):
        assert drag_list is not None

    def test_is_list_widget(self, drag_list):
        from PySide6.QtWidgets import QListWidget

        assert isinstance(drag_list, QListWidget)

    def test_mime_type_constant(self):
        assert SLIDE_MIME_TYPE == "application/x-flow-slide-index"


class TestScoreCanvasDrop:
    def test_accepts_drops(self, canvas):
        assert canvas.acceptDrops()

    def test_has_drag_enter_event(self, canvas):
        assert hasattr(canvas, "dragEnterEvent")

    def test_has_drag_move_event(self, canvas):
        assert hasattr(canvas, "dragMoveEvent")

    def test_has_drop_event(self, canvas):
        assert hasattr(canvas, "dropEvent")

    def test_edit_mode_default_true(self, canvas):
        assert canvas._edit_mode is True

    def test_set_edit_mode_false(self, canvas):
        canvas.set_edit_mode(False)
        assert canvas._edit_mode is False

    def test_set_edit_mode_true(self, canvas):
        canvas.set_edit_mode(False)
        canvas.set_edit_mode(True)
        assert canvas._edit_mode is True


class TestScoreCanvasSignals:
    def test_slide_dropped_signal(self, canvas):
        spy = SignalSpy(canvas.slide_dropped_on_hotspot)
        assert not spy.called

    def test_popover_mapping_signal(self, canvas):
        spy = SignalSpy(canvas.popover_mapping_requested)
        assert not spy.called

    def test_live_hotspot_clicked_signal(self, canvas):
        spy = SignalSpy(canvas.live_hotspot_clicked)
        assert not spy.called

    def test_popover_unmap_signal(self, canvas):
        spy = SignalSpy(canvas.popover_unmap_requested)
        assert not spy.called
