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
    orig_attach = DisplayWindow._fill_screen
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
    monkeypatch.setattr(DisplayWindow, "_fill_screen", attach)
    monkeypatch.setattr(DisplayWindow, "showFullScreen", full)

    window.show_on_screen(_screen(qtbot))

    assert order == ["showNormal", "move", "showFullScreen"]


def test_attach_sets_geometry_to_the_target_screen(qtbot) -> None:
    window = DisplayWindow()
    qtbot.addWidget(window)
    screen = _screen(qtbot)
    window.showNormal()

    window._fill_screen(screen)

    assert window.geometry() == screen.geometry()


def test_windowed_never_covers_the_screen(qtbot) -> None:
    """윈도우 모드는 화면 전체 크기를 한 순간도 거치면 안 된다.

    전체화면 경로용 헬퍼를 윈도우 경로에서도 부르는 바람에 창이 먼저
    모니터를 덮었다. macOS에서는 그 상태가 별도 Space로 넘어가는 것처럼
    보여, 작은 창을 골랐는데 새 데스크탑에 전체화면으로 떴다.
    """
    window = DisplayWindow()
    qtbot.addWidget(window)
    screen = _screen(qtbot)
    seen: list[tuple[int, int]] = []

    orig_resize = DisplayWindow.resize
    orig_setgeom = DisplayWindow.setGeometry

    def resize(self, *a):
        r = orig_resize(self, *a)
        seen.append((self.width(), self.height()))
        return r

    def set_geometry(self, *a):
        r = orig_setgeom(self, *a)
        seen.append((self.width(), self.height()))
        return r

    DisplayWindow.resize, DisplayWindow.setGeometry = resize, set_geometry
    try:
        window.show_on_screen(screen, windowed=True)
    finally:
        DisplayWindow.resize, DisplayWindow.setGeometry = orig_resize, orig_setgeom

    full = (screen.geometry().width(), screen.geometry().height())
    assert full not in seen, f"윈도우 모드인데 화면 전체 크기를 거쳤다: {seen}"
    assert window.size().width() == 960


def test_windowed_leaves_fullscreen_first(qtbot) -> None:
    """전체화면 송출 중 윈도우 모드로 바꾸면 전체화면에서 빠져나와야 한다."""
    window = DisplayWindow()
    qtbot.addWidget(window)
    screen = _screen(qtbot)
    window.show_on_screen(screen)
    assert window.isFullScreen()

    window.show_on_screen(screen, windowed=True)

    assert not window.isFullScreen()
    assert window.size().width() == 960


def test_settle_is_a_noop_when_already_correct(qtbot) -> None:
    """이미 대상 모니터에 전체화면이면 다시 잡지 않는다 (재진입 애니메이션 방지)."""
    window = DisplayWindow()
    qtbot.addWidget(window)
    screen = _screen(qtbot)
    window.show_on_screen(screen)
    assert window.isFullScreen()

    calls = []
    orig = DisplayWindow.showNormal
    DisplayWindow.showNormal = lambda self: calls.append(1) or orig(self)
    try:
        window._settle_on_screen(screen)
    finally:
        DisplayWindow.showNormal = orig

    assert calls == []
    assert window.isFullScreen()


def test_settle_reapplies_when_not_fullscreen(qtbot) -> None:
    """이동이 늦게 반영돼 전체화면이 풀린 상태면 다시 잡는다."""
    window = DisplayWindow()
    qtbot.addWidget(window)
    screen = _screen(qtbot)
    window.show_on_screen(screen)
    window.showNormal()  # macOS에서 배치가 어긋난 상황을 흉내
    assert not window.isFullScreen()

    window._settle_on_screen(screen)

    assert window.isFullScreen()
    assert window.geometry().topLeft() == screen.geometry().topLeft()


def test_settle_ignores_a_hidden_window(qtbot) -> None:
    window = DisplayWindow()
    qtbot.addWidget(window)

    window._settle_on_screen(_screen(qtbot))  # 띄운 적 없음

    assert not window.isVisible()


def _slide(w=1920, h=1080):
    from PySide6.QtGui import QColor, QImage

    img = QImage(w, h, QImage.Format.Format_RGB32)
    img.fill(QColor("#204060"))
    return img


def test_slide_never_exceeds_the_label(qtbot) -> None:
    """픽스맵이 라벨보다 크면 QLabel이 축소 없이 잘라낸다 —
    송출 화면에서 슬라이드 가장자리가 잘려 보이던 원인."""
    window = DisplayWindow()
    qtbot.addWidget(window)
    window.resize(1000, 700)
    window.show()
    qtbot.waitExposed(window)

    window.show_image(_slide())

    pm = window._lyric_label.pixmap()
    ratio = pm.devicePixelRatio() or 1.0
    logical_w = pm.width() / ratio
    logical_h = pm.height() / ratio
    assert logical_w <= window._lyric_label.width() + 1
    assert logical_h <= window._lyric_label.height() + 1


def test_slide_keeps_aspect_ratio(qtbot) -> None:
    """16:9 슬라이드를 4:3 화면에 넣으면 잘리지 않고 여백이 남아야 한다."""
    window = DisplayWindow()
    qtbot.addWidget(window)
    window.resize(800, 600)  # 4:3
    window.show()
    qtbot.waitExposed(window)

    window.show_image(_slide(1920, 1080))

    pm = window._lyric_label.pixmap()
    assert abs(pm.width() / pm.height() - 16 / 9) < 0.02


def test_resize_rescales_the_slide(qtbot) -> None:
    window = DisplayWindow()
    qtbot.addWidget(window)
    window.resize(400, 300)
    window.show()
    qtbot.waitExposed(window)
    window.show_image(_slide())
    small = window._lyric_label.pixmap().width()

    window.resize(1200, 900)
    qtbot.waitUntil(
        lambda: window._lyric_label.pixmap().width() != small, timeout=2000
    )

    pm = window._lyric_label.pixmap()
    ratio = pm.devicePixelRatio() or 1.0
    assert pm.width() / ratio <= window._lyric_label.width() + 1


def test_label_growth_alone_rescales_the_slide(qtbot) -> None:
    """라벨만 커지는 경우에도 다시 맞춰야 한다.

    전체화면 진입 때 창은 즉시 커져 resizeEvent가 한 번 뜨지만, 그 시점의
    라벨은 아직 옛 크기다. 이후 레이아웃이 라벨을 키울 때 창에는 아무
    신호도 오지 않으므로, 창 resizeEvent만 보면 큰(혹은 작은) 픽스맵이
    그대로 남아 가장자리가 잘린다.
    """
    window = DisplayWindow()
    qtbot.addWidget(window)
    window.resize(400, 300)
    window.show()
    qtbot.waitExposed(window)
    window.show_image(_slide())
    before = window._lyric_label.pixmap().width()

    # 창은 그대로 두고 라벨만 키운다 (레이아웃이 뒤늦게 반영되는 상황)
    window._lyric_label.resize(1200, 900)

    after = window._lyric_label.pixmap().width()
    assert after != before, "라벨이 커졌는데 픽스맵이 그대로 — 잘리거나 여백이 남는다"
    ratio = window._lyric_label.pixmap().devicePixelRatio() or 1.0
    assert window._lyric_label.pixmap().width() / ratio <= 1200 + 1
