"""Split-pane emergency patch editor for live mode.

Architecture:
    - Left pane of the live screen during emergency-patch sessions.
    - One panel instance per session. Carries pending changes across slide
      navigation in memory; commits all on Ctrl+Enter.
    - Owns the markdown text editor, a preview, and the apply/revert/close
      controls.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from flow.services.markdown import SongSpec
from flow.ui import styles


@dataclass
class _PendingState:
    """In-memory edit state for one slide-position in this session."""

    text: str
    is_dirty: bool  # True if text != original loaded text


class EmergencyPatchPanel(QWidget):
    """The split-pane editor widget. See spec for behavior detail."""

    # Emitted when user presses Ctrl+Enter / clicks 적용. Payload: list of
    # (slot_key, text) tuples; slot_key is int (existing slide index) or
    # str like "add:N" (append slot allocated this session).
    applied = Signal(list)
    close_requested = Signal()

    def __init__(
        self,
        *,
        spec: SongSpec,
        song_dir: Path,
        initial_index: int | None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._spec = spec
        self._song_dir = song_dir

        self._current_key: int | str
        self._pending: dict[int | str, _PendingState] = {}
        self._add_counter = 0  # next "add:N" suffix to allocate

        self._build_ui()

        if initial_index is None:
            self._current_key = self._allocate_add_slot()
        else:
            self._current_key = initial_index

        self._refresh_editor_for_current()

    # --- Public API used by tests + main_window --------------------------

    def current_text(self) -> str:
        return self._editor.toPlainText()

    def is_add_mode(self) -> bool:
        return isinstance(self._current_key, str)

    def has_pending_changes(self) -> bool:
        # Sync current editor text into pending store, then check
        self._sync_current_to_pending()
        return any(s.is_dirty for s in self._pending.values())

    def set_text(self, text: str) -> None:
        self._editor.setPlainText(text)

    # --- Internals --------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            styles.SP_MD, styles.SP_MD, styles.SP_MD, styles.SP_MD
        )
        layout.setSpacing(styles.SP_SM)

        self._title_label = QLabel("긴급 수정")
        self._title_label.setStyleSheet(
            f"color: {styles.AMBER}; font-size: {styles.FONT_SM}px; font-weight: 600;"
        )
        layout.addWidget(self._title_label)

        self._editor = QPlainTextEdit()
        self._editor.setStyleSheet(
            f"QPlainTextEdit {{ background-color: {styles.BG_ELEVATED}; "
            f"color: {styles.TEXT_PRIMARY}; border: none; "
            f"padding: {styles.SP_MD}px; "
            f"font-family: '{styles.FONT_FAMILY}'; "
            f"font-size: {styles.FONT_MD}px; }}"
        )
        self._editor.setTabChangesFocus(True)
        layout.addWidget(self._editor, 1)

        self._preview_label = QLabel()
        self._preview_label.setMinimumHeight(120)
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setStyleSheet(
            f"background-color: {styles.BG_DEEP}; "
            f"border: 1px solid {styles.BG_ELEVATED};"
        )
        layout.addWidget(self._preview_label)

        self._apply_btn = QPushButton("적용 (Ctrl+Enter)")
        self._apply_btn.setStyleSheet(
            f"QPushButton {{ background-color: {styles.ACCENT}; color: white; "
            f"border: none; border-radius: 6px; "
            f"padding: {styles.SP_SM}px {styles.SP_LG}px; font-weight: 600; }}"
        )
        layout.addWidget(self._apply_btn)

    def _allocate_add_slot(self) -> str:
        slot = f"add:{self._add_counter}"
        self._add_counter += 1
        return slot

    def _refresh_editor_for_current(self) -> None:
        """Load `_current_key`'s text into the editor, recording original."""
        key = self._current_key
        if isinstance(key, int):
            original = self._spec.slides[key].main
        else:
            original = ""  # add-mode start
        # If we have a pending entry, prefer it; else seed with original.
        existing = self._pending.get(key)
        if existing is not None:
            text = existing.text
        else:
            text = original
            self._pending[key] = _PendingState(text=text, is_dirty=False)
        self._editor.setPlainText(text)
        self._update_title_label()

    def _sync_current_to_pending(self) -> None:
        """Store current editor text into pending and update dirty flag."""
        key = self._current_key
        text = self._editor.toPlainText()
        if isinstance(key, int):
            original = self._spec.slides[key].main
        else:
            original = ""
        self._pending[key] = _PendingState(text=text, is_dirty=(text != original))

    def _update_title_label(self) -> None:
        key = self._current_key
        if isinstance(key, int):
            total = len(self._spec.slides)
            self._title_label.setText(f"긴급 수정 — 슬라이드 #{key + 1} / {total}")
        else:
            self._title_label.setText("새 슬라이드 추가")
