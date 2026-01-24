"""Flow 메인 윈도우

편집/라이브 모드를 통합한 메인 애플리케이션 윈도우
"""

from pathlib import Path
import shutil

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QSplitter,
    QToolBar, QStatusBar, QFileDialog, QMessageBox, QTabWidget,
    QLabel, QFrame, QButtonGroup, QRadioButton, QPushButton, QToolButton,
    QLineEdit, QTextEdit, QPlainTextEdit, QStackedWidget, QSizePolicy
)
from PySide6.QtGui import QAction, QKeySequence, QPixmap, QUndoStack
from PySide6 import QtGui
from PySide6.QtCore import Qt, QTimer, QEvent
from flow.ui.undo_commands import (
    AddHotspotCommand, RemoveHotspotCommand, MoveHotspotCommand, 
    MapSlideCommand, UnlinkAllSlidesCommand
)

from flow.domain.project import Project
from flow.domain.score_sheet import ScoreSheet
from flow.domain.hotspot import Hotspot
from flow.repository.project_repository import ProjectRepository

from flow.ui.editor.song_list_widget import SongListWidget
from flow.ui.editor.score_canvas import ScoreCanvas
from flow.ui.editor.slide_preview_panel import SlidePreviewPanel
from flow.ui.display.display_window import DisplayWindow
from flow.services.slide_manager import SlideManager
from flow.services.config_service import ConfigService
from flow.ui.project_launcher import ProjectLauncher


