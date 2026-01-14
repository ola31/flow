"""Flow 메인 윈도우

편집/라이브 모드를 통합한 메인 애플리케이션 윈도우
"""

from pathlib import Path
import shutil

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QSplitter,
    QToolBar, QStatusBar, QFileDialog, QMessageBox, QTabWidget
)
from PySide6.QtGui import QAction, QKeySequence, QPixmap
from PySide6 import QtGui
from PySide6.QtCore import Qt, QTimer

from flow.domain.project import Project
from flow.domain.score_sheet import ScoreSheet
from flow.domain.hotspot import Hotspot
from flow.repository.project_repository import ProjectRepository

from flow.ui.editor.song_list_widget import SongListWidget
from flow.ui.editor.score_canvas import ScoreCanvas
from flow.ui.editor.slide_preview_panel import SlidePreviewPanel
from flow.ui.display.display_window import DisplayWindow
from flow.ui.live.live_controller import LiveController
from flow.services.slide_manager import SlideManager


class MainWindow(QMainWindow):
    """Flow 메인 윈도우"""
    
    def __init__(self) -> None:
        super().__init__()
        
        self._project: Project | None = None
        self._project_path: Path | None = None
        self._repo = ProjectRepository(Path.home() / "flow_projects")
        
        # 송출 관련
        self._display_window: DisplayWindow | None = None
        self._slide_manager = SlideManager()
        self._live_controller = LiveController(self, slide_manager=self._slide_manager)
        
        # 슬라이드 클릭/더블클릭 구분용 타이머
        self._slide_click_timer = QTimer(self)
        self._slide_click_timer.setSingleShot(True)
        self._slide_click_timer.timeout.connect(self._execute_slide_navigation)
        self._pending_slide_index = -1
        
        self._setup_ui()
        self._setup_toolbar()
        self._setup_statusbar()
        self._connect_signals()
        
        # SongListWidget에 메인 윈도우 참조 연결 (경로 획득용)
        self._song_list.set_main_window(self)
        
        # 앱 시작 시 기본 프로젝트 생성 (파일 다이얼로그 없이)
        self._create_initial_project()
        self._toggle_edit_mode()
    
    def _setup_ui(self) -> None:
        """UI 초기화"""
        self.setWindowTitle("Flow - 찬양 가사 송출")
        self.setMinimumSize(800, 600)
        
        # 중앙 위젯
        central = QWidget()
        self.setCentralWidget(central)
        
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
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
        self._v_splitter.addWidget(self._h_splitter)
        
        # 초기 비율 설정 (상단 슬라이드 영역은 내용만큼만, 하단이 가득 차도록)
        self._v_splitter.setStretchFactor(0, 0)
        self._v_splitter.setStretchFactor(1, 1)
        self._v_splitter.setHandleWidth(2) # 핸들 두께 줄임
        
        # 왼쪽: 곡 목록
        self._song_list = SongListWidget()
        self._song_list.setMaximumWidth(250)
        self._song_list.setMinimumWidth(150)
        self._h_splitter.addWidget(self._song_list)
        
        # 중앙: 악보 캔버스
        self._canvas = ScoreCanvas()
        self._h_splitter.addWidget(self._canvas)
        
        # 오른쪽: 편집 패널
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_panel.setMaximumWidth(300)
        right_panel.setMinimumWidth(200)
        
        # Preview 패널 (다음 가사)
        from PySide6.QtWidgets import QLabel, QFrame
        
        preview_frame = QFrame()
        preview_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        preview_layout = QVBoxLayout(preview_frame)
        preview_layout.setContentsMargins(8, 8, 8, 8)
        
        preview_header = QLabel("📺 PREVIEW (다음)")
        preview_header.setStyleSheet("font-weight: bold; font-size: 12px; color: #888;")
        preview_layout.addWidget(preview_header)
        
        self._preview_text = QLabel("미리보기")
        self._preview_text.setStyleSheet("""
            background-color: #333; 
            color: white; 
            padding: 10px;
            border-radius: 6px;
            font-size: 14px;
        """)
        self._preview_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_text.setWordWrap(True)
        preview_layout.addWidget(self._preview_text)

        self._preview_image = QLabel()
        self._preview_image.setFixedSize(280, 157)
        self._preview_image.setScaledContents(True)
        self._preview_image.setStyleSheet("background-color: black; border: 1px solid #555;")
        self._preview_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_layout.addWidget(self._preview_image)
        self._preview_image.hide()
        right_layout.addWidget(preview_frame)
        
        # Live 패널 (현재 송출 중)
        self._live_panel = QFrame()
        self._live_panel.setFrameStyle(QFrame.Shape.StyledPanel)
        live_layout = QVBoxLayout(self._live_panel)
        live_layout.setContentsMargins(8, 8, 8, 8)
        
        live_header = QLabel("🔴 LIVE (송출 중)")
        live_header.setStyleSheet("font-weight: bold; font-size: 12px; color: #ff4444;")
        live_layout.addWidget(live_header)
        
        self._live_text = QLabel("(송출 없음)")
        self._live_text.setStyleSheet("""
            background-color: #1a1a1a; 
            color: #00ff00; 
            padding: 10px;
            border: 2px solid #ff4444;
            border-radius: 6px;
            font-size: 16px;
            font-weight: bold;
        """)
        self._live_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._live_text.setWordWrap(True)
        live_layout.addWidget(self._live_text)

        self._live_image = QLabel()
        self._live_image.setFixedSize(280, 157)
        self._live_image.setScaledContents(True)
        self._live_image.setStyleSheet("background-color: black; border: 2px solid #ff4444;")
        self._live_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        live_layout.addWidget(self._live_image)
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
        
        # 스플리터 비율 설정
        self._h_splitter.setSizes([200, 700, 300])
    
    def _setup_toolbar(self) -> None:
        """툴바 설정"""
        toolbar = QToolBar("메인 툴바")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        
        # 파일 메뉴
        new_action = QAction("📄 새 프로젝트", self)
        new_action.setShortcut(QKeySequence.StandardKey.New)
        new_action.triggered.connect(self._new_project)
        self._new_action = new_action
        toolbar.addAction(new_action)
        
        open_action = QAction("📂 열기", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self._open_project)
        self._open_action = open_action
        toolbar.addAction(open_action)
        
        save_action = QAction("💾 저장", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self._save_project)
        toolbar.addAction(save_action)
        self._save_action = save_action
        
        save_as_action = QAction("💾 다른 이름으로 저장", self)
        save_as_action.triggered.connect(self._save_project_as)
        toolbar.addAction(save_as_action)
        self._save_as_action = save_as_action
        
        toolbar.addSeparator()
        
        # PPT 로드 액션 추가 (단일 버튼으로 유지)
        self._load_ppt_action = QAction("📽 PPT 로드", self)
        self._load_ppt_action.triggered.connect(self._on_load_ppt)
        toolbar.addAction(self._load_ppt_action)
        
        toolbar.addSeparator()
        
        # 슬라이드 패널 토글 액션
        self._toggle_slide_action = QAction("🖼 슬라이드 목록", self)
        self._toggle_slide_action.setCheckable(True)
        self._toggle_slide_action.setChecked(True)
        self._toggle_slide_action.setShortcut("Ctrl+H")
        self._toggle_slide_action.triggered.connect(self._toggle_slide_preview)
        toolbar.addAction(self._toggle_slide_action)
        
        toolbar.addSeparator()
        self._edit_mode_action = QAction("✏️ 편집", self)
        self._edit_mode_action.setCheckable(True)
        self._edit_mode_action.setChecked(True)
        self._edit_mode_action.triggered.connect(self._toggle_edit_mode)
        toolbar.addAction(self._edit_mode_action)
        
        self._live_mode_action = QAction("🔴 라이브", self)
        self._live_mode_action.setCheckable(True)
        self._live_mode_action.triggered.connect(self._toggle_live_mode)
        toolbar.addAction(self._live_mode_action)
        
        toolbar.addSeparator()
        
        # 송출 제어 (초기상태 비활성)
        self._display_action = QAction("📺 송출 시작", self)
        self._display_action.setShortcut("F11")
        self._display_action.setEnabled(False) # 편집 모드에선 비활성
        self._display_action.triggered.connect(self._toggle_display)
        toolbar.addAction(self._display_action)
    
    def _setup_statusbar(self) -> None:
        """상태바 설정"""
        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)
        self._statusbar.showMessage("준비됨")
    
    def _connect_signals(self) -> None:
        """시그널 연결"""
        # 곡 목록 시그널
        self._song_list.song_selected.connect(self._on_song_selected)
        self._song_list.song_added.connect(self._on_song_added)
        
        # 캔버스 시그널
        self._canvas.hotspot_selected.connect(self._on_hotspot_selected)
        self._canvas.hotspot_created.connect(self._on_hotspot_created)
        
        # 라이브 컨트롤러 시그널 - 메인 윈도우 및 송출창 업데이트
        self._live_controller.live_changed.connect(self._on_live_changed)
        # 슬라이드 이미지 송출 연결
        self._live_controller.slide_changed.connect(self._on_slide_changed)
        
        # PPT 비동기 로딩 시그널
        self._slide_manager.load_started.connect(self._on_ppt_load_started)
        self._slide_manager.load_finished.connect(self._on_ppt_load_finished)
        self._slide_manager.load_error.connect(self._on_ppt_load_error)
    
    # === 프로젝트 관리 ===
    
    def _new_project(self) -> None:
        """새 프로젝트 폴더 생성 및 시작"""
        from PySide6.QtWidgets import QFileDialog
        
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
            self._statusbar.showMessage(f"새 프로젝트가 생성되었습니다: {project_dir}")
            self._toggle_edit_mode()
        except Exception as e:
            QMessageBox.critical(self, "오류", f"프로젝트 폴더를 생성할 수 없습니다:\n{e}")

    def _create_initial_project(self) -> None:
        """앱 시작 시 조용히 기본 프로젝트 생성"""
        self._project = Project(name="새 프로젝트")
        self._project_path = None
        self._song_list.set_project(self._project)
        self._canvas.set_score_sheet(None)
        self._slide_preview.refresh_slides()
        self.setWindowTitle("Flow - 새 프로젝트")
    
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
                # 곡 목록 UI에서 첫 번째 항목 선택 표시
                self._song_list._list.setCurrentRow(0)
            else:
                self._canvas.set_score_sheet(None)
            
            self.setWindowTitle(f"Flow - {self._project.name}")
            self._statusbar.showMessage(f"프로젝트를 열었습니다: {self._project.name}")
            
        except Exception as e:
            QMessageBox.critical(self, "오류", f"프로젝트를 열 수 없습니다:\n{e}")
    
    def _save_project(self) -> None:
        """프로젝트 저장"""
        if not self._project:
            return
        
        # 저장 경로가 없거나 처음 저장하는 경우 이름/위치 묻기
        if not self._project_path:
            from PySide6.QtWidgets import QFileDialog
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
            self._statusbar.showMessage(f"프로젝트가 저장되었습니다: {self._project_path.name}")
            
        except Exception as e:
            QMessageBox.critical(self, "오류", f"프로젝트를 저장할 수 없습니다:\n{e}")

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
        self._load_ppt_action.setEnabled(editable)
        
        # 위젯 내부 버튼
        self._song_list.set_editable(editable)
        self._slide_preview.set_editable(editable)

    # === PPT 비동기 로딩 핸들러 ===
    
    def _on_ppt_load_started(self) -> None:
        """PPT 로딩 시작"""
        self._statusbar.showMessage("📽 PPT 변환 중... 잠시만 기다려주세요.", 0) # 0은 무한 지속
        self._slide_preview.setEnabled(False) # 로딩 중 조작 방지
        
    def _on_ppt_load_finished(self, count: int) -> None:
        """PPT 로딩 완료"""
        self._slide_preview.setEnabled(True)
        self._slide_preview.refresh_slides()
        self._statusbar.showMessage(f"✅ PPT 로드 완료 ({count} 슬라이드)", 3000)
        
    def _on_ppt_load_error(self, message: str) -> None:
        """PPT 로딩 에러"""
        self._slide_preview.setEnabled(True)
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
        self._canvas.set_score_sheet(sheet)
        self._statusbar.showMessage(f"새 곡 추가: {sheet.name}")
        
    def _project_dir(self) -> str:
        """현재 프로젝트의 디렉토리 경로 반환"""
        return str(self._project_path.parent) if self._project_path else ""
    
    def _on_hotspot_selected(self, hotspot: Hotspot) -> None:
        """핫스팟 선택됨"""
        self._update_preview(hotspot)
        
        # 모드와 관계없이 항상 Preview에 설정 (전환 시 즉시 송출 대기용)
        self._live_controller.set_preview(hotspot)
        
        # 슬라이드가 매핑되어 있다면 썸네일 목록에서 강조 및 스크롤
        slide_idx = getattr(hotspot, 'slide_index', -1)
        if slide_idx >= 0:
            self._slide_preview.select_slide(slide_idx)
    
    def _on_hotspot_created(self, hotspot: Hotspot) -> None:
        """핫스팟 생성됨"""
        self._statusbar.showMessage(f"핫스팟 추가됨: #{hotspot.order + 1}")
    
    def _on_lyric_changed(self, hotspot: Hotspot) -> None:
        """가사 변경됨"""
        self._canvas.update()
        self._update_preview(hotspot)
    
    def _update_preview(self, hotspot: Hotspot | None) -> None:
        """미리보기 업데이트"""
        text = "(선택된 핫스팟 없음)"
        show_img = False
        
        if hotspot:
            lyric = getattr(hotspot, 'lyric', "")
            slide_idx = getattr(hotspot, 'slide_index', -1)
            
            if lyric:
                text = lyric
            elif slide_idx >= 0:
                text = f"슬라이드 {slide_idx + 1}"
            else:
                text = "(가사/슬라이드 없음)"
            
            # 매핑된 슬라이드 이미지가 있다면 프리뷰에 표시
            if slide_idx >= 0:
                from PySide6.QtGui import QPixmap
                try:
                    qimg = self._slide_manager.get_slide_image(slide_idx)
                    self._preview_image.setPixmap(QtGui.QPixmap.fromImage(qimg))
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
        if image:
            from PySide6.QtGui import QPixmap
            pixmap = QPixmap.fromImage(image)
            self._live_image.setPixmap(pixmap)
            self._live_image.show()
            # 이미지가 송출될 때는 가사 텍스트를 숨기거나 작게 표시 (여기선 유지)
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
                if getattr(hotspot, 'slide_index', -1) == index:
                    found_sheet = sheet
                    found_hotspot = hotspot
                    break
            if found_sheet:
                break
        
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

        # 1:1 매핑 체크: 이 슬라이드가 이미 다른 곳에 매핑되어 있는지 확인
        existing_info = None
        for sheet in self._project.score_sheets:
            # 순서 보장을 위해 정렬된 핫스팟 목록 사용
            ordered_hotspots = sheet.get_ordered_hotspots()
            for i, hotspot in enumerate(ordered_hotspots):
                if getattr(hotspot, 'slide_index', -1) == index:
                    # 현재 매핑하려는 핫스팟 자체가 이미 이 슬라이드인 경우는 제외
                    if hotspot != selected_hotspot:
                        existing_info = {
                            "sheet_name": sheet.name,
                            "order": i + 1,
                            "lyric": hotspot.lyric or "가사 없음"
                        }
                        break
            if existing_info:
                break
        
        if existing_info:
            QMessageBox.warning(
                self, "매핑 중복",
                f"슬라이드 {index + 1}은(는) 이미 다른 곳에 매핑되어 있습니다.\n\n"
                f"📍 곡명: {existing_info['sheet_name']}\n"
                f"📍 위치: {existing_info['order']}번 버튼 ({existing_info['lyric']})\n\n"
                "먼저 해당 위치의 매핑을 해제한 후 다시 시도해 주세요."
            )
            return
            
        # 현재 핫스팟에 매핑 진행
        selected_hotspot.slide_index = index
        if not selected_hotspot.lyric:
            selected_hotspot.lyric = f"Slide {index + 1}"
        
        self._canvas.update()
        self._update_preview(selected_hotspot)
        self._update_mapped_slides_ui()
        self.statusBar().showMessage(f"매핑 완료: 슬라이드 {index + 1} → 현재 핫스팟", 3000)

    def _update_mapped_slides_ui(self) -> None:
        """전체 프로젝트를 뒤져 매핑된 슬라이드 정보를 UI에 반영"""
        if not self._project:
            return
            
        mapped_indices = set()
        for sheet in self._project.score_sheets:
            for hotspot in sheet.hotspots:
                idx = getattr(hotspot, 'slide_index', -1)
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
                if getattr(hotspot, 'slide_index', -1) == index:
                    hotspot.slide_index = -1
                    count += 1
        
        if count > 0:
            self._canvas.update()
            self._update_mapped_slides_ui()
            # 현재 선택된 핫스팟의 프리뷰도 갱신될 수 있도록 처리
            self._update_preview(self._canvas.get_selected_hotspot())
            self.statusBar().showMessage(f"해제 완료: {count}개의 핫스팟에서 슬라이드 {index + 1} 연결을 끊었습니다.", 3000)

    def _on_unlink_current_hotspot(self) -> None:
        """현재 선택된 핫스팟의 슬라이드 매핑만 해제"""
        hotspot = self._canvas.get_selected_hotspot()
        if hotspot:
            hotspot.slide_index = -1
            self._canvas.update()
            self._update_preview(hotspot)
            self._update_mapped_slides_ui()
            self.statusBar().showMessage("현재 핫스팟의 매핑을 해제했습니다.", 3000)

    def _update_preview_with_index(self, index: int) -> None:
        """인덱스로 직접 프리뷰 이미지 갱신 (핫스팟 없을 때)"""
        try:
            qimg = self._slide_manager.get_slide_image(index)
            self._preview_image.setPixmap(QtGui.QPixmap.fromImage(qimg))
            self._preview_image.show()
            self._preview_text.setText(f"슬라이드 {index + 1} (직접 선택)")
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
        
        # [중요] 텍스트 입력 중일 때는 전역 키 조작을 하지 않음 (커서 이동/줄바꿈 보호)
        from PySide6.QtWidgets import QLineEdit, QTextEdit, QPlainTextEdit
        if isinstance(focused, (QLineEdit, QTextEdit, QPlainTextEdit)):
            super().keyPressEvent(event)
            return

        # 라이브 모드뿐만 아니라 편집 모드에서도 방향키 탐색 지원
        current_sheet = self._project.get_current_score_sheet()
        selected_id = getattr(self._canvas, '_selected_hotspot_id', None)
        
        # 방향키: 핫스팟 탐색 시스템
        if key == Qt.Key.Key_Right:
            target = None
            if current_sheet:
                if selected_id:
                    target = current_sheet.get_next_hotspot(selected_id)
                else:
                    ordered = current_sheet.get_ordered_hotspots()
                    if ordered: target = ordered[0]
            
            if target:
                self._canvas.select_hotspot(target.id)
                self._on_hotspot_selected(target)
                self.statusBar().showMessage(f"탐색: 가사 #{target.order + 1}", 1000)
                event.accept()
                return
            # 이동할 가사가 없는데 슬라이드 클릭 중이면 슬라이드 넘김 허용
            if focused == self._slide_preview._list:
                super().keyPressEvent(event)
                return
            event.accept()
            return

        elif key == Qt.Key.Key_Left:
            target = None
            if current_sheet and selected_id:
                target = current_sheet.get_previous_hotspot(selected_id)
            
            if target:
                self._canvas.select_hotspot(target.id)
                self._on_hotspot_selected(target)
                self.statusBar().showMessage(f"탐색: 가사 #{target.order + 1}", 1000)
                event.accept()
                return
            # 이동할 가사가 없는데 슬라이드 클릭 중이면 슬라이드 넘김 허용
            if focused == self._slide_preview._list:
                super().keyPressEvent(event)
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
