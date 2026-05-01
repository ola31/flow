from __future__ import annotations

from PySide6.QtGui import QTextDocument

from flow.ui.editor.markdown_highlighter import MarkdownHighlighter


def test_highlighter_attaches_to_document(qapp) -> None:
    doc = QTextDocument()
    h = MarkdownHighlighter(doc)
    assert h.document() is doc


def test_highlighter_processes_text_without_error(qapp) -> None:
    doc = QTextDocument()
    MarkdownHighlighter(doc)
    doc.setPlainText(
        "---\nmain_size: 56\n---\n\n# T\n\n## 1절 :: T 1절\n\n"
        "{main_size: 72}\n가사\n> sub\n"
    )
    # If we got here without exception, syntax highlight ran without crashing
    assert doc.blockCount() > 0
