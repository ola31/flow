from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QPushButton,
    QWidget,
)


class VerseSelector(QWidget):
    verse_changed = Signal(int)

    _BASE_STYLE = """
        QPushButton {
            background-color: #333;
            border: 1px solid #444;
            border-radius: 6px;
            color: #999;
            font-size: 12px;
            font-weight: bold;
            padding: 0 6px;
        }
        QPushButton:hover {
            background-color: #3a3a3a;
            color: #ddd;
        }
        QPushButton:checked {
            background-color: #1a2a40;
            color: #64b5f6;
            font-weight: 900;
            border: 1px solid #42a5f5;
            border-bottom: 3px solid #42a5f5;
        }
    """

    _MAPPED_PATCH = {
        "border: 1px solid #444;": "border: 1px solid #546e7a;",
        "color: #999;": "color: #cfd8dc;",
    }

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(42)
        self.setStyleSheet("background-color: #252525; border-bottom: 1px solid #333;")

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(12, 0, 12, 0)
        self._layout.setSpacing(4)

        self._btn_group = QButtonGroup(self)
        self._btn_group.idClicked.connect(self._on_clicked)

        self._max_verses = 5
        self._build_buttons()

    @property
    def button_group(self) -> QButtonGroup:
        return self._btn_group

    def set_max_verses(self, count: int) -> None:
        if count == self._max_verses:
            return
        self._max_verses = count
        self._build_buttons()

    def set_current_verse(self, verse_index: int) -> None:
        btn = self._btn_group.button(verse_index)
        if btn:
            btn.setChecked(True)

    def get_current_verse(self) -> int:
        return self._btn_group.checkedId()

    def update_mapping_state(self, mapping_flags: dict[int, bool]) -> None:
        for idx, has_mapping in mapping_flags.items():
            btn = self._btn_group.button(idx)
            if not btn:
                continue
            style = self._BASE_STYLE
            if has_mapping:
                for old, new in self._MAPPED_PATCH.items():
                    style = style.replace(old, new)
            btn.setStyleSheet(style)

    def button(self, idx: int) -> QPushButton | None:
        return self._btn_group.button(idx)

    def _build_buttons(self) -> None:
        for btn in self._btn_group.buttons():
            self._btn_group.removeButton(btn)
            btn.deleteLater()

        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._layout.addStretch()

        for i in range(self._max_verses):
            idx = i if i < 5 else i + 1
            btn = QPushButton(f"{i + 1}절")
            btn.setCheckable(True)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setFixedSize(48, 30)
            btn.setStyleSheet(self._BASE_STYLE)
            if i == 0:
                btn.setChecked(True)
            self._btn_group.addButton(btn, idx)
            self._layout.addWidget(btn)

        sep = QWidget()
        sep.setFixedSize(1, 22)
        sep.setStyleSheet("background-color: #444;")
        self._layout.addWidget(sep)

        btn_chorus = QPushButton("후렴")
        btn_chorus.setCheckable(True)
        btn_chorus.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_chorus.setFixedSize(56, 30)
        btn_chorus.setStyleSheet(self._BASE_STYLE)
        self._btn_group.addButton(btn_chorus, 5)
        self._layout.addWidget(btn_chorus)

        self._layout.addStretch()

    def _on_clicked(self, verse_index: int) -> None:
        self.verse_changed.emit(verse_index)
