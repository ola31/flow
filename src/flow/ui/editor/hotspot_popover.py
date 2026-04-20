from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QPoint, QRect, QEvent, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtGui import QPixmap, QColor
from PySide6.QtWidgets import (
    QApplication,
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
        self._info.setStyleSheet("font-size: 12px; font-weight: 500; color: #ccc;")
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
                border-radius: 4px; font-size: 11px; padding: 0 10px;
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

        # 팝오버 외부 클릭 시 자동 닫기 — 앱 전역 이벤트 필터 설치
        # (중복 설치 방지를 위해 먼저 제거)
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
            app.installEventFilter(self)

    def eventFilter(self, obj, event) -> bool:
        """팝오버 외부 클릭 자동 닫기.

        팝오버 자신이나 캔버스(부모) 안의 클릭은 통과시켜서 기존 핸들러가
        처리하도록 하고, 그 외 영역(슬라이드 패널, 툴바 등) 클릭은 즉시 닫는다.
        이벤트 자체는 소비하지 않아서 원본 위젯도 그대로 클릭을 받는다.

        dismiss는 QTimer로 지연시켜 이벤트 필터 내 재진입(hide 중 paint/focus 등)
        에 의한 crash를 피한다.
        """
        if event.type() == QEvent.Type.MouseButtonPress and self.isVisible():
            try:
                global_pos = event.globalPosition().toPoint()
            except AttributeError:
                global_pos = event.globalPos()

            # 1) 팝오버 자신 영역 안: 통과
            popover_rect = QRect(self.mapToGlobal(QPoint(0, 0)), self.size())
            if popover_rect.contains(global_pos):
                return False

            # 2) 부모(캔버스) 영역 안: 캔버스의 mousePressEvent가 기존 로직으로
            #    (같은 핫스팟 재클릭 토글, 빈 영역 dismiss 등) 처리하도록 통과
            parent = self.parentWidget()
            if parent is not None:
                parent_rect = QRect(parent.mapToGlobal(QPoint(0, 0)), parent.size())
                if parent_rect.contains(global_pos):
                    return False

            # 3) 그 외 모든 영역: 다음 이벤트 루프에서 안전하게 닫기
            QTimer.singleShot(0, self.dismiss)
        return False

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
        parent = self.parentWidget()
        if not parent:
            return

        self.ensurePolished()
        w = self.sizeHint().width()
        h = self.sizeHint().height()

        # 기본 위치: anchor 아래 중앙 (부모 로컬 좌표)
        x = anchor.x() - w // 2
        y = anchor.y() + 24
        margin = 8

        # 1. 부모 위젯 경계 내 클램핑
        pw, ph = parent.width(), parent.height()
        if x < margin:
            x = margin
        if x + w > pw - margin:
            x = pw - margin - w
        if y + h > ph - margin:
            y = anchor.y() - h - 24
        if y < margin:
            y = margin

        # 2. 멀티모니터 대응: 화면 경계 내 클램핑 (글로벌 좌표 기준)
        global_pos = parent.mapToGlobal(QPoint(x, y))
        screen = QGuiApplication.screenAt(parent.mapToGlobal(anchor))
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        if screen:
            avail: QRect = screen.availableGeometry()
            gx, gy = global_pos.x(), global_pos.y()
            if gx < avail.left() + margin:
                gx = avail.left() + margin
            if gx + w > avail.right() - margin:
                gx = avail.right() - margin - w
            if gy + h > avail.bottom() - margin:
                gy = parent.mapToGlobal(anchor).y() - h - 24
            if gy < avail.top() + margin:
                gy = avail.top() + margin
            local = parent.mapFromGlobal(QPoint(gx, gy))
            x, y = local.x(), local.y()

        self.move(x, y)

    def _on_unmap(self) -> None:
        self.unmap_requested.emit()
        self.dismiss()

    def dismiss(self) -> None:
        self._remove_global_filter()
        self.hide()
        self.closed.emit()

    def _remove_global_filter(self) -> None:
        """전역 이벤트 필터 해제. 중복 호출 안전."""
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)

    def hideEvent(self, event) -> None:
        # 팝오버가 어떤 이유로든 숨겨지면 필터도 함께 해제해 dangling 방지
        self._remove_global_filter()
        super().hideEvent(event)

    def closeEvent(self, event) -> None:
        self._remove_global_filter()
        super().closeEvent(event)
