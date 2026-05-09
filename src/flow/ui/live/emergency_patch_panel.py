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

from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtGui import QKeyEvent, QKeySequence, QShortcut
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

    def can_go_prev(self) -> bool:
        if isinstance(self._current_key, int):
            return self._current_key > 0
        # Add mode: prev goes back to the last existing slide.
        return len(self._spec.slides) > 0

    def can_go_next(self) -> bool:
        if isinstance(self._current_key, int):
            return self._current_key < len(self._spec.slides) - 1
        # Add mode: next always offers "add another" (no hard limit)
        return True

    def go_prev(self) -> None:
        if not self.can_go_prev():
            return
        self._sync_current_to_pending()
        if isinstance(self._current_key, int):
            self._current_key = self._current_key - 1
        else:
            # add mode → last existing slide
            self._current_key = len(self._spec.slides) - 1
        self._refresh_editor_for_current()

    def go_next(self) -> None:
        # Edit mode, not at last → just move forward
        if isinstance(self._current_key, int):
            if self._current_key < len(self._spec.slides) - 1:
                self._sync_current_to_pending()
                self._current_key = self._current_key + 1
                self._refresh_editor_for_current()
                return
            # At last existing slide → ask
            if self._ask_add_another():
                self._sync_current_to_pending()
                self._current_key = self._allocate_add_slot()
                self._refresh_editor_for_current()
            return
        # Add mode → ask for another
        if self._ask_add_another():
            self._sync_current_to_pending()
            self._current_key = self._allocate_add_slot()
            self._refresh_editor_for_current()

    def apply_now(self) -> None:
        self._sync_current_to_pending()
        dirty = [
            (key, state.text)
            for key, state in self._pending.items()
            if state.is_dirty
        ]
        self.applied.emit(dirty)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Intercept Ctrl+Return on the editor before QPlainTextEdit handles it."""
        if (
            watched is self._editor
            and event.type() == QEvent.Type.KeyPress
        ):
            key_event = QKeyEvent(event)
            if (
                key_event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
                and key_event.modifiers() & Qt.KeyboardModifier.ControlModifier
            ):
                self.apply_now()
                return True
        return super().eventFilter(watched, event)

    def _ask_add_another(self) -> bool:
        """Show 'add new slide?' popup, return True if user said yes."""
        from flow.ui.live.confirm_dialog import ConfirmDialog

        dlg = ConfirmDialog(
            title="새 슬라이드 추가",
            message="새 슬라이드를 추가하시겠습니까?",
            left_label="예",
            right_label="아니오",
            parent=self,
        )
        dlg.exec()
        return dlg.result_choice == "left"

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
        self._editor.textChanged.connect(self._on_text_changed)
        layout.addWidget(self._editor, 1)

        QShortcut(QKeySequence("Ctrl+Right"), self, activated=self.go_next)
        QShortcut(QKeySequence("Ctrl+Left"), self, activated=self.go_prev)

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

        self._apply_btn.clicked.connect(self.apply_now)
        # QPlainTextEdit consumes Ctrl+Return before window shortcuts fire,
        # so intercept it via an event filter installed directly on the editor.
        self._editor.installEventFilter(self)

    def preview_pixmap(self):  # -> QPixmap | None
        return self._preview_label.pixmap()

    def _on_text_changed(self) -> None:
        self._sync_current_to_pending()
        self._render_preview()

    def _render_preview(self) -> None:
        from PySide6.QtCore import Qt as _Qt
        from PySide6.QtGui import QPixmap

        from flow.services.markdown import Slide, render_slide

        text = self._editor.toPlainText()
        slide = Slide(main=text, sub_override=None, section_sub_default=None)
        try:
            img = render_slide(self._spec, slide, song_dir=self._song_dir)
        except Exception:
            self._preview_label.setText("(미리보기 오류)")
            return
        pix = QPixmap.fromImage(img)
        scaled = pix.scaled(
            self._preview_label.width(),
            self._preview_label.height(),
            _Qt.AspectRatioMode.KeepAspectRatio,
            _Qt.TransformationMode.SmoothTransformation,
        )
        self._preview_label.setPixmap(scaled)

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
        self._render_preview()

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
