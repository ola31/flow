"""동시 송출(모니터+웹) 테스트

F11 픽커의 "웹 송출도 함께 시작" 체크박스로 모니터와 웹을 동시에 켜고,
F11 재누름은 둘 다 끈다. 프레임 배분은 기존대로 양쪽 독립.
"""
from __future__ import annotations

from flow.ui.dialogs import DisplayTarget


class TestDisplayTarget:
    def test_with_web_defaults_false(self):
        t = DisplayTarget(mode="screen")
        assert t.with_web is False

    def test_web_mode_target_never_sets_with_web(self):
        t = DisplayTarget(mode="web")
        assert t.with_web is False


class TestConfigWithWeb:
    def test_roundtrip_and_default(self, tmp_path):
        from flow.services.config_service import ConfigService

        svc = ConfigService()
        # 실제 홈 설정에 오염되지 않게 격리 (기존 config 테스트 픽스처 패턴)
        svc._config_dir = tmp_path / ".flow"
        svc._config_file = svc._config_dir / "config.json"
        svc._config = {}

        assert svc.get_display_with_web() is False  # 기본 꺼짐
        svc.set_display_with_web(True)
        assert svc.get_display_with_web() is True


class _FakeSignal:
    def connect(self, *a, **k):
        pass

    def disconnect(self, *a, **k):
        pass


class _FakeWebServer:
    client_count_changed = _FakeSignal()

    def __init__(self):
        self.running = False
        self.start_calls = 0

    def start(self):
        self.start_calls += 1
        self.running = True
        return "http://10.0.0.1:8777"

    def stop(self):
        self.running = False

    def is_running(self):
        return self.running

    def local_urls(self):
        return ["http://10.0.0.1:8777"] if self.running else []

    def http_port(self):
        return 8777 if self.running else None

    def ws_port(self):
        return 8778 if self.running else None

    def client_count(self):
        return 0


class _FakeDisplay:
    class _Sig:
        def connect(self, *a, **k):
            pass

    def __init__(self):
        self.visible = False
        self.closed = self._Sig()

    def show_on_screen(self, screen, windowed=False):
        self.visible = True

    def isVisible(self):
        return self.visible

    def close(self):
        self.visible = False

    def show_lyric(self, lyric):
        pass

    def show_image(self, image):
        pass


def _make_mw(qtbot, monkeypatch, target):
    from flow.ui.main_window import MainWindow

    mw = MainWindow()
    qtbot.addWidget(mw)
    monkeypatch.setattr(mw, "_pick_display_screen", lambda: target)
    mw._display_window = _FakeDisplay()
    mw._web_broadcast = _FakeWebServer()
    return mw


class TestSimultaneousToggle:
    def _target(self, with_web):
        return DisplayTarget(
            mode="screen", screen=None, windowed=True, with_web=with_web
        )

    def test_start_opens_display_and_web(self, qtbot, monkeypatch):
        mw = _make_mw(qtbot, monkeypatch, self._target(True))
        try:
            mw._toggle_display()
            assert mw._display_window.isVisible()
            assert mw._web_broadcast.is_running()
        finally:
            mw._slide_manager.shutdown()
            mw._clear_dirty()
            mw.close()

    def test_second_f11_stops_both(self, qtbot, monkeypatch):
        mw = _make_mw(qtbot, monkeypatch, self._target(True))
        try:
            mw._toggle_display()
            mw._toggle_display()
            assert not mw._display_window.isVisible()
            assert not mw._web_broadcast.is_running()
        finally:
            mw._slide_manager.shutdown()
            mw._clear_dirty()
            mw.close()

    def test_f11_with_web_only_running_stops_all(self, qtbot, monkeypatch):
        """합의된 의미: 무엇이든 켜져 있으면 F11 = 전체 중지.

        웹만 켜진 상태(웹 송출 화면에서 켰든 F11 웹 모드로 켰든)에서
        F11을 누르면 픽커를 띄우지 않고 웹을 끈다. 동시 송출은 꺼진
        상태에서 F11 픽커의 체크박스로 시작한다.
        """
        mw = _make_mw(qtbot, monkeypatch, self._target(True))
        try:
            mw._web_broadcast.start()
            mw._toggle_display()
            assert not mw._web_broadcast.is_running()
            assert not mw._display_window.isVisible()
        finally:
            mw._slide_manager.shutdown()
            mw._clear_dirty()
            mw.close()

    def test_helper_does_not_double_start(self, qtbot, monkeypatch):
        """_start_web_broadcast_if_needed는 이미 실행 중이면 start() 재호출 없음."""
        mw = _make_mw(qtbot, monkeypatch, self._target(True))
        try:
            mw._web_broadcast.start()
            mw._start_web_broadcast_if_needed()
            assert mw._web_broadcast.start_calls == 1
        finally:
            mw._slide_manager.shutdown()
            mw._clear_dirty()
            mw.close()

    def test_without_web_checkbox_only_display(self, qtbot, monkeypatch):
        mw = _make_mw(qtbot, monkeypatch, self._target(False))
        try:
            mw._toggle_display()
            assert mw._display_window.isVisible()
            assert not mw._web_broadcast.is_running()
        finally:
            mw._slide_manager.shutdown()
            mw._clear_dirty()
            mw.close()


