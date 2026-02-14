from __future__ import annotations

GLOBAL_STYLESHEET = """
    QMainWindow { background-color: #1a1a1a; }
    QWidget { color: #ddd; font-family: 'Malgun Gothic', 'Segoe UI', sans-serif; }

    QSplitter::handle { background-color: #222; }
    QSplitter::handle:horizontal { width: 1px; }
    QSplitter::handle:vertical { height: 1px; }

    QWidget#CustomToolbar {
        background-color: #252525;
        border-bottom: 1px solid #333;
    }
    QToolButton {
        background-color: transparent;
        padding: 4px 8px;
        border-radius: 6px;
        font-weight: bold;
        font-size: 11px;
        color: #ccc;
    }
    QToolButton:hover { background-color: #383838; color: white; }
    QToolButton:pressed { background-color: #1e1e1e; }
    QToolButton:checked { background-color: #2196f3; color: white; }

    QStatusBar {
        background-color: #1e1e1e;
        color: #888;
        font-size: 11px;
        border-top: 1px solid #333;
    }

    QPushButton {
        background-color: #333;
        border-radius: 6px;
        padding: 5px 15px;
        color: #ddd;
    }
    QPushButton:hover { background-color: #444; }
    QPushButton:pressed { background-color: #222; }

    QMenu {
        background-color: #252525;
        color: #ddd;
        border: 1px solid #444;
    }
    QMenu::item:selected { background-color: #2196f3; color: white; }

    QScrollBar:vertical {
        border: none; background: #1a1a1a; width: 10px; margin: 0px;
    }
    QScrollBar::handle:vertical {
        background: #333; min-height: 20px; border-radius: 5px; margin: 2px;
    }
    QScrollBar::handle:vertical:hover { background: #2196f3; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }

    QDialog, QMessageBox, QMenu {
        background-color: #252525; color: #ddd; border: 1px solid #444;
    }
    QDialog QLabel, QMessageBox QLabel {
        color: #ddd; background-color: transparent;
    }
    QDialog QPushButton, QMessageBox QPushButton {
        background-color: #333; color: #ddd; border: 1px solid #555; padding: 5px 15px;
    }
    QDialog QPushButton:hover, QMessageBox QPushButton:hover {
        background-color: #444; border: 1px solid #2196f3;
    }

    QLineEdit, QTextEdit, QPlainTextEdit, QAbstractItemView {
        background-color: #2a2a2a; color: #ddd; border: 1px solid #444;
        selection-background-color: #2196f3; selection-color: white;
    }

    QScrollBar:horizontal {
        border: none; background: #1a1a1a; height: 10px; margin: 0px;
    }
    QScrollBar::handle:horizontal {
        background: #333; min-width: 20px; border-radius: 5px; margin: 2px;
    }
    QScrollBar::handle:horizontal:hover { background: #2196f3; }
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: none; }

    QWidget#SongEditorToolbar {
        background-color: #2a2500;
        border-bottom: 2px solid #fbc02d;
    }
"""

TOOLBAR_DEFAULT = """
    QWidget#CustomToolbar {
        background-color: #252525;
        border-bottom: 1px solid #333;
    }
    QToolButton {
        background-color: transparent;
        padding: 4px 8px;
        border-radius: 6px;
        font-weight: bold;
        font-size: 11px;
        color: #ccc;
    }
    QToolButton:hover { background-color: #383838; color: white; }
    QToolButton:pressed { background-color: #1e1e1e; }
    QToolButton:checked { background-color: #2196f3; color: white; }
"""

TOOLBAR_LIVE = """
    QWidget#CustomToolbar {
        background-color: #2a1818;
        border-bottom: 2px solid #ff4444;
    }
    QToolButton {
        background-color: transparent;
        padding: 4px 8px;
        border-radius: 6px;
        font-weight: bold;
        font-size: 11px;
        color: #ccc;
    }
    QToolButton:hover { background-color: #383838; color: white; }
    QToolButton:pressed { background-color: #1e1e1e; }
    QToolButton:checked { background-color: #ff4444; color: white; }
"""

TOOLBAR_SONG_EDIT = """
    QWidget#CustomToolbar {
        background-color: #2a2518;
        border-bottom: 2px solid #fbc02d;
    }
    QToolButton {
        background-color: transparent;
        padding: 4px 8px;
        border-radius: 6px;
        font-weight: bold;
        font-size: 11px;
        color: #ccc;
    }
    QToolButton:hover { background-color: #383838; color: white; }
    QToolButton:pressed { background-color: #1e1e1e; }
    QToolButton:checked { background-color: #fbc02d; color: #1a1a1a; }
"""
