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
from PySide6.QtCore import Qt, QTimer
from flow.ui.undo_commands import AddHotspotCommand, RemoveHotspotCommand, MoveHotspotCommand, MapSlideCommand

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
        self.setWindowTitle("Flow - 찬양 가사 송출")
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
        
        row1.addStretch()
        
        # --- 2단: 뷰 제어 및 모드 전환 ---
        self._toggle_slide_action = QAction("🖼 슬라이드 목록", self)
        self._toggle_slide_action.setCheckable(True)
        self._toggle_slide_action.setChecked(True)
        self._toggle_slide_action.setShortcut("Ctrl+H")
        self._toggle_slide_action.triggered.connect(self._toggle_slide_preview)
        create_tool_btn(self._toggle_slide_action, row2)
        
        add_sep(row2)
        
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
        
        redo_action = self._undo_stack.createRedoAction(self, "↪️ 다시 실행")
        redo_action.setShortcut(QKeySequence.Redo)
        create_tool_btn(redo_action, row2, icon_only=False)
        self._redo_action = redo_action
        
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
        
        # 라이브 컨트롤러 시그널 - 메인 윈도우 및 송출창 업데이트
        self._live_controller.live_changed.connect(self._on_live_changed)
        # 슬라이드 이미지 송출 연결
        self._live_controller.slide_changed.connect(self._on_slide_changed)
        
        # PPT 비동기 로딩 시그널
        self._slide_manager.load_started.connect(self._on_ppt_load_started)
        self._slide_manager.load_finished.connect(self._on_ppt_load_finished)
        self._slide_manager.load_error.connect(self._on_ppt_load_error)
        
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
            self._toggle_edit_mode()
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
            
            # 곡 목록 및 UI 갱신 (기존 _open_project 로직과 유사)
            self._song_list.set_project(self._project)
            v_idx = self._project.current_verse_index
            self._verse_group.button(v_idx).setChecked(True)
            self._canvas.set_verse_index(v_idx)
            self._update_mapped_slides_ui()
            
            if self._project.pptx_path:
                self._slide_manager.load_pptx(self._project.pptx_path)
            else:
                self._slide_preview.refresh_slides()

            if self._project.score_sheets:
                self._on_song_selected(self._project.score_sheets[0])
                self._song_list._list.setCurrentRow(0)
            else:
                self._canvas.set_score_sheet(None)
            
            # 최근 목록 업데이트 및 에디터 표시
            self._config_service.add_recent_project(path_str)
            self._clear_dirty()
            self._show_editor()
            self._toggle_edit_mode()
            self._statusbar.showMessage(f"프로젝트를 열었습니다: {self._project.name}")
            
        except Exception as e:
            QMessageBox.critical(self, "오류", f"프로젝트를 열 수 없습니다:\n{e}")
    
    def _save_project(self) -> None:
        """프로젝트 저장"""
        if not self._project:
            return
        
        # 저장 경로가 없거나 처음 저장하는 경우 이름/위치 묻기
        if not self._project_path:
            file_path, _ = QFileDialog.getSaveFileName(
                self, "프로젝트 저장",
                str(self._repo.base_path / f"{self._project.name}.json"),
                "Flow 프로젝트 (*.json)"
            )
            if not file_path:
                return
            self._project_path = Path(file_path)

        try:
            self._project_path = self._repo.save(self._project, self._project_path)
            self.setWindowTitle(f"Flow - {self._project.name}")
            self._undo_stack.setClean() # 저장 시점 기록
            self._statusbar.showMessage(f"프로젝트가 저장되었습니다: {self._project_path.name}")
        except Exception as e:
            QMessageBox.critical(self, "오류", f"프로젝트를 저장할 수 없습니다:\n{e}")

    def _on_undo_stack_clean_changed(self, is_clean: bool) -> None:
        """Undo 스택 상태에 따른 dirty 표시 업데이트"""
        if is_clean:
            self._clear_dirty()
        else:
            self._mark_dirty()

    def _on_verse_changed(self, verse_index: int) -> None:
        """현재 선택된 절 변경 핸들러"""
        if not self._project:
            return
            
        self._project.current_verse_index = verse_index
        self._canvas.set_verse_index(verse_index)
        
        # [수정] 현재 선택된 핫스팟이 바뀐 절에 매핑되어 있지 않다면 선택 해제 (화면 정돈)
        current_hotspot = self._canvas.get_selected_hotspot()
        if current_hotspot:
            if current_hotspot.get_slide_index(verse_index) >= 0:
                self._update_preview(current_hotspot)
                self._live_controller.set_preview(current_hotspot)
            else:
                self._canvas.select_hotspot(None)
                self._update_preview(None)
                self._live_controller.set_preview(None)
            
        self._statusbar.showMessage(f"{verse_index + 1 if verse_index < 5 else '후렴'}을(를) 선택했습니다.", 1000)

    def _save_project_as(self) -> None:
        """현재 프로젝트를 다른 이름(폴더 통째로 복사)으로 저장"""
        if not self._project:
            return
            
        # 기본 저장 경로 설정 (.json을 붙여 제안하여 폴더 진입 방지)
        if self._project_path:
            initial_path = self._project_path.parent.parent / f"{self._project.name}_복사본.json"
        else:
            initial_path = self._repo.base_path / f"{self._project.name}_복사본.json"
            
        file_path, _ = QFileDialog.getSaveFileName(
            self, "다른 이름으로 저장 (새 폴더 생성)",
            str(initial_path),
            "Flow 프로젝트 (*.json)"
        )
        
        if not file_path:
            return
            
        p_base = Path(file_path).resolve()
        if p_base.suffix.lower() == ".json":
            p_base = p_base.with_suffix("")
            
        new_project_dir = p_base
        old_project_dir = self._project_path.parent if self._project_path else None
        
        try:
            # 1. 새 폴더가 이미 있으면 삭제 (깨끗한 복제를 위해)
            if new_project_dir.exists():
                shutil.rmtree(new_project_dir)
                
            # 2. 기존 프로젝트 폴더가 있다면 그 내용물을 모두 복사
            if old_project_dir and old_project_dir.exists():
                shutil.copytree(old_project_dir, new_project_dir)
            else:
                # 기존 폴더가 없는 경우(임의의 초기 프로젝트) 새 폴더만 생성
                new_project_dir.mkdir(parents=True, exist_ok=True)
            
            # 3. 프로젝트 객체 정보 업데이트
            self._project.name = new_project_dir.name
            self._project_path = new_project_dir / "project.json"
            
            # 4. 새로운 위치에 project.json 덮어씌워 저장 (수정된 이름 반영)
            self._save_project()
            
            # 5. 복사된 환경에 맞춰 PPT 다시 로드 (복사본 파일 사용을 위해)
            if self._project.pptx_path:
                self._slide_manager.load_pptx(self._project.pptx_path)

            self._statusbar.showMessage(f"프로젝트 전용 폴더가 생성되고 모든 파일이 복제되었습니다: {new_project_dir.name}")
            
        except Exception as e:
            QMessageBox.critical(self, "오류", f"프로젝트를 복제할 수 없습니다:\n{e}")
    
    # === 모드 전환 ===
    
    def _toggle_edit_mode(self) -> None:
        """편집 모드 토글"""
        self._edit_mode_action.setChecked(True)
        self._live_mode_action.setChecked(False)
        self._canvas.set_edit_mode(True)
        
        # 편집 기능 활성화
        self._set_project_editable(True)
        
        # Live 패널 숨기기
        self._live_panel.hide()
        
        # 송출 중지 및 비활성화
        if self._display_window and self._display_window.isVisible():
            self._toggle_display()
        self._display_action.setEnabled(False)
        
        self._statusbar.showMessage("편집 모드")
    
    def _toggle_live_mode(self) -> None:
        """라이브 모드 토글"""
        self._edit_mode_action.setChecked(False)
        self._live_mode_action.setChecked(True)
        self._canvas.set_edit_mode(False)
        
        # 편집 기능 비활성화
        self._set_project_editable(False)
        
        # Live 패널 표시
        self._live_panel.show()
        
        # 송출 시작 버튼 활성화
        self._display_action.setEnabled(True)
        
        self.setFocus()
        self._statusbar.showMessage("라이브 모드 - F11로 송출 시작")
    
    def _toggle_display(self) -> None:
        """송출 시작/중지 토글"""
        if self._display_window and self._display_window.isVisible():
            # 중지 로직
            self._display_window.close()
            # closeEvent에서 _on_display_closed가 호출되어 UI가 갱신됨
        else:
            # 시작 로직
            if self._display_window is None:
                self._display_window = DisplayWindow()
                self._display_window.closed.connect(self._on_display_closed)
                # 시그널 연결 (MainWindow의 핸들러를 통해 전달됨)
            
            self._display_window.show_fullscreen_on_secondary()
            
            # [중요] 송출창이 열린 후 현재 라이브 상태를 즉시 동기화
            self._live_controller.sync_live()
            
            self._display_action.setText("⏹ 송출 중지")
            self._statusbar.showMessage("송출이 시작되었습니다 (F11로 중지)")
    
    def _on_display_closed(self) -> None:
        """송출창이 닫혔을 때 (ESC로 닫거나 버튼으로 닫혔을 때 공통)"""
        self._display_action.setText("📺 송출 시작")
        self._statusbar.showMessage("송출이 중지되었습니다")
    
    def _set_project_editable(self, editable: bool) -> None:
        """프로젝트 편집 관련 UI 요소들 활성/비활성 제어"""
        # 툴바 액션
        self._new_action.setEnabled(editable)
        self._open_action.setEnabled(editable)
        self._save_action.setEnabled(editable)
        self._save_as_action.setEnabled(editable)
        self._close_project_action.setEnabled(editable)
        self._load_ppt_action.setEnabled(editable)
        self._undo_action.setEnabled(editable)
        self._redo_action.setEnabled(editable)
        
        # 위젯 내부 버튼
        self._song_list.set_editable(editable)
        self._slide_preview.set_editable(editable)

    def _mark_dirty(self) -> None:
        """변경사항이 있음을 표시"""
        if not self._is_dirty:
            self._is_dirty = True
            title = self.windowTitle()
            if not title.endswith("*"):
                self.setWindowTitle(title + " *")

    def _clear_dirty(self) -> None:
        """변경사항이 없음을 표시 (저장/로드 후)"""
        self._is_dirty = False
        title = self.windowTitle()
        if title.endswith("*"):
            self.setWindowTitle(title[:-2].strip())

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """윈도우 종료 시 저장 확인"""
        if self._is_dirty:
            reply = QMessageBox.question(
                self, "저장 확인",
                "저장되지 않은 변경사항이 있습니다.\n종료하기 전에 저장하시겠습니까?",
                QMessageBox.StandardButton.Save | 
                QMessageBox.StandardButton.Discard | 
                QMessageBox.StandardButton.Cancel
            )
            
            if reply == QMessageBox.StandardButton.Save:
                self._save_project()
                event.accept()
            elif reply == QMessageBox.StandardButton.Discard:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()

    def _close_current_project(self) -> None:
        """현재 프로젝트를 닫고 시작 화면으로 회귀"""
        if self._is_dirty:
            reply = QMessageBox.question(
                self, "저장 확인",
                "저장되지 않은 변경사항이 있습니다.\n닫기 전에 저장하시겠습니까?",
                QMessageBox.StandardButton.Save | 
                QMessageBox.StandardButton.Discard | 
                QMessageBox.StandardButton.Cancel
            )
            
            if reply == QMessageBox.StandardButton.Save:
                self._save_project()
            elif reply == QMessageBox.StandardButton.Cancel:
                return

        # 상태 초기화
        self._project = None
        self._project_path = None
        self._song_list.set_project(None)
        self._canvas.set_score_sheet(None)
        
        # PPT 조작 중지 및 UI 초기화
        self._slide_manager.stop_watching()
        self._slide_manager.load_pptx("")
        self._slide_preview.refresh_slides()
        self._preview_image.hide()
        self._preview_text.setText("선택된 슬라이드가 없습니다.")
        
        self._undo_stack.clear()
        self._clear_dirty() # 런처로 돌아갈 때는 dirty 표시 제거
        
        self._show_launcher()

    # === PPT 비동기 로딩 핸들러 ===
    
    def _on_ppt_load_started(self) -> None:
        """PPT 로딩 시작"""
        self._statusbar.showMessage("📽 PPT 변환 중... 잠시만 기다려주세요.", 0) # 0은 무한 지속
        self._slide_preview.show_loading() # 로딩 오버레이 표시
        
    def _on_ppt_load_finished(self, count: int) -> None:
        """PPT 로딩 완료"""
        self._slide_preview.hide_loading() # 로딩 오버레이 숨김
        self._slide_preview.refresh_slides()
        self._statusbar.showMessage(f"✅ PPT 로드 완료 ({count} 슬라이드)", 3000)
        
    def _on_ppt_load_error(self, message: str) -> None:
        """PPT 로딩 에러"""
        self._slide_preview.hide_loading() # 로딩 오버레이 숨김
        self._slide_preview.refresh_slides()
        QMessageBox.warning(self, "PPT 로딩 오류", message)
        self._statusbar.showMessage("❌ PPT 로드 실패", 3000)

    # === 이벤트 핸들러 ===
    
    def _on_song_selected(self, sheet: ScoreSheet) -> None:
        """곡 선택됨"""
        self._canvas.set_score_sheet(sheet)
        
        # PPT 로드 (곡별 PPT가 없으면 프로젝트 전역 PPT 사용)
        ppt_to_load = (sheet.pptx_path or self._project.pptx_path)
        ppt_to_load = str(Path(ppt_to_load).resolve()) if ppt_to_load else ""
        
        # 최적화: 현재 로드된 PPT와 동일하다면 새로고침 생략
        current_ppt = str(self._slide_manager._pptx_path.resolve()) if self._slide_manager._pptx_path else ""
        
        if ppt_to_load != current_ppt:
            if ppt_to_load:
                self._slide_manager.load_pptx(ppt_to_load)
                self._slide_manager.start_watching(ppt_to_load)
            else:
                self._slide_manager.load_pptx("")
                self._slide_manager.stop_watching()
                self._slide_preview.refresh_slides()
            
        self._statusbar.showMessage(f"곡 선택: {sheet.name}")
        self._update_preview(None)
        
        # 최적화: PPT가 새로 로드된 경우에만 매핑 UI 전체 갱신
        # 단순 곡 전환 시에는 프로젝트 전체 매핑 세트가 바뀌지 않으므로 호출할 필요 없음
        if ppt_to_load != current_ppt:
            self._update_mapped_slides_ui()
    
    def _on_song_added(self, sheet: ScoreSheet) -> None:
        """곡 추가됨"""
        self._mark_dirty()
        self._canvas.set_score_sheet(sheet)
        self._statusbar.showMessage(f"새 곡 추가: {sheet.name}")
        
    def _on_song_removed(self, sheet_id: str) -> None:
        """곡 삭제됨"""
        self._mark_dirty()
        self._canvas.set_score_sheet(None)
        self._statusbar.showMessage("곡 삭제됨")
        
    def _project_dir(self) -> str:
        """현재 프로젝트의 디렉토리 경로 반환"""
        return str(self._project_path.parent) if self._project_path else ""
    
    def _on_hotspot_selected(self, hotspot: Hotspot) -> None:
        """핫스팟 선택됨"""
        self._update_preview(hotspot)
        
        # 모드와 관계없이 항상 Preview에 설정 (전환 시 즉시 송출 대기용)
        self._live_controller.set_preview(hotspot)
        
        # [수정] 현재 절 매핑 우선, 없으면 후렴 매핑 확인 (내비게이션용)
        v_idx = self._project.current_verse_index
        slide_idx = hotspot.get_slide_index(v_idx)
        
        # 현재 절에 매핑이 없더라도 후렴 매핑이 있다면 해당 슬라이드 강조
        if slide_idx < 0:
            slide_idx = hotspot.get_slide_index(5) # 후렴 체크
            
        if slide_idx >= 0:
            self._slide_preview.select_slide(slide_idx)
    
    def _on_hotspot_created_request(self, x: int, y: int, index: int | None = None) -> None:
        """핫스팟 생성 요청 처리 (Undo 지원)"""
        sheet = self._canvas._score_sheet
        if not sheet: return
        
        # 새 핫스팟 객체 생성 (실제 추가는 Command가 수행)
        hotspot = Hotspot(x=x, y=y)
        # 현재 레이어 정보 주입
        hotspot.set_slide_index(-1, self._project.current_verse_index)
        
        # UI 갱신 헬퍼 (생성 시 선택, 취소 시 해제)
        def refresh_ui(selected_id=None):
            self._canvas.select_hotspot(selected_id)
            if selected_id:
                self._on_hotspot_selected(hotspot)
            else:
                self._update_preview(None)
            self._canvas.update()

        command = AddHotspotCommand(
            sheet, hotspot, index,
            undo_cb=lambda: refresh_ui(None),
            redo_cb=lambda: refresh_ui(hotspot.id)
        )
        self._undo_stack.push(command)

    def _on_hotspot_removed_request(self, hotspot: Hotspot) -> None:
        """핫스팟 삭제 요청 처리 (Undo 지원)"""
        sheet = self._canvas._score_sheet
        if not sheet or not hotspot: return
        
        # UI 갱신 헬퍼 (삭제 시 해제, 취소 시 복구 및 선택)
        def refresh_ui(selected_id=None):
            self._canvas.select_hotspot(selected_id)
            if selected_id:
                self._on_hotspot_selected(hotspot)
            else:
                self._update_preview(None)
            self._canvas.update()

        command = RemoveHotspotCommand(
            sheet, hotspot,
            undo_cb=lambda: refresh_ui(hotspot.id),
            redo_cb=lambda: refresh_ui(None)
        )
        self._undo_stack.push(command)

    def _on_hotspot_moved(self, hotspot: Hotspot, old_pos: tuple[int, int], new_pos: tuple[int, int]) -> None:
        """핫스팟 이동 완료 처리 (Undo 지원)"""
        command = MoveHotspotCommand(hotspot, old_pos, new_pos, self._canvas.update)
        self._undo_stack.push(command)
        self.statusBar().showMessage(f"핫스팟 이동됨: #{hotspot.order + 1}")
    
    # === 슬라이드 미리보기 및 매핑 정보 동기화 ===
    
    def _update_preview(self, hotspot: Hotspot | None) -> None:
        """미리보기 업데이트"""
        text = "(선택된 핫스팟 없음)"
        show_img = False
        
        if hotspot:
            lyric = getattr(hotspot, 'lyric', "")
            # [수정] 현재 절의 슬라이드를 가져오되, 없으면 후렴 매핑 활용 (범용 내비게이션)
            v_idx = self._project.current_verse_index
            slide_idx = hotspot.get_slide_index(v_idx)
            
            # 현재 절 매핑이 없고 후렴 매핑이 있는 경우 후렴 슬라이드를 보여줌
            if slide_idx < 0:
                slide_idx = hotspot.get_slide_index(5)
            
            if lyric:
                text = lyric
            elif slide_idx >= 0:
                text = f"#{slide_idx + 1}"
            else:
                text = "(없음)"
            
            # 매핑된 슬라이드 이미지가 있다면 프리뷰에 표시
            if slide_idx >= 0:
                from PySide6.QtGui import QPixmap
                try:
                    qimg = self._slide_manager.get_slide_image(slide_idx)
                    pixmap = QtGui.QPixmap.fromImage(qimg)
                    self._preview_image.setPixmap(pixmap) # setScaledContents(True)로 자동 스케일링
                    show_img = True
                except Exception:
                    pass
                
        self._preview_text.setText(text)
        self._preview_image.setVisible(show_img)
    
    def _on_live_changed(self, lyric: str) -> None:
        """Live 가사 변경됨 - 메인 윈도우와 송출창 모두 업데이트"""
        self._live_text.setText(lyric or "(송출 없음)")
        
        if self._display_window and self._display_window.isVisible():
            self._display_window.show_lyric(lyric)
        
        # 가사가 있으면 이미지는 숨김 (텍스트 우선 송출 정책)
        if lyric:
            self._live_image.hide()

    def _on_slide_changed(self, image) -> None:
        """슬라이드 이미지 변경됨 - 메인 윈도우와 송출창 업데이트"""
        self._current_live_image = image # [추가] 리사이징 대응을 위해 현재 이미지 보관
        if image:
            from PySide6.QtGui import QPixmap
            pixmap = QPixmap.fromImage(image)
            self._live_image.setPixmap(pixmap) # setScaledContents(True)로 자동 스케일링
            self._live_image.show()
        else:
            self._live_image.hide()

        if self._display_window and self._display_window.isVisible():
            self._display_window.show_image(image)

    def _on_load_ppt(self) -> None:
        """PPTX 파일 로드 핸들러 - 프로젝트 폴더 우선 탐색"""
        if not self._project:
            return
            
        from PySide6.QtWidgets import QFileDialog
        # 프로젝트 폴더가 있으면 그곳을 기본 경로로 설정
        initial_dir = str(self._project_path.parent) if self._project_path else ""
        
        file_path, _ = QFileDialog.getOpenFileName(
            self, "PPTX 파일 선택", initial_dir, "PPTX 파일 (*.pptx)"
        )
        
        if file_path:
            try:
                # PPT 로드 시도 및 프로젝트 전역 PPT로 설정
                self._slide_manager.load_pptx(file_path)
                self._project.pptx_path = file_path
                self._slide_manager.start_watching(file_path)
                
                # UI 갱신
                self._slide_preview.refresh_slides()
                self._mark_dirty()
                self.statusBar().showMessage(f"전역 PPT 설정 완료: {file_path}", 5000)
                
                # 현재 선택된 핫스팟이 있다면 프리뷰 갱신
                current_sheet = self._project.get_current_score_sheet()
                if current_sheet:
                    self._update_preview(self._canvas.get_selected_hotspot())
            except Exception as e:
                # ... 
                from flow.services.slide_manager import SlideLoadError
                if isinstance(e, SlideLoadError):
                    QMessageBox.warning(self, "PPTX 로드 실패", str(e))
                else:
                    QMessageBox.critical(self, "오류", f"PPT를 로드할 수 없습니다:\n{e}")

    def _on_close_ppt(self) -> None:
        """현재 PPT 닫기 핸들러"""
        if not self._project:
            return
            
        self._slide_manager.load_pptx("")
        self._slide_manager.stop_watching()
        self._project.pptx_path = ""
        
        self._slide_preview.refresh_slides()
        self.statusBar().showMessage("PPT가 닫혔습니다", 3000)
        self._update_preview(self._canvas.get_selected_hotspot())

    def _on_slide_selected(self, index: int) -> None:
        """상단 슬라이드 목록에서 슬라이드 클릭 시 핸들러 - 타이머로 더블클릭 대기"""
        if not self._project:
            return
            
        self._pending_slide_index = index
        # 더블클릭 속도(보통 200~300ms)만큼 대기 후 내비게이션 실행
        self._slide_click_timer.start(250)

    def _execute_slide_navigation(self) -> None:
        """지연된 슬라이드 내비게이션 실행 (싱글클릭일 때만 실행됨)"""
        if not self._project or self._pending_slide_index < 0:
            return
            
        index = self._pending_slide_index
        self._pending_slide_index = -1
        
        # 역방향 검색: 이 슬라이드가 매핑된 곡과 핫스팟 찾기
        found_sheet = None
        found_hotspot = None
        
        # 1. 모든 곡(ScoreSheet) 탐색
        for sheet in self._project.score_sheets:
            for hotspot in sheet.hotspots:
                # 모든 절 매핑을 검사
                for v_idx_str, s_idx in hotspot.slide_mappings.items():
                    if s_idx == index:
                        found_sheet = sheet
                        found_hotspot = hotspot
                        # 찾은 경우 해당 절로 전환 시도
                        v_idx = int(v_idx_str)
                        if self._project.current_verse_index != v_idx:
                            self._on_verse_changed(v_idx)
                            # 버튼 UI 동기화
                            self._verse_group.button(v_idx).setChecked(True)
                        break
                if found_sheet: break
            if found_sheet: break
        
        # 2. 결과에 따른 처리
        if found_sheet and found_hotspot:
            # 매핑된 항목이 있으면 해당 곡으로 전환하고 핫스팟 선택
            # 버그 수정: 캔버스가 비어있을 수 있으므로 항상 또는 조건부로 강제 설정
            if self._canvas._score_sheet != found_sheet:
                self._on_song_selected(found_sheet)
                
                # 곡 목록 UI 동기화
                for i in range(self._song_list._list.count()):
                    item = self._song_list._list.item(i)
                    if item.data(Qt.ItemDataRole.UserRole) == found_sheet.id:
                        self._song_list._list.setCurrentRow(i)
                        break
            
            # 핫스팟 선택 및 프리뷰 갱신
            self._canvas.select_hotspot(found_hotspot.id)
            
            # (수정: 모드와 무관하게 항상 LiveController의 Preview를 업데이트하여 송출 대기)
            self._live_controller.set_preview(found_hotspot)
            self._update_preview(found_hotspot)
            
            self.statusBar().showMessage(f"탐색: 슬라이드 {index + 1} - '{found_sheet.name}'", 2000)
        else:
            # 대응되는 핫스팟이 없으면 악보 영역 초기화 여부 결정
            # (수정: 현재 핫스팟이 선택되어 있다면 매핑 시도로 보고 악보를 지우지 않음)
            if not self._canvas.get_selected_hotspot():
                self._canvas.set_score_sheet(None)
                self._song_list._list.clearSelection() # 곡 목록 선택도 해제
                msg = f"미리보기: 슬라이드 {index + 1} (매칭 없음 - 악보 가림)"
            else:
                msg = f"미리보기: 슬라이드 {index + 1} (매칭 없음 - 매핑 대기 중)"
            
            # 라이브 컨트롤러에도 알려서 Enter 입력 시 송출 가능하게 함
            # (수정: 대기 상태 유지를 위해 편집/라이브 모드와 관계없이 항상 설정)
            self._live_controller.set_preview_slide(index)
            
            # 매칭된 항목이 없으면 단순히 프리뷰 이미지만 갱신 (매핑하지 않음)
            self._update_preview_with_index(index)
            self.statusBar().showMessage(msg, 2000)

    def _on_slide_double_clicked(self, index: int) -> None:
        """상단 슬라이드 목록에서 슬라이드 더블클릭 시 핸들러 - 중복 매핑 방지 강화"""
        if not self._project:
            return
            
        # 싱글클릭 내비게이션 타이머 중지
        self._slide_click_timer.stop()
        self._pending_slide_index = -1
        
        selected_hotspot = self._canvas.get_selected_hotspot()
        if not selected_hotspot:
            QMessageBox.information(self, "매핑 안내", "슬라이드를 매핑하려면 먼저 악보에서 핫스팟을 선택하세요.")
            return

        # [추가] 현재 모드에서 편집 가능한 버튼인지 확인 (타 레이어 전용 버튼 보호)
        if not self._canvas.is_hotspot_editable(selected_hotspot, self._project.current_verse_index):
            v_name = f"{self._project.current_verse_index + 1}절" if self._project.current_verse_index < 5 else "후렴"
            QMessageBox.warning(self, "매핑 제한", f"이 버튼은 타 레이어에서 생성되었습니다.\n{v_name}에서 작업하시려면 해당 레이어로 이동하거나 새 버튼을 만들어 주세요.")
            return

        # 1:1 매핑 체크: 이 슬라이드가 이미 다른 곳에 매핑되어 있는지 확인
        existing_info = None
        for sheet in self._project.score_sheets:
            ordered_hotspots = sheet.get_ordered_hotspots()
            for i, hotspot in enumerate(ordered_hotspots):
                # 모든 절 매핑을 검사
                for v_idx_str, s_idx in hotspot.slide_mappings.items():
                    if s_idx == index:
                        if hotspot != selected_hotspot:
                            v_idx = int(v_idx_str)
                            v_name = f"{v_idx + 1}절" if v_idx < 5 else "후렴"
                            existing_info = {
                                "sheet_name": sheet.name,
                                "order": i + 1,
                                "verse": v_name,
                                "lyric": hotspot.lyric or "가사 없음"
                            }
                            break
                if existing_info: break
            if existing_info: break
        
        if existing_info:
            QMessageBox.warning(
                self, "매핑 중복",
                f"슬라이드 {index + 1}은(는) 이미 다른 곳에 매핑되어 있습니다.\n\n"
                f"📍 곡명: {existing_info['sheet_name']}\n"
                f"📍 위치: {existing_info['verse']}의 {existing_info['order']}번 버튼 ({existing_info['lyric']})\n\n"
                "먼저 해당 위치의 매핑을 해제한 후 다시 시도해 주세요."
            )
            return
            
        # 현재 핫스팟의 '현재 절'에 매핑 진행 (Undo 지원)
        old_slide = selected_hotspot.get_slide_index(self._project.current_verse_index)
        
        command = MapSlideCommand(
            selected_hotspot, 
            self._project.current_verse_index,
            old_slide,
            index,
            lambda: (self._canvas.update(), self._update_preview(selected_hotspot), self._update_mapped_slides_ui())
        )
        self._undo_stack.push(command)
        
        if not selected_hotspot.lyric:
            selected_hotspot.lyric = f"Slide {index + 1}"
        
        self.statusBar().showMessage(f"매핑 완료: 슬라이드 {index + 1} → 현재 핫스팟", 3000)

    def _update_mapped_slides_ui(self) -> None:
        """전체 프로젝트를 뒤져 현재 절에 매핑된 슬라이드 정보를 UI에 반영"""
        if not self._project:
            return
            
        mapped_indices = set()
        for sheet in self._project.score_sheets:
            for hotspot in sheet.hotspots:
                # [수정] 현재 절의 매핑만 추출
                idx = hotspot.get_slide_index(self._project.current_verse_index)
                if idx >= 0:
                    mapped_indices.add(idx)
        
        self._slide_preview.set_mapped_slides(mapped_indices)

    def _on_slide_unlink_all_requested(self, index: int) -> None:
        """특정 슬라이드가 매핑된 모든 곳에서 해제"""
        if not self._project:
            return
            
        count = 0
        for sheet in self._project.score_sheets:
            for hotspot in sheet.hotspots:
                # 모든 절 매핑에서 해당 슬라이드 제거
                keys_to_remove = [k for k, v in hotspot.slide_mappings.items() if v == index]
                for k in keys_to_remove:
                    del hotspot.slide_mappings[k]
                    count += 1
                # 하위 호환 필드도 체크
                if hotspot.slide_index == index:
                    hotspot.slide_index = -1
                    count += 1
        
        if count > 0:
            self._canvas.update()
            self._update_mapped_slides_ui()
            # 현재 선택된 핫스팟의 프리뷰도 갱신될 수 있도록 처리
            self._update_preview(self._canvas.get_selected_hotspot())
            self.statusBar().showMessage(f"해제 완료: {count}개의 핫스팟에서 슬라이드 {index + 1} 연결을 끊었습니다.", 3000)

    def _on_unlink_current_hotspot(self) -> None:
        """현재 선택된 핫스팟의 '현재 절' 슬라이드 매핑만 해제 (Undo 지원)"""
        hotspot = self._canvas.get_selected_hotspot()
        if hotspot:
            v_idx = self._project.current_verse_index
            old_slide = hotspot.get_slide_index(v_idx)
            
            if old_slide >= 0:
                command = MapSlideCommand(
                    hotspot, v_idx, old_slide, -1,
                    lambda: (self._canvas.update(), self._update_preview(hotspot), self._update_mapped_slides_ui())
                )
                self._undo_stack.push(command)
                self.statusBar().showMessage("현재 절의 매핑을 해제했습니다.", 3000)

    def _update_preview_with_index(self, index: int) -> None:
        """인덱스로 직접 프리뷰 이미지 갱신 (핫스팟 없을 때)"""
        self._last_preview_index = index # 상태 저장
        try:
            qimg = self._slide_manager.get_slide_image(index)
            pixmap = QtGui.QPixmap.fromImage(qimg)
            self._preview_image.setPixmap(pixmap) # setScaledContents(True)로 자동 스케일링
            self._preview_image.show()
            self._preview_text.setText(f"#{index + 1} (미매핑)")
        except Exception:
            pass
    
    # === 키보드 이벤트 ===
    

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        """키보드 이벤트 핸들러"""
        if not self._project:
            super().keyPressEvent(event)
            return
            
        key = event.key()
        focused = self.focusWidget()
        
        # 숫자키 1-6 (상단 숫자키): 절(Verse) 즉시 전환
        verse_idx = -1
        if Qt.Key.Key_1 <= key <= Qt.Key.Key_6:
            verse_idx = key - Qt.Key.Key_1
            
        if verse_idx != -1:
            self._on_verse_changed(verse_idx)
            # 버튼 UI 동기화
            btn = self._verse_group.button(verse_idx)
            if btn:
                btn.setChecked(True)
            self.statusBar().showMessage(f"레이어 전환: {verse_idx + 1 if verse_idx < 5 else '후렴'}", 1000)
            event.accept()
            return
        
        # [중요] 텍스트 입력 중일 때는 전역 키 조작을 하지 않음 (커서 이동/줄바꿈 보호)
        if isinstance(focused, (QLineEdit, QTextEdit, QPlainTextEdit)):
            super().keyPressEvent(event)
            return

        # 라이브 모드뿐만 아니라 편집 모드에서도 방향키 탐색 지원
        current_sheet = self._project.get_current_score_sheet()
        selected_id = getattr(self._canvas, '_selected_hotspot_id', None)
        
        # 방향키: 핫스팟 탐색 시스템 (현재 모드 내에서만 순환)
        if key == Qt.Key.Key_Right:
            target = None
            if current_sheet:
                v_idx = self._project.current_verse_index
                ordered = current_sheet.get_ordered_hotspots()
                
                # 탐색 대상(eligible) 결정 및 정렬 규칙: (레이어 간 물리적/논리적 분리 엄격 적용)
                chorus_ids = [h.id for h in ordered if ("5" in h.slide_mappings or h.get_slide_index(5) >= 0)]
                
                if v_idx < 5:
                    # 1~5절 모드: 오직 절 전용 버튼(숫자)들만 탐색하고 순환함
                    eligible = [h for h in ordered if h.id not in chorus_ids]
                else:
                    # 후렴 모드: 오직 후렴 전용 버튼(ABC)들만 탐색하고 순환함
                    eligible = [h for h in ordered if h.id in chorus_ids]
                
                if not eligible:
                    event.accept()
                    return

                if selected_id:
                    # 현재 가사의 순서 찾기
                    cur_idx = -1
                    for i, h in enumerate(eligible):
                        if h.id == selected_id:
                            cur_idx = i
                            break
                    
                    if cur_idx != -1 and cur_idx < len(eligible) - 1:
                        # 1. 다음 버튼으로 이동
                        target = eligible[cur_idx + 1]
                    else:
                        # 2. 마지막이면 해당 모드의 처음으로 순환 (다른 레이어로 점프 금지)
                        target = eligible[0]
                else:
                    # 선택된 게 없으면 해당 모드의 첫 번째 버튼
                    target = eligible[0]
            
            if target:
                self._canvas.select_hotspot(target.id)
                self._on_hotspot_selected(target)
                
                # 레이블 이름 판별 (상태바 표시용)
                label = ""
                # 어떤 버튼인지에 따라 A, B, C 또는 1, 2, 3 판별
                chorus_ids = [h.id for h in ordered if ("5" in h.slide_mappings or h.get_slide_index(5) >= 0)]
                if target.id in chorus_ids:
                    c_idx = chorus_ids.index(target.id)
                    label = chr(65 + c_idx) if c_idx < 26 else str(c_idx + 1)
                else:
                    v_ids = [h.id for h in ordered if h.id not in chorus_ids]
                    v_num = v_ids.index(target.id) + 1 if target.id in v_ids else "?"
                    label = str(v_num)
                
                display_v = "후렴" if v_idx == 5 else f"{v_idx + 1}절"
                self.statusBar().showMessage(f"탐색({display_v}): {label}번 가사", 1000)
                event.accept()
                return
            event.accept()
            return

        elif key == Qt.Key.Key_Left:
            target = None
            if current_sheet:
                v_idx = self._project.current_verse_index
                ordered = current_sheet.get_ordered_hotspots()
                
                # 탐색 대상(eligible) 결정 및 정렬 규칙:
                chorus_ids = [h.id for h in ordered if ("5" in h.slide_mappings or h.get_slide_index(5) >= 0)]
                
                if v_idx < 5:
                    # 1~5절 모드: 오직 절 전용 버튼(숫자)들만 탐색함
                    eligible = [h for h in ordered if h.id not in chorus_ids]
                else:
                    # 후렴 모드: 후렴 전용 버튼(ABC)들만 탐색함
                    eligible = [h for h in ordered if h.id in chorus_ids]
                
                if not eligible:
                    event.accept()
                    return

                if selected_id:
                    # 현재 가사의 순서 찾기
                    cur_idx = -1
                    for i, h in enumerate(eligible):
                        if h.id == selected_id:
                            cur_idx = i
                            break
                    
                    if cur_idx > 0:
                        # 1. 이전 버튼으로 이동
                        target = eligible[cur_idx - 1]
                    else:
                        # 2. 처음이면 해당 모드의 마지막으로 순환 (다른 레이어로 점프 금지)
                        target = eligible[-1]
                else:
                    # 선택된 게 없으면 해당 모드의 마지막 버튼
                    target = eligible[-1]
            
            if target:
                self._canvas.select_hotspot(target.id)
                self._on_hotspot_selected(target)
                
                # 레이블 이름 판별 (상태바 표시용)
                label = ""
                chorus_ids = [h.id for h in ordered if ("5" in h.slide_mappings or h.get_slide_index(5) >= 0)]
                if target.id in chorus_ids:
                    c_idx = chorus_ids.index(target.id)
                    label = chr(65 + c_idx) if c_idx < 26 else str(c_idx + 1)
                else:
                    v_ids = [h.id for h in ordered if h.id not in chorus_ids]
                    v_num = v_ids.index(target.id) + 1 if target.id in v_ids else "?"
                    label = str(v_num)
                
                display_v = "후렴" if v_idx == 5 else f"{v_idx + 1}절"
                self.statusBar().showMessage(f"탐색({display_v}): {label}번 가사", 1000)
                event.accept()
                return
            event.accept()
            return
            
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            # 엔터: 라이브 송출
            self._live_controller.send_to_live()
            self._statusbar.showMessage("🔴 LIVE 송출!", 2000)
            event.accept()
            return
            
        elif key == Qt.Key.Key_Escape:
            # ESC: 송출 지움
            self._live_controller.clear_live()
            self._statusbar.showMessage("송출 지움", 2000)
            event.accept()
            return
            
        elif key == Qt.Key.Key_Up:
            # 위쪽 키: 이전 곡으로 전환
            if self._song_list.select_previous_song():
                event.accept()
                return
                
        elif key == Qt.Key.Key_Down:
            # 아래쪽 키: 다음 곡으로 전환
            if self._song_list.select_next_song():
                event.accept()
                return
                
        super().keyPressEvent(event)

    def _toggle_slide_preview(self, checked: bool) -> None:
        """상단 슬라이드 패널 보이기/숨기기"""
        self._slide_preview.setVisible(checked)
        if checked:
            self._statusbar.showMessage("슬라이드 목록을 표시합니다.", 2000)
        else:
            self._statusbar.showMessage("슬라이드 목록을 숨겼습니다. (Ctrl+H)", 2000)
