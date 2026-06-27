from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from flow.ui.editor.song_list_widget import SongLibraryBrowser
from flow.ui.styles import (
    ACCENT,
    BG_SURFACE,
    BORDER,
    FONT_LG,
    FW_SEMI,
    RADIUS_MD,
    SP_MD,
    SP_SM,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class LiveSongAddPanel(QWidget):
    """라이브 중 좌측에 장착되는 곡 검색/추가 패널 (긴급 패치 패널과 동형)."""

    song_chosen = Signal(str, str)  # (name, source)
    close_requested = Signal()

    def __init__(
        self,
        songs_dir: Path,
        included_names: set[str],
        parent=None,
        workspace=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("LiveSongAddPanel")
        self._active = False
        self._build_ui(songs_dir, included_names, workspace)

    def _build_ui(self, songs_dir, included_names, workspace) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(SP_MD, SP_MD, SP_MD, SP_MD)
        root.setSpacing(SP_SM)

        header = QHBoxLayout()
        title = QLabel("곡 추가")
        title.setStyleSheet(
            f"font-size: {FONT_LG}px; font-weight: {FW_SEMI}; color: {TEXT_PRIMARY};"
        )
        header.addWidget(title)
        header.addStretch()
        self._btn_close = QPushButton("닫기  Esc")
        self._btn_close.setFixedHeight(28)
        self._btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_close.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_close.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {TEXT_SECONDARY};"
            f" border: 1px solid {BORDER}; border-radius: {RADIUS_MD}px;"
            f" padding: 0 12px; }}"
        )
        self._btn_close.clicked.connect(self.close_requested)
        header.addWidget(self._btn_close)
        root.addLayout(header)

        self._browser = SongLibraryBrowser(songs_dir, included_names, self, workspace)
        self._browser.song_chosen.connect(self.song_chosen)
        root.addWidget(self._browser, 1)

        self._apply_active_style()

    def focus_target(self):
        return self._browser._search

    def mark_added(self, name: str) -> None:
        self._browser.mark_added(name)

    def set_active(self, active: bool) -> None:
        self._active = active
        self._apply_active_style()

    def _apply_active_style(self) -> None:
        left = ACCENT if self._active else BORDER
        self.setStyleSheet(
            f"QWidget#LiveSongAddPanel {{ background: {BG_SURFACE};"
            f" border-left: 3px solid {left}; }}"
        )

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.close_requested.emit()
            return
        super().keyPressEvent(event)
