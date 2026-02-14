import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtTest import QTest

from flow.ui.screens.project_screen import LivePIP


class SignalSpy:
    def __init__(self, signal):
        self.called = False
        self.args = None
        signal.connect(self.callback)

    def callback(self, *args):
        self.called = True
        self.args = args


@pytest.fixture
def pip(qapp):
    return LivePIP()


class TestLivePIPInitial:
    def test_starts_hidden(self, pip):
        assert not pip.isVisible()

    def test_has_preview_and_live_panes(self, pip):
        assert pip._preview_pane is not None
        assert pip._live_pane is not None

    def test_preview_badge_says_preview(self, pip):
        assert "PREVIEW" in pip._preview_pane._badge.text()

    def test_live_badge_says_live(self, pip):
        assert "LIVE" in pip._live_pane._badge.text()

    def test_fixed_width(self, pip):
        assert pip.width() == 280


class TestLivePIPDualContent:
    def test_set_preview_image_shows_widget(self, pip):
        pip.set_preview_image(QPixmap(100, 100))
        assert pip.isVisible()

    def test_set_preview_text(self, pip):
        pip.set_preview_text("Next")
        assert pip._preview_pane._text.text() == "Next"

    def test_set_live_image_shows_widget(self, pip):
        pip.set_live_image(QPixmap(100, 100))
        assert pip.isVisible()

    def test_set_live_text(self, pip):
        pip.set_live_text("Current")
        assert pip._live_pane._text.text() == "Current"

    def test_clear_hides_widget(self, pip):
        pip.set_preview_image(QPixmap(100, 100))
        pip.clear()
        assert not pip.isVisible()

    def test_clear_resets_both_panes(self, pip):
        pip.set_preview_text("A")
        pip.set_live_text("B")
        pip.clear()
        assert pip._preview_pane._text.text() == ""
        assert pip._live_pane._text.text() == ""

    def test_clear_preview_only(self, pip):
        pip.set_preview_text("A")
        pip.set_live_text("B")
        pip.clear_preview()
        assert pip._preview_pane._text.text() == ""
        assert pip._live_pane._text.text() == "B"

    def test_clear_live_only(self, pip):
        pip.set_preview_text("A")
        pip.set_live_text("B")
        pip.clear_live()
        assert pip._preview_pane._text.text() == "A"
        assert pip._live_pane._text.text() == ""


class TestLivePIPSignals:
    def test_clicked_signal(self, pip):
        spy = SignalSpy(pip.clicked)
        pip.show()
        QTest.mouseClick(pip, Qt.MouseButton.LeftButton)
        assert spy.called
