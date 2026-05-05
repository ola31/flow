"""Syntax highlighter for markdown song files."""
from __future__ import annotations

import re

from PySide6.QtGui import (
    QColor,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextDocument,
)


class MarkdownHighlighter(QSyntaxHighlighter):
    """Highlights frontmatter, headers, sub override (>), slide override ({...})."""

    def __init__(self, document: QTextDocument) -> None:
        super().__init__(document)

        # Color palette — soft, not distracting
        self._fmt_frontmatter = self._format("#7DA0CA")  # blue
        self._fmt_header = self._format("#E5C07B", bold=True)  # gold
        self._fmt_section = self._format("#98C379")  # green
        self._fmt_section_sub = self._format("#56B6C2", italic=True)
        self._fmt_sub_override = self._format("#56B6C2")  # cyan
        self._fmt_slide_override = self._format("#C678DD", italic=True)

    def _format(
        self, color: str, bold: bool = False, italic: bool = False
    ) -> QTextCharFormat:
        f = QTextCharFormat()
        f.setForeground(QColor(color))
        if bold:
            f.setFontWeight(700)
        if italic:
            f.setFontItalic(True)
        return f

    def highlightBlock(self, text: str) -> None:  # noqa: N802 (Qt override)
        # Toggle frontmatter state on `---`
        if text.strip() == "---":
            self.setFormat(0, len(text), self._fmt_frontmatter)
            prev = self.previousBlockState()
            self.setCurrentBlockState(1 if prev <= 0 else 0)
            return
        prev = self.previousBlockState()
        if prev == 1:
            # Inside frontmatter
            self.setFormat(0, len(text), self._fmt_frontmatter)
            self.setCurrentBlockState(1)
            return
        self.setCurrentBlockState(0)

        # Slide override: leading {...}
        if re.match(r"\{[^}]*\}\s*$", text):
            self.setFormat(0, len(text), self._fmt_slide_override)
            return

        # Header: # Title or ## Section
        if text.startswith("# ") and not text.startswith("## "):
            self.setFormat(0, len(text), self._fmt_header)
            return
        if text.startswith("## "):
            sep = text.find("::")
            if sep == -1:
                self.setFormat(0, len(text), self._fmt_section)
            else:
                self.setFormat(0, sep, self._fmt_section)
                self.setFormat(sep, len(text) - sep, self._fmt_section_sub)
            return

        # Sub override: leading >
        if text.lstrip().startswith("> "):
            self.setFormat(0, len(text), self._fmt_sub_override)
            return
