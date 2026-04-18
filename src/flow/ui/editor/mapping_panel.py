from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from flow.domain.hotspot import Hotspot

_PANEL_W = 260
_THUMB_W = _PANEL_W - 32  # left/right padding
_THUMB_H = int(_THUMB_W * 9 / 16)

_VERSE_NAMES = ["1절", "2절", "3절", "4절", "5절", "후렴"]
_VERSE_COLORS = ["#64b5f6", "#81c784", "#ffb74d", "#ce93d8", "#ef9a9a", "#fff176"]


class _VerseRow(QFrame):
    """한 절(또는 후렴)의 매핑 상태를 보여주는 행."""

    activated = Signal(int)       # 이 행을 클릭 → 해당 절로 이동
    unmap_requested = Signal(int) # 해제 버튼 클릭

    def __init__(self, verse_index: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._verse_index = verse_index
        self._is_active = False
        self._is_mapped = False
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setObjectName("VerseRow")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedWidth(_PANEL_W - 16)

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 6, 8, 6)
        root.setSpacing(4)

        # ── 헤더: 절 이름 + 해제 버튼
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(4)

        color = _VERSE_COLORS[self._verse_index]
        self._badge = QLabel(_VERSE_NAMES[self._verse_index])
        self._badge.setFixedSize(32, 20)
        self._badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._badge.setStyleSheet(
            f"background: transparent; color: {color}; "
            "font-size: 11px; font-weight: 900; border: none;"
        )
        header.addWidget(self._badge)

        self._slide_label = QLabel("—")
        self._slide_label.setStyleSheet("font-size: 11px; color: #555; border: none;")
        header.addWidget(self._slide_label)
        header.addStretch()

        self._btn_unmap = QPushButton("해제")
        self._btn_unmap.setFixedSize(36, 20)
        self._btn_unmap.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_unmap.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_unmap.setStyleSheet("""
            QPushButton {
                background: #3a2222; color: #e57373; border: none;
                border-radius: 3px; font-size: 10px; padding: 0;
            }
            QPushButton:hover { background: #522828; }
        """)
        self._btn_unmap.clicked.connect(lambda: self.unmap_requested.emit(self._verse_index))
        self._btn_unmap.hide()
        header.addWidget(self._btn_unmap)

        root.addLayout(header)

        # ── 썸네일
        self._thumb = QLabel()
        self._thumb.setFixedHeight(_THUMB_H)
        self._thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._thumb)

        self._refresh_style()

    def set_mapped(self, slide_index: int, get_image_fn) -> None:
        self._is_mapped = slide_index >= 0
        if self._is_mapped and get_image_fn:
            try:
                qimg = get_image_fn(slide_index)
                if qimg:
                    pm = QPixmap.fromImage(qimg).scaled(
                        _THUMB_W, _THUMB_H,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    self._thumb.setPixmap(pm)
                    self._thumb.setText("")
                    self._slide_label.setText(f"슬라이드 {slide_index + 1}")
                    self._slide_label.setStyleSheet(
                        "font-size: 11px; color: #4caf50; border: none;"
                    )
                    self._btn_unmap.show()
                    self._refresh_style()
                    return
            except Exception:
                pass

        # 매핑 없음
        self._thumb.setPixmap(QPixmap())
        self._thumb.setText("없음")
        self._slide_label.setText("—")
        self._slide_label.setStyleSheet("font-size: 11px; color: #555; border: none;")
        self._btn_unmap.hide()
        self._is_mapped = False
        self._refresh_style()

    def set_active(self, active: bool) -> None:
        self._is_active = active
        self._refresh_style()

    def _refresh_style(self) -> None:
        color = _VERSE_COLORS[self._verse_index]
        if self._is_active:
            border = f"2px solid {color}"
            bg = "#1e2a38"
            thumb_border = f"1px solid {color}"
        elif self._is_mapped:
            border = "1px solid #3a4a3a"
            bg = "#1a221a"
            thumb_border = "1px solid #3a4a3a"
        else:
            border = "1px solid #2a2a2a"
            bg = "#1a1a1a"
            thumb_border = "1px dashed #2a2a2a"

        self.setStyleSheet(
            f"QFrame#VerseRow {{ background: {bg}; border: {border}; border-radius: 6px; }}"
        )
        self._thumb.setStyleSheet(
            f"background: #111; border: {thumb_border}; border-radius: 3px; "
            "color: #444; font-size: 11px;"
        )

    def mousePressEvent(self, event) -> None:
        self.activated.emit(self._verse_index)
        super().mousePressEvent(event)


class MappingPanel(QFrame):
    """핫스팟의 절별 매핑 현황을 보여주는 우측 패널."""

    verse_activated = Signal(int)   # 절 행 클릭 → 해당 절로 이동
    unmap_requested = Signal(int)   # 특정 절 매핑 해제 요청
    closed = Signal()               # X 버튼으로 닫기

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("MappingPanel")
        self.setFixedWidth(_PANEL_W)
        self._hotspot: Hotspot | None = None
        self._active_verse = 0
        self._get_image = None
        self._rows: list[_VerseRow] = []
        self._setup_ui()
        self.hide()

    def _setup_ui(self) -> None:
        self.setStyleSheet("""
            QFrame#MappingPanel {
                background: #1a1a1a;
                border-left: 1px solid #333;
            }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 10, 8, 10)
        root.setSpacing(6)

        # ── 헤더
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        self._title = QLabel("핫스팟 매핑")
        self._title.setStyleSheet(
            "font-size: 13px; font-weight: 900; color: #ccc; border: none;"
        )
        header.addWidget(self._title)
        header.addStretch()

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(24, 24)
        btn_close.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet("""
            QPushButton {
                background: transparent; color: #666; border: none;
                font-size: 13px; padding: 0;
            }
            QPushButton:hover { color: #ccc; }
        """)
        btn_close.clicked.connect(self._on_close)
        header.addWidget(btn_close)
        root.addLayout(header)

        # 부제
        self._subtitle = QLabel()
        self._subtitle.setStyleSheet(
            "font-size: 11px; color: #555; border: none; margin-bottom: 4px;"
        )
        root.addWidget(self._subtitle)

        # 구분선
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background: #2a2a2a; max-height: 1px; border: none;")
        root.addWidget(sep)

        # ── 절 행 스크롤 영역
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical {
                border: none; background: transparent; width: 4px; margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #333; border-radius: 2px; min-height: 20px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        rows_widget = QWidget()
        rows_widget.setStyleSheet("background: transparent;")
        rows_layout = QVBoxLayout(rows_widget)
        rows_layout.setContentsMargins(0, 0, 0, 0)
        rows_layout.setSpacing(6)

        for i in range(6):
            row = _VerseRow(i)
            row.activated.connect(self.verse_activated.emit)
            row.unmap_requested.connect(self.unmap_requested.emit)
            self._rows.append(row)
            rows_layout.addWidget(row)

        rows_layout.addStretch()
        scroll.setWidget(rows_widget)
        root.addWidget(scroll, 1)

        # ── 하단 안내
        hint = QLabel("슬라이드 패널에서 더블클릭하면\n현재 절에 매핑됩니다")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet(
            "font-size: 10px; color: #444; border: none; padding: 4px 0;"
        )
        root.addWidget(hint)

    def show_for_hotspot(
        self,
        hotspot: Hotspot,
        active_verse: int,
        get_image_fn,
    ) -> None:
        self._hotspot = hotspot
        self._active_verse = active_verse
        self._get_image = get_image_fn
        self._refresh()
        self.show()

    def refresh(
        self,
        hotspot: Hotspot | None = None,
        active_verse: int | None = None,
        get_image_fn=None,
    ) -> None:
        if hotspot is not None:
            self._hotspot = hotspot
        if active_verse is not None:
            self._active_verse = active_verse
        if get_image_fn is not None:
            self._get_image = get_image_fn
        if self.isVisible():
            self._refresh()

    def set_active_verse(self, verse_index: int) -> None:
        self._active_verse = verse_index
        for i, row in enumerate(self._rows):
            row.set_active(i == verse_index)

    def _refresh(self) -> None:
        if not self._hotspot:
            return

        self._title.setText(f"핫스팟  #{self._hotspot.order + 1}")
        lyric = getattr(self._hotspot, "lyric", "") or ""
        self._subtitle.setText(lyric if lyric else "절별 슬라이드 매핑")

        for i, row in enumerate(self._rows):
            slide_idx = self._hotspot.get_slide_index(i)
            row.set_mapped(slide_idx, self._get_image)
            row.set_active(i == self._active_verse)

    def _on_close(self) -> None:
        self.hide()
        self.closed.emit()
