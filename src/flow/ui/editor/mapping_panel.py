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
from flow.ui.styles import (
    BG_DEEP, BG_SURFACE, BG_ELEVATED,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_TERTIARY, TEXT_QUAT,
    ACCENT, ACCENT_INTER, RED, GREEN,
    SURFACE_GHOST, SURFACE_SUBTLE, SURFACE_RAISED,
    BORDER_SUBTLE_RGBA, BORDER_STANDARD_RGBA, BORDER_FOCUS,
    FONT_XS, FONT_SM, FONT_MD, FONT_LG, FONT_TITLE, FW_REGULAR, FW_MEDIUM, FW_SEMI,
    RADIUS_SM, RADIUS_MD, SP_XS, SP_SM, SP_MD,
)

_PANEL_W = 260
_THUMB_W = _PANEL_W - 32  # left/right padding
_THUMB_H = int(_THUMB_W * 9 / 16)

_VERSE_NAMES = ["1절", "2절", "3절", "4절", "5절", "후렴"]
# 절 라벨용 차분한 무채색 — 액센트는 active 상태에만 등장하도록
_VERSE_LABEL_COLOR = TEXT_SECONDARY


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

        self._badge = QLabel(_VERSE_NAMES[self._verse_index])
        self._badge.setFixedHeight(20)
        self._badge.setMinimumWidth(34)
        self._badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._badge.setStyleSheet(
            f"background: transparent; color: {_VERSE_LABEL_COLOR}; "
            f"font-size: {FONT_SM}px; font-weight: {FW_MEDIUM}; border: none;"
        )
        header.addWidget(self._badge)

        self._slide_label = QLabel("—")
        self._slide_label.setStyleSheet(
            f"font-size: {FONT_SM}px; color: {TEXT_QUAT}; border: none;"
        )
        header.addWidget(self._slide_label)
        header.addStretch()

        self._btn_unmap = QPushButton("해제")
        self._btn_unmap.setFixedHeight(20)
        self._btn_unmap.setMinimumWidth(40)
        self._btn_unmap.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_unmap.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_unmap.setStyleSheet(f"""
            QPushButton {{
                background: {SURFACE_GHOST}; color: {RED};
                border: 1px solid {BORDER_SUBTLE_RGBA};
                border-radius: {RADIUS_SM}px; font-size: {FONT_XS}px; padding: 0;
            }}
            QPushButton:hover {{
                background: {SURFACE_SUBTLE};
                border-color: {RED};
            }}
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
                        f"font-size: {FONT_SM}px; color: {GREEN}; border: none;"
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
        self._slide_label.setStyleSheet(
            f"font-size: {FONT_SM}px; color: {TEXT_QUAT}; border: none;"
        )
        self._btn_unmap.hide()
        self._is_mapped = False
        self._refresh_style()

    def set_active(self, active: bool) -> None:
        self._is_active = active
        self._refresh_style()

    def _refresh_style(self) -> None:
        # active: white-overlay + ACCENT 좌측 바 (Linear 패턴)
        # mapped: 미묘한 white-overlay
        # idle:   거의 투명
        if self._is_active:
            row_style = (
                f"QFrame#VerseRow {{ background: {SURFACE_SUBTLE}; "
                f"border: 1px solid {BORDER_STANDARD_RGBA}; "
                f"border-left: 3px solid {ACCENT_INTER}; "
                f"border-radius: {RADIUS_MD}px; }}"
            )
            thumb_border = f"1px solid {BORDER_STANDARD_RGBA}"
        elif self._is_mapped:
            row_style = (
                f"QFrame#VerseRow {{ background: {SURFACE_GHOST}; "
                f"border: 1px solid {BORDER_STANDARD_RGBA}; "
                f"border-radius: {RADIUS_MD}px; }}"
            )
            thumb_border = f"1px solid {BORDER_SUBTLE_RGBA}"
        else:
            row_style = (
                f"QFrame#VerseRow {{ background: transparent; "
                f"border: 1px dashed {BORDER_SUBTLE_RGBA}; "
                f"border-radius: {RADIUS_MD}px; }}"
            )
            thumb_border = f"1px dashed {BORDER_SUBTLE_RGBA}"

        self.setStyleSheet(row_style)
        self._thumb.setStyleSheet(
            f"background: {BG_DEEP}; border: {thumb_border}; "
            f"border-radius: {RADIUS_SM}px; "
            f"color: {TEXT_QUAT}; font-size: {FONT_SM}px;"
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
        self.setStyleSheet(f"""
            QFrame#MappingPanel {{
                background: {BG_SURFACE};
                border-left: 1px solid {BORDER_SUBTLE_RGBA};
            }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(SP_SM, SP_SM + 2, SP_SM, SP_SM + 2)
        root.setSpacing(SP_SM - 2)

        # ── 헤더
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        self._title = QLabel("핫스팟 매핑")
        self._title.setStyleSheet(
            f"font-size: {FONT_TITLE}px; font-weight: {FW_SEMI}; "
            f"color: {TEXT_PRIMARY}; border: none;"
        )
        header.addWidget(self._title)
        header.addStretch()

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(24, 24)
        btn_close.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {TEXT_TERTIARY}; border: none;
                font-size: {FONT_TITLE}px; padding: 0;
            }}
            QPushButton:hover {{ color: {TEXT_PRIMARY}; }}
        """)
        btn_close.clicked.connect(self._on_close)
        header.addWidget(btn_close)
        root.addLayout(header)

        # 부제
        self._subtitle = QLabel()
        self._subtitle.setStyleSheet(
            f"font-size: {FONT_SM}px; color: {TEXT_TERTIARY}; "
            "border: none;"
        )
        root.addWidget(self._subtitle)

        # 구분선 (헤어라인)
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(
            f"background: {BORDER_SUBTLE_RGBA}; max-height: 1px; border: none;"
        )
        root.addWidget(sep)

        # ── 절 행 스크롤 영역 — 글로벌 스크롤바 스타일 사용
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
        )

        rows_widget = QWidget()
        rows_widget.setStyleSheet("background: transparent;")
        rows_layout = QVBoxLayout(rows_widget)
        rows_layout.setContentsMargins(0, 0, 0, 0)
        rows_layout.setSpacing(SP_XS + 2)

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
            f"font-size: {FONT_XS}px; color: {TEXT_QUAT}; "
            "border: none; padding: 4px 0;"
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
