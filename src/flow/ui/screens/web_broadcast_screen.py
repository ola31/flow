"""Web broadcast status screen — 웹 송출 켜기/끄기, URL, QR 코드, 접속자 수."""
from __future__ import annotations

import io

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from flow.ui.styles import (
    BG_DEEP,
    BORDER_SUBTLE_RGBA,
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
        hotspot_toggle_requested(): 핫스팟 켜기/끄기 버튼 클릭
        captive_install_requested(): 폰 튕김 방지 설정 버튼 클릭
    """

    toggle_requested = Signal()
    hotspot_toggle_requested = Signal()
    captive_install_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._server = None
        self._hotspot = None

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

        root.addSpacing(SP_LG)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet(f"background: {BORDER_SUBTLE_RGBA}; max-height: 1px;")
        root.addWidget(separator)

        root.addSpacing(SP_LG)

        hotspot_header = QLabel("핫스팟")
        hotspot_header.setStyleSheet(
            f"color: {TEXT_PRIMARY}; font-size: {FONT_HEAD}px; "
            f"font-weight: {FW_SEMI};"
        )
        root.addWidget(hotspot_header)

        hotspot_desc = QLabel(
            "네트워크가 없을 때, 이 노트북을 Wi-Fi 핫스팟으로 만들어 폰이 "
            "접속하게 합니다."
        )
        hotspot_desc.setStyleSheet(f"color: {TEXT_TERTIARY}; font-size: {FONT_MD}px;")
        hotspot_desc.setWordWrap(True)
        root.addWidget(hotspot_desc)

        root.addSpacing(SP_MD)

        self._hotspot_toggle_btn = QPushButton("핫스팟 켜기")
        self._hotspot_toggle_btn.setProperty("variant", "primary")
        self._hotspot_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hotspot_toggle_btn.clicked.connect(
            self.hotspot_toggle_requested.emit
        )
        root.addWidget(
            self._hotspot_toggle_btn, 0, Qt.AlignmentFlag.AlignLeft
        )

        root.addSpacing(SP_SM)

        self._hotspot_info_label = QLabel("")
        self._hotspot_info_label.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: {FONT_MD}px;"
        )
        self._hotspot_info_label.setWordWrap(True)
        self._hotspot_info_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        root.addWidget(self._hotspot_info_label)

        self._captive_status_label = QLabel("")
        self._captive_status_label.setStyleSheet(
            f"color: {TEXT_TERTIARY}; font-size: {FONT_SM}px;"
        )
        root.addWidget(self._captive_status_label)

        self._captive_btn = QPushButton("폰 튕김 방지 설정하기")
        self._captive_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._captive_btn.clicked.connect(self.captive_install_requested.emit)
        root.addWidget(self._captive_btn, 0, Qt.AlignmentFlag.AlignLeft)

        self._hotspot_ssid = ""
        self._hotspot_password = ""

        root.addStretch()

        self._url_label.hide()
        self._qr_label.hide()
        self._clients_label.hide()

        self.refresh_hotspot()

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

    def set_hotspot(self, manager) -> None:
        """핫스팟 매니저를 등록하고 화면을 갱신."""
        if self._hotspot is not None:
            try:
                self._hotspot.state_changed.disconnect(self.refresh_hotspot)
            except (TypeError, RuntimeError):
                pass
        self._hotspot = manager
        if self._hotspot is not None:
            try:
                self._hotspot.state_changed.connect(self.refresh_hotspot)
            except (TypeError, RuntimeError):
                pass
        self.refresh_hotspot()

    def set_hotspot_credentials(self, ssid: str, password: str) -> None:
        """핫스팟 SSID/비밀번호를 저장하고 표시를 갱신."""
        self._hotspot_ssid = ssid
        self._hotspot_password = password
        self.refresh_hotspot()

    def refresh_hotspot(self) -> None:
        """핫스팟 상태에 맞춰 라벨/버튼을 갱신."""
        if self._hotspot is None:
            self._hotspot_toggle_btn.setVisible(False)
            self._hotspot_info_label.setVisible(False)
            self._captive_status_label.setVisible(False)
            self._captive_btn.setVisible(False)
            return

        supported = self._hotspot.is_supported()
        if not supported:
            self._hotspot_toggle_btn.setVisible(False)
            self._captive_status_label.setVisible(False)
            self._captive_btn.setVisible(False)
            self._hotspot_info_label.setText(self._hotspot.support_message())
            self._hotspot_info_label.setVisible(True)
            return

        self._hotspot_toggle_btn.setVisible(True)
        active = self._hotspot.is_active()
        self._hotspot_toggle_btn.setText("핫스팟 끄기" if active else "핫스팟 켜기")

        if active:
            self._hotspot_info_label.setText(
                f"SSID: {self._hotspot_ssid}\n비밀번호: {self._hotspot_password}"
            )
            self._hotspot_info_label.setVisible(True)
        else:
            self._hotspot_info_label.setVisible(False)

        if active:
            installed = self._hotspot.captive_portal_installed()
            if installed:
                self._captive_btn.setVisible(False)
                self._captive_status_label.setText("폰 튕김 방지 켜짐")
                self._captive_status_label.setVisible(True)
            else:
                self._captive_btn.setVisible(True)
                self._captive_status_label.setText(
                    "폰이 자동으로 끊길 수 있습니다. 폰 튕김 방지를 설정하세요."
                )
                self._captive_status_label.setVisible(True)
        else:
            self._captive_btn.setVisible(False)
            self._captive_status_label.setVisible(False)
