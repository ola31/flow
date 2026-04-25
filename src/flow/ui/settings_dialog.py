from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QPushButton,
    QFrame,
    QFormLayout,
)
from PySide6.QtCore import Qt

from flow.ui.styles import (
    BG_ELEVATED, TEXT_PRIMARY, TEXT_SECONDARY, BORDER_STANDARD_RGBA,
    SURFACE_GHOST, FONT_MD, FONT_LG, FW_MEDIUM, FW_SEMI,
    RADIUS_MD, RADIUS_LG, SP_MD, SP_LG, SP_XL,
)


class SettingsDialog(QDialog):
    """애플리케이션 환경설정 다이얼로그"""

    def __init__(self, config_service, parent=None):
        super().__init__(parent)
        self.config_service = config_service
        self.setWindowTitle("환경설정")
        self.setMinimumWidth(360)
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SP_XL, SP_XL, SP_XL, SP_XL)
        layout.setSpacing(SP_LG)

        # 섹션 타이틀
        title = QLabel("일반 설정")
        title.setStyleSheet(
            f"font-weight: {FW_SEMI}; color: {TEXT_PRIMARY}; font-size: {FONT_LG}px;"
        )
        layout.addWidget(title)

        # 1. 일반 설정 섹션
        group = QFrame()
        group.setStyleSheet(
            f"QFrame {{ background-color: {BG_ELEVATED}; "
            f"border: 1px solid {BORDER_STANDARD_RGBA}; "
            f"border-radius: {RADIUS_LG}px; }}"
        )
        form = QFormLayout(group)
        form.setContentsMargins(SP_LG, SP_LG, SP_LG, SP_LG)
        form.setSpacing(SP_MD)

        # 최대 절 수 설정
        self.verse_count = QSpinBox()
        self.verse_count.setRange(1, 10)
        self.verse_count.setFixedWidth(80)
        self.verse_count.setStyleSheet(
            f"QSpinBox {{ background-color: {SURFACE_GHOST}; color: {TEXT_PRIMARY}; "
            f"border: 1px solid {BORDER_STANDARD_RGBA}; "
            f"padding: 4px; border-radius: {RADIUS_MD}px; "
            f"font-weight: {FW_MEDIUM}; }}"
        )

        lbl_verse = QLabel("최대 절(Layer) 수:")
        lbl_verse.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: {FONT_MD}px;")
        form.addRow(lbl_verse, self.verse_count)

        layout.addWidget(group)
        layout.addStretch()

        # 하단 버튼 — 글로벌 스타일 사용 (Cancel: ghost, OK: primary)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_cancel = QPushButton("취소")
        btn_cancel.setFixedSize(80, 32)
        btn_cancel.clicked.connect(self.reject)

        btn_save = QPushButton("확인")
        btn_save.setFixedSize(80, 32)
        btn_save.setProperty("variant", "primary")
        btn_save.clicked.connect(self._on_save_clicked)

        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_save)
        layout.addLayout(btn_layout)

    def _load_settings(self):
        """저장된 설정값 불러오기"""
        max_verses = self.config_service.get_max_verses()
        self.verse_count.setValue(max_verses)

    def _on_save_clicked(self):
        """설정 저장 및 다이얼로그 닫기"""
        self.config_service.set_max_verses(self.verse_count.value())
        self.accept()
