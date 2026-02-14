from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from flow.services.config_service import ConfigService
from flow.services.slide_manager import SlideManager
from flow.ui.editor.score_canvas import ScoreCanvas
from flow.ui.editor.slide_preview_panel import SlidePreviewPanel
from flow.ui.editor.song_list_widget import SongListWidget
from flow.ui.editor.verse_selector import VerseSelector


class _PIPPane(QFrame):
    def __init__(self, label: str, color: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._color = color
        self._source_pixmap: QPixmap | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        self._badge = QLabel(label)
        self._badge.setFixedHeight(16)
        self._badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._badge.setStyleSheet(
            f"font-size: 10px; font-weight: 900; color: {color}; letter-spacing: 1px;"
        )
        layout.addWidget(self._badge)

        self._image = QLabel()
        self._image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image.setStyleSheet(
            f"background: #000; border: 1px solid {color}; border-radius: 3px;"
        )
        self._image.setMinimumSize(160, 90)
        layout.addWidget(self._image, 1)

        self._text = QLabel()
        self._text.setFixedHeight(16)
        self._text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._text.setStyleSheet("font-size: 10px; color: #aaa;")
        layout.addWidget(self._text)

    def _rescale(self) -> None:
        if not self._source_pixmap:
            return
        self._image.setPixmap(
            self._source_pixmap.scaled(
                self._image.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._rescale()

    def set_image(self, pixmap: QPixmap | None) -> None:
        if pixmap and not pixmap.isNull():
            self._source_pixmap = pixmap
            self._rescale()
        else:
            self._source_pixmap = None
            self._image.setPixmap(QPixmap())

    def set_text(self, text: str) -> None:
        self._text.setText(text)

    def clear(self) -> None:
        self._source_pixmap = None
        self._image.setPixmap(QPixmap())
        self._text.setText("")


class LivePIP(QFrame):
    clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("LivePIP")
        self.setFixedWidth(280)

        self.setStyleSheet("""
            QFrame#LivePIP {
                background: #1a1a1a;
                border-left: 1px solid #333;
            }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        self._preview_pane = _PIPPane("▶  PREVIEW", "#64b5f6")
        self._live_pane = _PIPPane("🔴  LIVE", "#ff4444")

        root.addWidget(self._preview_pane, 1)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background: #333; max-height: 1px;")
        root.addWidget(sep)

        root.addWidget(self._live_pane, 1)
        self.hide()

    def set_live(self, live: bool) -> None:
        if live:
            self.setStyleSheet("""
                QFrame#LivePIP {
                    background: #1a1a1a;
                    border-left: 2px solid #ff4444;
                }
            """)
        else:
            self.setStyleSheet("""
                QFrame#LivePIP {
                    background: #1a1a1a;
                    border-left: 1px solid #333;
                }
            """)

    def set_preview_image(self, pixmap: QPixmap | None) -> None:
        self._preview_pane.set_image(pixmap)
        if not self.isVisible():
            self.show()

    def set_preview_text(self, text: str) -> None:
        self._preview_pane.set_text(text)

    def set_live_image(self, pixmap: QPixmap | None) -> None:
        self._live_pane.set_image(pixmap)
        if not self.isVisible():
            self.show()

    def set_live_text(self, text: str) -> None:
        self._live_pane.set_text(text)

    def set_image(self, pixmap: QPixmap | None) -> None:
        self.set_preview_image(pixmap)

    def set_text(self, text: str) -> None:
        self.set_preview_text(text)

    @property
    def _badge(self) -> QLabel:
        return self._preview_pane._badge

    @property
    def _image(self) -> QLabel:
        return self._preview_pane._image

    @property
    def _text(self) -> QLabel:
        return self._preview_pane._text

    def clear(self) -> None:
        self._preview_pane.clear()
        self._live_pane.clear()
        self.hide()

    def clear_preview(self) -> None:
        self._preview_pane.clear()

    def clear_live(self) -> None:
        self._live_pane.clear()

    def mousePressEvent(self, event) -> None:
        self.clicked.emit()
        super().mousePressEvent(event)


class ProjectScreen(QWidget):
    live_toggle_requested = Signal()
    song_prev_requested = Signal()
    song_next_requested = Signal()
    live_verse_changed = Signal(int)

    def __init__(
        self,
        slide_manager: SlideManager,
        config_service: ConfigService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._slide_manager = slide_manager
        self._config_service = config_service
        self._is_live = False
        self._setup_ui()

    @property
    def toolbar_container(self) -> QWidget:
        return self._toolbar

    @property
    def slide_preview(self) -> SlidePreviewPanel:
        return self._slide_preview

    @property
    def song_list(self) -> SongListWidget:
        return self._song_list

    @property
    def canvas(self) -> ScoreCanvas:
        return self._canvas

    @property
    def verse_selector(self) -> VerseSelector:
        return self._verse_selector

    @property
    def pip(self) -> LivePIP:
        return self._pip

    @property
    def h_splitter(self) -> QSplitter:
        return self._h_splitter

    @property
    def v_splitter(self) -> QSplitter:
        return self._v_splitter

    @property
    def is_live(self) -> bool:
        return self._is_live

    def set_live_mode(self, live: bool) -> None:
        self._is_live = live
        self._song_list.setVisible(True)
        self._song_nav_bar.setVisible(live)
        self._slide_preview.setVisible(True)
        self._verse_selector.setVisible(not live)
        self._pip.setVisible(live)
        self._pip.set_live(live)
        self._canvas_container.setStyleSheet(
            "background: #111; border: 2px solid #ff4444; border-radius: 4px;"
            if live
            else "background: #111;"
        )
        if live:
            self._h_splitter.setSizes([220, 800, 280])
        else:
            self._h_splitter.setSizes([220, 800, 0])

    def sync_nav_verse(self, verse_index: int) -> None:
        btn = self._nav_verse_group.button(verse_index)
        if btn:
            btn.setChecked(True)

    def set_nav_song_name(self, name: str) -> None:
        self._nav_song_name.setText(name)

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self._toolbar = QWidget()
        self._toolbar.setObjectName("CustomToolbar")
        self._toolbar.setFixedHeight(44)
        main_layout.addWidget(self._toolbar)

        self._song_nav_bar = QWidget()
        self._song_nav_bar.setFixedHeight(36)
        self._song_nav_bar.setStyleSheet(
            "background-color: #1e1e1e; border-bottom: 1px solid #333;"
        )
        nav_layout = QHBoxLayout(self._song_nav_bar)
        nav_layout.setContentsMargins(12, 0, 12, 0)
        nav_layout.setSpacing(8)

        _nav_btn_style = """
            QPushButton {
                background: #2a2a2a; color: #aaa; border: 1px solid #444;
                border-radius: 4px; padding: 2px 10px; font-size: 11px; font-weight: bold;
            }
            QPushButton:hover { background: #3a3a3a; color: white; }
        """

        btn_prev = QPushButton("◀ 이전곡")
        btn_prev.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_prev.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_prev.setStyleSheet(_nav_btn_style)
        btn_prev.clicked.connect(self.song_prev_requested)
        nav_layout.addWidget(btn_prev)

        self._nav_song_name = QLabel("")
        self._nav_song_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._nav_song_name.setStyleSheet(
            "font-size: 13px; font-weight: bold; color: #e0e0e0;"
        )
        nav_layout.addWidget(self._nav_song_name, 1)

        btn_next = QPushButton("다음곡 ▶")
        btn_next.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_next.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_next.setStyleSheet(_nav_btn_style)
        btn_next.clicked.connect(self.song_next_requested)
        nav_layout.addWidget(btn_next)

        nav_sep = QFrame()
        nav_sep.setFrameShape(QFrame.Shape.VLine)
        nav_sep.setStyleSheet("background: #444; max-width: 1px; margin: 6px 4px;")
        nav_layout.addWidget(nav_sep)

        _verse_btn_style = """
            QPushButton {
                background: #2a2a2a; color: #999; border: 1px solid #444;
                border-radius: 4px; padding: 2px 6px; font-size: 11px; font-weight: bold;
                min-width: 32px;
            }
            QPushButton:hover { background: #3a3a3a; color: white; }
            QPushButton:checked {
                background: #1a2a40; color: #64b5f6;
                border: 1px solid #42a5f5; font-weight: 900;
            }
        """

        from PySide6.QtWidgets import QButtonGroup

        self._nav_verse_group = QButtonGroup(self)
        self._nav_verse_btns: list[QPushButton] = []

        max_v = self._config_service.get_max_verses()
        for i in range(max_v):
            idx = i if i < 5 else i + 1
            btn = QPushButton(f"{i + 1}절")
            btn.setCheckable(True)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(_verse_btn_style)
            btn.setFixedHeight(26)
            if i == 0:
                btn.setChecked(True)
            self._nav_verse_group.addButton(btn, idx)
            self._nav_verse_btns.append(btn)
            nav_layout.addWidget(btn)

        btn_chorus = QPushButton("C")
        btn_chorus.setCheckable(True)
        btn_chorus.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_chorus.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_chorus.setStyleSheet(_verse_btn_style)
        btn_chorus.setFixedHeight(26)
        btn_chorus.setToolTip("후렴")
        self._nav_verse_group.addButton(btn_chorus, 5)
        self._nav_verse_btns.append(btn_chorus)
        nav_layout.addWidget(btn_chorus)

        self._nav_verse_group.idClicked.connect(self.live_verse_changed.emit)

        self._song_nav_bar.hide()
        main_layout.addWidget(self._song_nav_bar)

        self._h_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._h_splitter.setStyleSheet(
            "QSplitter::handle { background-color: #333; width: 1px; }"
        )

        self._song_list = SongListWidget()
        self._song_list.setMaximumWidth(280)
        self._song_list.setMinimumWidth(180)
        self._h_splitter.addWidget(self._song_list)

        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)

        self._verse_selector = VerseSelector()
        self._verse_selector.set_max_verses(self._config_service.get_max_verses())
        center_layout.addWidget(self._verse_selector)

        self._canvas_container = QWidget()
        self._canvas_container.setStyleSheet("background: #111;")
        canvas_container_layout = QVBoxLayout(self._canvas_container)
        canvas_container_layout.setContentsMargins(0, 0, 0, 0)
        self._canvas = ScoreCanvas()
        canvas_container_layout.addWidget(self._canvas)

        self._v_splitter = QSplitter(Qt.Orientation.Vertical)
        self._v_splitter.addWidget(self._canvas_container)

        self._slide_preview = SlidePreviewPanel()
        self._slide_preview.set_slide_manager(self._slide_manager)
        self._v_splitter.addWidget(self._slide_preview)

        self._v_splitter.setStretchFactor(0, 1)
        self._v_splitter.setStretchFactor(1, 0)
        self._v_splitter.setHandleWidth(4)
        self._v_splitter.setSizes([600, 160])

        center_layout.addWidget(self._v_splitter)
        self._h_splitter.addWidget(center_widget)

        self._pip = LivePIP()
        self._pip.hide()
        self._h_splitter.addWidget(self._pip)

        self._h_splitter.setStretchFactor(0, 0)
        self._h_splitter.setStretchFactor(1, 1)
        self._h_splitter.setStretchFactor(2, 0)
        self._h_splitter.setSizes([220, 800, 0])

        main_layout.addWidget(self._h_splitter)
