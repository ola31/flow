"""Markdown editor screen — MarkdownEditor wrapped with header + back button."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from flow.ui.editor.markdown_editor import MarkdownEditor
from flow.ui.styles import (
    BG_DEEP,
    BG_SURFACE,
    BORDER_SUBTLE_RGBA,
    SP_LG,
    SP_MD,
    SP_SM,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TEXT_TERTIARY,
)


class MarkdownEditorScreen(QWidget):
    """Top-level screen hosting a MarkdownEditor with a header bar.

    Signals:
        back_requested: emitted when user clicks the back button.
    """

    back_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._md_path: Path | None = None
        self._song_name: str = ""
        self._song = None
        self._editor: MarkdownEditor | None = None

        self.setStyleSheet(f"background: {BG_DEEP};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header bar
        header = QWidget()
        header.setStyleSheet(
            f"background: {BG_SURFACE}; "
            f"border-bottom: 1px solid {BORDER_SUBTLE_RGBA};"
        )
        header.setFixedHeight(56)
        h = QHBoxLayout(header)
        h.setContentsMargins(SP_LG, SP_SM, SP_LG, SP_SM)
        h.setSpacing(SP_MD)

        self._btn_back = QPushButton("← 돌아가기")
        self._btn_back.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {TEXT_SECONDARY}; "
            f"border: none; font-size: 13px; padding: 6px 10px; }} "
            f"QPushButton:hover {{ color: {TEXT_PRIMARY}; }}"
        )
        self._btn_back.setCursor(self._btn_back.cursor())
        self._btn_back.clicked.connect(self.back_requested.emit)
        h.addWidget(self._btn_back)

        # 곡 이름만 작게 표시 — "마크다운 편집"은 자명하므로 생략.
        self._title_label = QLabel("")
        self._title_label.setStyleSheet(
            f"color: {TEXT_TERTIARY}; font-size: 12px;"
        )
        h.addWidget(self._title_label)
        h.addStretch()

        layout.addWidget(header)

        # Editor host (replaced when load_song is called)
        self._editor_host = QWidget()
        self._editor_layout = QVBoxLayout(self._editor_host)
        self._editor_layout.setContentsMargins(0, 0, 0, 0)
        self._editor_layout.setSpacing(0)
        layout.addWidget(self._editor_host, 1)

    def load_song(self, song) -> None:
        """Replace the current editor with a new one for the given song."""
        self._md_path = song.markdown_path
        self._song_name = song.name
        # 편집을 마치고 나갈 때 이 곡의 슬라이드를 다시 세고 렌더해야 하므로
        # 곡 객체를 붙들어 둔다 (SlideManager._songs와 같은 인스턴스).
        self._song = song
        self._title_label.setText(song.name)

        # Tear down previous editor
        if self._editor is not None:
            self._editor_layout.removeWidget(self._editor)
            self._editor.deleteLater()
            self._editor = None

        self._editor = MarkdownEditor(self._md_path)
        self._editor_layout.addWidget(self._editor)

    def is_dirty(self) -> bool:
        return self._editor is not None and self._editor.is_dirty()

    def content_changed(self) -> bool:
        """이 편집 세션에서 저장했든 안 했든 내용이 바뀐 적 있는가."""
        return self._editor is not None and self._editor.content_changed()

    def save_if_dirty(self) -> None:
        if self.is_dirty() and self._editor is not None:
            self._editor.save()

    def current_song(self):
        """편집 중인 곡 (없으면 None)."""
        return self._song
