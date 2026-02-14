from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtGui import QPixmap, QColor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QGraphicsDropShadowEffect,
)

from flow.domain.hotspot import Hotspot

_POPOVER_W = 340


class HotspotPopover(QFrame):
    mapping_requested = Signal(int)
    unmap_requested = Signal()
    closed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("HotspotPopover")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

        self._hotspot: Hotspot | None = None
        self._verse_index: int = 0
        self._slide_count: int = 0
        self._get_slide_image = None

        self._setup_ui()
        self.hide()

    def _setup_ui(self) -> None:
        self.setFixedWidth(_POPOVER_W)
        self.setStyleSheet("""
            QFrame#HotspotPopover {
                background: #2a2a2a;
                border: 1px solid #555;
                border-radius: 10px;
            }
        """)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 120))
        self.setGraphicsEffect(shadow)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)

        self._info = QLabel()
        self._info.setStyleSheet("font-size: 12px; font-weight: bold; color: #ccc;")
        root.addWidget(self._info)

        self._preview_row = QWidget()
        preview_layout = QVBoxLayout(self._preview_row)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(6)

        thumb_w = _POPOVER_W - 24
        thumb_h = int(thumb_w * 9 / 16)
        self._preview_img = QLabel()
        self._preview_img.setFixedSize(thumb_w, thumb_h)
        self._preview_img.setScaledContents(True)
        self._preview_img.setStyleSheet(
            "background: #111; border: 1px solid #333; border-radius: 6px;"
        )
        self._preview_img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_layout.addWidget(self._preview_img)

        bottom_row = QHBoxLayout()
        bottom_row.setContentsMargins(0, 0, 0, 0)
        bottom_row.setSpacing(8)

        self._mapping_label = QLabel()
        self._mapping_label.setStyleSheet("font-size: 12px; color: #aaa;")
        bottom_row.addWidget(self._mapping_label)

        bottom_row.addStretch()

        self._btn_unmap = QPushButton("매핑 해제")
        self._btn_unmap.setFixedHeight(26)
        self._btn_unmap.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_unmap.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_unmap.setStyleSheet("""
            QPushButton {
                background: #444; color: #e57373; border: none;
                border-radius: 4px; font-size: 11px; font-weight: bold; padding: 0 10px;
            }
            QPushButton:hover { background: #555; }
        """)
        self._btn_unmap.clicked.connect(self._on_unmap)
        bottom_row.addWidget(self._btn_unmap)

        preview_layout.addLayout(bottom_row)
        root.addWidget(self._preview_row)

        self._no_mapping_row = QWidget()
        no_map_layout = QHBoxLayout(self._no_mapping_row)
        no_map_layout.setContentsMargins(0, 0, 0, 0)

        no_map_label = QLabel("매핑 없음 — 슬라이드를 더블클릭하여 매핑")
        no_map_label.setStyleSheet("font-size: 11px; color: #888;")
        no_map_layout.addWidget(no_map_label)

        self._no_mapping_row.hide()
        root.addWidget(self._no_mapping_row)

    def set_slide_source(self, count: int, get_image_fn) -> None:
        self._slide_count = count
        self._get_slide_image = get_image_fn

    def show_for_hotspot(
        self,
        hotspot: Hotspot,
        verse_index: int,
        anchor: QPoint,
    ) -> None:
        self._hotspot = hotspot
        self._verse_index = verse_index

        self._update_content()
        self._position_at(anchor)
        self.show()
        self.raise_()

    def _update_content(self) -> None:
        if not self._hotspot:
            return

        h = self._hotspot
        v_name = f"{self._verse_index + 1}절" if self._verse_index < 5 else "후렴"
        self._info.setText(f"#{h.order + 1}  •  {v_name}")

        slide_idx = h.get_slide_index(self._verse_index)

        if slide_idx >= 0:
            self._preview_row.show()
            self._no_mapping_row.hide()
            self._mapping_label.setText(f"슬라이드 {slide_idx + 1}")
            self._btn_unmap.setEnabled(True)

            if self._get_slide_image:
                try:
                    qimg = self._get_slide_image(slide_idx)
                    if qimg:
                        self._preview_img.setPixmap(QPixmap.fromImage(qimg))
                    else:
                        self._preview_img.setText("?")
                except Exception:
                    self._preview_img.setText("?")
            else:
                self._preview_img.setText("?")
        else:
            self._preview_row.hide()
            self._no_mapping_row.show()

    def _position_at(self, anchor: QPoint) -> None:
        if not self.parentWidget():
            return

        parent = self.parentWidget()
        pw, ph = parent.width(), parent.height()
        w, h = self.sizeHint().width(), self.sizeHint().height()

        x = anchor.x() - w // 2
        y = anchor.y() + 24

        if x < 8:
            x = 8
        if x + w > pw - 8:
            x = pw - w - 8
        if y + h > ph - 8:
            y = anchor.y() - h - 24

        self.move(x, y)

    def _on_unmap(self) -> None:
        self.unmap_requested.emit()
        self.dismiss()

    def dismiss(self) -> None:
        self.hide()
        self.closed.emit()
