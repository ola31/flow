"""시작 로고 창.

Qt의 QSplashScreen은 쓰지 않는다 — 이 Qt 버전에서 show() 한 번이 내용·
플랫폼과 무관하게 ~1.0초 블로킹한다(offscreen/minimal/xcb/wayland 모두에서
재현). 같은 그림을 띄우는 프레임리스 위젯은 10ms 미만이라, 로고 하나를
띄우려고 시작 시간의 큰 몫을 낼 이유가 없다.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from flow.ui.styles import BG_DEEP, TEXT_SECONDARY


class Splash(QWidget):
    """로고 + 한 줄 메시지를 띄우는 프레임리스 창."""

    def __init__(self, pixmap: QPixmap, message: str = "") -> None:
        super().__init__(
            None,
            Qt.WindowType.SplashScreen
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        # 메시지 줄이 이미지 아래에 붙으므로, 그 띠가 시스템 기본색(밝은
        # 회색)으로 뜨지 않게 앱 배경색으로 맞춘다.
        self.setStyleSheet(f"background: {BG_DEEP};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._image = QLabel(self)
        self._image.setPixmap(pixmap)
        self._image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._image)

        self._message = QLabel(message, self)
        self._message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._message.setStyleSheet(f"color: {TEXT_SECONDARY}; padding: 6px;")
        self._message.setVisible(bool(message))
        layout.addWidget(self._message)

        self.resize(layout.sizeHint())

    def show_message(self, message: str) -> None:
        self._message.setText(message)
        self._message.setVisible(bool(message))

    def center_on(self, screen) -> None:
        """주어진 화면 중앙에 놓는다 (QSplashScreen이 해주던 일)."""
        if screen is None:
            return
        frame = self.frameGeometry()
        frame.moveCenter(screen.availableGeometry().center())
        self.move(frame.topLeft())

    def finish(self, _window=None) -> None:
        """메인 창이 뜨면 닫는다 (QSplashScreen.finish과 같은 자리)."""
        self.close()
