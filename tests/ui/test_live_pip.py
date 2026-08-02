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

    def test_width_is_resizable_not_fixed(self, pip):
        from PySide6.QtWidgets import QSizePolicy
        assert pip.sizePolicy().horizontalPolicy() != QSizePolicy.Policy.Fixed
        assert pip.minimumWidth() == 220


class TestLivePIPDualContent:
    def test_set_preview_image_does_not_force_visible(self, pip):
        """PIP 표시 여부는 ProjectScreen.set_live_mode가 전담해야 하며,
        에디터(비라이브) 화면에서 핫스팟 선택만으로 나타나면 안 된다."""
        pip.set_preview_image(QPixmap(100, 100))
        assert not pip.isVisible()

    def test_set_preview_text(self, pip):
        pip.set_preview_text("Next")
        assert pip._preview_pane._text.text() == "Next"

    def test_set_live_image_does_not_force_visible(self, pip):
        pip.set_live_image(QPixmap(100, 100))
        assert not pip.isVisible()

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


class TestPipSharpness:
    """PIP 썸네일이 흐릿하던 문제 — 논리 크기로 스케일하면 배율 1.5인
    화면에서 실제 픽셀의 2/3만 그려 Qt가 다시 확대한다."""

    def _pane(self, qtbot):
        from flow.ui.screens.project_screen import LivePIP

        pip = LivePIP()
        qtbot.addWidget(pip)
        pip.resize(420, 600)
        pip.show()
        return pip

    def test_scaled_pixmap_carries_device_pixel_ratio(self, qtbot):
        from PySide6.QtGui import QColor, QImage, QPixmap

        pip = self._pane(qtbot)
        img = QImage(1920, 1080, QImage.Format.Format_RGB32)
        img.fill(QColor("#204060"))

        pip.set_preview_image(QPixmap.fromImage(img))

        shown = pip._preview_pane._image.pixmap()
        assert not shown.isNull()
        assert shown.devicePixelRatio() == pip._preview_pane.devicePixelRatioF()

    def test_source_size_hint_covers_the_pane(self, qtbot):
        pip = self._pane(qtbot)
        pane = pip._preview_pane

        w, h = pip.preview_source_size()

        ratio = pane.devicePixelRatioF() or 1.0
        assert w >= pane._image.width() * ratio
        assert w % 240 == 0  # 캐시 키 종류 제한
        assert h == int(w * 9 / 16)

    def test_source_size_hint_is_capped(self, qtbot):
        pip = self._pane(qtbot)
        pip.resize(4000, 3000)

        w, _h = pip.preview_source_size()

        assert w <= 1920


class TestPipPanesPackedTop:
    """PREVIEW와 LIVE는 위쪽에 붙어야 한다.

    두 판에 stretch를 주면 세로 공간을 반씩 나눠 가져 사이가 크게
    벌어진다 — 남는 공간은 아래로 몰아준다.
    """

    def _pip(self, qtbot, height=900):
        from flow.ui.screens.project_screen import LivePIP

        pip = LivePIP()
        qtbot.addWidget(pip)
        pip.resize(420, height)
        pip.show()
        qtbot.waitExposed(pip)
        return pip

    def test_panes_are_adjacent_not_spread(self, qtbot):
        pip = self._pip(qtbot)

        gap = (
            pip._live_pane.geometry().top()
            - pip._preview_pane.geometry().bottom()
        )

        # 구분선 + 여백 정도만 — 세로를 나눠 가지면 수백 px가 뜬다
        assert 0 < gap < 40, f"두 판 사이가 {gap}px 벌어짐"

    def test_panes_do_not_consume_all_height(self, qtbot):
        pip = self._pip(qtbot, height=900)

        used = pip._live_pane.geometry().bottom()

        assert used < 700, f"판이 세로를 {used}px까지 차지 — 위로 붙지 않음"

    def test_image_keeps_16_9(self, qtbot):
        pip = self._pip(qtbot)
        pane = pip._preview_pane

        expected = int(
            (pane.width()
             - pane.layout().contentsMargins().left()
             - pane.layout().contentsMargins().right()) * 9 / 16
        )

        assert abs(pane._image.height() - expected) <= 1
