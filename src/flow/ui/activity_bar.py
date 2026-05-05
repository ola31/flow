"""Activity Bar — VS Code 패턴.

40px 너비의 영구 좌측 nav. 모드와 무관하게 항상 같은 자리에 있음 →
앱의 시각적 anchor 역할.

상단: 워크스페이스/홈/설정 같은 최상위 액션
하단: 부가 기능 (theme toggle 등은 추후)
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from flow.ui.icons import icon_qicon
from flow.ui.styles import (
    BG_DEEP, BG_SURFACE,
    TEXT_TERTIARY, TEXT_PRIMARY,
    BORDER_SUBTLE_RGBA, SURFACE_SUBTLE,
    RADIUS_MD, SP_XS, SP_SM,
)


class ActivityBar(QFrame):
    """좌측 영구 nav 스트립.

    Signals:
        home_requested: 홈으로 이동
        settings_requested: 설정 다이얼로그 열기
    """

    home_requested = Signal()
    library_requested = Signal()
    projects_requested = Signal()
    settings_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ActivityBar")
        self.setFixedWidth(52)
        self.setStyleSheet(f"""
            QFrame#ActivityBar {{
                background-color: {BG_SURFACE};
                border-right: 1px solid {BORDER_SUBTLE_RGBA};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SP_XS + 2, SP_SM + 2, SP_XS + 2, SP_SM + 2)
        layout.setSpacing(SP_XS + 2)

        # 상단 액션
        self._btn_home = self._make_button("home", "홈으로 이동")
        self._btn_home.clicked.connect(self.home_requested.emit)
        layout.addWidget(self._btn_home)

        self._btn_projects = self._make_button("view_list", "프로젝트")
        self._btn_projects.clicked.connect(self.projects_requested.emit)
        layout.addWidget(self._btn_projects)

        self._btn_library = self._make_button("library_music", "곡 라이브러리")
        self._btn_library.clicked.connect(self.library_requested.emit)
        layout.addWidget(self._btn_library)

        layout.addStretch()

        # 하단 액션
        self._btn_settings = self._make_button("settings", "환경설정")
        self._btn_settings.clicked.connect(self.settings_requested.emit)
        layout.addWidget(self._btn_settings)

    def _make_button(self, icon_name: str, tooltip: str) -> QToolButton:
        btn = QToolButton()
        btn.setIcon(icon_qicon(icon_name, 26, TEXT_TERTIARY))
        from PySide6.QtCore import QSize
        btn.setIconSize(QSize(26, 26))
        btn.setFixedSize(40, 40)
        btn.setToolTip(tooltip)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.setStyleSheet(f"""
            QToolButton {{
                background: transparent;
                border: none;
                border-radius: {RADIUS_MD}px;
            }}
            QToolButton:hover {{
                background: {SURFACE_SUBTLE};
            }}
            QToolButton:pressed {{
                background: {BG_DEEP};
            }}
        """)
        return btn

    def set_home_enabled(self, enabled: bool) -> None:
        """라이브 모드 등에서 홈 액션 비활성화 시 호출."""
        self._btn_home.setEnabled(enabled)
        self._btn_home.setToolTip(
            "홈으로 이동" if enabled
            else "라이브 모드 중에는 홈으로 이동할 수 없습니다"
        )