class TestWebStatusLabel:
    """웹 송출 중 상태바 우측에 URL·접속 수 상시 표시 (라이브 중에도 보임)."""

    def test_visible_with_url_while_running(self, qtbot, monkeypatch):
        mw = _make_mw(
            qtbot, monkeypatch,
            DisplayTarget(mode="screen", screen=None, windowed=True, with_web=True),
        )
        try:
            mw._toggle_display()
            assert not mw._web_status_label.isHidden()
            assert "8777" in mw._web_status_label.text()
        finally:
            mw._slide_manager.shutdown()
            mw._clear_dirty()
            mw.close()

    def test_hidden_after_stop(self, qtbot, monkeypatch):
        mw = _make_mw(
            qtbot, monkeypatch,
            DisplayTarget(mode="screen", screen=None, windowed=True, with_web=True),
        )
        try:
            mw._toggle_display()
            mw._toggle_display()  # 전체 중지
            assert mw._web_status_label.isHidden()
        finally:
            mw._slide_manager.shutdown()
            mw._clear_dirty()
            mw.close()

    def test_shows_client_count(self, qtbot, monkeypatch):
        mw = _make_mw(
            qtbot, monkeypatch,
            DisplayTarget(mode="screen", screen=None, windowed=True, with_web=True),
        )
        try:
            mw._toggle_display()
            mw._on_web_client_count(3)
            assert "3" in mw._web_status_label.text()
        finally:
            mw._slide_manager.shutdown()
            mw._clear_dirty()
            mw.close()


class TestQrButton:
    """상태바 QR 버튼 — 웹 송출 중에만 표시, 클릭 시 QR 팝업."""

    def test_build_qr_pixmap_returns_image(self, qapp):
        from flow.ui.qr import build_qr_pixmap

        pm = build_qr_pixmap("http://10.0.0.1:8777")
        assert pm is not None and not pm.isNull()

    def test_button_visibility_follows_web_state(self, qtbot, monkeypatch):
        mw = _make_mw(
            qtbot, monkeypatch,
            DisplayTarget(mode="screen", screen=None, windowed=True, with_web=True),
        )
        try:
            assert mw._web_qr_button.isHidden()
            mw._toggle_display()
            assert not mw._web_qr_button.isHidden()
            mw._toggle_display()  # 전체 중지
            assert mw._web_qr_button.isHidden()
        finally:
            mw._slide_manager.shutdown()
            mw._clear_dirty()
            mw.close()

    def test_click_opens_qr_popup_with_url(self, qtbot, monkeypatch):
        mw = _make_mw(
            qtbot, monkeypatch,
            DisplayTarget(mode="screen", screen=None, windowed=True, with_web=True),
        )
        try:
            mw._toggle_display()
            shown = []
            monkeypatch.setattr(
                "flow.ui.dialogs.flow_show_qr",
                lambda parent, url, **k: shown.append(url),
            )
            mw._web_qr_button.click()
            assert shown == ["http://10.0.0.1:8777"]
        finally:
            mw._slide_manager.shutdown()
            mw._clear_dirty()
            mw.close()


class TestErrorPopupDedupe:
    """같은 PPT 오류 팝업의 연속 표시 억제 — 팝업 폭풍으로 앱이 죽는 것 방지."""

    def test_repeated_same_error_shows_one_popup(self, qtbot, monkeypatch):
        from PySide6.QtWidgets import QMessageBox

        mw = _make_mw(
            qtbot, monkeypatch,
            DisplayTarget(mode="screen", screen=None, windowed=True, with_web=False),
        )
        try:
            popups = []
            monkeypatch.setattr(
                QMessageBox, "warning",
                staticmethod(lambda *a, **k: popups.append(a[2] if len(a) > 2 else "")),
            )
            mw._on_ppt_load_error("PPTX 로드 중 오류 발생: X")
            mw._on_ppt_load_error("PPTX 로드 중 오류 발생: X")
            mw._on_ppt_load_error("PPTX 로드 중 오류 발생: X")
            assert len(popups) == 1
        finally:
            mw._slide_manager.shutdown()
            mw._clear_dirty()
            mw.close()
