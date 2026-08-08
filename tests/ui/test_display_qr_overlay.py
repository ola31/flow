"""송출 화면 QR 오버레이 — 우측 상단 배치, 슬라이드 비침범, 팝업 연동."""
from __future__ import annotations

from PySide6.QtGui import QPixmap

from flow.ui.display.display_window import DisplayWindow


def _qr() -> QPixmap:
    pixmap = QPixmap(370, 370)
    pixmap.fill()
    return pixmap


def _sized_window(qtbot, w: int = 1920, h: int = 1080) -> DisplayWindow:
    window = DisplayWindow()
    qtbot.addWidget(window)
    window.resize(w, h)
    return window


class TestQrOverlayPlacement:
    def test_sits_in_the_top_right_corner(self, qtbot) -> None:
        window = _sized_window(qtbot)

        window.show_qr(_qr())

        box = window._qr_frame.geometry()
        assert box.top() < window.height() / 2, "위쪽 절반에 있어야 한다"
        assert box.left() > window.width() / 2, "오른쪽 절반에 있어야 한다"
        # 가장자리에 딱 붙지 않고 여백을 둔다.
        assert 0 < box.top()
        assert box.right() < window.width()

    def test_scales_with_the_output_resolution(self, qtbot) -> None:
        small = _sized_window(qtbot, 1280, 720)
        large = _sized_window(qtbot, 3840, 2160)

        small.show_qr(_qr())
        large.show_qr(_qr())

        assert large._qr_frame.width() > small._qr_frame.width()

    def test_follows_the_window_when_it_is_resized(self, qtbot) -> None:
        """창만 커지고 오버레이가 옛 좌표에 남으면 화면 한복판에 떠 버린다."""
        window = _sized_window(qtbot, 1280, 720)
        # 숨어 있는 창은 resize()가 resizeEvent를 미뤄 두므로 실제로 띄운다.
        window.show()
        qtbot.waitExposed(window)
        window.show_qr(_qr())
        small_box = window._qr_frame.geometry()
        small_gap = window.width() - small_box.right()

        window.resize(1920, 1080)

        box = window._qr_frame.geometry()
        gap = window.width() - box.right()
        # 옛 자리에 남으면 오른쪽 여백이 640px 넘게 벌어진다.
        assert gap < window.width() * 0.05
        assert gap >= small_gap, "커진 화면에서 여백이 줄어들 이유는 없다"
        assert box.width() > small_box.width(), "크기도 함께 커져야 한다"

    def test_does_not_shrink_the_slide_area(self, qtbot) -> None:
        """레이아웃에 넣으면 슬라이드가 밀려 가로세로비가 틀어진다."""
        window = _sized_window(qtbot)
        window.show()
        qtbot.waitExposed(window)
        before = window._lyric_label.size()

        window.show_qr(_qr())

        assert window._lyric_label.size() == before


class TestQrOverlayToggle:
    def test_hidden_until_asked_for(self, qtbot) -> None:
        window = _sized_window(qtbot)

        assert not window.is_qr_visible()

    def test_show_then_hide(self, qtbot) -> None:
        window = _sized_window(qtbot)
        window.show()
        qtbot.waitExposed(window)

        window.show_qr(_qr())
        assert window.is_qr_visible()

        window.hide_qr()
        assert not window.is_qr_visible()

    def test_hide_before_any_show_is_harmless(self, qtbot) -> None:
        window = _sized_window(qtbot)

        window.hide_qr()  # 오버레이가 아직 만들어지지도 않은 상태

        assert not window.is_qr_visible()

    def test_missing_pixmap_shows_nothing(self, qtbot) -> None:
        """qrcode 미설치 등으로 build_qr_pixmap이 None을 준 경우."""
        window = _sized_window(qtbot)
        window.show()
        qtbot.waitExposed(window)
        window.show_qr(_qr())

        window.show_qr(None)

        assert not window.is_qr_visible()


class TestQrDialogWiring:
    def test_button_toggles_and_close_always_turns_it_off(self, qtbot) -> None:
        """팝업을 닫으면 켜져 있었더라도 반드시 내려간다."""
        from flow.ui import dialogs

        calls: list[bool] = []

        # 팝업이 뜨자마자 '송출 화면에 표시'를 누른 뒤 닫는 시나리오.
        def exec_and_click(self) -> int:
            from PySide6.QtWidgets import QPushButton

            for btn in self.findChildren(QPushButton):
                if btn.isCheckable():
                    btn.setChecked(True)
            return 0

        original = dialogs._FlowDialog.exec
        dialogs._FlowDialog.exec = exec_and_click
        try:
            dialogs.flow_show_qr(
                None, "http://192.168.0.2:8000", on_live_toggle=calls.append
            )
        finally:
            dialogs._FlowDialog.exec = original

        assert calls, "토글 버튼이 눌리면 콜백이 와야 한다"
        assert calls[0] is True
        assert calls[-1] is False, "닫을 때 반드시 꺼야 한다"

    def test_no_toggle_button_when_caller_offers_none(self, qtbot) -> None:
        from PySide6.QtWidgets import QPushButton

        from flow.ui import dialogs

        seen: list[list[str]] = []

        def capture(self) -> int:
            seen.append(
                [b.text() for b in self.findChildren(QPushButton) if b.isCheckable()]
            )
            return 0

        original = dialogs._FlowDialog.exec
        dialogs._FlowDialog.exec = capture
        try:
            dialogs.flow_show_qr(None, "http://192.168.0.2:8000")
        finally:
            dialogs._FlowDialog.exec = original

        assert seen == [[]], "송출창이 없으면 겹쳐 표시 버튼도 없어야 한다"
