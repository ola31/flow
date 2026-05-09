"""Flow 메인 윈도우

편집/라이브 모드를 통합한 메인 애플리케이션 윈도우
"""

from pathlib import Path
import shutil

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QSplitter,
    QToolBar,
    QStatusBar,
    QFileDialog,
    QMessageBox,
    QTabWidget,
    QLabel,
    QFrame,
    QPushButton,
    QToolButton,
    QLineEdit,
    QTextEdit,
    QPlainTextEdit,
    QStackedWidget,
    QSizePolicy,
    QInputDialog,
)
from PySide6.QtGui import QAction, QKeySequence, QPixmap, QUndoStack
from PySide6 import QtGui
from PySide6.QtCore import Qt, QEvent
from flow.ui.undo_commands import (
    AddHotspotCommand,
    RemoveHotspotCommand,
    MoveHotspotCommand,
    MapSlideCommand,
    UnlinkAllSlidesCommand,
)

from flow.domain.project import Project
from flow.domain.score_sheet import ScoreSheet
from flow.domain.hotspot import Hotspot
from flow.repository.project_repository import ProjectRepository

from flow.ui.editor.song_list_widget import SongListWidget
from flow.ui.editor.score_canvas import ScoreCanvas

from flow.ui.editor.verse_selector import VerseSelector
from flow.ui.display.display_window import DisplayWindow
from flow.services.slide_manager import SlideManager
from flow.services.config_service import ConfigService
from flow.ui.project_launcher import ProjectLauncher
from flow.ui.screens.home_screen import HomeScreen
from flow.ui.screens.project_screen import ProjectScreen
from flow.ui.styles import (
    GLOBAL_STYLESHEET,
    TOOLBAR_DEFAULT,
    TOOLBAR_LIVE,
    TOOLBAR_SONG_EDIT,
    RED,
    RED_HOVER,
    RADIUS_MD,
    FONT_MD,
    SP_XS,
    SP_SM,
)
from flow.ui.dialogs import flow_show_install_guide


