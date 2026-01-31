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


class SettingsDialog(QDialog):
    """애플리케이션 환경설정 다이얼로그"""

    def __init__(self, config_service, parent=None):
        super().__init__(parent)
        self.config_service = config_service
        self.setWindowTitle("환경설정")
        self.setMinimumWidth(350)
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # 1. 일반 설정 섹션
        group = QFrame()
        group.setStyleSheet("QFrame { background-color: #2a2a2a; border-radius: 8px; }")
        form = QFormLayout(group)
        form.setContentsMargins(15, 15, 15, 15)
        form.setSpacing(10)

        title = QLabel("일반 설정")
        title.setStyleSheet("font-weight: bold; color: #2196f3; font-size: 14px;")
        layout.addWidget(title)

        # 최대 절 수 설정
        self.verse_count = QSpinBox()
        self.verse_count.setRange(1, 10)
        self.verse_count.setFixedWidth(80)
        self.verse_count.setStyleSheet("""
            QSpinBox { 
                background-color: #333; color: white; border: 1px solid #444; 
                padding: 4px; border-radius: 4px;
            }
        """)

        lbl_verse = QLabel("최대 절(Layer) 수:")
        lbl_verse.setStyleSheet("color: #ccc;")
        form.addRow(lbl_verse, self.verse_count)

        layout.addWidget(group)
        layout.addStretch()

        # 하단 버튼
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_cancel = QPushButton("취소")
        btn_cancel.setFixedSize(80, 30)
        btn_cancel.clicked.connect(self.reject)
        btn_cancel.setStyleSheet(
            "background-color: #444; color: white; border: none; border-radius: 4px;"
        )

        btn_save = QPushButton("확인")
        btn_save.setFixedSize(80, 30)
        btn_save.clicked.connect(self._on_save_clicked)
        btn_save.setStyleSheet(
            "background-color: #2196f3; color: white; border: none; border-radius: 4px; font-weight: bold;"
        )

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
