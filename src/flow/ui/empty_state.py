"""빈 상태(Empty State) 위젯.

Linear 등 상용 SW가 prototype과 구분되는 핵심 요소 중 하나는 빈 상태도
하나의 디자인된 화면이라는 점이다. "아직 없습니다" 같은 평범한 텍스트
대신 아이콘 + 설명 + 선택적 CTA 패턴으로 통일한다.

Usage:
    from flow.ui.empty_state import EmptyState

    es = EmptyState(
        icon="music_note",
        title="곡 라이브러리가 비어있습니다",
        description="새 곡을 만들거나 외부 폴더에서 가져오세요",
        cta_text="새 곡 만들기",
        on_cta=self._on_new_song,
    )
    layout.addWidget(es)
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from flow.ui.icons import icon_label
from flow.ui.styles import (
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_TERTIARY,
    FONT_SM, FONT_MD, FONT_LG, FW_REGULAR, FW_MEDIUM, FW_SEMI,
    SP_SM, SP_MD, SP_LG, SP_XL, SP_2XL,
)


class EmptyState(QFrame):
    """공용 빈 상태 위젯 — 아이콘 + 제목 + 설명 + (선택) CTA.

    스타일은 토큰 기반. 부모 컨테이너에 그대로 추가하면 자동으로
    중앙 정렬되고 적절한 padding을 갖는다.
    """

    def __init__(
        self,
        icon: str = "search",
        title: str = "",
        description: str = "",
        cta_text: str = "",
        on_cta: Callable[[], None] | None = None,
        *,
        compact: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("EmptyState")
        self.setStyleSheet(
            "QFrame#EmptyState { background: transparent; border: none; }"
        )

        root = QVBoxLayout(self)
        root.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.setSpacing(SP_SM if compact else SP_MD)
        if compact:
            root.setContentsMargins(SP_LG, SP_LG, SP_LG, SP_LG)
        else:
            root.setContentsMargins(SP_2XL, SP_2XL, SP_2XL, SP_2XL)

        # 아이콘 — 큰 사이즈, 절제된 색상
        if icon:
            icon_size = 28 if compact else 36
            ic = icon_label(icon, icon_size, TEXT_TERTIARY, self)
            ic.setFixedSize(icon_size + 12, icon_size + 12)
            ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
            root.addWidget(ic, 0, Qt.AlignmentFlag.AlignCenter)

        # 제목 — TEXT_PRIMARY, semibold
        if title:
            title_lbl = QLabel(title)
            title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            title_size = FONT_MD if compact else FONT_LG
            title_lbl.setStyleSheet(
                f"color: {TEXT_PRIMARY}; font-size: {title_size}px; "
                f"font-weight: {FW_SEMI}; background: transparent;"
            )
            title_lbl.setWordWrap(True)
            root.addWidget(title_lbl)

        # 설명 — TEXT_TERTIARY, 더 작게
        if description:
            desc_lbl = QLabel(description)
            desc_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            desc_lbl.setWordWrap(True)
            desc_size = FONT_SM if compact else FONT_MD
            desc_lbl.setStyleSheet(
                f"color: {TEXT_TERTIARY}; font-size: {desc_size}px; "
                f"font-weight: {FW_REGULAR}; background: transparent;"
            )
            desc_lbl.setMaximumWidth(360)
            root.addWidget(desc_lbl)

        # CTA — 옵션
        if cta_text and on_cta is not None:
            cta = QPushButton(cta_text)
            cta.setFixedHeight(34)
            cta.setMinimumWidth(140)
            cta.setCursor(Qt.CursorShape.PointingHandCursor)
            cta.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            cta.setProperty("variant", "primary")
            cta.clicked.connect(on_cta)
            row = QFrame()
            row.setStyleSheet("background: transparent;")
            row_layout = QVBoxLayout(row)
            row_layout.setContentsMargins(0, SP_MD, 0, 0)
            row_layout.addWidget(cta, 0, Qt.AlignmentFlag.AlignCenter)
            root.addWidget(row)