class MainWindow(QMainWindow):
    """Flow 메인 윈도우"""

    def __init__(self, workspace=None) -> None:
        super().__init__()

        self._project: Project | None = None
        self._project_path: Path | None = None
        self._is_standalone: bool = False
        self._parent_project: Project | None = None
        self._parent_project_path: Path | None = None
        self._workspace = workspace  # Workspace | None — 워크스페이스 모드 활성화 시 설정
        repo_base = workspace.projects_dir if workspace else (Path.home() / "flow_projects")
        self._repo = ProjectRepository(repo_base)
        self._config_service = ConfigService()
        self._sync_output_resolution()

        # 송출 관련
        self._display_window: DisplayWindow | None = None
        self._slide_manager = SlideManager()
        self._engine_dialog_shown = False
        self._slide_manager.engine_missing.connect(self._on_engine_missing)
        from flow.ui.live.live_controller import LiveController

        self._live_controller = LiveController(self, slide_manager=self._slide_manager)

        # Undo/Redo 관련
        self._undo_stack = QUndoStack(self)
        self._undo_stack.setUndoLimit(100)
        self._undo_stack.cleanChanged.connect(self._on_undo_stack_clean_changed)

        self._is_dirty = False
        self._in_transition = False

        # Emergency patch panel state
        self._patch_panel = None  # EmergencyPatchPanel | None
        self._patch_splitter = None  # QSplitter | None (unused — kept for API compat)
        self._patch_original_index = -1

        self._apply_global_style()
        self._setup_ui()
        self._setup_toolbar()
        self._setup_statusbar()
        self._connect_signals()

        # SongListWidget에 메인 윈도우 참조 연결 (경로 획득용)
        self._song_list.set_main_window(self)
        self._song_list.install_event_filter(self)  # [추가] 곡 목록 키 전역 필터

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

    def _clone_project(self, source_path: str) -> None:
        """워크스페이스 프로젝트를 복제해 새 프로젝트 생성.

        library 곡은 참조 그대로 유지, 로컬 오버라이드만 복사됨.
        """
        if self._workspace is None:
            QMessageBox.warning(
                self,
                "워크스페이스 필요",
                "복제는 워크스페이스 모드에서만 사용할 수 있습니다.",
            )
            return

        src_name = self._detect_workspace_project(Path(source_path))
        if src_name is None:
            QMessageBox.warning(
                self,
                "복제 불가",
                "이 프로젝트는 현재 워크스페이스에 속하지 않아 복제할 수 없습니다.",
            )
            return

        from flow.ui.dialogs import flow_input_text

        new_name, ok = flow_input_text(
            self,
            "프로젝트 복제",
            f"'{src_name}'의 복사본 이름:",
            default=f"{src_name} 복사본",
        )
        if not ok or not new_name:
            return

        try:
            self._repo.clone_workspace_project(self._workspace, src_name, new_name)
            self._launcher.refresh_workspace_items()
            self._statusbar.showMessage(
                f"프로젝트 '{src_name}'을(를) '{new_name}'(으)로 복제했습니다."
            )
        except FileExistsError:
            QMessageBox.warning(
                self,
                "이미 존재합니다",
                f"같은 이름의 프로젝트가 이미 있습니다: {new_name}",
            )
        except Exception as e:
            QMessageBox.critical(
                self, "복제 실패", f"프로젝트를 복제할 수 없습니다:\n{e}"
            )

    def _detect_workspace_project(self, path: Path) -> str | None:
        """path가 현재 워크스페이스 내의 프로젝트면 프로젝트 이름 반환.

        path가 workspace/projects/{name}/project.json 형태이고
        self._workspace가 설정되어 있으면 {name}을 반환, 아니면 None.
        """
        if self._workspace is None:
            return None
        try:
            rel = Path(path).resolve().relative_to(self._workspace.projects_dir)
        except ValueError:
            return None
        # projects/{name}/project.json 형태여야 함
        parts = rel.parts
        if len(parts) == 2 and parts[1] == "project.json":
            return parts[0]
        return None

    def _switch_workspace(self) -> None:
        """워크스페이스 변경 다이얼로그 열기"""
        from flow.ui.workspace_dialog import WorkspaceDialog
        from flow.domain.workspace import Workspace
        from flow.repository.project_repository import ProjectRepository

        recent = self._config_service.get_recent_workspaces()
        dlg = WorkspaceDialog(recent_paths=recent, parent=self)
        if dlg.exec() != dlg.DialogCode.Accepted or dlg.selected_workspace is None:
            return

        ws: Workspace = dlg.selected_workspace
        self._workspace = ws
        self._repo = ProjectRepository(ws.projects_dir)
        self._config_service.add_recent_workspace(str(ws.root))

        # 현재 프로젝트가 있으면 닫고 홈으로
        self._project = None
        self._project_path = None
        self.show_home()

    def _remove_recent_item(self, path: str, item_type: str):
        """카드에서 '목록에서 제거' 선택 시 호출.

        - 레거시 모드: config의 최근 목록에서 제거 (파일은 보존)
        - 워크스페이스 모드 + 프로젝트: 확인 후 projects/{name}/ 폴더 삭제
        """
        # 워크스페이스 프로젝트는 파일시스템에서도 제거
        if item_type == "project" and self._workspace is not None:
            ws_name = self._detect_workspace_project(Path(path))
            if ws_name is not None:
                from flow.ui.dialogs import flow_question, flow_error
                ok = flow_question(
                    self,
                    "프로젝트 삭제",
                    f"'{ws_name}' 프로젝트를 워크스페이스에서 완전히 삭제할까요?\n"
                    "로컬 곡(songs/)도 함께 삭제됩니다. library/의 공용 곡은 영향받지 않습니다.",
                    yes_text="삭제", no_text="취소",
                )
                if not ok:
                    return
                try:
                    self._repo.delete_workspace_project(self._workspace, ws_name)
                except Exception as e:
                    flow_error(
                        self, "삭제 실패", f"프로젝트를 삭제할 수 없습니다:\n{e}"
                    )
                    return
                self._launcher.refresh_workspace_items()
                self._statusbar.showMessage(f"'{ws_name}' 프로젝트를 삭제했습니다.")
                return

        # 레거시 모드: config에서만 제거
        if item_type == "project":
            self._config_service.remove_recent_project(path)
        else:
            self._config_service.remove_recent_song(path)

        self._launcher.set_recent_items(
            self._config_service.get_recent_projects(),
            self._config_service.get_recent_songs(),
        )

    def show_home(self) -> None:
        self._stack.setCurrentIndex(0)
        if self._workspace is not None:
            self._launcher.set_workspace(self._workspace)
        else:
            self._home_screen.set_recent_items(
                self._config_service.get_recent_projects(),
                self._config_service.get_recent_songs(),
            )
        self._toolbar.hide()
        self._statusbar.hide()
        self.setWindowTitle("Flow - 시작하기")

    def _on_engine_missing(self) -> None:
        """SlideManager가 PPT 변환 엔진을 못 찾았을 때 설치 안내를 띄운다.

        세션당 한 번만 띄우도록 _engine_dialog_shown 플래그를 사용.
        """
        if self._engine_dialog_shown:
            return
        self._engine_dialog_shown = True
        flow_show_install_guide(self)

    def _show_launcher(self):
        self.show_home()

    def _show_library_screen(self) -> None:
        """ActivityBar의 라이브러리 버튼 → 곡 라이브러리 페이지."""
        if self._workspace is None:
            self.show_home()
            return
        self._library_screen.set_workspace(self._workspace)
        self._stack.setCurrentWidget(self._library_screen)
        self._toolbar.hide()
        self._statusbar.hide()
        self.setWindowTitle("Flow - 라이브러리")

    def _show_projects_screen(self) -> None:
        """ActivityBar의 프로젝트 버튼 → 프로젝트 페이지."""
        if self._workspace is None:
            self.show_home()
            return
        self._projects_screen.set_workspace(self._workspace)
        self._stack.setCurrentWidget(self._projects_screen)
        self._toolbar.hide()
        self._statusbar.hide()
        self.setWindowTitle("Flow - 프로젝트")

    def show_project(self) -> None:
        self._stack.setCurrentIndex(1)
        self._toolbar.show()
        self._statusbar.show()
        if self._project:
            self.setWindowTitle(f"Flow - {self._project.name}")
        self._is_live = False
        self._live_mode_action.setChecked(False)
        self._canvas.set_edit_mode(True)
        self._set_project_editable(True)
        self._update_toolbar_for_mode("default")

    def _show_editor(self):
        self.show_project()

    def _setup_ui(self) -> None:
        self.setWindowTitle("Flow - 슬라이드 송출")
        self.setMinimumSize(840, 600)

        from PySide6.QtCore import QByteArray

        geo_str, state_str = self._config_service.get_window_layout()
        if geo_str:
            self.restoreGeometry(QByteArray.fromHex(geo_str.encode()))
        if state_str:
            self.restoreState(QByteArray.fromHex(state_str.encode()))

        # 활동바 + 콘텐츠 스택 — VS Code 패턴
        from flow.ui.activity_bar import ActivityBar

        central = QWidget()
        central_layout = QHBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)

        self._activity_bar = ActivityBar()
        self._activity_bar.home_requested.connect(self._close_current_project)
        self._activity_bar.settings_requested.connect(self._show_settings)
        self._activity_bar.library_requested.connect(self._show_library_screen)
        self._activity_bar.projects_requested.connect(self._show_projects_screen)
        central_layout.addWidget(self._activity_bar)

        self._stack = QStackedWidget()
        central_layout.addWidget(self._stack, 1)
        self.setCentralWidget(central)

        self._home_screen = HomeScreen()
        self._stack.addWidget(self._home_screen)

        self._project_screen = ProjectScreen(self._slide_manager, self._config_service)
        self._stack.addWidget(self._project_screen)

        from flow.ui.screens.markdown_editor_screen import MarkdownEditorScreen
        self._markdown_editor_screen = MarkdownEditorScreen()
        self._markdown_editor_screen.back_requested.connect(self._exit_markdown_editor)
        self._stack.addWidget(self._markdown_editor_screen)
        self._markdown_editor_prev_index: int = 1  # default fallback to project

        # Library / Projects browser screens
        from flow.ui.screens.library_screen import LibraryScreen
        from flow.ui.screens.projects_screen import ProjectsScreen
        self._library_screen = LibraryScreen()
        self._library_screen.song_selected.connect(self._open_song_by_path)
        self._library_screen.new_song_requested.connect(
            lambda: self._launcher.new_song_requested.emit()
        )
        self._stack.addWidget(self._library_screen)

        self._projects_screen = ProjectsScreen()
        self._projects_screen.project_selected.connect(self._open_project_by_path)
        self._projects_screen.new_project_requested.connect(
            lambda: self._launcher.new_project_requested.emit()
        )
        self._stack.addWidget(self._projects_screen)

        self._launcher = self._home_screen.launcher
        self._toolbar = self._project_screen.toolbar_container
        self._slide_preview = self._project_screen.slide_preview
        self._song_list = self._project_screen.song_list
        self._canvas = self._project_screen.canvas
        self._verse_selector = self._project_screen.verse_selector
        self._pip = self._project_screen.pip
        self._mapping_panel = self._project_screen.mapping_panel
        self._h_splitter = self._project_screen.h_splitter
        self._v_splitter = self._project_screen.v_splitter

        self._slide_preview.slide_selected.connect(self._on_slide_selected)
        self._slide_preview.slide_double_clicked.connect(self._on_slide_double_clicked)
        self._slide_preview.slide_unlink_all_requested.connect(
            self._on_slide_unlink_all_requested
        )
        self._slide_preview._list.installEventFilter(self)
        self._slide_preview.reload_all_requested.connect(self._on_reload_all_ppt)
        self._slide_preview._btn_close.clicked.connect(self._on_close_ppt)

        self._verse_selector.verse_changed.connect(self._on_verse_changed)
        self._project_screen.live_verse_changed.connect(self._on_verse_changed)

        self._mapping_panel.verse_activated.connect(self._on_mapping_panel_verse)
        self._mapping_panel.unmap_requested.connect(self._on_mapping_panel_unmap)
        self._mapping_panel.closed.connect(self._on_mapping_panel_closed)

    def _apply_global_style(self):
        self.setStyleSheet(GLOBAL_STYLESHEET)

    def _setup_toolbar(self) -> None:
        """커스텀 1단 툴바 설정 (모드별 자동 전환).

        Linear-style: 슬림 헤더 (40px 정도), 헤어라인 separator,
        패딩 최소화로 콘텐츠 영역 최대화.
        """
        from flow.ui.styles import BORDER_SUBTLE_RGBA

        self._toolbar.setFixedHeight(44)
        layout = QHBoxLayout(self._toolbar)
        layout.setContentsMargins(SP_SM, SP_XS, SP_SM, SP_XS)
        layout.setSpacing(2)

        # 공통 버튼 생성 헬퍼
        def create_tool_btn(action, icon_only=False):
            btn = QToolButton()
            btn.setDefaultAction(action)
            btn.setMinimumHeight(32)
            if icon_only:
                btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            else:
                btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            return btn

        def create_sep():
            sep = QFrame()
            sep.setFrameShape(QFrame.Shape.VLine)
            sep.setFrameShadow(QFrame.Shadow.Plain)
            sep.setStyleSheet(
                f"background-color: {BORDER_SUBTLE_RGBA}; "
                "width: 1px; margin: 8px 4px; max-width: 1px;"
            )
            return sep

        # === 모든 액션 생성 (단축키 유지를 위해) ===
        from flow.ui.icons import icon_qicon

        self._new_song_action = QAction("새 곡", self)
        self._new_song_action.triggered.connect(self._new_song)

        self._open_action = QAction("열기", self)
        self._open_action.setShortcut(QKeySequence.StandardKey.Open)
        self._open_action.triggered.connect(self._open_project)

        self._save_action = QAction(icon_qicon("save", 18, "#a0a0a0"), "저장", self)
        self._save_action.setShortcut(QKeySequence.StandardKey.Save)
        self._save_action.triggered.connect(self._save_project)

        self._save_as_action = QAction("다른 이름 저장", self)
        self._save_as_action.triggered.connect(self._save_project_as)

        self._close_project_action = QAction(icon_qicon("home", 18, "#a0a0a0"), "홈", self)
        self._close_project_action.triggered.connect(self._close_current_project)

        self._back_to_project_action = QAction(icon_qicon("arrow_back", 18, "#a0a0a0"), "프로젝트로 돌아가기", self)
        self._back_to_project_action.triggered.connect(self._exit_song_edit_mode)

        self._settings_action = QAction(icon_qicon("settings", 18, "#a0a0a0"), "설정", self)
        self._settings_action.setToolTip("환경설정")
        self._settings_action.triggered.connect(self._show_settings)

        self._toggle_slide_action = QAction("슬라이드 목록", self)
        self._toggle_slide_action.setCheckable(True)
        self._toggle_slide_action.setChecked(True)
        self._toggle_slide_action.setShortcut("Ctrl+H")
        self._toggle_slide_action.triggered.connect(self._toggle_slide_preview)
        self.addAction(self._toggle_slide_action)

        self._live_mode_action = QAction(icon_qicon("play", 18, "#a0a0a0"), "라이브 F5", self)
        self._live_mode_action.setCheckable(True)
        self._live_mode_action.triggered.connect(self._toggle_live_mode)
        self._is_live = False

        self._exit_live_action = QAction("라이브 종료", self)
        self._exit_live_action.triggered.connect(self._toggle_live_mode)

        self._display_action = QAction(icon_qicon("tv", 18, "#a0a0a0"), "송출 시작", self)
        self._display_action.setShortcut("F11")
        self._display_action.setEnabled(False)
        self._display_action.triggered.connect(self._toggle_display)

        undo_action = self._undo_stack.createUndoAction(self, "실행 취소")
        undo_action.setIcon(icon_qicon("undo", 18, "#a0a0a0"))
        undo_action.setShortcut(QKeySequence.Undo)
        self._undo_action = undo_action
        self.addAction(undo_action)

        redo_action = self._undo_stack.createRedoAction(self, "다시 실행")
        redo_action.setIcon(icon_qicon("redo", 18, "#a0a0a0"))
        redo_action.setShortcuts([QKeySequence.Redo, QtGui.QKeySequence("Ctrl+Y")])
        self._redo_action = redo_action
        self.addAction(redo_action)

        # === 버튼 인스턴스 생성 (모드별 show/hide 대상) ===
        self._btn_home = create_tool_btn(self._close_project_action)
        self._btn_save = create_tool_btn(self._save_action)
        self._btn_save_as = create_tool_btn(self._save_as_action)
        self._btn_settings = create_tool_btn(self._settings_action)
        self._btn_undo = create_tool_btn(self._undo_action)
        self._btn_redo = create_tool_btn(self._redo_action)
        self._btn_to_live = create_tool_btn(self._live_mode_action)
        self._btn_display = create_tool_btn(self._display_action)
        self._btn_back = create_tool_btn(self._back_to_project_action)

        self._btn_exit_live = QPushButton("라이브 종료  Esc")
        self._btn_exit_live.setFixedHeight(32)
        self._btn_exit_live.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_exit_live.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_exit_live.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {RED};
                border: 1px solid {RED}; border-radius: {RADIUS_MD}px;
                font-size: {FONT_MD}px; font-weight: 500; padding: 0 18px;
            }}
            QPushButton:hover {{
                background: {RED}; color: #fff;
            }}
        """)
        self._btn_exit_live.clicked.connect(self._toggle_live_mode)
        self._btn_exit_live.hide()

        # 구분선 인스턴스
        self._sep_edit1 = create_sep()
        self._sep_edit2 = create_sep()
        self._sep_live1 = create_sep()
        self._sep_song1 = create_sep()

        # 라이브 송출 중 배지 — 빨간 닷 + 텍스트, 라이브 모드에서만 표시
        self._live_badge = QLabel("●  라이브 송출 중")
        self._live_badge.setStyleSheet(
            f"color: {RED}; background: transparent; "
            f"font-size: {FONT_MD}px; font-weight: 600; padding: 0 8px;"
        )
        self._live_badge.hide()

        # === 모드별 버튼 그룹 정의 ===
        # 홈/설정은 활동바(좌측)로 이동했으므로 툴바에서 제거됨
        self._toolbar_groups = {
            "default": [
                self._btn_save,
                self._btn_save_as,
                "stretch",
                self._btn_undo,
                self._btn_redo,
                self._sep_live1,
                self._btn_to_live,
            ],
            "live": [
                self._live_badge,
                "stretch",
                self._btn_display,
                self._btn_exit_live,
            ],
            "song_edit": [
                self._btn_back,
                self._sep_song1,
                self._btn_save,
                self._btn_save_as,
                "stretch",
                self._btn_undo,
                self._btn_redo,
            ],
        }

    def _update_toolbar_for_mode(self, mode: str) -> None:
        """모드별 툴� 버튼 show/hide 업데이트"""
        if mode not in self._toolbar_groups:
            return

        layout = self._toolbar.layout()

        # 기존 위젯/스페이서 모두 제거
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().hide()
            del item

        # 모든 버튼/구분선 숨김
        for btn in [
            self._btn_home,
            self._btn_save,
            self._btn_save_as,
            self._btn_settings,
            self._btn_undo,
            self._btn_redo,
            self._btn_to_live,
            self._btn_display,
            self._btn_back,
            self._btn_exit_live,
        ]:
            btn.hide()
        for sep in [
            self._sep_edit1,
            self._sep_edit2,
            self._sep_live1,
            self._sep_song1,
        ]:
            sep.hide()

        # 해당 모드 그룹만 레이아웃에 추가
        group = self._toolbar_groups[mode]
        for item in group:
            if item == "stretch":
                layout.addStretch()
            elif isinstance(item, QFrame):  # separator
                item.show()
                layout.addWidget(item)
            else:  # button
                item.show()
                layout.addWidget(item)

        # 툴� 스타일 업데이트
        self._update_toolbar_style(mode)

    def _update_toolbar_style(self, mode: str) -> None:
        styles = {
            "song_edit": TOOLBAR_SONG_EDIT,
            "live": TOOLBAR_LIVE,
        }
        self._toolbar.setStyleSheet(styles.get(mode, TOOLBAR_DEFAULT))

    def _setup_statusbar(self) -> None:
        """상태바 설정"""
        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)
        self._statusbar.showMessage("준비됨")

    def _connect_signals(self) -> None:
        """시그널 연결"""
        # 런처 시그널
        self._launcher.project_selected.connect(self._open_project_by_path)
        self._launcher.song_selected.connect(self._open_song_by_path)
        self._launcher.new_project_requested.connect(self._new_project)
        self._launcher.new_song_requested.connect(self._new_song)
        self._launcher.open_project_requested.connect(self._open_project)
        self._launcher.remove_recent_requested.connect(self._remove_recent_item)
        self._launcher.switch_workspace_requested.connect(self._switch_workspace)
        self._launcher.clone_project_requested.connect(self._clone_project)

        # 곡 목록 시그널
        self._song_list.song_selected.connect(self._on_song_selected)
        self._song_list.song_added.connect(self._on_song_added)
        self._song_list.song_edit_requested.connect(self._enter_song_edit_mode)

        # 캔버스 시그널 (Undo 대응 요청 시그널로 변경)
        self._canvas.hotspot_created_request.connect(self._on_hotspot_created_request)
        self._canvas.hotspot_removed_request.connect(self._on_hotspot_removed_request)
        self._canvas.hotspot_selected.connect(self._on_hotspot_selected)
        self._canvas.hotspot_moved.connect(self._on_hotspot_moved)
        self._canvas.hotspot_unmap_request.connect(self._on_hotspot_unmap_request)
        self._canvas.popover_mapping_requested.connect(self._on_popover_mapping)
        self._canvas.popover_unmap_requested.connect(self._on_popover_unmap)
        self._canvas.slide_dropped_on_hotspot.connect(self._on_popover_mapping)
        self._canvas.live_hotspot_clicked.connect(self._on_live_hotspot_clicked)
        self._canvas.emergency_patch_requested.connect(
            self._on_canvas_emergency_patch_requested
        )
        self._slide_preview.emergency_patch_requested.connect(
            self._on_preview_emergency_patch_requested
        )
        self._slide_preview.append_slide_requested.connect(
            self._on_append_slide_requested
        )
        # Whenever the thumbnail list is rebuilt, recompute the AMBER patch
        # badge set so existing patches show up immediately on song load.
        self._slide_preview.slides_refreshed.connect(
            self._recompute_patched_badges
        )

        # 라이브 컨트롤러 시그널 - 메인 윈도우 및 송출창 업데이트
        self._live_controller.live_changed.connect(self._on_live_changed)
        # 슬라이드 이미지 송출 연결
        self._live_controller.slide_changed.connect(self._on_slide_changed)

        # PPT 비동기 로딩 시그널
        self._slide_manager.load_started.connect(self._on_ppt_load_started)
        self._slide_manager.load_finished.connect(self._on_ppt_load_finished)
        self._slide_manager.load_error.connect(self._on_ppt_load_error)
        self._slide_manager.load_progress.connect(self._on_ppt_load_progress)
        self._slide_manager.load_status.connect(self._on_ppt_load_status)

        self._slide_manager.songs_metadata_started.connect(
            self._on_songs_metadata_started
        )
        self._slide_manager.songs_metadata_finished.connect(
            self._on_songs_metadata_finished
        )

        # 프로젝트 변경 감지 시그널 (SongListWidget)
        self._song_list.song_added.connect(self._on_song_added)
        self._song_list.song_removed.connect(self._on_song_removed)
        self._song_list.song_reload_requested.connect(self._on_reload_song_ppt)

    # === 프로젝트 관리 ===

    def _check_unsaved_changes(self) -> bool:
        if not self._is_dirty and self._undo_stack.isClean():
            return True

        from flow.ui.dialogs import flow_save_changes, SAVE, DISCARD

        choice = flow_save_changes(self)
        if choice == SAVE:
            self._save_project()
            return True
        return choice == DISCARD

    def _new_project(self) -> None:
        """새 프로젝트 폴더 생성 및 시작"""
        if not self._check_unsaved_changes():
            return

        # 워크스페이스 모드: 이름만 묻고 workspace/projects/ 하위에 생성
        if self._workspace is not None:
            from flow.ui.dialogs import flow_input_text

            name, ok = flow_input_text(
                self, "새 프로젝트", "프로젝트 이름:",
                placeholder="예: 2024-12-25 공연",
            )
            if not ok or not name:
                return

            project_dir = self._workspace.project_dir(name)
            if project_dir.exists():
                QMessageBox.warning(
                    self,
                    "이미 존재합니다",
                    f"같은 이름의 프로젝트가 이미 있습니다:\n{project_dir}",
                )
                return

            try:
                self._is_standalone = False
                self._project = Project(name=name)
                self._live_controller.set_project(self._project)
                self._project_path = self._repo.save_to_workspace(
                    self._project, self._workspace
                )

                self._song_list.set_standalone(False)
                self._canvas.set_hotspot_editable(False)
                self._song_list.set_project(self._project)
                self._canvas.set_score_sheet(None)
                self._slide_manager.load_pptx("")
                self._slide_preview.refresh_slides()

                self.setWindowTitle(f"Flow - {name}")
                self._clear_dirty()
                self._show_editor()
                self._statusbar.showMessage(f"새 프로젝트가 생성되었습니다: {name}")
            except Exception as e:
                QMessageBox.critical(
                    self, "오류", f"프로젝트를 생성할 수 없습니다:\n{e}"
                )
            return

        # 레거시 모드: 파일 다이얼로그로 위치 선택
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "새 프로젝트 생성 (폴더명 입력)",
            str(self._repo.base_path / "새 프로젝트.json"),
            "Flow 프로젝트 (*.json)",
        )

        if not file_path:
            return

        p_base = Path(file_path).resolve()
        if p_base.suffix.lower() == ".json":
            p_base = p_base.with_suffix("")

        project_dir = p_base
        self._is_standalone = False
        self._project_path = project_dir / "project.json"
        self._project = Project(name=project_dir.name)
        self._live_controller.set_project(self._project)

        try:
            project_dir.mkdir(parents=True, exist_ok=True)
            self._repo.save(self._project, self._project_path)

            self._song_list.set_standalone(False)
            self._canvas.set_hotspot_editable(False)
            self._song_list.set_project(self._project)
            self._canvas.set_score_sheet(None)
            self._slide_manager.load_pptx("")
            self._slide_preview.refresh_slides()

            self.setWindowTitle(f"Flow - {self._project.name}")
            self._config_service.add_recent_project(str(self._project_path))
            self._clear_dirty()
            self._show_editor()
            self._statusbar.showMessage(f"새 프로젝트가 생성되었습니다: {project_dir}")
        except Exception as e:
            QMessageBox.critical(
                self, "오류", f"프로젝트 폴더를 생성할 수 없습니다:\n{e}"
            )

    def _new_song(self) -> None:
        # 1. 곡 이름 입력 받기
        from flow.ui.dialogs import flow_input_text

        name, ok = flow_input_text(
            self, "새 곡 생성", "곡 제목을 입력하세요:",
            placeholder="예: 새 곡 이름",
        )
        if not ok or not name:
            return

        # 2. 모드에 따른 처리
        if self._project and not self._is_standalone:
            song_dir = self._project_path.parent / "songs" / name

            try:
                self._repo.init_song_folder(song_dir, name)

                virtual_proj = self._repo.load_standalone_song(song_dir)
                new_song = virtual_proj.selected_songs[0]
                new_song.project_dir = self._project_path.parent
                new_song.folder = Path("songs") / name

                if new_song.name not in [s.name for s in self._project.selected_songs]:
                    self._project.selected_songs.append(new_song)
                    if new_song.name not in self._project.song_order:
                        self._project.song_order.append(new_song.name)

                self._song_list.refresh_list()

                if new_song.score_sheets:
                    target_sheet = new_song.score_sheets[0]
                    self._on_song_selected(target_sheet)
                    self._song_list.select_sheet_by_id(target_sheet.id)

                self._mark_dirty()
                self._statusbar.showMessage(
                    f"새 곡이 프로젝트에 추가되었습니다: {name}", 3000
                )

                self._prompt_song_format(new_song)

            except Exception as e:
                QMessageBox.critical(self, "오류", f"곡을 생성할 수 없습니다:\n{e}")

        else:
            if not self._check_unsaved_changes():
                return

            folder = QFileDialog.getExistingDirectory(
                self, "곡 폴더를 생성할 위치 선택", str(self._repo.base_path)
            )
            if not folder:
                return

            song_dir = Path(folder) / name

            try:
                self._is_standalone = True
                self._project = self._repo.create_standalone_song(song_dir, name)
                self._project_path = song_dir
                self._live_controller.set_project(self._project)

                self._song_list.set_standalone(True)
                self._canvas.set_hotspot_editable(True)
                self._song_list.set_project(self._project)
                self._canvas.set_score_sheet(None)
                self._slide_manager.load_pptx("")
                self._slide_manager.load_songs(self._project.selected_songs)

                self.setWindowTitle(f"Flow - {self._project.name}")
                self._clear_dirty()
                self._show_editor()
                self._statusbar.showMessage(f"새 곡이 생성되었습니다: {name}")

                # 슬라이드 형식 선택 (standalone 모드에서도 동일하게)
                if self._project.selected_songs:
                    self._prompt_song_format(self._project.selected_songs[0])
                else:
                    QMessageBox.information(
                        self,
                        "새 곡 편집 시작",
                        f"'{name}' 곡이 생성되었습니다.\n\n"
                        "1. 왼쪽 하단의 '+ 시트(이미지) 추가' 버튼으로 악보 이미지를 등록하세요.\n"
                        "2. 'PPT 가져오기' 버튼으로 슬라이드 파일을 등록하면 매핑을 시작할 수 있습니다.",
                    )
            except Exception as e:
                QMessageBox.critical(self, "오류", f"곡을 생성할 수 없습니다:\n{e}")

    def _prompt_song_format(self, song) -> None:
        """새 곡 생성 후 슬라이드 형식(마크다운/PPT) 선택 다이얼로그.

        마크다운 선택 시 starter 템플릿 생성 후 인앱 에디터 띄움.
        PPT 선택 시 그대로 둠 (기존 PPT 가져오기 등 흐름 사용).
        """
        from flow.ui.dialogs import flow_question

        use_markdown = flow_question(
            self,
            "슬라이드 형식 선택",
            "새 곡 슬라이드를 어떤 형식으로 시작할까요?\n\n"
            "• 마크다운: 텍스트로 가사를 적으면 Flow가 슬라이드로 자동 변환\n"
            "• PowerPoint: 외부 도구로 만든 .pptx 가져오기",
            yes_text="마크다운",
            no_text="PowerPoint",
        )
        if not use_markdown:
            return

        template = (
            "---\n"
            "main_size: 56\n"
            "sub_size: 18\n"
            "background: \"#000000\"\n"
            "---\n"
            "\n"
            f"# {song.name}\n"
            "\n"
            "## 1절\n"
            "\n"
            "첫 슬라이드 가사\n"
        )
        try:
            song.markdown_path.write_text(template, encoding="utf-8")
        except Exception as e:
            QMessageBox.warning(self, "오류", f"마크다운 파일 생성 실패: {e}")
            return

        self.show_markdown_editor(song)

    def show_markdown_editor(self, song) -> None:
        """곡의 마크다운 파일을 인앱 에디터 화면으로 띄움."""
        if not song.markdown_path.exists():
            QMessageBox.warning(
                self, "오류", f"마크다운 파일이 없습니다:\n{song.markdown_path}"
            )
            return
        self._markdown_editor_prev_index = self._stack.currentIndex()
        self._markdown_editor_screen.load_song(song)
        self._stack.setCurrentWidget(self._markdown_editor_screen)
        self._toolbar.hide()
        self._statusbar.hide()
        self.setWindowTitle(f"Flow - 마크다운 편집: {song.name}")

    def _exit_markdown_editor(self) -> None:
        """마크다운 에디터에서 이전 화면으로 복귀."""
        self._markdown_editor_screen.save_if_dirty()
        # 슬라이드 리렌더 트리거 — 현재 곡이 마크다운이면 캐시 리로드
        if self._slide_manager._pptx_path is not None:
            p = self._slide_manager._pptx_path
            if str(p).lower().endswith(".md"):
                self._slide_manager._markdown_converter.invalidate_cache(p)
                self._slide_manager.file_changed.emit()
        self._stack.setCurrentIndex(self._markdown_editor_prev_index)
        self._toolbar.show()
        self._statusbar.show()
        if self._project:
            self.setWindowTitle(f"Flow - {self._project.name}")

    def _enter_song_edit_mode(self, song) -> None:
        if self._is_live:
            from flow.ui.dialogs import flow_warning
            flow_warning(
                self,
                "라이브 모드",
                "라이브 송출 중에는 곡 편집 모드로 전환할 수 없습니다.\n"
                "먼저 라이브 모드를 종료해 주세요(Esc).",
            )
            return
        if not self._project or self._is_standalone:
            return

        self._in_transition = True
        self._localize_project_indices()
        self._canvas.set_score_sheet(None)

        try:
            self._parent_project = self._project
            self._parent_project_path = self._project_path

            # 곡 폴더 해석:
            #  1) Song.folder가 절대 경로(워크스페이스 library/local 모두 해당)
            #     이면 그대로 사용
            #  2) 상대 경로면 project_path.parent 기준으로 결합 (레거시)
            #  3) project_path가 없는 워크스페이스 모드라면 workspace에서 유추
            if song.folder is None:
                raise ValueError("곡에 폴더 경로가 지정되어 있지 않습니다.")
            if Path(song.folder).is_absolute():
                song_abs_dir = Path(song.folder)
            elif self._project_path is not None:
                song_abs_dir = self._project_path.parent / song.folder
            elif self._workspace is not None and self._project is not None:
                # 워크스페이스 모드에서 path가 아직 없지만 project 이름으로 추론
                song_abs_dir = (
                    self._workspace.project_dir(self._project.name) / song.folder
                )
            else:
                raise ValueError(
                    "프로젝트가 아직 저장되지 않아 곡 편집을 시작할 수 없습니다."
                )

            self._is_standalone = True
            self._project = self._repo.load_standalone_song(song_abs_dir)
            self._project_path = song_abs_dir

            self._live_controller.set_project(self._project)
            self._song_list.set_standalone(True)
            self._canvas.set_hotspot_editable(True)
            self._song_list.set_project(self._project)

            self._back_to_project_action.setText(
                f"'{self._parent_project.name}' 프로젝트로 돌아가기"
            )
            self._update_toolbar_for_mode("song_edit")

            self.setWindowTitle(f"Flow - [곡 편집] {song.name}")
            self._clear_dirty()
            self._statusbar.showMessage(f"곡 편집 모드로 전환되었습니다: {song.name}")

            sheets = self._project.all_score_sheets
            if sheets:
                self._on_song_selected(sheets[0])
                self._song_list.set_current_index(0)

            self._undo_stack.clear()
            self._slide_manager.reset_worker()
            self._in_transition = False
            self._slide_manager.load_songs(self._project.selected_songs)

        except Exception as e:
            self._in_transition = False
            self._project = self._parent_project
            self._project_path = self._parent_project_path
            self._parent_project = None
            self._is_standalone = False
            self._globalize_project_indices()
            # 비모달 상태바 알림 — 테스트 중 반복 발생해도 진행 차단 안 함
            # (자세한 원인은 로그로 확인)
            import traceback
            print(
                f"[_enter_song_edit_mode] FAILED: {e}\n{traceback.format_exc()}",
                flush=True,
            )
            self._statusbar.showMessage(
                f"곡 편집 모드로 전환 실패: {e}", 6000
            )

    def _reload_song_from_disk(self, song_name: str, song_dir: Path) -> None:
        import json
        from flow.domain.score_sheet import ScoreSheet

        song_json = song_dir / "song.json"
        if not song_json.exists() or not self._project:
            return

        try:
            with open(song_json, "r", encoding="utf-8-sig") as f:
                data = json.load(f)

            sheets_data = data.get("sheets", [])
            if not sheets_data and data.get("sheet"):
                sheets_data = [data["sheet"]]

            new_sheets = [ScoreSheet.from_dict(sd) for sd in sheets_data if sd]
            if not new_sheets:
                new_sheets = [ScoreSheet(name=song_name)]

            for song in self._project.selected_songs:
                if song.name == song_name:
                    song.score_sheets = new_sheets
                    break
        except Exception:
            pass

    def _exit_song_edit_mode(self) -> None:
        if not self._parent_project:
            return

        if not self._check_unsaved_changes():
            return

        self._in_transition = True
        self._canvas.set_score_sheet(None)

        try:
            edited_song_name = (
                self._project.selected_songs[0].name
                if self._project.selected_songs
                else None
            )
            edited_song_dir = self._project_path

            self._project = self._parent_project
            self._project_path = self._parent_project_path
            self._parent_project = None
            self._parent_project_path = None
            self._is_standalone = False

            if edited_song_name and edited_song_dir:
                self._reload_song_from_disk(edited_song_name, edited_song_dir)

            self._live_controller.set_project(self._project)
            self._song_list.set_standalone(False)
            self._canvas.set_hotspot_editable(False)
            self._song_list.set_project(self._project)

            self._update_toolbar_for_mode("default")
            self.setWindowTitle(f"Flow - {self._project.name}")
            self._clear_dirty()

            self._statusbar.showMessage(
                f"프로젝트로 복귀했습니다: {self._project.name}"
            )

            all_sheets = self._project.all_score_sheets
            if all_sheets:
                idx = self._project.current_sheet_index
                if 0 <= idx < len(all_sheets):
                    self._on_song_selected(all_sheets[idx])
                    self._song_list.set_current_index(idx)

            self._undo_stack.clear()
            self._slide_manager.reset_worker()
            self._in_transition = False

            if self._project and self._project.selected_songs:
                self._slide_manager.load_songs(self._project.selected_songs)

        except Exception as e:
            self._in_transition = False
            QMessageBox.critical(self, "오류", f"프로젝트 복귀 중 오류 발생:\n{e}")

    def _open_project(self) -> None:
        """프로젝트 열기"""
        if not self._check_unsaved_changes():
            return

        self._slide_manager.stop_workers()

        file_path, _ = QFileDialog.getOpenFileName(
            self, "프로젝트 열기", str(self._repo.base_path), "Flow 프로젝트 (*.json)"
        )

        if not file_path:
            return

        try:
            self._project = self._repo.load(Path(file_path))
            self._project_path = Path(file_path)

            # [추가] 로드 즉시 ID 충돌 체크 및 자동 복구 (마크 더티)
            if self._project.ensure_unique_ids():
                self._mark_dirty()

            self._live_controller.set_project(self._project)

            # 1. 곡 목록 갱신
            self._song_list.set_standalone(False)
            self._canvas.set_hotspot_editable(False)
            self._song_list.set_project(self._project)

            v_idx = self._project.current_verse_index
            self._verse_selector.set_current_verse(v_idx)
            self._canvas.set_verse_index(v_idx)

            # 2. 매핑 상태 UI 동기화
            self._update_mapped_slides_ui()

            # 3. PPT 로드 (새 구조 우선)
            if self._project.selected_songs:
                self._slide_manager.load_songs(self._project.selected_songs)
            elif self._project.pptx_path:
                self._slide_manager.load_pptx(self._project.pptx_path)
            else:
                self._slide_preview.refresh_slides()

            self.setWindowTitle(f"Flow - {self._project.name}")
            self._config_service.add_recent_project(str(self._project_path))
            self._clear_dirty()
            self._show_editor()
            self._statusbar.showMessage(f"프로젝트를 열었습니다: {self._project.name}")

        except Exception as e:
            QMessageBox.critical(self, "오류", f"프로젝트를 열 수 없습니다:\n{e}")

    def _open_project_by_path(self, path_str: str) -> None:
        """지정된 경로의 프로젝트를 직접 열기"""
        if not self._check_unsaved_changes():
            return

        self._slide_manager.stop_workers()

        from pathlib import Path

        path = Path(path_str)
        if not path.exists():
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.warning(self, "오류", "해당 프로젝트 파일이 존재하지 않습니다.")
            self._config_service.remove_recent_project(path_str)
            self._launcher.set_recent_items(
                self._config_service.get_recent_projects(),
                self._config_service.get_recent_songs(),
            )
            return

        try:
            self._is_standalone = False

            # 워크스페이스 프로젝트인지 감지 (projects/{name}/project.json 형태)
            workspace_project_name = self._detect_workspace_project(path)
            if workspace_project_name is not None:
                self._project = self._repo.load_from_workspace(
                    self._workspace, workspace_project_name
                )
            else:
                self._project = self._repo.load(path)
            self._project_path = path

            # [추가] 로드 즉시 ID 충돌 체크 및 자동 복구 (마크 더티)
            if self._project.ensure_unique_ids():
                self._mark_dirty()

            self._live_controller.set_project(self._project)

            # 곡 목록 및 UI 갱신 (기존 _open_project 로직과 유사)
            self._song_list.set_standalone(False)
            self._canvas.set_hotspot_editable(False)
            self._song_list.set_project(self._project)
            v_idx = self._project.current_verse_index
            self._verse_selector.set_current_verse(v_idx)
            self._canvas.set_verse_index(v_idx)
            self._update_mapped_slides_ui()

            if self._project.selected_songs:
                self._slide_manager.load_songs(self._project.selected_songs)
            elif self._project.pptx_path:
                self._slide_manager.load_pptx(self._project.pptx_path)
            else:
                self._slide_preview.refresh_slides()

            self.setWindowTitle(f"Flow - {self._project.name}")
            self._config_service.add_recent_project(path_str)
            self._clear_dirty()
            self._show_editor()
            self._statusbar.showMessage(f"프로젝트를 열었습니다: {self._project.name}")

        except Exception as e:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.critical(self, "오류", f"프로젝트를 열 수 없습니다:\n{e}")

    def _open_song_by_path(self, path_str: str) -> None:
        """지정된 경로의 단일 곡을 열기"""
        if not self._check_unsaved_changes():
            return

        self._slide_manager.stop_workers()

        path = Path(path_str)
        if not path.exists():
            QMessageBox.warning(self, "오류", "해당 곡 폴더가 존재하지 않습니다.")
            self._config_service.remove_recent_song(path_str)
            self._launcher.set_recent_items(
                self._config_service.get_recent_projects(),
                self._config_service.get_recent_songs(),
            )
            return

        try:
            self._is_standalone = True
            self._project = self._repo.load_standalone_song(path)
            self._project_path = path

            # [추가] 최근 곡 목록에 저장
            self._config_service.add_recent_song(path_str)

            self._live_controller.set_project(self._project)

            self._song_list.set_standalone(True)
            self._canvas.set_hotspot_editable(True)
            self._song_list.set_project(self._project)

            v_idx = self._project.current_verse_index
            self._verse_selector.set_current_verse(v_idx)
            self._canvas.set_verse_index(v_idx)
            self._update_mapped_slides_ui()

            if self._project.selected_songs:
                self._slide_manager.load_songs(self._project.selected_songs)

            self._clear_dirty()
            self._show_editor()
            self.setWindowTitle(f"Flow - {self._project.name}")
            self._statusbar.showMessage(f"곡을 열었습니다: {path.name}")

        except Exception as e:
            QMessageBox.critical(self, "오류", f"곡을 열 수 없습니다:\n{e}")

    def _save_project(self) -> None:
        """프로젝트 또는 단일 곡 저장"""
        if not self._project:
            return

        if self._is_standalone:
            try:
                self._repo.save_standalone_song(self._project)
                self._undo_stack.setClean()
                self._clear_dirty()  # [추가] 수동 dirty 플래그 명시적 제거
                self._statusbar.showMessage("곡 정보가 저장되었습니다.", 2000)
            except Exception as e:
                QMessageBox.critical(
                    self, "오류", f"곡 정보를 저장할 수 없습니다:\n{e}"
                )
            return

        # 저장 경로가 없거나 처음 저장하는 경우 이름/위치 묻기
        if not self._project_path:
            from PySide6.QtWidgets import QFileDialog

            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "프로젝트 저장",
                str(self._repo.base_path / f"{self._project.name}.json"),
                "Flow 프로젝트 (*.json)",
            )
            if not file_path:
                return
            from pathlib import Path

            self._project_path = Path(file_path)

        try:
            # 저장 전 로컬 인덱스로 변환
            self._localize_project_indices()

            # 워크스페이스 프로젝트면 save_to_workspace 사용
            ws_name = self._detect_workspace_project(self._project_path)
            if ws_name is not None:
                # 현재 프로젝트 이름이 바뀌었다면 이름도 반영
                self._project.name = ws_name
                self._project_path = self._repo.save_to_workspace(
                    self._project, self._workspace
                )
            else:
                self._project_path = self._repo.save(
                    self._project, self._project_path
                )

            # 다시 전역 인덱스로 원복
            self._globalize_project_indices()

            self.setWindowTitle(f"Flow - {self._project.name}")
            self._undo_stack.setClean()  # 저장 시점 기록
            self._clear_dirty()  # [추가] 수동 dirty 플래그 명시적 제거 (Undo 스택과 별개로 보장)
            self._statusbar.showMessage(
                f"프로젝트가 저장되었습니다: {self._project_path.name}"
            )
        except Exception as e:
            # 에러 발생 시에도 원복 시도
            self._globalize_project_indices()
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.critical(self, "오류", f"프로젝트를 저장할 수 없습니다:\n{e}")

    def _on_undo_stack_clean_changed(self, is_clean: bool) -> None:
        """Undo 스택 상태에 따른 dirty 표시 업데이트"""
        if is_clean:
            self._clear_dirty()
        else:
            self._mark_dirty()

    def _update_verse_buttons(self) -> None:
        self._verse_selector.set_max_verses(self._config_service.get_max_verses())

    def _show_settings(self) -> None:
        """환경설정 다이얼로그 표시"""
        from flow.ui.settings_dialog import SettingsDialog

        dialog = SettingsDialog(self._config_service, self)
        if dialog.exec():
            # 설정 변경 시 버튼 갱신
            self._update_verse_buttons()
            self._sync_output_resolution()
            self._statusbar.showMessage("설정이 저장되었습니다.", 2000)

    def _sync_output_resolution(self) -> None:
        """Push the configured output resolution into the converter + md renderer.

        Both modules cache target size in module globals so PPT- and
        markdown-sourced slides stay in sync without per-call plumbing.
        """
        from flow.services import slide_converter
        from flow.services.markdown import parser as md_parser

        size = self._config_service.get_output_resolution()
        slide_converter.set_target_size(size)
        md_parser.set_default_resolution(size)

    def _on_verse_changed(self, verse_index: int) -> None:
        if not self._project:
            return

        self._project.current_verse_index = verse_index
        self._canvas.set_verse_index(verse_index)
        self._verse_selector.set_current_verse(verse_index)
        self._project_screen.sync_nav_verse(verse_index)

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

        if self._is_live and self._live_controller.live_hotspot:
            self._live_controller.sync_live()

        self._update_mapped_slides_ui()

        # 매핑 패널 절 동기화
        if self._mapping_panel.isVisible():
            self._mapping_panel.set_active_verse(verse_index)

        v_text = "후렴" if verse_index == 5 else f"{verse_index + 1}절"
        self._statusbar.showMessage(f"{v_text}을(를) 선택했습니다.", 1000)

    def _save_project_as(self) -> None:
        """현재 프로젝트를 다른 이름(폴더 통째로 복사)으로 저장"""
        if not self._project:
            return

        if self._is_standalone:
            self._save_standalone_song_as()
            return

        if self._project_path:
            initial_path = (
                self._project_path.parent.parent / f"{self._project.name}_복사본.json"
            )
        else:
            initial_path = self._repo.base_path / f"{self._project.name}_복사본.json"

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "다른 이름으로 저장 (새 폴더 생성)",
            str(initial_path),
            "Flow 프로젝트 (*.json)",
        )

        if not file_path:
            return

        p_base = Path(file_path).resolve()
        if p_base.suffix.lower() == ".json":
            p_base = p_base.with_suffix("")

        new_project_dir = p_base
        old_project_dir = self._project_path.parent if self._project_path else None

        try:
            if new_project_dir.exists():
                shutil.rmtree(new_project_dir)

            if old_project_dir and old_project_dir.exists():
                shutil.copytree(old_project_dir, new_project_dir)
            else:
                new_project_dir.mkdir(parents=True, exist_ok=True)

            self._project.name = new_project_dir.name
            self._project_path = new_project_dir / "project.json"

            self._save_project()

            if self._project.pptx_path:
                self._slide_manager.load_pptx(self._project.pptx_path)

            self._statusbar.showMessage(
                f"프로젝트 전용 폴더가 생성되고 모든 파일이 복제되었습니다: {new_project_dir.name}"
            )

        except Exception as e:
            QMessageBox.critical(self, "오류", f"프로젝트를 복제할 수 없습니다:\n{e}")

    def _save_standalone_song_as(self) -> None:
        """곡 편집 모드: 곡 폴더를 다른 위치에 복사하여 저장"""
        song = self._project.selected_songs[0]
        old_song_dir = song.project_dir

        base_name = song.name.replace("[곡 편집] ", "")
        default_name = f"{base_name}_복사본"

        folder_name, ok = QInputDialog.getText(
            self, "곡 폴더 이름", "새 곡 폴더 이름:", text=default_name
        )
        if not ok or not folder_name.strip():
            return
        folder_name = folder_name.strip()

        initial_dir = (
            str(old_song_dir.parent) if old_song_dir else str(self._repo.base_path)
        )
        parent_dir = QFileDialog.getExistingDirectory(
            self, "저장할 위치 선택", initial_dir
        )
        if not parent_dir:
            return

        new_song_dir = Path(parent_dir).resolve() / folder_name
        if new_song_dir.exists():
            from flow.ui.dialogs import flow_question
            ok = flow_question(
                self,
                "폴더 존재",
                f"'{folder_name}' 폴더가 이미 존재합니다. 덮어쓰시겠습니까?",
                yes_text="덮어쓰기", no_text="취소",
            )
            if not ok:
                return
            shutil.rmtree(new_song_dir)

        try:
            if old_song_dir and old_song_dir.exists():
                shutil.copytree(old_song_dir, new_song_dir)
            else:
                new_song_dir.mkdir(parents=True, exist_ok=True)

            song.project_dir = new_song_dir
            song.name = new_song_dir.name
            self._project_path = new_song_dir
            self._project.name = f"[곡 편집] {song.name}"

            self._save_project()

            self.setWindowTitle(f"Flow - [곡 편집] {song.name}")
            self._clear_dirty()
            self._statusbar.showMessage(
                f"곡이 새 폴더에 저장되었습니다: {new_song_dir}"
            )

        except Exception as e:
            QMessageBox.critical(self, "오류", f"곡을 복제할 수 없습니다:\n{e}")

    # === 모드 전환 ===

    def _toggle_live_mode(self) -> None:
        if self._is_live:
            from flow.ui.dialogs import flow_question
            if flow_question(
                self,
                "라이브 모드 종료",
                "라이브 모드를 종료하시겠습니까?",
                yes_text="종료", no_text="계속 송출",
            ):
                self._exit_live()
        else:
            self._enter_live()

    def _on_live_hotspot_clicked(self, hotspot: Hotspot) -> None:
        if not self._is_live:
            return
        self._live_controller.set_preview(hotspot)
        self._statusbar.showMessage(
            f"프리뷰: #{hotspot.order + 1}  (Enter로 송출)", 1500
        )

    def _enter_live(self) -> None:
        self._is_live = True
        self._live_mode_action.setChecked(True)
        self._canvas.set_edit_mode(False)
        self._set_project_editable(False)
        self._display_action.setEnabled(True)
        if self._project:
            v_idx = self._project.current_verse_index
            self._project_screen.sync_nav_verse(v_idx)
            sheet = self._canvas.get_score_sheet()
            if sheet:
                song = next(
                    (
                        s
                        for s in (self._project.selected_songs or [])
                        if any(sh.id == sheet.id for sh in s.score_sheets)
                    ),
                    None,
                )
                self._project_screen.set_nav_song_name(
                    song.name if song else sheet.name
                )
        self._project_screen.set_live_mode(True)
        self._update_toolbar_for_mode("live")
        self._canvas.setFocus()
        self._statusbar.showMessage("라이브 — 핫스팟 클릭 → Enter로 송출  |  Esc로 종료")
        title = self.windowTitle().replace(" [LIVE]", "")
        self.setWindowTitle(title + " [LIVE]")
        # Propagate live + slide_source to widgets that gate emergency patch
        song = self._current_markdown_song()
        if song is not None:
            source = "markdown"
        else:
            try:
                sheet = self._canvas.get_score_sheet()
                actual_song = (
                    next(
                        (
                            s
                            for s in (self._project.selected_songs or [])
                            if sheet and any(sh.id == sheet.id for sh in s.score_sheets)
                        ),
                        None,
                    )
                    if self._project
                    else None
                )
                source = actual_song.slide_source if actual_song else "none"
            except Exception:
                source = "none"
        self._canvas.set_live_mode(is_live=True, slide_source=source)
        self._slide_preview.set_live_mode(is_live=True, slide_source=source)

    def _exit_live(self) -> None:
        self._is_live = False
        self._live_mode_action.setChecked(False)
        self._canvas.set_edit_mode(True)
        self._set_project_editable(True)
        if self._display_window and self._display_window.isVisible():
            self._toggle_display()
        self._display_action.setEnabled(False)
        self._canvas.set_live_mode(is_live=False, slide_source="none")
        self._slide_preview.set_live_mode(is_live=False, slide_source="none")
        self._close_emergency_patch_panel()  # close if open
        self._project_screen.set_live_mode(False)
        self._update_toolbar_for_mode("default")
        self._statusbar.showMessage("편집 모드")
        title = self.windowTitle().replace(" [LIVE]", "")
        self.setWindowTitle(title)

    # === 긴급 슬라이드 패치 (Emergency Patch Panel) ===

    def _current_markdown_song(self):
        """Return the active song iff its slide source is markdown, else None."""
        if not self._project:
            return None
        sheet = self._canvas.get_score_sheet()
        if sheet is None:
            return None
        song = next(
            (
                s
                for s in (self._project.selected_songs or [])
                if any(sh.id == sheet.id for sh in s.score_sheets)
            ),
            None,
        )
        if song is None:
            return None
        if song.slide_source != "markdown":
            return None
        return song

    def _resolve_global_slide(self, global_index: int):
        """Convert a project-global slide index to (song, local_index).

        Returns (song, local_index) when the index resolves to a markdown
        song, else (None, -1). The slide preview's thumbnail strip and
        Hotspot.get_slide_index() both report GLOBAL indices across all
        songs in the project.
        """
        try:
            song_name, local_idx = self._slide_manager.global_to_local(global_index)
        except (ValueError, AttributeError):
            return (None, -1)
        if not self._project:
            return (None, -1)
        song = next(
            (s for s in (self._project.selected_songs or []) if s.name == song_name),
            None,
        )
        if song is None or song.slide_source != "markdown":
            return (None, -1)
        return (song, local_idx)

    def _on_canvas_emergency_patch_requested(self, hotspot) -> None:
        if not self._is_live or not self._project:
            return
        verse_index = self._project.current_verse_index
        global_slide = hotspot.get_slide_index(verse_index)
        if global_slide < 0:
            global_slide = hotspot.get_slide_index(5)  # fallback to chorus
        if global_slide < 0:
            return
        song, local_idx = self._resolve_global_slide(global_slide)
        if song is None:
            return
        self._open_emergency_patch_panel(song=song, initial_index=local_idx)

    def _on_preview_emergency_patch_requested(self, slide_index: int) -> None:
        if not self._is_live:
            return
        song, local_idx = self._resolve_global_slide(slide_index)
        if song is None:
            return
        self._open_emergency_patch_panel(song=song, initial_index=local_idx)

    def _on_append_slide_requested(self) -> None:
        if not self._is_live:
            return
        # Append is anchored to the song that owns the canvas's current sheet
        song = self._current_markdown_song()
        if song is None:
            return
        self._open_emergency_patch_panel(song=song, initial_index=None)

    def _open_emergency_patch_panel(self, *, song, initial_index) -> None:
        from flow.services.markdown import PatchStore, apply_patches, parse
        from flow.ui.live.emergency_patch_panel import EmergencyPatchPanel

        if not self._is_live:
            return
        if self._patch_panel is not None:
            return  # already open

        md_path = song.markdown_path
        text = md_path.read_text(encoding="utf-8")
        spec = parse(text)
        store = PatchStore(md_path.parent / ".patches.json")
        patched_spec = apply_patches(spec, store.patches)

        panel = EmergencyPatchPanel(
            spec=patched_spec,
            song_dir=md_path.parent,
            initial_index=initial_index,
            parent=self._h_splitter,
        )
        panel.applied.connect(
            lambda payload: self._on_patch_applied(song, payload)
        )
        panel.close_requested.connect(self._close_emergency_patch_panel)

        # Bound the panel width so the QPlainTextEdit's growing sizeHint
        # can't push other splitter panes to zero as the operator types.
        panel.setMinimumWidth(360)
        panel.setMaximumWidth(560)

        # Snapshot pre-insert sizes so we can restore them on close.
        # Pre-insert layout = 4 panes [song_list, center, pip, mapping].
        self._patch_pre_sizes = list(self._h_splitter.sizes())

        # Insert as the leftmost pane (left of song_list). The patch session
        # is a focused emergency action that's visually distinct from the
        # normal project context.
        self._h_splitter.insertWidget(0, panel)
        # Post-insert layout: [patch, song_list, center, pip, mapping]
        # Preserve everything else; subtract the panel width from center.
        pre = self._patch_pre_sizes
        song_list_w = pre[0] if len(pre) > 0 else 220
        center_w_old = pre[1] if len(pre) > 1 else 800
        pip_w = pre[2] if len(pre) > 2 else 0
        mapping_w = pre[3] if len(pre) > 3 else 0
        panel_width = 400
        center_w_new = max(360, center_w_old - panel_width)
        new_sizes = [panel_width, song_list_w, center_w_new, pip_w, mapping_w]
        # Pad / clip so length matches splitter
        while len(new_sizes) < self._h_splitter.count():
            new_sizes.append(0)
        new_sizes = new_sizes[: self._h_splitter.count()]
        self._h_splitter.setSizes(new_sizes)
        # Stretch factors: center grows on window resize; everything else
        # keeps its snapshot width. Center is now at index 2.
        for i in range(self._h_splitter.count()):
            self._h_splitter.setStretchFactor(i, 1 if i == 2 else 0)

        self._patch_panel = panel
        # Application-level eventFilter to capture Tab regardless of which
        # widget currently has focus. Qt would otherwise deliver Tab to the
        # focused QPlainTextEdit (which uses setTabChangesFocus) instead of
        # bubbling up to MainWindow.keyPressEvent.
        from PySide6.QtWidgets import QApplication
        QApplication.instance().installEventFilter(self)

        # Focus the editor immediately so the operator can type right away.
        try:
            panel._editor.setFocus(Qt.FocusReason.OtherFocusReason)
        except AttributeError:
            pass

    def _close_emergency_patch_panel(self) -> None:
        if self._patch_panel is None:
            return
        from PySide6.QtWidgets import QApplication
        QApplication.instance().removeEventFilter(self)
        self._patch_panel.setParent(None)  # type: ignore[arg-type]
        self._patch_panel.deleteLater()
        self._patch_panel = None
        self._patch_splitter = None
        self._patch_original_index = -1
        # Restore the snapshot taken on open (4-pane layout).
        if self._is_live:
            pre = getattr(self, "_patch_pre_sizes", None) or [240, 800, 280, 0]
            self._h_splitter.setSizes(pre)

    def _patch_panel_has_focus(self) -> bool:
        """Return True when the emergency patch panel (or any child widget) has keyboard focus."""
        if self._patch_panel is None:
            return False
        try:
            return self._patch_panel.hasFocus() or self._patch_panel.isAncestorOf(
                self.focusWidget()
            )
        except (RuntimeError, AttributeError):
            return False

    def _toggle_patch_focus(self) -> None:
        """Toggle keyboard focus between the patch panel and the live canvas.

        The panel itself has FocusPolicy.NoFocus by default, so calling
        setFocus on the panel widget is a no-op. Focus the editor inside
        instead — that's what should receive keystrokes.
        """
        if self._patch_panel is None:
            return
        if self._patch_panel_has_focus():
            self._canvas.setFocus(Qt.FocusReason.TabFocusReason)
        else:
            try:
                self._patch_panel._editor.setFocus(Qt.FocusReason.TabFocusReason)
            except AttributeError:
                self._patch_panel.setFocus(Qt.FocusReason.TabFocusReason)

    def _on_patch_applied(self, song, payload: list) -> None:
        import uuid
        from datetime import datetime, timezone

        from flow.services.markdown import (
            PatchStore,
            PatchType,
            SlidePatch,
            parse,
            slide_hash,
        )

        md_path = song.markdown_path
        spec = parse(md_path.read_text(encoding="utf-8"))
        store = PatchStore(md_path.parent / ".patches.json")
        now = datetime.now(timezone.utc).isoformat()

        for key, text in payload:
            if isinstance(key, int):
                if 0 <= key < len(spec.slides):
                    h = slide_hash(spec.slides[key].main)
                else:
                    h = None
                store.add(
                    SlidePatch(
                        id=str(uuid.uuid4()),
                        type=PatchType.EDIT,
                        patched_main=text,
                        slide_hash=h,
                        slide_index=key,
                        created_at=now,
                        created_during="live",
                    )
                )
            else:
                store.add(
                    SlidePatch(
                        id=str(uuid.uuid4()),
                        type=PatchType.APPEND,
                        patched_main=text,
                        slide_hash=None,
                        slide_index=None,
                        created_at=now,
                        created_during="live",
                    )
                )
        store.save()

        # Invalidate cache so next read sees patches
        self._slide_manager._markdown_converter.invalidate_cache(md_path)
        # Rebuild the thumbnail strip so the new pixmaps reflect patches.
        # SlidePreviewPanel.refresh_slides() emits slides_refreshed which
        # triggers _recompute_patched_badges to set the AMBER dots.
        self._slide_preview.refresh_slides()
        self._refresh_live_display_for_patched(song)
        self._close_emergency_patch_panel()

    def _recompute_patched_badges(self) -> None:
        """Scan all markdown songs in the project and mark patched slides
        on the global thumbnail strip.

        Called from SlidePreviewPanel.slides_refreshed so badges re-appear
        whenever the thumbnail list is rebuilt — including when a song
        loads with patches from a previous session.
        """
        from flow.services.markdown import PatchStore, PatchType, parse

        global_indices: set[int] = set()
        if self._project is None:
            try:
                self._slide_preview.set_patched_indices(global_indices)
            except AttributeError:
                pass
            return

        for song in (self._project.selected_songs or []):
            if getattr(song, "slide_source", None) != "markdown":
                continue
            md_path = song.markdown_path
            try:
                store = PatchStore(md_path.parent / ".patches.json")
            except Exception:
                continue
            if not store.patches:
                continue
            try:
                spec = parse(md_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            n_original = len(spec.slides)
            try:
                base = self._slide_manager.local_to_global(song.name, 0)
            except (ValueError, AttributeError):
                continue
            for p in store.patches:
                if p.type is PatchType.EDIT and p.slide_index is not None:
                    if 0 <= p.slide_index < n_original:
                        global_indices.add(base + p.slide_index)
            n_appended = sum(
                1 for p in store.patches if p.type is PatchType.APPEND
            )
            for i in range(n_appended):
                global_indices.add(base + n_original + i)
        try:
            self._slide_preview.set_patched_indices(global_indices)
        except AttributeError:
            pass

    def _refresh_live_display_for_patched(self, song) -> None:
        """If the audience display is showing a slide that was just patched
        for `song`, re-emit the (now-patched) image."""
        if getattr(song, "slide_source", None) != "markdown":
            return
        from flow.services.markdown import PatchStore, PatchType, parse

        md_path = song.markdown_path
        try:
            store = PatchStore(md_path.parent / ".patches.json")
            spec = parse(md_path.read_text(encoding="utf-8"))
        except Exception:
            return
        n_original = len(spec.slides)
        local_patched: set[int] = set()
        for p in store.patches:
            if p.type is PatchType.EDIT and p.slide_index is not None:
                if 0 <= p.slide_index < n_original:
                    local_patched.add(p.slide_index)
        n_appended = sum(1 for p in store.patches if p.type is PatchType.APPEND)
        for i in range(n_appended):
            local_patched.add(n_original + i)

        try:
            lc = self._live_controller
            live_global: int = -1
            if lc._live_slide_index >= 0:
                live_global = lc._live_slide_index
            elif lc._live_hotspot is not None:
                v_idx = self._project.current_verse_index if self._project else 0
                slide_idx = lc._live_hotspot.get_slide_index(v_idx)
                if slide_idx < 0:
                    slide_idx = lc._live_hotspot.get_slide_index(5)
                if slide_idx >= 0:
                    live_global = slide_idx

            if live_global >= 0:
                try:
                    _name, local_idx = self._slide_manager.global_to_local(
                        live_global
                    )
                except Exception:
                    local_idx = live_global
                if local_idx in local_patched:
                    lc.sync_live()
        except Exception:
            pass

    def _toggle_display(self) -> None:
        """송출 시작/중지 토글"""
        if self._display_window and self._display_window.isVisible():
            self._display_window.close()
            return

        # 송출 시작 — 모니터 선택 먼저 (사용자가 취소하면 송출 안 함)
        result = self._pick_display_screen()
        if result is None:
            return  # 사용자 취소
        screen, windowed = result

        if self._display_window is None:
            self._display_window = DisplayWindow()
            self._display_window.closed.connect(self._on_display_closed)

        self._display_window.show_on_screen(screen, windowed=windowed)

        # [중요] 송출창이 열린 후 현재 라이브 상태를 즉시 동기화
        self._live_controller.sync_live()

        self._display_action.setText("송출 중지")
        screen_name = screen.name() if screen else "모니터"
        mode = "윈도우" if windowed else "전체화면"
        self._statusbar.showMessage(
            f"송출이 시작되었습니다: {screen_name} · {mode} (F11로 중지)"
        )

    def _pick_display_screen(self):
        """송출 모니터/모드 결정. (screen, windowed) 튜플 또는 None(취소).

        매번 다이얼로그를 띄워 사용자가 확인하도록 한다. 이전에 저장된
        선택은 기본값으로 미리 체크되어 있어 Enter 한 번이면 바로 진행.
        """
        from PySide6.QtWidgets import QApplication

        screens = QApplication.screens()
        if not screens:
            return None

        saved_name = self._config_service.get_display_screen_name()
        saved_windowed = self._config_service.get_display_windowed_mode()

        # 저장된 모니터가 더 이상 없으면 안내
        if saved_name and not any(s.name() == saved_name for s in screens):
            self._statusbar.showMessage(
                f"이전 송출 모니터('{saved_name}')를 찾을 수 없습니다. 다시 선택해 주세요.",
                4000,
            )
            saved_name = ""

        # 매 송출마다 확인 다이얼로그 (저장된 선택은 미리 체크됨)
        from flow.ui.dialogs import flow_select_screen
        result = flow_select_screen(
            self, screens,
            current_name=saved_name,
            default_windowed=saved_windowed,
        )
        if result is None:
            return None  # 사용자 취소

        screen, windowed = result
        # 다음 송출의 기본값으로 저장
        if screen is not None:
            self._config_service.set_display_screen_name(screen.name())
        self._config_service.set_display_windowed_mode(windowed)
        return (screen, windowed)

    def _on_display_closed(self) -> None:
        """송출창이 닫혔을 때 (ESC로 닫거나 버튼으로 닫혔을 때 공통)"""
        self._display_action.setText("송출 시작")
        self._statusbar.showMessage("송출이 중지되었습니다")

    def _set_project_editable(self, editable: bool) -> None:
        """프로젝트 편집 관련 UI 요소들 활성/비활성 제어"""
        # 툴바 액션 - 파일 관리 관련은 항상 활성화
        self._new_song_action.setEnabled(True)
        self._open_action.setEnabled(True)
        self._save_action.setEnabled(True)
        self._save_as_action.setEnabled(True)
        # 홈 버튼은 라이브 모드(editable=False)에서 비활성 → 라이브 종료 후 이동
        self._close_project_action.setEnabled(editable)
        self._close_project_action.setToolTip(
            "" if editable else "라이브 모드 중에는 홈으로 이동할 수 없습니다 (Esc로 먼저 라이브 종료)"
        )
        # 활동바 홈 버튼도 동일 상태
        if hasattr(self, "_activity_bar"):
            self._activity_bar.set_home_enabled(editable)

        # 편집 관련 액션만 제어
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
        """창 닫기 이벤트 (저장 확인 및 레이아웃 저장)"""
        if not self._check_unsaved_changes():
            event.ignore()
            return

        # [추가] 창 위치 및 크기 상태 저장
        geo = self.saveGeometry().toHex().data().decode()
        state = self.saveState().toHex().data().decode()
        self._config_service.set_window_layout(geo, state)

        self._slide_manager.shutdown()

        if self._display_window:
            self._display_window.close()
        event.accept()

    def _close_current_project(self) -> None:
        if self._is_live:
            self._statusbar.showMessage(
                "라이브 모드 중에는 홈으로 이동할 수 없습니다. Esc로 먼저 라이브를 종료하세요.",
                4000,
            )
            return
        if not self._check_unsaved_changes():
            return

        if self._is_standalone and self._parent_project:
            self._parent_project = None
            self._parent_project_path = None

        self._project = None
        self._project_path = None
        self._is_standalone = False

        self._song_list.set_project(None)
        self._canvas.set_score_sheet(None)

        self._slide_manager.stop_watching()
        self._slide_manager.reset_worker()
        self._slide_preview.refresh_slides()
        self._pip.clear()

        self._undo_stack.clear()
        self._clear_dirty()

        self._show_launcher()

    # === PPT 비동기 로딩 핸들러 ===

    def _on_ppt_load_started(self) -> None:
        if self._in_transition or self._slide_manager.signalsBlocked():
            return
        self._statusbar.showMessage("PPT 변환 중... 잠시만 기다려주세요.", 0)
        self._slide_preview.show_loading()

    def _on_ppt_load_progress(self, current: int, total: int, engine_name: str) -> None:
        if self._in_transition or self._slide_manager.signalsBlocked():
            return
        self._slide_preview.update_progress(current, total, engine_name)
        self._statusbar.showMessage(
            f"이미지 생성 중... ({current}/{total}) — {engine_name}", 0
        )

    def _on_ppt_load_status(self, status: str) -> None:
        if self._in_transition or self._slide_manager.signalsBlocked():
            return
        self._statusbar.showMessage(f"{status}", 0)

    def _on_ppt_load_finished(self, count: int) -> None:
        if self._in_transition or self._slide_manager.signalsBlocked():
            return
        self._slide_preview.hide_loading()
        self._slide_preview.refresh_slides()
        self._canvas.popover.set_slide_source(
            count, self._slide_manager.get_slide_image
        )
        self._statusbar.showMessage(f"PPT 로드 완료 ({count} 슬라이드)", 3000)

    def _on_songs_metadata_started(self) -> None:
        if self._in_transition or self._slide_manager.signalsBlocked():
            return
        self._statusbar.showMessage("곡 정보를 불러오는 중...", 0)
        self._slide_preview.show_loading("곡 정보를 불러오는 중...")

    def _on_songs_metadata_finished(self, total_slides: int) -> None:
        if self._in_transition or self._slide_manager.signalsBlocked():
            return
        self._slide_preview.hide_loading()
        self._statusbar.showMessage(
            f"곡 정보를 불러왔습니다 ({total_slides} 슬라이드)", 3000
        )

        if self._project:
            self._globalize_project_indices()

            all_sheets = self._project.all_score_sheets
            if all_sheets:
                idx = self._project.current_sheet_index
                if not (0 <= idx < len(all_sheets)):
                    idx = 0
                target_sheet = all_sheets[idx]
                self._on_song_selected(target_sheet)
                self._song_list.set_current_index(idx)
            else:
                self._canvas.set_score_sheet(None)

        self._slide_preview.refresh_slides()
        self._canvas.popover.set_slide_source(
            self._slide_manager.get_slide_count(),
            self._slide_manager.get_slide_image,
        )

    def _on_ppt_load_error(self, message: str) -> None:
        if self._in_transition or self._slide_manager.signalsBlocked():
            return
        self._slide_preview.hide_loading()
        self._slide_preview.refresh_slides()
        QMessageBox.warning(self, "PPT 로딩 오류", message)
        self._statusbar.showMessage("PPT 로드 실패", 3000)

    # === 이벤트 핸들러 ===

    def _on_song_selected(self, sheet: ScoreSheet) -> None:
        """곡 선택됨"""
        if sheet is None:
            return

        from pathlib import Path

        base_path = self._get_song_base_path(sheet)
        self._canvas.set_score_sheet(sheet, base_path)

        # PPT 로드 (다중 곡 모드인 경우 생략 - 이미 load_songs로 로드됨)
        if self._project and self._project.selected_songs:
            song = next(
                (
                    s
                    for s in self._project.selected_songs
                    if any(sh.id == sheet.id for sh in s.score_sheets)
                ),
                None,
            )
            if song and song.has_slides:
                self._slide_manager.start_watching(str(song.abs_slides_path))

        self._update_verse_buttons_state()
        self._update_mapped_slides_ui()
        self._update_preview(None)
        self._canvas.setFocus()

        if self._is_live:
            song = next(
                (
                    s
                    for s in (self._project.selected_songs or [])
                    if any(sh.id == sheet.id for sh in s.score_sheets)
                ),
                None,
            )
            self._project_screen.set_nav_song_name(song.name if song else sheet.name)

        self._statusbar.showMessage(
            f"곡 선택: {sheet.name} (핫스팟: {len(sheet.hotspots)}개)"
        )

        if self._project and self._project.current_verse_index != 0:
            self._on_verse_changed(0)
            self._verse_selector.set_current_verse(0)

    def _on_song_added(self, sheet: ScoreSheet) -> None:
        """곡 추가됨"""
        self._mark_dirty()
        self._canvas.set_score_sheet(sheet)
        self._statusbar.showMessage(f"새 곡 추가: {sheet.name}")

    def _on_song_removed(self, sheet_id: str) -> None:
        """곡 또는 시트 삭제됨"""
        self._mark_dirty()

        # 1. 곡 전체가 삭제된 경우 ("ALL_OF_SONG") -> 무조건 초기화
        if sheet_id == "ALL_OF_SONG":
            self._canvas.set_score_sheet(None)
            self._statusbar.showMessage("곡 제거됨")
            return

        # 2. 현재 열려있는 시트가 삭제되었는지 확인
        current_sheet = self._canvas.get_score_sheet()
        if current_sheet and current_sheet.id == sheet_id:
            self._canvas.set_score_sheet(None)
            self._statusbar.showMessage("현재 시트 삭제됨")
        else:
            self._statusbar.showMessage("시트 삭제됨")
            # 현재 시트가 살아있다면 아무것도 지우지 않음 (사용자 혼란 방지)

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
            slide_idx = hotspot.get_slide_index(5)  # 후렴 체크

        if slide_idx >= 0:
            self._slide_preview.select_slide(slide_idx)

        # 편집 모드에서 매핑 패널 표시
        if not self._is_live:
            self._mapping_panel.show_for_hotspot(
                hotspot,
                v_idx,
                self._slide_manager.get_slide_image,
            )
            sizes = self._h_splitter.sizes()
            if len(sizes) > 3 and sizes[3] == 0:
                self._h_splitter.setSizes([sizes[0], sizes[1], 0, 260])

        # [추가] 슬라이드 선택 과정에서 빼앗긴 포커스를 캔버스로 복구 (텍스트 입력 중이 아닐 때만)
        focused = self.focusWidget()
        if not isinstance(focused, (QLineEdit, QTextEdit, QPlainTextEdit)):
            self._canvas.setFocus()

    def _on_mapping_panel_verse(self, verse_index: int) -> None:
        """매핑 패널에서 절 행 클릭 → 해당 절로 이동"""
        self._on_verse_changed(verse_index)
        self._verse_selector.set_current_verse(verse_index)
        self._mapping_panel.set_active_verse(verse_index)

    def _on_mapping_panel_unmap(self, verse_index: int) -> None:
        """매핑 패널에서 특정 절 매핑 해제"""
        if not self._project or self._is_live:
            return
        hotspot = self._canvas.get_selected_hotspot()
        if not hotspot:
            return
        from flow.ui.undo_commands import MapSlideCommand
        old_slide = hotspot.get_slide_index(verse_index)
        if old_slide < 0:
            return
        command = MapSlideCommand(
            hotspot,
            verse_index,
            old_slide,
            -1,
            lambda: (
                self._canvas.update(),
                self._update_preview(hotspot),
                self._update_mapped_slides_ui(),
                self._update_verse_buttons_state(),
                self._mapping_panel.refresh(
                    hotspot,
                    self._project.current_verse_index,
                    self._slide_manager.get_slide_image,
                ) if self._mapping_panel.isVisible() else None,
            ),
        )
        self._undo_stack.push(command)

    def _on_mapping_panel_closed(self) -> None:
        """매핑 패널 X 버튼 → 패널 숨기고 선택 해제"""
        sizes = self._h_splitter.sizes()
        if len(sizes) > 3:
            self._h_splitter.setSizes([sizes[0], sizes[1], 0, 0])
        self._canvas.select_hotspot(None)

    def _on_hotspot_created_request(
        self, x: int, y: int, index: int | None = None
    ) -> None:
        """핫스팟 생성 요청 처리 (Undo 지원)"""
        if self._is_live:
            return

        sheet = self._canvas._score_sheet
        if not sheet:
            return

        # 새 핫스팟 객체 생성 (실제 추가는 Command가 수행)
        hotspot = Hotspot(x=x, y=y)
        # 현재 레이어 정보 주입
        hotspot.set_slide_index(-1, self._project.current_verse_index)

        def refresh_ui(selected_id=None):
            self._canvas.select_hotspot(selected_id)
            if selected_id:
                self._on_hotspot_selected(hotspot)
            else:
                self._update_preview(None)
            self._canvas.update()
            self._update_verse_buttons_state()
            self._update_mapped_slides_ui()

        command = AddHotspotCommand(
            sheet,
            hotspot,
            index,
            undo_cb=lambda: refresh_ui(None),
            redo_cb=lambda: refresh_ui(hotspot.id),
        )
        self._undo_stack.push(command)

    def _on_hotspot_removed_request(self, hotspot: Hotspot) -> None:
        """핫스팟 삭제 요청 처리 (Undo 지원)"""
        if self._is_live:
            return

        sheet = self._canvas._score_sheet
        if not sheet or not hotspot:
            return

        def refresh_ui(selected_id=None):
            self._canvas.select_hotspot(selected_id)
            if selected_id:
                self._on_hotspot_selected(hotspot)
            else:
                self._update_preview(None)
            self._canvas.update()
            self._update_verse_buttons_state()
            self._update_mapped_slides_ui()

        command = RemoveHotspotCommand(
            sheet,
            hotspot,
            undo_cb=lambda: refresh_ui(hotspot.id),
            redo_cb=lambda: refresh_ui(None),
        )
        self._undo_stack.push(command)

    def _on_hotspot_moved(
        self, hotspot: Hotspot, old_pos: tuple[int, int], new_pos: tuple[int, int]
    ) -> None:
        """핫스팟 이동 완료 처리 (Undo 지원)"""
        if self._is_live:
            hotspot.x, hotspot.y = old_pos
            self._canvas.update()
            return

        command = MoveHotspotCommand(hotspot, old_pos, new_pos, self._canvas.update)
        self._undo_stack.push(command)
        self.statusBar().showMessage(f"핫스팟 이동됨: #{hotspot.order + 1}")

    # === 슬라이드 미리보기 및 매핑 정보 동기화 ===

    def _update_preview(self, hotspot: Hotspot | None) -> None:
        if not hotspot:
            self._pip.clear_preview()
            return

        v_idx = self._project.current_verse_index
        slide_idx = hotspot.get_slide_index(v_idx)
        if slide_idx < 0:
            slide_idx = hotspot.get_slide_index(5)

        lyric = getattr(hotspot, "lyric", "")
        text = lyric or (f"#{slide_idx + 1}" if slide_idx >= 0 else "")
        self._pip.set_preview_text(text)

        if slide_idx >= 0:
            try:
                qimg = self._slide_manager.get_slide_image(slide_idx)
                self._pip.set_preview_image(QtGui.QPixmap.fromImage(qimg))
            except Exception:
                pass
        else:
            self._pip.set_preview_image(None)

    def _on_live_changed(self, lyric: str) -> None:
        if self._display_window and self._display_window.isVisible():
            self._display_window.show_lyric(lyric)

    def _on_slide_changed(self, image) -> None:
        self._current_live_image = image
        if image:
            self._pip.set_live_image(QtGui.QPixmap.fromImage(image))
        else:
            self._pip.set_live_image(None)

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
                    QMessageBox.critical(
                        self, "오류", f"PPT를 로드할 수 없습니다:\n{e}"
                    )

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

    def _on_reload_all_ppt(self) -> None:
        if not self._project or not self._project.selected_songs:
            self.statusBar().showMessage("로드된 곡이 없습니다", 3000)
            return

        # 외부 PPT 편집 중이었다면 watcher 재개 (PowerPoint 저장/종료 후
        # 사용자가 '새로고침'을 누르는 흐름을 가정)
        if self._slide_manager.is_watch_paused():
            self._slide_manager.resume_file_watching()

        self.statusBar().showMessage("슬라이드 새로고침 중...", 0)
        self._slide_manager.reload_all_songs()
        self._slide_preview.refresh_slides()
        self.statusBar().showMessage(
            f"전체 슬라이드 새로고침 완료 ({self._slide_manager.get_slide_count()}장)",
            3000,
        )

    def _on_reload_song_ppt(self, song) -> None:
        if not song:
            return

        self.statusBar().showMessage(f"'{song.name}' 새로고침 중...", 0)

        if not self._is_standalone:
            song_dir = self._project_path.parent / song.folder
            self._reload_song_from_disk(song.name, song_dir)
            self._song_list.refresh_list()

        self._slide_manager.reload_song(song)

    def _on_slide_selected(self, index: int) -> None:
        """슬라이드 선택 시 즉시 미리보기 업데이트"""
        if not self._project:
            return
        self._live_controller.set_preview_slide(index)
        self._update_preview_with_index(index)

    def _on_slide_double_clicked(self, index: int) -> None:
        if not self._project:
            return

        if self._is_live or not self._is_standalone:
            return

        selected_hotspot = self._canvas.get_selected_hotspot()
        if not selected_hotspot:
            QMessageBox.information(
                self,
                "매핑 안내",
                "슬라이드를 매핑하려면 먼저 시트에서 핫스팟을 선택하세요.",
            )
            return

        # [추가] 현재 모드에서 편집 가능한 버튼인지 확인 (타 레이어 전용 버튼 보호)
        if not self._canvas.is_hotspot_editable(
            selected_hotspot, self._project.current_verse_index
        ):
            v_name = (
                f"{self._project.current_verse_index + 1}절"
                if self._project.current_verse_index < 5
                else "후렴"
            )
            QMessageBox.warning(
                self,
                "매핑 제한",
                f"이 버튼은 타 레이어에서 생성되었습니다.\n{v_name}에서 작업하시려면 해당 레이어로 이동하거나 새 버튼을 만들어 주세요.",
            )
            return

        # 1:1 매핑 체크: 이 슬라이드가 "현재 절"에서 이미 다른 곳에 매핑되어 있는지 확인
        # (다른 절에서는 같은 슬라이드가 매핑되어 있어도 무관)
        existing_info = None
        current_verse = self._project.current_verse_index
        current_verse_key = str(current_verse)

        for sheet in self._get_relevant_sheets():
            ordered_hotspots = sheet.get_ordered_hotspots()
            for i, hotspot in enumerate(ordered_hotspots):
                # 현재 절의 매핑만 검사
                if current_verse_key in hotspot.slide_mappings:
                    s_idx = hotspot.slide_mappings[current_verse_key]
                    if s_idx == index and hotspot != selected_hotspot:
                        v_name = (
                            f"{current_verse + 1}절" if current_verse < 5 else "후렴"
                        )
                        existing_info = {
                            "sheet_name": sheet.name,
                            "order": i + 1,
                            "verse": v_name,
                            "lyric": hotspot.lyric or "텍스트 없음",
                        }
                        break
                # 하위 호환: verse 0인 경우 slide_index 필드도 체크
                elif (
                    current_verse == 0
                    and hotspot.slide_index == index
                    and hotspot != selected_hotspot
                ):
                    existing_info = {
                        "sheet_name": sheet.name,
                        "order": i + 1,
                        "verse": "1절",
                        "lyric": hotspot.lyric or "텍스트 없음",
                    }
                    break
            if existing_info:
                break

        if existing_info:
            QMessageBox.warning(
                self,
                "매핑 중복",
                f"슬라이드 {index + 1}은(는) 현재 절에서 이미 다른 곳에 매핑되어 있습니다.\n\n"
                f"📍 곡명: {existing_info['sheet_name']}\n"
                f"📍 위치: {existing_info['verse']}의 {existing_info['order']}번 버튼 ({existing_info['lyric']})\n\n"
                "먼저 해당 위치의 매핑을 해제한 후 다시 시도해 주세요.",
            )
            return

        # 현재 핫스팟의 '현재 절'에 매핑 진행 (Undo 지원)
        old_slide = selected_hotspot.get_slide_index(self._project.current_verse_index)

        command = MapSlideCommand(
            selected_hotspot,
            self._project.current_verse_index,
            old_slide,
            index,
            lambda: (
                self._canvas.update(),
                self._update_preview(selected_hotspot),
                self._update_mapped_slides_ui(),
                self._update_verse_buttons_state(),
                self._mapping_panel.refresh(
                    selected_hotspot,
                    self._project.current_verse_index,
                    self._slide_manager.get_slide_image,
                ) if self._mapping_panel.isVisible() else None,
            ),
        )
        self._undo_stack.push(command)

        if not selected_hotspot.lyric:
            selected_hotspot.lyric = f"Slide {index + 1}"

        self.statusBar().showMessage(
            f"매핑 완료: 슬라이드 {index + 1} → 현재 핫스팟", 3000
        )

    def _update_mapped_slides_ui(self) -> None:
        """전체 프로젝트를 뒤져 현재 절에 매핑된 슬라이드 정보를 UI에 반영"""
        if not self._project:
            return

        mapped_indices = set()
        for sheet in self._get_relevant_sheets():
            for hotspot in sheet.hotspots:
                # [수정] 현재 절의 매핑만 추출
                idx = hotspot.get_slide_index(self._project.current_verse_index)
                if idx >= 0:
                    mapped_indices.add(idx)

        self._slide_preview.set_mapped_slides(mapped_indices)

    def _get_relevant_sheets(self) -> list[ScoreSheet]:
        """현재 화면에 표시된 PPT와 관련된 시트들만 반환 (정확한 매핑 표시용)"""
        if not self._project:
            return []

        # 다중 곡 모드: 현재 선택된 악보가 속한 '곡'의 시트들만 반환
        current_sheet = self._canvas.get_score_sheet()
        if current_sheet and self._project.selected_songs:
            song = next(
                (
                    s
                    for s in self._project.selected_songs
                    if any(sh.id == current_sheet.id for sh in s.score_sheets)
                ),
                None,
            )
            if song:
                return song.score_sheets

        return self._project.all_score_sheets

    def _on_slide_unlink_all_requested(self, index: int) -> None:
        """특정 슬라이드가 매핑된 모든 곳에서 해제 (Undo 지원)"""
        if not self._project:
            return

        if self._is_live:
            return

        command = UnlinkAllSlidesCommand(
            self._project,
            index,
            lambda: (
                self._canvas.update(),
                self._update_mapped_slides_ui(),
                self._update_preview(self._canvas.get_selected_hotspot()),
                self._update_verse_buttons_state(),
                # 우측 매핑 패널도 동기화 (선택된 핫스팟이 있고 패널이 열려있으면)
                self._mapping_panel.refresh(
                    self._canvas.get_selected_hotspot(),
                    self._project.current_verse_index,
                    self._slide_manager.get_slide_image,
                ) if (
                    self._mapping_panel.isVisible()
                    and self._canvas.get_selected_hotspot() is not None
                ) else None,
            ),
        )
        self._undo_stack.push(command)

        count = len(command.affected_items)
        if count > 0:
            self.statusBar().showMessage(
                f"해제 완료: {count}개의 핫스팟에서 슬라이드 {index + 1} 연결을 끊었습니다. (Ctrl+Z 가능)",
                3000,
            )
        else:
            self.statusBar().showMessage(
                "해당 슬라이드가 매핑된 핫스팟이 없습니다.", 2000
            )

    def _update_verse_buttons_state(self) -> None:
        if not self._project:
            return
        sheet = self._project.get_current_score_sheet()
        if not sheet:
            return
        flags: dict[int, bool] = {}
        for i in range(6):
            flags[i] = any(h.get_slide_index(i) >= 0 for h in sheet.hotspots)
        self._verse_selector.update_mapping_state(flags)

    def _on_popover_mapping(self, hotspot: Hotspot, slide_index: int) -> None:
        if self._is_live or not self._project:
            return

        if not self._canvas.is_hotspot_editable(
            hotspot, self._project.current_verse_index
        ):
            return

        v_idx = self._project.current_verse_index
        old_slide = hotspot.get_slide_index(v_idx)

        command = MapSlideCommand(
            hotspot,
            v_idx,
            old_slide,
            slide_index,
            lambda: (
                self._canvas.update(),
                self._update_preview(hotspot),
                self._update_mapped_slides_ui(),
                self._update_verse_buttons_state(),
                self._mapping_panel.refresh(
                    hotspot, v_idx, self._slide_manager.get_slide_image
                ) if self._mapping_panel.isVisible() else None,
                # 매핑 완료 후 팝오버 자동 닫기 (시트 가림 방지)
                self._canvas.popover.dismiss(),
            ),
        )
        self._undo_stack.push(command)

        if not hotspot.lyric:
            hotspot.lyric = f"Slide {slide_index + 1}"

        self.statusBar().showMessage(
            f"매핑 완료: 슬라이드 {slide_index + 1} → 핫스팟 #{hotspot.order + 1}", 3000
        )

    def _on_popover_unmap(self, hotspot: Hotspot) -> None:
        self._on_hotspot_unmap_request(hotspot)

    def _on_hotspot_unmap_request(self, hotspot: Hotspot) -> None:
        if self._is_live:
            return
        if hotspot is None:
            return
        v_idx = self._project.current_verse_index
        old_slide = hotspot.get_slide_index(v_idx)
        if old_slide >= 0:
            command = MapSlideCommand(
                hotspot,
                v_idx,
                old_slide,
                -1,
                lambda: (
                    self._canvas.update(),
                    self._update_preview(hotspot),
                    self._update_mapped_slides_ui(),
                    self._update_verse_buttons_state(),
                ),
            )
            self._undo_stack.push(command)
            self.statusBar().showMessage("매핑을 해제했습니다.", 2000)

    def _on_unlink_current_hotspot(self) -> None:
        """현재 선택된 핫스팟의 '현재 절' 슬라이드 매핑만 해제 (Undo 지원)"""
        if self._is_live:
            return

        hotspot = self._canvas.get_selected_hotspot()
        if hotspot:
            v_idx = self._project.current_verse_index
            old_slide = hotspot.get_slide_index(v_idx)

            if old_slide >= 0:
                command = MapSlideCommand(
                    hotspot,
                    v_idx,
                    old_slide,
                    -1,
                    lambda: (
                        self._canvas.update(),
                        self._update_preview(hotspot),
                        self._update_mapped_slides_ui(),
                    ),
                )
                self._undo_stack.push(command)
                self.statusBar().showMessage("현재 절의 매핑을 해제했습니다.", 3000)

    def _update_preview_with_index(self, index: int) -> None:
        self._last_preview_index = index
        try:
            qimg = self._slide_manager.get_slide_image(index)
            self._pip.set_preview_image(QtGui.QPixmap.fromImage(qimg))
            self._pip.set_preview_text(f"#{index + 1}")
        except Exception:
            pass

    # === 키보드 이벤트 ===

    def eventFilter(self, watched, event) -> bool:
        """자식 위젯(리스트 등)의 특정 키 이벤트를 메인 창에서 가로채기 위한 필터"""
        # Tab toggle for emergency patch panel — installed app-wide while panel
        # is open so Tab is captured even when QPlainTextEdit has focus.
        if (
            self._patch_panel is not None
            and event.type() == QEvent.Type.KeyPress
            and event.key() == Qt.Key.Key_Tab
            and not (event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        ):
            from PySide6.QtWidgets import QApplication
            # Don't hijack Tab inside modal dialogs spawned by the panel
            # (ConfirmDialog, etc. — they handle their own keyboard).
            modal = QApplication.activeModalWidget()
            if modal is None or modal is self:
                self._toggle_patch_focus()
                return True

        if event.type() == QEvent.Type.KeyPress:
            # [수정] 뷰포트가 아닌 위젯 본체만 감시하여 이벤트 흐름 단일화 (중복 호출 차단)
            is_slide_list = watched == self._slide_preview._list
            is_song_tree = (
                hasattr(self, "_song_list") and watched == self._song_list._scroll
            )

            if is_slide_list or is_song_tree:
                key = event.key()
                # 엔터, 숫자키(1-6), 모든 방향키인 경우 MainWindow의 핸들러를 직접 실행
                if key in (
                    Qt.Key.Key_Return,
                    Qt.Key.Key_Enter,
                    Qt.Key.Key_Left,
                    Qt.Key.Key_Right,
                    Qt.Key.Key_Up,
                    Qt.Key.Key_Down,
                ) or (Qt.Key.Key_1 <= key <= Qt.Key.Key_6):
                    # 핸들러 실행
                    self.keyPressEvent(event)
                    return True
        return super().eventFilter(watched, event)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        """키보드 이벤트 핸들러"""
        # Patch panel focused → don't dispatch live shortcuts; let normal Qt
        # event flow handle text editing inside the panel.
        if self._patch_panel_has_focus():
            super().keyPressEvent(event)
            return

        # Tab toggles between live and patch panel (only when panel is open)
        if event.key() == Qt.Key.Key_Tab and self._patch_panel is not None:
            self._toggle_patch_focus()
            event.accept()
            return

        if not self._project:
            super().keyPressEvent(event)
            return

        key = event.key()
        focused = self.focusWidget()

        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self._is_live or not isinstance(
                focused, (QLineEdit, QTextEdit, QPlainTextEdit)
            ):
                self._live_controller.send_to_live()
                self.statusBar().showMessage("라이브 송출 실행", 1000)
                event.accept()
                return

        if key == Qt.Key.Key_Space and self._is_live:
            self._live_controller.send_to_live()
            self.statusBar().showMessage("라이브 송출 실행", 1000)
            event.accept()
            return

        if key == Qt.Key.Key_F5:
            self._toggle_live_mode()
            event.accept()
            return

        if key == Qt.Key.Key_B and self._is_live:
            self._live_controller.clear_live()
            if self._display_window and self._display_window.isVisible():
                self._display_window.clear()
            self.statusBar().showMessage("블랙아웃", 1000)
            event.accept()
            return

        if key == Qt.Key.Key_Escape and self._is_live:
            self._toggle_live_mode()
            event.accept()
            return

        # 숫자키 및 단축키: 절(Verse) / 후렴 전환
        verse_idx = -1
        max_v = self._config_service.get_max_verses()

        if Qt.Key.Key_1 <= key <= Qt.Key.Key_9:
            k_num = key - Qt.Key.Key_1 + 1
            if k_num <= max_v:
                verse_idx = k_num - 1 if k_num <= 5 else k_num
        elif key == Qt.Key.Key_0:
            if max_v >= 10:
                verse_idx = 10  # ID 10은 10절
        elif key in (Qt.Key.Key_C, Qt.Key.Key_QuoteLeft, Qt.Key.Key_AsciiTilde):
            # C 키 또는 ` (백틱) 키: 후렴 전환
            verse_idx = 5
        elif key == Qt.Key.Key_6 and max_v < 6:
            # 하위 호환: 최대 절 수가 5 이하일 때 6번 키는 후렴으로 동작
            verse_idx = 5

        if verse_idx != -1:
            self._verse_selector.set_current_verse(verse_idx)
            self._on_verse_changed(verse_idx)
            self._canvas.setFocus()
            event.accept()
            return

        # [중요] 텍스트 입력 중일 때는 전역 키 조작을 하지 않음 (커서 이동/줄바꿈 보호)
        if isinstance(focused, (QLineEdit, QTextEdit, QPlainTextEdit)):
            super().keyPressEvent(event)
            return

        # 라이브 모드뿐만 아니라 편집 모드에서도 방향키 탐색 지원
        # [수정] 캔버스에 표시된 시트를 최우선으로 사용하여 동기화 오류 방지
        current_sheet = (
            self._canvas.get_score_sheet() or self._project.get_current_score_sheet()
        )
        selected_id = getattr(self._canvas, "_selected_hotspot_id", None)

        # 방향키: 핫스팟 탐색 시스템 (현재 레이어 내 가시적 핫스팟 순환)
        if key in (Qt.Key.Key_Right, Qt.Key.Key_Left):
            target = None
            if current_sheet:
                v_idx = self._project.current_verse_index
                ordered = current_sheet.get_ordered_hotspots()

                # 핫스팟 분류
                chorus_ids = [
                    h.id
                    for h in ordered
                    if ("5" in h.slide_mappings or h.get_slide_index(5) >= 0)
                ]
                v_hotspots = [h for h in ordered if h.id not in chorus_ids]
                c_hotspots = [h for h in ordered if h.id in chorus_ids]

                # 현재 모드(v_idx)에서 보이는 핫스팟 목록 구성
                if v_idx != 5:
                    # 절 모드: 숫자 버튼(절)과 알파벳 버튼(후렴)이 모두 보이므로 전체 탐색
                    all_eligible = v_hotspots + c_hotspots
                else:
                    # 후렴 모드: 알파벳 버튼(후렴)만 보이므로 후렴만 탐색
                    all_eligible = c_hotspots

                if not all_eligible:
                    self.statusBar().showMessage(
                        "현재 레이어에 탐색 가능한 핫스팟이 없습니다.", 2000
                    )
                    event.accept()
                    return

                # 현재 선택된 핫스팟의 탐색 목록 내 인덱스 찾기
                if selected_id:
                    cur_idx = -1
                    for i, h in enumerate(all_eligible):
                        if h.id == selected_id:
                            cur_idx = i
                            break

                    if cur_idx != -1:
                        if key == Qt.Key.Key_Right:
                            target_idx = (cur_idx + 1) % len(all_eligible)
                        else:
                            target_idx = (cur_idx - 1) % len(all_eligible)
                        target = all_eligible[target_idx]
                    else:
                        # 선택된 게 목록에 없으면 첫 번째/마지막 버튼 선택
                        target = (
                            all_eligible[0]
                            if key == Qt.Key.Key_Right
                            else all_eligible[-1]
                        )
                else:
                    # 선택된 게 없으면 첫 번째/마지막 버튼 선택
                    target = (
                        all_eligible[0] if key == Qt.Key.Key_Right else all_eligible[-1]
                    )

            if target:
                self._canvas.select_hotspot(target.id)
                self._on_hotspot_selected(target)

                if self._is_live:
                    self._live_controller.set_preview(target)
                    self.statusBar().showMessage(
                        f"프리뷰: #{target.order + 1}  (Enter로 송출)", 1500
                    )
                else:
                    label = ""
                    if target.id in chorus_ids:
                        c_idx = chorus_ids.index(target.id)
                        label = chr(65 + c_idx) if c_idx < 26 else str(c_idx + 1)
                    else:
                        v_ids = [h for h in all_eligible if h.id not in chorus_ids]
                        v_num = v_ids.index(target) + 1 if target in v_ids else "?"
                        label = str(v_num)
                    display_v = "후렴" if v_idx == 5 else f"{v_idx + 1}절"
                    self.statusBar().showMessage(
                        f"탐색({display_v}): {label}번 가사", 1000
                    )
                event.accept()
                return
            event.accept()
            return

        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            # 엔터: 중복 방지 (위에서 이미 처리됨)
            event.ignore()
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
                # [수정] 캔버스에 포커스를 주어 연속 조작 준비 (트리에서 키 소모 방지)
                self._canvas.setFocus()
                event.accept()
                return True  # 확실한 종료 알림

        elif key == Qt.Key.Key_Down:
            # 아래쪽 키: 다음 곡으로 전환
            if self._song_list.select_next_song():
                # [수정] 캔버스에 포커스를 주어 연속 조작 준비 (트리에서 키 소모 방지)
                self._canvas.setFocus()
                event.accept()
                return True  # 확실한 종료 알림

        super().keyPressEvent(event)

    def _toggle_slide_preview(self, checked: bool) -> None:
        """상단 슬라이드 패널 보이기/숨기기"""
        self._slide_preview.setVisible(checked)
        if checked:
            self._statusbar.showMessage("슬라이드 목록을 표시합니다.", 2000)
        else:
            self._statusbar.showMessage("슬라이드 목록을 숨겼습니다. (Ctrl+H)", 2000)

    def _manage_songs(self):
        """곡 관리 다이얼로그 표시"""
        if not self._project or not self._project_path:
            return

        from flow.ui.song_manager_dialog import SongManagerDialog

        # 단독 모드인 경우 곡 폴더를 상위 폴더로 간주하여 전달 (ProjectRepository 호환)
        project_dir = (
            self._project_path if self._is_standalone else self._project_path.parent
        )

        dialog = SongManagerDialog(
            project_dir, self._project, is_standalone=self._is_standalone, parent=self
        )
        dialog.songs_changed.connect(self._on_songs_changed)
        dialog.exec()

    def _on_songs_changed(self):
        """곡 목록 변경 시 (추가/삭제/순서변경 등)"""
        # 1. 일단 현재 상태 저장
        self._save_project()

        # 2. 다시 로컬화 (현재 SlideManager의 오프셋 기준)
        self._localize_project_indices()

        # 3. SlideManager 갱신
        if self._project.selected_songs:
            self._slide_manager.load_songs(self._project.selected_songs)

        # UI 업데이트
        self._song_list.refresh_list()
        self._statusbar.showMessage("곡 목록이 업데이트되었습니다.", 3000)
        self._mark_dirty()

    def _get_song_base_path(self, sheet: ScoreSheet) -> "Path | None":
        """ScoreSheet이 속한 곡의 베이스 경로 반환"""
        if not self._project or not self._project_path:
            return None

        # 단독 편집 모드인 경우 곡 폴더 자체가 베이스 경로
        if getattr(self, "_is_standalone", False):
            return self._project_path

        if self._project.selected_songs:
            # 다중 곡 모드에서 해당 시트가 속한 곡 찾기
            song = next(
                (
                    s
                    for s in self._project.selected_songs
                    if any(sh.id == sheet.id for sh in s.score_sheets)
                ),
                None,
            )
            if song:
                return self._project_path.parent / song.folder

        return self._project_path.parent

    def _globalize_project_indices(self):
        """프로젝트의 모든 핫스팟 인덱스를 로컬에서 전역으로 변환"""
        if not self._project or not self._project.selected_songs:
            return

        for song in self._project.selected_songs:
            offset = self._slide_manager.get_song_offset(song.name)
            if offset > 0:
                song.shift_indices(offset)

    def _localize_project_indices(self):
        """프로젝트의 모든 핫스팟 인덱스를 전역에서 로컬로 변환"""
        if not self._project or not self._project.selected_songs:
            return

        for song in self._project.selected_songs:
            offset = self._slide_manager.get_song_offset(song.name)
            if offset > 0:
                song.shift_indices(-offset)
