from __future__ import annotations

from PySide6.QtCore import Qt

from flow.ui.display.display_window import DisplayWindow


def test_show_on_screen_windowed_clears_fullscreen_state(qtbot) -> None:
    window = DisplayWindow()
    qtbot.addWidget(window)

    window.showFullScreen()
    assert window.isFullScreen()

    window.show_on_screen(None, windowed=True)

    assert not window.isFullScreen()
    assert window.windowState() == Qt.WindowState.WindowNoState
    assert window.size().width() == 960
    assert window.size().height() == 540


def _screen(qtbot):
    from PySide6.QtWidgets import QApplication

    return QApplication.primaryScreen() or QApplication.screens()[0]


def test_fullscreen_creates_native_handle_before_assigning_screen(qtbot) -> None:
    """windowHandle()은 네이티브 창이 생긴 뒤에만 존재한다.

    예전에는 한 번도 띄운 적 없는 창에서 handle이 None이라 setScreen이
    통째로 건너뛰어졌고, 첫 송출이 대상 모니터를 벗어나 작은 창으로 떴다.
    """
    window = DisplayWindow()
    qtbot.addWidget(window)
    assert window.windowHandle() is None  # 아직 네이티브 창 없음

    window.show_on_screen(_screen(qtbot))

    assert window.windowHandle() is not None
    assert window.windowHandle().screen() is _screen(qtbot)


def test_fullscreen_matches_target_screen_geometry(qtbot) -> None:
    window = DisplayWindow()
    qtbot.addWidget(window)
    screen = _screen(qtbot)

    window.show_on_screen(screen)

    assert window.isFullScreen()
    assert window.geometry().topLeft() == screen.geometry().topLeft()


def test_fullscreen_is_frameless(qtbot) -> None:
    window = DisplayWindow()
    qtbot.addWidget(window)

    window.show_on_screen(_screen(qtbot))

    assert window.windowFlags() & Qt.WindowType.FramelessWindowHint


def test_windowed_mode_has_a_frame(qtbot) -> None:
    """작은 창은 제목표시줄이 있어야 옮기고 닫을 수 있다."""
    window = DisplayWindow()
    qtbot.addWidget(window)

    window.show_on_screen(_screen(qtbot), windowed=True)

    assert not (window.windowFlags() & Qt.WindowType.FramelessWindowHint)


def test_windowed_then_fullscreen_restores_frameless(qtbot) -> None:
    """윈도우 모드가 뗀 테두리 없음 플래그를 전체화면이 되돌린다."""
    window = DisplayWindow()
    qtbot.addWidget(window)

    window.show_on_screen(_screen(qtbot), windowed=True)
    window.show_on_screen(_screen(qtbot))

    assert window.isFullScreen()
    assert window.windowFlags() & Qt.WindowType.FramelessWindowHint


def test_none_screen_falls_back_to_primary(qtbot) -> None:
    window = DisplayWindow()
    qtbot.addWidget(window)

    window.show_on_screen(None)

    assert window.isFullScreen()
    assert window.windowHandle() is not None


def test_screen_is_attached_before_going_fullscreen(qtbot, monkeypatch) -> None:
    """showFullScreen은 창이 놓인 모니터를 기준으로 펼쳐진다.

    따라서 그 시점에 이미 대상 모니터가 지정돼 있어야 한다. 예전 코드는
    네이티브 창이 없어 windowHandle()이 None이었고 setScreen을 통째로
    건너뛴 채 showFullScreen을 불렀다 — 외부 모니터를 골라도 엉뚱한
    화면에서 펼쳐지거나 작은 창으로 뜨던 원인.
    """
    window = DisplayWindow()
    qtbot.addWidget(window)
    target = _screen(qtbot)
    seen: dict = {}

    original = DisplayWindow.showFullScreen

    def spy(self) -> None:
        handle = self.windowHandle()
        seen["handle"] = handle
        seen["screen"] = handle.screen() if handle is not None else None
        original(self)

    monkeypatch.setattr(DisplayWindow, "showFullScreen", spy)

    window.show_on_screen(target)

    assert seen["handle"] is not None, "전체화면 전에 네이티브 창이 있어야 함"
    assert seen["screen"] is target, "전체화면 전에 대상 모니터가 지정돼야 함"


def test_window_is_realized_before_being_moved(qtbot, monkeypatch) -> None:
    """숨겨진 창은 옮길 수 없다 (Windows).

    setGeometry/setScreen은 네이티브 창이 아직 어느 모니터에도 매핑되지
    않았으면 무시된다. 그래서 showNormal로 먼저 띄운 뒤 옮겨야 하고,
    그 순서를 지키지 않으면 첫 송출이 주 모니터에 뜬다 — 껐다 켜야
    외부 모니터로 가던 증상.
    """
    window = DisplayWindow()
    qtbot.addWidget(window)
    order: list[str] = []

    orig_normal = DisplayWindow.showNormal
    orig_attach = DisplayWindow._attach_to_screen
    orig_full = DisplayWindow.showFullScreen

    def normal(self):
        order.append("showNormal")
        return orig_normal(self)

    def attach(self, screen):
        order.append("move")
        return orig_attach(self, screen)

    def full(self):
        order.append("showFullScreen")
        return orig_full(self)

    monkeypatch.setattr(DisplayWindow, "showNormal", normal)
    monkeypatch.setattr(DisplayWindow, "_attach_to_screen", attach)
    monkeypatch.setattr(DisplayWindow, "showFullScreen", full)

    window.show_on_screen(_screen(qtbot))

    assert order == ["showNormal", "move", "showFullScreen"]


def test_attach_sets_geometry_to_the_target_screen(qtbot) -> None:
    window = DisplayWindow()
    qtbot.addWidget(window)
    screen = _screen(qtbot)
    window.showNormal()

    window._attach_to_screen(screen)

    assert window.geometry() == screen.geometry()
