"""Split-view markdown song editor with live preview."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from flow.services.markdown import parse, render_all, render_slide
from flow.ui.editor.markdown_frontmatter_dialog import (
    FrontmatterDialog,
    apply_frontmatter_to_text,
)
from flow.ui.editor.markdown_highlighter import MarkdownHighlighter


class MarkdownEditor(QWidget):
    """Split-view editor: text on left, preview on right."""

    def __init__(self, md_path: Path, parent=None) -> None:
        super().__init__(parent)
        self._md_path = md_path
        self._original_text = (
            md_path.read_text(encoding="utf-8") if md_path.exists() else ""
        )

        # Toolbar
        toolbar = QToolBar()
        save_btn = QPushButton("저장 (Ctrl+S)")
        section_btn = QPushButton("섹션 추가")
        slide_btn = QPushButton("슬라이드 나누기")
        fm_btn = QPushButton("Frontmatter 편집")
        toolbar.addWidget(save_btn)
        toolbar.addWidget(section_btn)
        toolbar.addWidget(slide_btn)
        toolbar.addWidget(fm_btn)

        # Text editor (left)
        self._text_edit = QPlainTextEdit()
        self._text_edit.setPlainText(self._original_text)
        self._highlighter = MarkdownHighlighter(self._text_edit.document())

        # Preview (right): big preview + thumbnail list
        self._preview_label = QLabel("미리보기")
        self._preview_label.setMinimumSize(400, 225)
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thumbs = QListWidget()
        self._thumbs.setFlow(QListWidget.Flow.LeftToRight)
        self._thumbs.setFixedHeight(80)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(self._preview_label, 1)
        right_layout.addWidget(self._thumbs)

        # Split
        splitter = QSplitter()
        splitter.addWidget(self._text_edit)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)

        # Layout
        layout = QVBoxLayout(self)
        layout.addWidget(toolbar)
        layout.addWidget(splitter, 1)

        # Wire
        save_btn.clicked.connect(self.save)
        section_btn.clicked.connect(self._insert_section)
        slide_btn.clicked.connect(self._insert_slide_break)
        fm_btn.clicked.connect(self._open_frontmatter_dialog)
        self._text_edit.cursorPositionChanged.connect(self._on_cursor_moved)

        # Ctrl+S shortcut
        save_sc = QShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_S), self)
        save_sc.activated.connect(self.save)

        self._render_preview()

    # Public API
    def text(self) -> str:
        return self._text_edit.toPlainText()

    def set_text(self, t: str) -> None:
        self._text_edit.setPlainText(t)

    def is_dirty(self) -> bool:
        return self.text() != self._original_text

    def save(self) -> None:
        text = self.text()
        self._md_path.write_text(text, encoding="utf-8")
        self._original_text = text
        self._render_preview()

    # Internals
    def _on_cursor_moved(self) -> None:
        line_num = self._text_edit.textCursor().blockNumber()
        idx = self._slide_index_at_line(line_num)
        if 0 <= idx < self._thumbs.count():
            self._thumbs.setCurrentRow(idx)
            self._render_main_preview(idx)

    def _slide_index_at_line(self, line: int) -> int:
        """Map cursor line to slide index by counting blank-line blocks above."""
        text = self.text()
        slides = parse(text).slides
        if not slides:
            return -1
        running_idx = 0
        in_slide = False
        for i, raw in enumerate(text.splitlines()):
            stripped = raw.strip()
            if stripped.startswith("#"):
                if in_slide:
                    in_slide = False
                continue
            if not stripped:
                if in_slide:
                    running_idx += 1
                    in_slide = False
                continue
            if not in_slide:
                in_slide = True
            if i >= line:
                break
        return min(running_idx, len(slides) - 1)

    def _render_preview(self) -> None:
        """Re-parse + render all slides; populate thumbnails + main preview."""
        text = self.text()
        spec = parse(text)
        images = render_all(spec, song_dir=self._md_path.parent)
        self._thumbs.clear()
        for i, img in enumerate(images):
            item = QListWidgetItem(f"{i + 1}")
            pix = QPixmap.fromImage(img).scaled(
                100, 56, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            item.setIcon(QIcon(pix))
            self._thumbs.addItem(item)
        if images:
            self._render_main_preview(0)

    def _render_main_preview(self, idx: int) -> None:
        text = self.text()
        spec = parse(text)
        if idx < 0 or idx >= len(spec.slides):
            return
        img = render_slide(spec, spec.slides[idx], song_dir=self._md_path.parent)
        pix = QPixmap.fromImage(img).scaled(
            self._preview_label.width(), self._preview_label.height(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._preview_label.setPixmap(pix)

    def _insert_section(self) -> None:
        cursor = self._text_edit.textCursor()
        cursor.insertText("\n## 새 섹션\n\n")

    def _insert_slide_break(self) -> None:
        cursor = self._text_edit.textCursor()
        cursor.insertText("\n\n")

    def _open_frontmatter_dialog(self) -> None:
        spec = parse(self.text())
        dlg = FrontmatterDialog(spec.frontmatter, parent=self)
        if dlg.exec() == FrontmatterDialog.DialogCode.Accepted:
            new_fm = dlg.result_frontmatter()
            new_text = apply_frontmatter_to_text(self.text(), new_fm)
            self._text_edit.setPlainText(new_text)
