"""Two-option keyboard-only confirm dialog used by emergency-patch flows.

Selection moves with ← / →, confirms with Enter, cancels with Esc.
The selected button gets the ACCENT highlight styling.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from flow.ui import styles


class ConfirmDialog(QDialog):
    """A modal yes/no-style dialog operable with arrow keys + Enter only."""

    def __init__(
        self,
        *,
        title: str,
        message: str,
        left_label: str,
        right_label: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._selected = 0  # 0 = left, 1 = right
        self.result_choice: str | None = None  # "left" | "right" | None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            styles.SP_XL, styles.SP_LG, styles.SP_XL, styles.SP_LG
        )
        layout.setSpacing(styles.SP_LG)

        msg = QLabel(message)
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(msg)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(styles.SP_MD)
        self._left_btn = QPushButton(left_label)
        self._right_btn = QPushButton(right_label)
        for b in (self._left_btn, self._right_btn):
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # we drive selection ourselves
            b.setMinimumWidth(96)
            b.setMinimumHeight(32)
        btn_row.addStretch(1)
        btn_row.addWidget(self._left_btn)
        btn_row.addWidget(self._right_btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        self._left_btn.clicked.connect(lambda: self._accept_with("left"))
        self._right_btn.clicked.connect(lambda: self._accept_with("right"))

        self._refresh_styles()

    def selected_index(self) -> int:
        return self._selected

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 (Qt API)
        key = event.key()
        if key == Qt.Key.Key_Left:
            self._selected = 0
            self._refresh_styles()
            return
        if key == Qt.Key.Key_Right:
            self._selected = 1
            self._refresh_styles()
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._accept_with("left" if self._selected == 0 else "right")
            return
        if key == Qt.Key.Key_Escape:
            self.result_choice = None
            self.reject()
            return
        super().keyPressEvent(event)

    def _accept_with(self, choice: str) -> None:
        self.result_choice = choice
        self.accept()

    def _refresh_styles(self) -> None:
        for i, btn in enumerate((self._left_btn, self._right_btn)):
            if i == self._selected:
                btn.setStyleSheet(
                    f"QPushButton {{ "
                    f"background-color: {styles.ACCENT}; "
                    f"color: white; "
                    f"border: none; "
                    f"border-radius: 6px; "
                    f"padding: {styles.SP_SM}px {styles.SP_LG}px; "
                    f"font-weight: 600; "
                    f"}}"
                )
            else:
                btn.setStyleSheet(
                    f"QPushButton {{ "
                    f"background-color: {styles.BG_ELEVATED}; "
                    f"border: none; "
                    f"border-radius: 6px; "
                    f"padding: {styles.SP_SM}px {styles.SP_LG}px; "
                    f"}}"
                )
