"""Split-view markdown song editor with live preview."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QKeySequence, QPainter, QPixmap, QShortcut
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
    extract_raw_frontmatter,
)
from flow.ui.editor.markdown_help_dialog import MarkdownHelpDialog
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
        slide_btn = QPushButton("슬라이드 추가")
        fm_btn = QPushButton("Frontmatter 편집")
        help_btn = QPushButton("도움말")
        toolbar.addWidget(save_btn)
        toolbar.addWidget(section_btn)
        toolbar.addWidget(slide_btn)
        toolbar.addWidget(fm_btn)
        toolbar.addWidget(help_btn)

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
        self._thumbs.setIconSize(QSize(167, 93))
        self._thumbs.setFixedHeight(120)

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
        slide_btn.clicked.connect(self._insert_slide)
        fm_btn.clicked.connect(self._open_frontmatter_dialog)
        help_btn.clicked.connect(self._open_help_dialog)
        self._text_edit.cursorPositionChanged.connect(self._on_cursor_moved)
        self._thumbs.currentRowChanged.connect(self._on_thumb_selected)

        # Ctrl+S shortcut
        save_sc = QShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_S), self)
        save_sc.activated.connect(self.save)

        # Defer first render until after layout has settled — otherwise the
        # preview_label is still at minimumSize and the main preview comes out
        # too small until the user clicks the editor.
        QTimer.singleShot(0, self._render_preview)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self._thumbs.count() > 0:
            idx = max(0, self._thumbs.currentRow())
            self._render_main_preview(idx)

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
            # setCurrentRow triggers currentRowChanged → _on_thumb_selected,
            # which handles the preview render.
            self._thumbs.setCurrentRow(idx)

    def _on_thumb_selected(self, idx: int) -> None:
        if 0 <= idx < self._thumbs.count():
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
                167, 93, Qt.AspectRatioMode.KeepAspectRatio,
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
        # HiDPI: render at device pixel density so the preview stays as crisp
        # as the live output (which goes to the display at native resolution).
        dpr = self._preview_label.devicePixelRatioF() or 1.0
        # 슬라이드가 메인 영역을 꽉 채우지 않도록 가장자리 여백을 둔다.
        pad = 24
        label_w = max(1, self._preview_label.width() - 2 * pad)
        label_h = max(1, self._preview_label.height() - 2 * pad)
        pix = QPixmap.fromImage(img).scaled(
            int(label_w * dpr), int(label_h * dpr),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        pix.setDevicePixelRatio(dpr)
        # 검정 배경일 때 슬라이드 경계가 안 보이는 문제 보완 — 1px 흰색 outline.
        # 알파 60으로 매우 옅게: 어두운 배경에선 살짝 보이고 밝은 배경에선 거의 안 보임.
        bordered = QPixmap(pix.size())
        bordered.setDevicePixelRatio(dpr)
        bordered.fill(Qt.GlobalColor.transparent)
        painter = QPainter(bordered)
        painter.drawPixmap(0, 0, pix)
        painter.setPen(QColor(255, 255, 255, 60))
        # Painter coordinates are logical (Qt scales internally by dpr) — use
        # logical-pixel size, NOT device pixels (pix.width()) which would draw
        # off-canvas on HiDPI.
        logical_w = pix.width() / dpr
        logical_h = pix.height() / dpr
        painter.drawRect(0, 0, int(logical_w) - 1, int(logical_h) - 1)
        painter.end()
        self._preview_label.setPixmap(bordered)

    def _insert_section(self) -> None:
        cursor = self._text_edit.textCursor()
        cursor.insertText("\n## 새 섹션\n\n")

    def _insert_slide(self) -> None:
        cursor = self._text_edit.textCursor()
        cursor.insertText(
            "\n\n주 가사 첫 줄\n주 가사 둘째 줄\n> 보조 텍스트\n\n"
        )

    def _open_frontmatter_dialog(self) -> None:
        text = self.text()
        raw = extract_raw_frontmatter(text)
        dlg = FrontmatterDialog(original_raw=raw, parent=self)
        if dlg.exec() == FrontmatterDialog.DialogCode.Accepted:
            new_raw = dlg.result_raw()
            new_text = apply_frontmatter_to_text(self.text(), new_raw)
            self._text_edit.setPlainText(new_text)

    def _open_help_dialog(self) -> None:
        MarkdownHelpDialog(parent=self).exec()
