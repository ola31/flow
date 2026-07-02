"""Web broadcast status screen — 웹 송출 켜기/끄기, URL, QR 코드, 접속자 수."""
from __future__ import annotations

import io

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from flow.ui.styles import (
    BG_DEEP,
    FONT_HEAD,
    FONT_MD,
    FONT_SM,
    FW_SEMI,
    SP_LG,
    SP_MD,
    SP_SM,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TEXT_TERTIARY,
)

_QR_SIZE = 200


class WebBroadcastScreen(QWidget):
    """웹 송출 상태 페이지 — 서버 켜기/끄기, 접속 URL/QR, 접속자 수 표시.

    Signals:
        toggle_requested(): 켜기/끄기 버튼 클릭
    """

    toggle_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._server = None

        self.setStyleSheet(f"background: {BG_DEEP};")
        root = QVBoxLayout(self)
        root.setContentsMargins(SP_LG * 2, SP_LG, SP_LG * 2, SP_LG)
        root.setSpacing(SP_MD)

        header = QLabel("웹 송출")
        header.setStyleSheet(
            f"color: {TEXT_PRIMARY}; font-size: {FONT_HEAD}px; "
            f"font-weight: {FW_SEMI};"
        )
        root.addWidget(header)

        desc = QLabel(
            "같은 네트워크의 브라우저(휴대폰 등)로 라이브 슬라이드를 송출합니다."
        )
        desc.setStyleSheet(f"color: {TEXT_TERTIARY}; font-size: {FONT_MD}px;")
        desc.setWordWrap(True)
        root.addWidget(desc)

        root.addSpacing(SP_LG)

        self._status_label = QLabel("서버가 꺼져 있습니다")
        self._status_label.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: {FONT_MD}px;"
        )
        root.addWidget(self._status_label)

        self._toggle_btn = QPushButton("웹 송출 켜기")
        self._toggle_btn.setProperty("variant", "primary")
        self._toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_btn.clicked.connect(self.toggle_requested.emit)
        root.addWidget(self._toggle_btn, 0, Qt.AlignmentFlag.AlignLeft)

        root.addSpacing(SP_LG)

        self._url_label = QLabel()
        self._url_label.setStyleSheet(
            f"color: {TEXT_PRIMARY}; font-size: {FONT_SM}px;"
        )
        self._url_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self._url_label.setWordWrap(True)
        root.addWidget(self._url_label)

        self._qr_label = QLabel()
        self._qr_label.setFixedSize(_QR_SIZE, _QR_SIZE)
        self._qr_label.setScaledContents(True)
        root.addWidget(self._qr_label, 0, Qt.AlignmentFlag.AlignLeft)

        root.addSpacing(SP_SM)

        self._clients_label = QLabel()
        self._clients_label.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: {FONT_SM}px;"
        )
        root.addWidget(self._clients_label)

        root.addStretch()

        self._url_label.hide()
        self._qr_label.hide()
        self._clients_label.hide()

    def set_server(self, server) -> None:
        """송출 서버 인스턴스를 등록하고 화면을 갱신."""
        if self._server is not None:
            try:
                self._server.client_count_changed.disconnect(self._on_client_count)
            except (TypeError, RuntimeError):
                pass
        self._server = server
        if self._server is not None:
            self._server.client_count_changed.connect(self._on_client_count)
        self.refresh()

    def refresh(self) -> None:
        """서버 상태에 맞춰 라벨/버튼/QR을 갱신."""
        if self._server is None or not self._server.is_running():
            self._status_label.setText("서버가 꺼져 있습니다")
            self._toggle_btn.setText("웹 송출 켜기")
            self._url_label.hide()
            self._qr_label.hide()
            self._clients_label.hide()
            return

        self._status_label.setText("송출 중")
        self._toggle_btn.setText("웹 송출 중지")

        urls = self._server.local_urls()
        self._url_label.setText("\n".join(urls))
        self._url_label.setVisible(bool(urls))

        if urls:
            self._qr_label.setPixmap(self._build_qr_pixmap(urls[0]))
            self._qr_label.show()
        else:
            self._qr_label.hide()

        self._clients_label.setText(f"접속: {self._server.client_count()}명")
        self._clients_label.show()

    def _build_qr_pixmap(self, url: str) -> QPixmap:
        import qrcode

        img = qrcode.make(url)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        pixmap = QPixmap()
        pixmap.loadFromData(buf.getvalue())
        return pixmap

    def _on_client_count(self, n: int) -> None:
        self._clients_label.setText(f"접속: {n}명")
