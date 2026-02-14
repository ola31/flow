import pytest
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QWidget

from flow.domain.hotspot import Hotspot
from flow.ui.editor.hotspot_popover import HotspotPopover


class SignalSpy:
    def __init__(self, signal):
        self.called = False
        self.args = None
        signal.connect(self.callback)

    def callback(self, *args):
        self.called = True
        self.args = args


@pytest.fixture
def popover(qapp):
    parent = QWidget()
    parent.setFixedSize(800, 600)
    parent.show()
    p = HotspotPopover(parent)
    p._test_parent = parent
    return p


def _make_mapped_hotspot(slide_idx=3, verse_idx=0):
    h = Hotspot(x=100, y=200, lyric="Test")
    h.set_slide_index(slide_idx, verse_index=verse_idx)
    return h


class TestHotspotPopoverInitial:
    def test_starts_hidden(self, popover):
        assert not popover.isVisible()

    def test_has_slide_count_zero(self, popover):
        assert popover._slide_count == 0


class TestHotspotPopoverShow:
    def test_show_mapped_hotspot(self, popover):
        h = _make_mapped_hotspot()
        popover.show_for_hotspot(h, 0, QPoint(100, 100))
        assert popover.isVisible()
        assert popover._preview_row.isVisible()
        assert not popover._no_mapping_row.isVisible()

    def test_show_unmapped_hotspot(self, popover):
        h = Hotspot(x=100, y=200, lyric="Unmapped")
        popover.show_for_hotspot(h, 0, QPoint(100, 100))
        assert popover.isVisible()
        assert not popover._preview_row.isVisible()
        assert popover._no_mapping_row.isVisible()

    def test_info_label_verse(self, popover):
        h = _make_mapped_hotspot()
        popover.show_for_hotspot(h, 2, QPoint(100, 100))
        assert "3절" in popover._info.text()

    def test_info_label_chorus(self, popover):
        h = Hotspot(x=100, y=200, lyric="C")
        h.set_slide_index(0, verse_index=5)
        popover.show_for_hotspot(h, 5, QPoint(100, 100))
        assert "후렴" in popover._info.text()

    def test_mapping_label_shows_slide_number(self, popover):
        h = _make_mapped_hotspot(slide_idx=7)
        popover.show_for_hotspot(h, 0, QPoint(100, 100))
        assert "8" in popover._mapping_label.text()


class TestHotspotPopoverDismiss:
    def test_dismiss_hides(self, popover):
        h = _make_mapped_hotspot()
        popover.show_for_hotspot(h, 0, QPoint(100, 100))
        popover.dismiss()
        assert not popover.isVisible()

    def test_dismiss_emits_closed(self, popover):
        spy = SignalSpy(popover.closed)
        h = _make_mapped_hotspot()
        popover.show_for_hotspot(h, 0, QPoint(100, 100))
        popover.dismiss()
        assert spy.called


class TestHotspotPopoverSignals:
    def test_unmap_requested(self, popover):
        spy = SignalSpy(popover.unmap_requested)
        h = _make_mapped_hotspot()
        popover.show_for_hotspot(h, 0, QPoint(100, 100))
        popover._on_unmap()
        assert spy.called

    def test_unmap_dismisses(self, popover):
        h = _make_mapped_hotspot()
        popover.show_for_hotspot(h, 0, QPoint(100, 100))
        popover._on_unmap()
        assert not popover.isVisible()

    def test_set_slide_source(self, popover):
        popover.set_slide_source(10, lambda i: None)
        assert popover._slide_count == 10


class TestHotspotPopoverPosition:
    def test_position_within_parent(self, popover):
        h = _make_mapped_hotspot()
        popover.show_for_hotspot(h, 0, QPoint(400, 300))
        assert popover.x() >= 0
        assert popover.y() >= 0

    def test_position_clamp_right_edge(self, popover):
        h = _make_mapped_hotspot()
        popover.show_for_hotspot(h, 0, QPoint(790, 300))
        parent_w = popover.parentWidget().width()
        assert popover.x() + popover.sizeHint().width() <= parent_w
