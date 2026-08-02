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
from flow.ui.styles import (
    BG_DEEP,
    BG_SURFACE,
    BORDER,
    BORDER_SUBTLE_RGBA,
    RED,
    RED_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TEXT_TERTIARY,
    ACCENT,
    ACCENT_MUTED,
    FONT_2XS, FONT_XS, FONT_SM, FONT_MD, FW_MEDIUM,
    SP_XS, SP_SM, SP_MD,
)
from flow.services.slide_manager import SlideManager
from flow.ui.editor.mapping_panel import MappingPanel
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
            f"font-size: {FONT_2XS}px; font-weight: {FW_MEDIUM}; color: {color};"
        )
        from PySide6.QtGui import QFont
        _bf = self._badge.font()
        _bf.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.0)
        self._badge.setFont(_bf)
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
        self._text.setStyleSheet(
            f"font-size: {FONT_2XS}px; color: {TEXT_TERTIARY};"
        )
        layout.addWidget(self._text)

    def _rescale(self) -> None:
        """원본을 판 크기에 맞춘다 (HiDPI 대응).

        논리 크기로 스케일하면 배율 1.5인 화면에서 실제 픽셀의 2/3만 그려
        Qt가 다시 확대한다 — 프리뷰/라이브 썸네일이 흐릿해지던 원인.
        물리 픽셀로 스케일한 뒤 배율을 심어 QLabel이 제 크기로 그리게 한다.
        """
        if not self._source_pixmap:
            return
        ratio = self.devicePixelRatioF() or 1.0
        target = self._image.size() * ratio
        scaled = self._source_pixmap.scaled(
            target,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        scaled.setDevicePixelRatio(ratio)
        self._image.setPixmap(scaled)

    def source_size_hint(self) -> tuple[int, int]:
        """이 판을 채우는 데 필요한 원본 크기(물리 픽셀).

        캐시 키가 크기별로 갈리므로 240px 단위로 올려 종류를 제한한다.
        """
        ratio = self.devicePixelRatioF() or 1.0
        width = max(1, int(self._image.width() * ratio))
        step = 240
        quantized = min(1920, max(step, ((width + step - 1) // step) * step))
        return quantized, int(quantized * 9 / 16)

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
        self.setMinimumWidth(220)

        from flow.ui.styles import (
            BG_SURFACE, BORDER_SUBTLE_RGBA, ACCENT_INTER, RED
        )
        self._idle_style = (
            f"QFrame#LivePIP {{ background: {BG_SURFACE}; "
            f"border-left: 1px solid {BORDER_SUBTLE_RGBA}; }}"
        )
        self._live_style = (
            f"QFrame#LivePIP {{ background: {BG_SURFACE}; "
            f"border-left: 2px solid {RED}; }}"
        )
        self.setStyleSheet(self._idle_style)

        root = QVBoxLayout(self)
        root.setContentsMargins(SP_SM, SP_SM, SP_SM, SP_SM)
        root.setSpacing(SP_SM)

        self._preview_pane = _PIPPane("PREVIEW", ACCENT_INTER)
        self._live_pane = _PIPPane("LIVE", RED)

        root.addWidget(self._preview_pane, 1)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(
            f"background: {BORDER_SUBTLE_RGBA}; max-height: 1px;"
        )
        root.addWidget(sep)

        root.addWidget(self._live_pane, 1)
        self.hide()

    def set_live(self, live: bool) -> None:
        self.setStyleSheet(self._live_style if live else self._idle_style)

    def preview_source_size(self) -> tuple[int, int]:
        """프리뷰 판을 선명하게 채우는 데 필요한 원본 크기."""
        return self._preview_pane.source_size_hint()

    def set_preview_image(self, pixmap: QPixmap | None) -> None:
        self._preview_pane.set_image(pixmap)

    def set_preview_text(self, text: str) -> None:
        self._preview_pane.set_text(text)

    def set_live_image(self, pixmap: QPixmap | None) -> None:
        self._live_pane.set_image(pixmap)

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
        # Object name + WA_StyledBackground let MainWindow toggle a focus
        # border on this screen without leaking into child widgets.
        self.setObjectName("projectScreen")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._setup_ui()
        # 스타일시트는 1회만 설정 — set_focus_active마다 setStyleSheet하면
        # 화면 전체(캔버스·썸네일·카드)가 리폴리시돼 Tab 전환이 버벅인다.
        self.setProperty("focusActive", False)
        self.setStyleSheet(
            f"#projectScreen {{ border: 4px solid transparent; "
            f"border-radius: 6px; }} "
            f"#projectScreen[focusActive=\"true\"] {{ "
            f"border-color: {ACCENT}; }}"
        )

    def set_focus_active(self, active: bool) -> None:
        """Show / hide a full ACCENT outline around this screen.

        Used by MainWindow during emergency-patch sessions to indicate
        that the live area (this screen) is the focused side rather than
        the patch panel. The border width is reserved when inactive
        (transparent) so toggling doesn't shift the layout. 동적
        프로퍼티 + 자기 자신만 재계산 (하위 위젯 리폴리시 방지).
        """
        self.setProperty("focusActive", active)
        self.style().unpolish(self)
        self.style().polish(self)

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
    def mapping_panel(self) -> MappingPanel:
        return self._mapping_panel

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
        self._live_hint_bar.setVisible(live)
        self._canvas_container.setStyleSheet(
            f"background: {BG_DEEP}; border: 2px solid {RED}; border-radius: 4px;"
            if live
            else f"background: {BG_DEEP};"
        )
        if live:
            self._mapping_panel.hide()
            self._h_splitter.setSizes([240, 800, 420, 0])
        else:
            self._pip.hide()
            # mapping panel visibility managed by MainWindow
            cur_map = self._h_splitter.sizes()[3] if len(self._h_splitter.sizes()) > 3 else 0
            self._h_splitter.setSizes([240, 800, 0, cur_map])

    def sync_nav_verse(self, verse_index: int) -> None:
        btn = self._nav_verse_group.button(verse_index)
        if btn:
            btn.setChecked(True)

    def set_nav_song_name(self, name: str) -> None:
        self._nav_song_name.setText(name)

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        # Reserve 4px on every side so the focus-active border (drawn via
        # set_focus_active) actually shows. Without this, child widgets
        # like the toolbar paint over the border at the screen's edges.
        # The 4px stays transparent when the screen is inactive, so the
        # only visible difference between modes is the border color.
        main_layout.setContentsMargins(4, 4, 4, 4)
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

        # 이전곡 / 다음곡 버튼은 긴급 수정 패널 헤더로 이동.
        # song name label 만 남김.
        self._nav_song_name = QLabel("")
        self._nav_song_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._nav_song_name.setStyleSheet(
            f"font-size: {FONT_MD}px; font-weight: {FW_MEDIUM}; color: {TEXT_PRIMARY};"
        )
        nav_layout.addWidget(self._nav_song_name, 1)

        nav_sep = QFrame()
        nav_sep.setFrameShape(QFrame.Shape.VLine)
        nav_sep.setStyleSheet("background: #444; max-width: 1px; margin: 6px 4px;")
        nav_layout.addWidget(nav_sep)

        _verse_btn_style = f"""
            QPushButton {{
                background: #2a2a2a; color: #999; border: 1px solid #444;
                border-radius: 4px; padding: 2px 6px; font-size: {FONT_XS}px; font-weight: {FW_MEDIUM};
                min-width: 32px;
            }}
            QPushButton:hover {{ background: #3a3a3a; color: white; }}
            QPushButton:checked {{
                background: #1a2a40; color: #64b5f6;
                border: 1px solid #42a5f5; font-weight: {FW_MEDIUM};
            }}
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
        from flow.ui.styles import BORDER_SUBTLE_RGBA
        self._h_splitter.setStyleSheet(
            f"QSplitter::handle {{ background-color: {BORDER_SUBTLE_RGBA}; width: 1px; }}"
        )
        self._h_splitter.setHandleWidth(1)

        self._song_list = SongListWidget()
        self._song_list.setMaximumWidth(320)
        self._song_list.setMinimumWidth(220)
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
        self._v_splitter.setStyleSheet(
            f"QSplitter::handle {{ background-color: {BORDER_SUBTLE_RGBA}; height: 1px; }}"
        )
        self._v_splitter.setHandleWidth(1)
        self._v_splitter.addWidget(self._canvas_container)

        self._slide_preview = SlidePreviewPanel()
        self._slide_preview.set_slide_manager(self._slide_manager)
        self._v_splitter.addWidget(self._slide_preview)

        self._v_splitter.setStretchFactor(0, 1)
        self._v_splitter.setStretchFactor(1, 0)
        self._v_splitter.setSizes([600, 160])

        center_layout.addWidget(self._v_splitter)

        # ── 라이브 단축키 힌트 바
        self._live_hint_bar = QFrame()
        self._live_hint_bar.setFixedHeight(30)
        self._live_hint_bar.setStyleSheet(f"""
            QFrame {{
                background: {RED_MUTED};
                border-top: 1px solid {RED};
            }}
        """)
        hint_layout = QHBoxLayout(self._live_hint_bar)
        hint_layout.setContentsMargins(16, 0, 16, 0)
        hint_layout.setSpacing(0)
        hint_label = QLabel(
            "Enter / Space : 송출     B : 블랙아웃     1–5 / C : 절 이동     Esc : 편집 모드로"
        )
        hint_label.setStyleSheet(
            f"font-size: {FONT_SM}px; color: {RED}; background: transparent;"
        )
        from PySide6.QtGui import QFont
        _hf = hint_label.font()
        _hf.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.5)
        hint_label.setFont(_hf)
        hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint_layout.addWidget(hint_label)
        self._live_hint_bar.hide()
        center_layout.addWidget(self._live_hint_bar)
        self._h_splitter.addWidget(center_widget)

        self._pip = LivePIP()
        self._pip.hide()
        self._h_splitter.addWidget(self._pip)
        self._h_splitter.setCollapsible(self._h_splitter.indexOf(self._pip), False)

        self._mapping_panel = MappingPanel()
        self._h_splitter.addWidget(self._mapping_panel)

        self._h_splitter.setStretchFactor(0, 0)
        self._h_splitter.setStretchFactor(1, 1)
        self._h_splitter.setStretchFactor(2, 0)
        self._h_splitter.setStretchFactor(3, 0)
        self._h_splitter.setSizes([240, 800, 0, 0])

        main_layout.addWidget(self._h_splitter)
