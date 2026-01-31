from pathlib import Path
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QFrame,
    QSizePolicy,
    QFileDialog,
)
from PySide6.QtGui import QFont, QIcon, QColor
from PySide6.QtCore import Qt, Signal, QSize


class ProjectLauncher(QWidget):
    """애플리케이션 시작 시 표시되는 프로젝트 선택 화면"""

    project_selected = Signal(str)  # 프로젝트 경로
    song_selected = Signal(str)  # 단일 곡 폴더 경로
    new_project_requested = Signal()
    new_song_requested = Signal()  # 새 곡 생성 요청
    open_project_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        # 전체 위젯의 강제 배경색 제거 (부모 스타일 따름)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(60, 50, 60, 50)
        layout.setSpacing(40)

        # 1. 헤더 (로고/타이틀)
        header = QVBoxLayout()
        title = QLabel("FLOW")
        title.setStyleSheet("""
            font-size: 56px; 
            font-weight: 900; 
            color: #2196f3; 
            letter-spacing: 2px;
        """)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addWidget(title)

        subtitle = QLabel("슬라이드 이동을 더 편리하게")
        subtitle.setStyleSheet("font-size: 16px; color: #888; font-weight: 400;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addWidget(subtitle)
        layout.addLayout(header)

        # 2. 메인 영역
        content_layout = QHBoxLayout()
        content_layout.setSpacing(50)

        # 왼쪽: 시작 옵션 (심플 레이아웃으로 복구)
        actions_layout = QVBoxLayout()
        actions_layout.setSpacing(15)
        actions_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        label_start = QLabel("시작하기")
        label_start.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: #ccc; margin-bottom: 5px;"
        )
        actions_layout.addWidget(label_start)

        btn_new = QPushButton("📄 새 프로젝트 만들기")
        btn_new.setFixedSize(220, 52)
        btn_new.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_new.setStyleSheet("""
            QPushButton {
                background-color: #2196f3; color: white; border: none; border-radius: 8px; font-size: 14px; font-weight: bold;
            }
            QPushButton:hover { background-color: #1e88e5; }
        """)
        btn_new.clicked.connect(self.new_project_requested.emit)
        actions_layout.addWidget(btn_new)

        btn_new_song = QPushButton("🎵 새 곡 만들기")
        btn_new_song.setFixedSize(220, 52)
        btn_new_song.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_new_song.setStyleSheet("""
            QPushButton {
                background-color: #4caf50; color: white; border: none; border-radius: 8px; font-size: 14px; font-weight: bold;
            }
            QPushButton:hover { background-color: #43a047; }
        """)
        btn_new_song.clicked.connect(self.new_song_requested.emit)
        actions_layout.addWidget(btn_new_song)

        btn_open = QPushButton("📂 프로젝트 열기...")
        btn_open.setFixedSize(220, 52)
        btn_open.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_open.setStyleSheet("""
            QPushButton {
                background-color: #333; color: #ccc; border: 1px solid #444; border-radius: 8px; font-size: 14px;
            }
            QPushButton:hover { background-color: #444; color: white; }
        """)
        btn_open.clicked.connect(self.open_project_requested.emit)
        actions_layout.addWidget(btn_open)

        btn_song = QPushButton("🎵 곡 폴더 열기 (단독 편집)")
        btn_song.setFixedSize(220, 52)
        btn_song.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_song.setStyleSheet("""
            QPushButton {
                background-color: #333; color: #ccc; border: 1px solid #444; border-radius: 8px; font-size: 14px;
            }
            QPushButton:hover { background-color: #444; color: #ffeb3b; border: 1px solid #fbc02d; }
        """)
        btn_song.clicked.connect(self._on_open_song_clicked)
        actions_layout.addWidget(btn_song)

        content_layout.addLayout(actions_layout)

        # 오른쪽: 최근 프로젝트 목록 (고대비 카드 스타일 유지)
        recent_panel = QFrame()
        recent_panel.setStyleSheet("""
            QFrame {
                background-color: #2a2a2a;
                border-radius: 12px;
                border: 1px solid #3d3d3d;
            }
            QLabel { border: none; background: transparent; }
        """)
        recent_layout = QVBoxLayout(recent_panel)
        recent_layout.setContentsMargins(20, 25, 20, 25)

        recent_label = QLabel("최근 사용한 프로젝트")
        recent_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #fff;")
        recent_layout.addWidget(recent_label)
        recent_layout.addSpacing(10)

        self.recent_list = QListWidget()
        self.recent_list.setStyleSheet("""
            QListWidget {
                background-color: transparent; border: none; outline: none;
            }
            QListWidget::item {
                background-color: #333;
                border-radius: 6px;
                margin-bottom: 6px;
                padding: 12px;
                color: #fff;
                border: 1px solid transparent;
            }
            QListWidget::item:hover {
                background-color: #3d3d3d;
                border: 1px solid #2196f3;
            }
            QListWidget::item:selected {
                background-color: #444;
                border: 1px solid #2196f3;
            }
            QScrollBar:vertical {
                border: none;
                background: #2a2a2a;
                width: 8px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #444;
                min-height: 20px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background: #555;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        self.recent_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.recent_list.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.recent_list.setWordWrap(True)
        recent_layout.addWidget(self.recent_list)

        content_layout.addWidget(recent_panel, 1)
        layout.addLayout(content_layout)

        # 3. 푸터
        footer = QLabel("v1.0.0 | Flow")
        footer.setStyleSheet("color: #555; font-size: 11px;")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(footer)

    def set_recent_projects(self, projects: list[str]):
        """최근 프로젝트 목록 갱신 (가독성 강화된 커스텀 텍스트)"""
        self.recent_list.clear()
        for p_path in projects:
            path = Path(p_path)
            # 폴더명 (프로젝트 이름으로 가정)
            name = path.parent.name if path.name == "project.json" else path.stem

            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, p_path)

            # 불필요한 기호 제거 및 깔끔한 텍스트 구성
            display_text = f"{name}\n{p_path}"
            item.setText(display_text)

            # 폰트 설정
            font = QFont("Malgun Gothic")
            font.setPixelSize(14)
            font.setBold(True)
            item.setFont(font)

            self.recent_list.addItem(item)

    def _on_item_double_clicked(self, item):
        path = item.data(Qt.ItemDataRole.UserRole)
        self.project_selected.emit(path)

    def _on_open_song_clicked(self):
        """곡 폴더 직접 선택 (유효성 검사 포함)"""
        folder_str = QFileDialog.getExistingDirectory(
            self, "편집할 곡 폴더 선택", "", QFileDialog.Option.ShowDirsOnly
        )
        if not folder_str:
            return

        folder = Path(folder_str)

        # 1. 선택한 폴더에 song.json이 있는지 확인
        if (folder / "song.json").exists():
            self.song_selected.emit(str(folder))
            return

        # 2. 실수로 sheets/ 폴더 등을 선택한 경우 부모 폴더 확인
        if (folder.parent / "song.json").exists():
            self.song_selected.emit(str(folder.parent))
            return

        # 3. 유효하지 않은 폴더인 경우 경고
        from PySide6.QtWidgets import QMessageBox

        QMessageBox.warning(
            self,
            "유효하지 않은 폴더",
            "선택한 폴더 또는 부모 폴더에 'song.json' 파일이 없습니다.\n정확한 곡 폴더를 선택해주세요.",
        )