class MainWindow(QMainWindow):
    """Flow 메인 윈도우"""
    
    def __init__(self) -> None:
        super().__init__()
        
        self._project: Project | None = None
        self._project_path: Path | None = None
        self._repo = ProjectRepository(Path.home() / "flow_projects")
        self._config_service = ConfigService()
        
        # 송출 관련
        self._display_window: DisplayWindow | None = None
        self._slide_manager = SlideManager()
        from flow.ui.live.live_controller import LiveController
        self._live_controller = LiveController(self, slide_manager=self._slide_manager)
        
        # Undo/Redo 관련
        self._undo_stack = QUndoStack(self)
        self._undo_stack.setUndoLimit(100)
        self._undo_stack.cleanChanged.connect(self._on_undo_stack_clean_changed)
        
        # 슬라이드 클릭/더블클릭 구분용 타이머
        self._slide_click_timer = QTimer(self)
        self._slide_click_timer.setSingleShot(True)
        self._slide_click_timer.timeout.connect(self._execute_slide_navigation)
        self._pending_slide_index = -1
        
        self._is_dirty = False
        
        self._apply_global_style()
        self._setup_ui()
        self._setup_toolbar()
        self._setup_statusbar()
        self._connect_signals()
        
        # SongListWidget에 메인 윈도우 참조 연결 (경로 획득용)
        self._song_list.set_main_window(self)
        self._song_list._list.installEventFilter(self) # [추가] 곡 목록 키 전역 필터
        
        # Windows 타이틀바 다크 모드 적용
        self._apply_dark_title_bar()
        
        # 앱 시작 시 런처(시작 화면) 표시
        self._show_launcher()

    def _apply_dark_title_bar(self):
        """Windows 10/11에서 타이틀바를 다크 모드로 강제 설정"""
        import sys
        if sys.platform != "win32":
            return
            
        try:
            from ctypes import windll, byref, sizeof, c_int
            # DWMWA_USE_IMMERSIVE_DARK_MODE
            # Windows 11 및 최신 Win 10 (Build 18985+)은 20번 속성 사용
            # 이전 빌드는 19번 사용
            hwnd = int(self.winId())
            value = c_int(1)
            
            # 먼저 20번 시도
            windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, byref(value), sizeof(value))
            # 이전 버전 대응을 위해 19번도 시도
            windll.dwmapi.DwmSetWindowAttribute(hwnd, 19, byref(value), sizeof(value))
        except Exception:
            pass

    def _show_launcher(self):
        """시작 화면(런처) 표시"""
        self._stack.setCurrentIndex(0)
        self._launcher.set_recent_projects(self._config_service.get_recent_projects())
        self._toolbar.hide()
        self._statusbar.hide()
        self.setWindowTitle("Flow - 시작하기")

    def _show_editor(self):
        """편집/라이브 화면 표시"""
        self._stack.setCurrentIndex(1)
        self._toolbar.show()
        self._statusbar.show()
        if self._project:
            self.setWindowTitle(f"Flow - {self._project.name}")

    def _setup_ui(self) -> None:
        """UI 초기화"""
        self.setWindowTitle("Flow - 슬라이드 송출")
        self.setMinimumSize(840, 600)
        
        # 중앙 위젯을 StackedWidget으로 변경
        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)
        
        # 1. 런처 화면 (인덱스 0)
        self._launcher = ProjectLauncher()
        self._stack.addWidget(self._launcher)
        
        # 2. 메인 에디터 화면 (인덱스 1)
        editor_widget = QWidget()
        self._stack.addWidget(editor_widget)
        
        main_layout = QVBoxLayout(editor_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # [NEW] 커스텀 툴바 영역 (항상 다 보이도록 2단 구성 가능하게 QWidget으로 구현)
        self._toolbar = QWidget()
        self._toolbar.setObjectName("CustomToolbar")
        self._toolbar.setFixedHeight(80) # 2단 구성을 위해 높이 확보
        main_layout.addWidget(self._toolbar)
        
        # 전체 수직 스플리터 (상단 슬라이드 영역 / 하단 편집 영역)
        self._v_splitter = QSplitter(Qt.Orientation.Vertical)
        main_layout.addWidget(self._v_splitter)
        
        # 1. 상단: 슬라이드 프리뷰 패널 (PPT 슬라이드 목록)
        self._slide_preview = SlidePreviewPanel()
        self._slide_preview.set_slide_manager(self._slide_manager)
        self._slide_preview.slide_selected.connect(self._on_slide_selected)
        self._slide_preview.slide_double_clicked.connect(self._on_slide_double_clicked)
        self._slide_preview.slide_unlink_all_requested.connect(self._on_slide_unlink_all_requested)
        self._slide_preview._list.installEventFilter(self) # [추가] 슬라이드 목록 키 전역 필터
        # 패널 내부의 로드/닫기 버튼 연동
        self._slide_preview._btn_load.clicked.connect(self._on_load_ppt)
        self._slide_preview._btn_close.clicked.connect(self._on_close_ppt)
        self._v_splitter.addWidget(self._slide_preview)
        
        # 2. 하단: 메인 스플리터 (곡 목록 + 악보 캔버스 + 라이브 패널)
        self._h_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._h_splitter.setStyleSheet("QSplitter::handle { background-color: #333; width: 1px; }")
        self._v_splitter.addWidget(self._h_splitter)
        
        # 초기 비율 설정 (상단 슬라이드 영역은 내용만큼만, 하단이 가득 차도록)
        self._v_splitter.setStretchFactor(0, 0)
        self._v_splitter.setStretchFactor(1, 1)
        self._v_splitter.setHandleWidth(1) # 아주 얇은 구분선
        
        # 왼쪽: 곡 목록
        self._song_list = SongListWidget()
        self._song_list.setMaximumWidth(280)
        self._song_list.setMinimumWidth(180)
        self._h_splitter.addWidget(self._song_list)
        
        # 중앙: 악보 캔버스 영역 (절 선택기 포함)
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)
        
        # [NEW] 절(Verse) 선택바 추가 (초슬림 모드)
        self._verse_container = QWidget()
        self._verse_container.setFixedHeight(28) # 높이 제한
        self._verse_container.setStyleSheet("background-color: #2a2a2a; border-bottom: 1px solid #3d3d3d;")
        verse_bar_layout = QHBoxLayout(self._verse_container)
        verse_bar_layout.setContentsMargins(8, 0, 8, 0)
        verse_bar_layout.setSpacing(4)
        
        lbl = QLabel("📂 LAYER")
        lbl.setStyleSheet("font-size: 10px; font-weight: 900; color: #555; letter-spacing: 1px; padding-right: 4px;")
        verse_bar_layout.addWidget(lbl)
        
        self._verse_group = QButtonGroup(self)
        verses = [("1", 0), ("2", 1), ("3", 2), ("4", 3), ("5", 4), ("후렴", 5)]
        for text, idx in verses:
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setFixedWidth(38 if idx < 5 else 50)
            btn.setFixedHeight(20)
            btn.setStyleSheet("""
                QPushButton { 
                    background-color: #333; 
                    border: 1px solid #444; 
                    border-radius: 4px; 
                    color: #888; 
                    font-size: 10px;
                    font-weight: bold;
                }
                QPushButton:hover { 
                    background-color: #444; 
                    color: white;
                }
                QPushButton:checked { 
                    background-color: #2a3a4f; 
                    color: #2196f3; 
                    font-weight: 900; 
                    border: 1px solid #2196f3; 
                }
            """)
            if idx == 0: btn.setChecked(True)
            self._verse_group.addButton(btn, idx)
            verse_bar_layout.addWidget(btn)
        
        self._verse_group.idClicked.connect(self._on_verse_changed)
        verse_bar_layout.addStretch()
        center_layout.addWidget(self._verse_container)
        
        self._canvas = ScoreCanvas()
        center_layout.addWidget(self._canvas)
        self._h_splitter.addWidget(center_widget)
        
        # 오른쪽: 편집 패널
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        # right_panel.setMaximumWidth(600)  # [수정] 제한을 제거하여 창 크기에 따라 무한 확장 가능하게 함
        right_panel.setMinimumWidth(260)
        
        # Preview 패널 (다음 가사)
        self._preview_panel = QFrame()
        self._preview_panel.setObjectName("PreviewPanel")
        self._preview_panel.setStyleSheet("""
            QFrame#PreviewPanel {
                background-color: #252525;
                border: 1px solid #333;
                border-radius: 12px;
                margin: 5px;
            }
        """)
        preview_layout = QVBoxLayout(self._preview_panel)
        preview_layout.setContentsMargins(5, 5, 5, 5)
        preview_layout.setSpacing(4)
        
        preview_header = QLabel("📺 PREVIEW")
        preview_header.setStyleSheet("font-weight: 800; font-size: 8px; color: #555; letter-spacing: 0.5px;")
        preview_layout.addWidget(preview_header)
        
        self._preview_text = QLabel("미리보기")
        self._preview_text.setStyleSheet("""
            background-color: #111; 
            color: #888; 
            padding: 1px 4px;
            border-radius: 2px;
            font-size: 9px;
            border: 1px solid #222;
        """)
        self._preview_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_text.setWordWrap(True)
        self._preview_text.setFixedHeight(16)
        preview_layout.addWidget(self._preview_text)

        self._preview_image = QLabel()
        self._preview_image.setFixedSize(256, 144) # [수정] 고정 크기(16:9)로 초기 팽창 문제 완전 해결
        self._preview_image.setScaledContents(True) # Qt가 자동으로 비율 맞춤 스케일링
        self._preview_image.setStyleSheet("background-color: black; border: 1px solid #333; border-radius: 4px;")
        self._preview_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_layout.addWidget(self._preview_image, 0, Qt.AlignmentFlag.AlignCenter)
        self._preview_image.hide()
        right_layout.addWidget(self._preview_panel)
        
        # Live 패널 (현재 송출 중)
        self._live_panel = QFrame()
        self._live_panel.setObjectName("LivePanel")
        self._live_panel.setStyleSheet("""
            QFrame#LivePanel {
                background-color: #252525;
                border: 1px solid #ff4444;
                border-radius: 12px;
                margin: 5px;
            }
        """)
        live_layout = QVBoxLayout(self._live_panel)
        live_layout.setContentsMargins(5, 5, 5, 5)
        live_layout.setSpacing(4)
        
        live_header = QLabel("🔴 LIVE")
        live_header.setStyleSheet("font-weight: 800; font-size: 8px; color: #883333; letter-spacing: 0.5px;")
        live_layout.addWidget(live_header)
        
        self._live_text = QLabel("(송출 없음)")
        self._live_text.setStyleSheet("""
            background-color: #000; 
            color: #008800; 
            padding: 1px 4px;
            border-radius: 2px;
            font-size: 10px;
            font-weight: bold;
        """)
        self._live_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._live_text.setWordWrap(True)
        self._live_text.setFixedHeight(18)
        live_layout.addWidget(self._live_text)

        self._live_image = QLabel()
        self._live_image.setFixedSize(256, 144) # [수정] 고정 크기(16:9)
        self._live_image.setScaledContents(True)
        self._live_image.setStyleSheet("background-color: #000; border: 1px solid #883333; border-radius: 4px;")
        self._live_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        live_layout.addWidget(self._live_image, 0, Qt.AlignmentFlag.AlignCenter)
        self._live_image.hide()
        right_layout.addWidget(self._live_panel)
        
        right_layout.addStretch()
        self._h_splitter.addWidget(right_panel)
        
        # 전체 수직 스플리터에 하단 영역 추가 완료
        self._v_splitter.addWidget(self._h_splitter)
        
        # 초기 비율 설정 (상단 슬라이드 영역은 내용만큼만, 하단이 가득 차도록)
        self._v_splitter.setStretchFactor(0, 0)
        self._v_splitter.setStretchFactor(1, 1)
        self._v_splitter.setHandleWidth(4)
        
        # 스플리터 비율 및 스트레치 설정 (창 확대 시 각 영역비율 유지)
        self._h_splitter.setStretchFactor(0, 0) # 곡 목록은 고정 위주
        self._h_splitter.setStretchFactor(1, 1) # 악보 중앙이 가장 많이 확장
        self._h_splitter.setStretchFactor(2, 1) # 우측 패널도 함께 확장되도록 설정
        self._h_splitter.setSizes([220, 700, 300])

    def _apply_global_style(self):
        """애플리케이션 전체 전역 스타일 적용 (프리미엄 다크 테마)"""
        self.setStyleSheet("""
            QMainWindow { background-color: #1a1a1a; }
            QWidget { color: #ddd; font-family: 'Malgun Gothic', 'Segoe UI', sans-serif; }
            
            /* 스플리터 핸들 스타일 */
            QSplitter::handle {
                background-color: #222;
            }
            QSplitter::handle:horizontal {
                width: 1px;
            }
            QSplitter::handle:vertical {
                height: 1px;
            }
            
            /* 툴바 스타일 */
            /* 커스텀 툴바 스타일 */
            QWidget#CustomToolbar {
                background-color: #252525;
                border-bottom: 1px solid #333;
            }
            QToolButton {
                background-color: transparent;
                padding: 4px 8px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 11px;
                color: #ccc;
            }
            QToolButton:hover {
                background-color: #383838;
                color: white;
            }
            QToolButton:pressed {
                background-color: #1e1e1e;
            }
            QToolButton:checked {
                background-color: #2196f3;
                color: white;
            }
            
            /* 상태바 스타일 */
            QStatusBar {
                background-color: #1e1e1e;
                color: #888;
                font-size: 11px;
                border-top: 1px solid #333;
            }
            
            /* 기본 버튼 스타일 */
            QPushButton {
                background-color: #333;
                border-radius: 6px;
                padding: 5px 15px;
                color: #ddd;
            }
            QPushButton:hover { background-color: #444; }
            QPushButton:pressed { background-color: #222; }
            
            /* 메뉴 스타일 (필요 시) */
            QMenu {
                background-color: #252525;
                color: #ddd;
                border: 1px solid #444;
            }
            QMenu::item:selected {
                background-color: #2196f3;
                color: white;
            }
            
            /* 애플리케이션 전역 스크롤바 스타일 개선 */
            QScrollBar:vertical {
                border: none;
                background: #1a1a1a;
                width: 10px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #333;
                min-height: 20px;
                border-radius: 5px;
                margin: 2px;
            }
            QScrollBar::handle:vertical:hover {
                background: #2196f3;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }

            /* 다이얼로그 및 메시지 박스 스타일 (화이트 배경 및 텍스트 시인성 해결) */
            QDialog, QMessageBox, QMenu {
                background-color: #252525;
                color: #ddd;
                border: 1px solid #444;
            }
            QDialog QLabel, QMessageBox QLabel {
                color: #ddd;
                background-color: transparent;
            }
            QDialog QPushButton, QMessageBox QPushButton {
                min-width: 80px;
                background-color: #333;
                color: #ddd;
                border: 1px solid #555;
                padding: 5px 15px;
            }
            QDialog QPushButton:hover, QMessageBox QPushButton:hover {
                background-color: #444;
                border: 1px solid #2196f3;
            }
            
            /* 입력창, 드롭다운, 리스트 뷰 스타일 */
            QLineEdit, QTextEdit, QPlainTextEdit, QAbstractItemView {
                background-color: #2a2a2a;
                color: #ddd;
                border: 1px solid #444;
                selection-background-color: #2196f3;
                selection-color: white;
            }

            QScrollBar:horizontal {
                border: none;
                background: #1a1a1a;
                height: 10px;
                margin: 0px;
            }
            QScrollBar::handle:horizontal {
                background: #333;
                min-width: 20px;
                border-radius: 5px;
                margin: 2px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #2196f3;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                background: none;
            }
        """)
    
    def _setup_toolbar(self) -> None:
        """커스텀 2단 툴바 설정 (창 너비 축소 대응)"""
        layout = QVBoxLayout(self._toolbar)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(4)
        
        row1 = QHBoxLayout()
        row1.setSpacing(4)
        row2 = QHBoxLayout()
        row2.setSpacing(4)
        
        # 공통 버튼 생성 헬퍼
        def create_tool_btn(action, row, icon_only=False):
            btn = QToolButton()
            btn.setDefaultAction(action)
            if icon_only:
                btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            else:
                btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            row.addWidget(btn)
            return btn

        def add_sep(row):
            sep = QFrame()
            sep.setFrameShape(QFrame.Shape.VLine)
            sep.setFrameShadow(QFrame.Shadow.Sunken)
            sep.setStyleSheet("background-color: #444; width: 1px; margin: 4px 2px;")
            row.addWidget(sep)

        # 파일 액션들
        self._new_action = QAction("📄 새 프로젝트", self)
        self._new_action.setShortcut(QKeySequence.StandardKey.New)
        self._new_action.triggered.connect(self._new_project)
        create_tool_btn(self._new_action, row1)
        
        self._open_action = QAction("📂 열기", self)
        self._open_action.setShortcut(QKeySequence.StandardKey.Open)
        self._open_action.triggered.connect(self._open_project)
        create_tool_btn(self._open_action, row1)
        
        self._save_action = QAction("💾 저장", self)
        self._save_action.setShortcut(QKeySequence.StandardKey.Save)
        self._save_action.triggered.connect(self._save_project)
        create_tool_btn(self._save_action, row1)
        
        self._save_as_action = QAction("💾 다른 이름 저장", self)
        self._save_as_action.triggered.connect(self._save_project_as)
        create_tool_btn(self._save_as_action, row1)
        
        self._close_project_action = QAction("🏠 닫기", self)
        self._close_project_action.triggered.connect(self._close_current_project)
        create_tool_btn(self._close_project_action, row1)
        
        add_sep(row1)
        
        self._load_ppt_action = QAction("📽 PPT 로드", self)
        self._load_ppt_action.triggered.connect(self._on_load_ppt)
        create_tool_btn(self._load_ppt_action, row1)
        
        # 곡 관리 버튼 추가
        self._manage_songs_action = QAction("🎵 곡 관리", self)
        self._manage_songs_action.setToolTip("곡 추가/제거/관리")
        self._manage_songs_action.setEnabled(False)
        self._manage_songs_action.triggered.connect(self._manage_songs)
        create_tool_btn(self._manage_songs_action, row1)
        
        row1.addStretch()
        
        # --- 2단: 뷰 제어 및 모드 전환 ---
        self._toggle_slide_action = QAction("🖼 슬라이드 목록", self)
        self._toggle_slide_action.setCheckable(True)
        self._toggle_slide_action.setChecked(True)
        self._toggle_slide_action.setShortcut("Ctrl+H")
        self._toggle_slide_action.triggered.connect(self._toggle_slide_preview)
        create_tool_btn(self._toggle_slide_action, row2)
        
        add_sep(row2)
        
        self._read_mode_action = QAction("📖 읽기 모드", self)
        self._read_mode_action.setCheckable(True)
        self._read_mode_action.triggered.connect(self._toggle_read_mode)
        create_tool_btn(self._read_mode_action, row2)
        
        self._edit_mode_action = QAction("✏️ 편집 모드", self)
        self._edit_mode_action.setCheckable(True)
        self._edit_mode_action.setChecked(True)
        self._edit_mode_action.triggered.connect(self._toggle_edit_mode)
        create_tool_btn(self._edit_mode_action, row2)
        
        self._live_mode_action = QAction("🔴 라이브 모드", self)
        self._live_mode_action.setCheckable(True)
        self._live_mode_action.triggered.connect(self._toggle_live_mode)
        create_tool_btn(self._live_mode_action, row2)
        
        add_sep(row2)
        
        self._display_action = QAction("📺 송출 시작", self)
        self._display_action.setShortcut("F11")
        self._display_action.setEnabled(False)
        self._display_action.triggered.connect(self._toggle_display)
        create_tool_btn(self._display_action, row2)
        
        add_sep(row2)
        
        undo_action = self._undo_stack.createUndoAction(self, "↩️ 실행 취소")
        undo_action.setShortcut(QKeySequence.Undo)
        create_tool_btn(undo_action, row2, icon_only=False)
        self._undo_action = undo_action
        self.addAction(undo_action) # [추가] 툴바 외 윈도우 단축키 활성화를 위함
        
        redo_action = self._undo_stack.createRedoAction(self, "↪️ 다시 실행")
        # [수정] 일부 리눅스 환경에서 Redo 표준 키가 Ctrl+Y가 아닐 수 있으므로 명시적 추가
        redo_action.setShortcuts([QKeySequence.Redo, QtGui.QKeySequence("Ctrl+Y")])
        create_tool_btn(redo_action, row2, icon_only=False)
        self._redo_action = redo_action
        self.addAction(redo_action) # [추가] 윈도우 단축키 활성화
        
        row2.addStretch()
        
        layout.addLayout(row1)
        layout.addLayout(row2)
    
    def _setup_statusbar(self) -> None:
        """상태바 설정"""
        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)
        self._statusbar.showMessage("준비됨")
    
    def _connect_signals(self) -> None:
        """시그널 연결"""
        # 런처 시그널
        self._launcher.project_selected.connect(self._open_project_by_path)
        self._launcher.new_project_requested.connect(self._new_project)
        self._launcher.open_project_requested.connect(self._open_project)
        
        # 곡 목록 시그널
        self._song_list.song_selected.connect(self._on_song_selected)
        self._song_list.song_added.connect(self._on_song_added)
        
        # 캔버스 시그널 (Undo 대응 요청 시그널로 변경)
        self._canvas.hotspot_created_request.connect(self._on_hotspot_created_request)
        self._canvas.hotspot_removed_request.connect(self._on_hotspot_removed_request)
        self._canvas.hotspot_selected.connect(self._on_hotspot_selected)
        self._canvas.hotspot_moved.connect(self._on_hotspot_moved)
        self._canvas.hotspot_unmap_request.connect(self._on_hotspot_unmap_request)
        
        # 라이브 컨트롤러 시그널 - 메인 윈도우 및 송출창 업데이트
        self._live_controller.live_changed.connect(self._on_live_changed)
        # 슬라이드 이미지 송출 연결
        self._live_controller.slide_changed.connect(self._on_slide_changed)
        
        # PPT 비동기 로딩 시그널
        self._slide_manager.load_started.connect(self._on_ppt_load_started)
        self._slide_manager.load_finished.connect(self._on_ppt_load_finished)
        self._slide_manager.load_error.connect(self._on_ppt_load_error)
        self._slide_manager.load_progress.connect(self._on_ppt_load_progress)
        
        # 프로젝트 변경 감지 시그널 (SongListWidget)
        self._song_list.song_added.connect(self._on_song_added)
        self._song_list.song_removed.connect(self._on_song_removed)
    
    # === 프로젝트 관리 ===
    
    def _new_project(self) -> None:
        """새 프로젝트 폴더 생성 및 시작"""
        
        # 1. 프로젝트 이름/위치 선택
        # [수정] 폴더 안으로 들어가는 것을 방지하기 위해 .json 확장자를 붙여서 제안
        file_path, _ = QFileDialog.getSaveFileName(
            self, "새 프로젝트 생성 (폴더명 입력)",
            str(self._repo.base_path / "새 프로젝트.json"),
            "Flow 프로젝트 (*.json)"
        )
        
        if not file_path:
            return

        # [핵심] 사용자가 입력한 경로(파일명)를 이름으로 하는 '폴더'를 생성
        p_base = Path(file_path).resolve()
        # 확장자가 붙어있다면 제거 (폴더명으로 쓰기 위함)
        if p_base.suffix.lower() == ".json":
            p_base = p_base.with_suffix("")
            
        project_dir = p_base
        self._project_path = project_dir / "project.json"
        self._project = Project(name=project_dir.name)
        self._live_controller.set_project(self._project)
        
        try:
            # 폴더 생성 및 저장
            project_dir.mkdir(parents=True, exist_ok=True)
            self._repo.save(self._project, self._project_path)
            
            # UI 초기화
            self._song_list.set_project(self._project)
            self._canvas.set_score_sheet(None)
            self._slide_manager.load_pptx("")
            self._slide_preview.refresh_slides()
            
            self.setWindowTitle(f"Flow - {self._project.name}")
            self._config_service.add_recent_project(str(self._project_path))
            self._clear_dirty() # 새 프로젝트는 깨끗한 상태
            self._show_editor() # 에디터 화면으로 전환
            self._toggle_edit_mode()
            self._statusbar.showMessage(f"새 프로젝트가 생성되었습니다: {project_dir}")
        except Exception as e:
            QMessageBox.critical(self, "오류", f"프로젝트 폴더를 생성할 수 없습니다:\n{e}")

    
    def _open_project(self) -> None:
        """프로젝트 열기"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "프로젝트 열기",
            str(self._repo.base_path),
            "Flow 프로젝트 (*.json)"
        )
        
        if not file_path:
            return
        
        try:
            self._project = self._repo.load(Path(file_path))
            self._project_path = Path(file_path)
            self._live_controller.set_project(self._project)
            
            # 1. 곡 목록 갱신
            self._song_list.set_project(self._project)
            
            # [NEW] 절 선택 UI 동기화
            v_idx = self._project.current_verse_index
            self._verse_group.button(v_idx).setChecked(True)
            self._canvas.set_verse_index(v_idx)
            
            # 2. 매핑 상태 UI 동기화
            self._update_mapped_slides_ui()
            
            # 3. 전역 PPT 설정 복구
            if self._project.pptx_path:
                self._slide_manager.load_pptx(self._project.pptx_path)
            else:
                self._slide_preview.refresh_slides()

            # 4. 첫 번째 곡 선택 및 악보 표시
            if self._project.score_sheets:
                first_sheet = self._project.score_sheets[0]
                self._on_song_selected(first_sheet)
                self._song_list._list.setCurrentRow(0)
            else:
                self._canvas.set_score_sheet(None)
            
            self.setWindowTitle(f"Flow - {self._project.name}")
            self._config_service.add_recent_project(str(self._project_path))
            self._clear_dirty()
            self._show_editor()
            self._toggle_read_mode()
            self._statusbar.showMessage(f"프로젝트를 열었습니다: {self._project.name}")
            
        except Exception as e:
            QMessageBox.critical(self, "오류", f"프로젝트를 열 수 없습니다:\n{e}")

    def _open_project_by_path(self, path_str: str) -> None:
    """지정된 경로의 프로젝트를 직접 열기"""
    path = Path(path_str)
    if not path.exists():
        QMessageBox.warning(self, "오류", "해당 프로젝트 파일이 존재하지 않습니다.")
        self._config_service.remove_recent_project(path_str)
        self._launcher.set_recent_projects(self._config_service.get_recent_projects())
        return
        
    try:
        self._project = self._repo.load(path)
        self._project_path = path
        self._live_controller.set_project(self._project)
        
        # 곡 목록 및 UI 갱신 (기존 _open_project 로직과 유사)
        self._song_list.set_project(self._project)
        v_idx = self._project.current_verse_index
        self._verse_group.button(v_idx).setChecked(True)
        self._canvas.set_verse_index(v_idx)
        self._update_mapped_slides_ui()
        
        if self._project.selected_songs:
            self._slide_manager.load_songs(self._project.selected_songs)
            # 전역 인덱스로 변환
            self._globalize_project_indices()
        elif self._project.pptx_path:
            self._slide_manager.load_pptx(self._project.pptx_path)
        else:
            self._slide_preview.refresh_slides()

        sheets = self._project.all_score_sheets
        if sheets:
            sheet = sheets[0]
            self._on_song_selected(sheet) # _on_song_selected가 이제 base_path를 처리함
            self._song_list._list.setCurrentRow(0)
        else:
            self._canvas.set_score_sheet(None)
        
        # 최근 목록 업데이트 및 에디터 표시
        self._config_service.add_recent_project(path_str)
        self._clear_dirty()
        self._show_editor()
        self._toggle_read_mode()
        self._statusbar.showMessage(f"프로젝트를 열었습니다: {self._project.name}")
        
    except Exception as e:
        QMessageBox.critical(self, "오류", f"프로젝트를 열 수 없습니다:\n{e}")

