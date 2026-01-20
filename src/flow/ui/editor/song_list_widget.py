"""곡 목록 사이드바 위젯

편집/라이브 모드에서 공통으로 사용되는 곡 목록 UI
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QFileDialog, QInputDialog, QMessageBox, QMenu
)
from PySide6.QtGui import QAction
from PySide6.QtCore import Signal, Qt, QPoint

from flow.domain.project import Project
from flow.domain.score_sheet import ScoreSheet


class SongListWidget(QWidget):
    """곡 목록 사이드바
    
    Signals:
        song_selected: 곡이 선택되었을 때 (ScoreSheet)
        song_added: 새 곡이 추가되었을 때 (ScoreSheet)
        song_removed: 곡이 삭제되었을 때 (str: sheet_id)
    """
    
    song_selected = Signal(object)  # ScoreSheet
    song_added = Signal(object)  # ScoreSheet
    song_removed = Signal(str)  # sheet_id
    
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._project: Project | None = None
        self._main_window = None # 메인 윈도우 참조 보관
        self._editable = True # [복구] 편집 가능 상태 보관
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """UI 초기화"""
        self.setStyleSheet("background-color: #1e1e1e; ")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # 헤더
        header = QLabel("📋 곡 목록")
        header.setStyleSheet("""
            font-weight: 800; 
            font-size: 15px; 
            color: #2196f3; 
            padding: 5px 2px;
            letter-spacing: 0.5px;
        """)
        layout.addWidget(header)
        
        # 곡 목록 (QListWidget 스타일 고도화)
        self._list = QListWidget()
        self._list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self._list.setStyleSheet("""
            QListWidget {
                background-color: #252525;
                border: 1px solid #333;
                border-radius: 8px;
                outline: none;
                padding: 4px;
            }
            QListWidget::item {
                background-color: transparent;
                border-radius: 6px;
                padding: 10px 12px;
                margin-bottom: 2px;
                color: #ddd;
            }
            QListWidget::item:hover {
                background-color: #333;
                color: white;
            }
            QListWidget::item:selected {
                background-color: #2a3a4f;
                color: #2196f3;
                font-weight: bold;
                border: 1px solid #2196f3;
            }
        """)
        self._list.currentItemChanged.connect(self._on_selection_changed)
        self._list.itemClicked.connect(self._on_item_clicked)
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._on_context_menu)
        layout.addWidget(self._list)
        
        # 버튼들
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(6)
        
        self._add_btn = QPushButton("+ 곡 추가")
        self._add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._add_btn.setFixedHeight(34)
        self._add_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196f3;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #1e88e5; }
            QPushButton:disabled { background-color: #333; color: #666; }
        """)
        self._add_btn.clicked.connect(self._on_add_clicked)
        btn_layout.addWidget(self._add_btn, 1)
        
        self._remove_btn = QPushButton("🗑️")
        self._remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._remove_btn.setFixedSize(34, 34)
        self._remove_btn.setStyleSheet("""
            QPushButton {
                background-color: #333;
                color: #888;
                border: 1px solid #444;
                border-radius: 6px;
                font-size: 14px;
            }
            QPushButton:hover { background-color: #444; color: #ff4444; border: 1px solid #ff4444; }
            QPushButton:disabled { background-color: #252525; color: #444; border: 1px solid #333; }
        """)
        self._remove_btn.clicked.connect(self._on_remove_clicked)
        btn_layout.addWidget(self._remove_btn)
        
        layout.addLayout(btn_layout)
    
    def set_project(self, project: Project) -> None:
        """프로젝트 설정 및 곡 목록 갱신"""
        self._project = project
        self.refresh_list()
        
    def set_main_window(self, win) -> None:
        """메인 윈도우 참조 설정 (프로젝트 경로 획득용)"""
        self._main_window = win
        
    def set_editable(self, editable: bool) -> None:
        """편집 모드 활성/비활성 제어"""
        self._editable = editable # [복구] 상태 보관
        self._add_btn.setEnabled(editable)
        self._remove_btn.setEnabled(editable)
        
    def select_next_song(self) -> bool:
        """다음 곡 선택"""
        if self._project and self._project.next_score_sheet():
            self._list.setCurrentRow(self._project.current_sheet_index)
            return True
        return False
        
    def select_previous_song(self) -> bool:
        """이전 곡 선택"""
        if self._project and self._project.previous_score_sheet():
            self._list.setCurrentRow(self._project.current_sheet_index)
            return True
        return False
    
    def refresh_list(self) -> None:
        """곡 목록 갱신"""
        # 시그널 차단하여 무한 재귀 방지
        self._list.blockSignals(True)
        
        self._list.clear()
        
        if not self._project:
            self._list.blockSignals(False)
            return
        
        for i, sheet in enumerate(self._project.score_sheets):
            item = QListWidgetItem(sheet.name)
            item.setData(Qt.ItemDataRole.UserRole, sheet.id)
            
            # 현재 곡 표시
            if i == self._project.current_sheet_index:
                item.setText(f"▶ {sheet.name}")
            
            self._list.addItem(item)
        
        # 현재 곡 선택
        if self._project.score_sheets:
            self._list.setCurrentRow(self._project.current_sheet_index)
        
        self._list.blockSignals(False)
    
    def _on_selection_changed(self, current: QListWidgetItem | None, 
                               previous: QListWidgetItem | None) -> None:
        """곡 선택 변경"""
        if not current or not self._project:
            return
        
        sheet_id = current.data(Qt.ItemDataRole.UserRole)
        sheet = self._project.find_score_sheet_by_id(sheet_id)
        
        if sheet:
            # 현재 인덱스 업데이트
            self._project.current_sheet_index = self._list.currentRow()
            
            # 삼각형 기호 업데이트
            self._update_indicators()
            
            self.song_selected.emit(sheet)

    def _update_indicators(self) -> None:
        """삼각형 기호(▶) 위치를 현재 인덱스에 맞게 업데이트"""
        if not self._project:
            return
            
        for i in range(self._list.count()):
            item = self._list.item(i)
            sheet_id = item.data(Qt.ItemDataRole.UserRole)
            sheet = self._project.find_score_sheet_by_id(sheet_id)
            if not sheet:
                continue
                
            if i == self._project.current_sheet_index:
                if not item.text().startswith("▶"):
                    item.setText(f"▶ {sheet.name}")
            else:
                if item.text().startswith("▶"):
                    item.setText(sheet.name)
    
    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        """아이템 클릭 시 (이미 선택된 항목을 다시 누를 때 대응)"""
        if not self._project:
            return
            
        sheet_id = item.data(Qt.ItemDataRole.UserRole)
        sheet = self._project.find_score_sheet_by_id(sheet_id)
        if sheet:
            self.song_selected.emit(sheet)
            # [복구] 포커스 반환
            if self._main_window:
                self._main_window.setFocus()
    
    def _on_add_clicked(self) -> None:
        """곡 추가 버튼 클릭"""
        if not self._project:
            return
        
        # 곡 이름 입력
        name, ok = QInputDialog.getText(
            self, "새 곡 추가", "곡 이름을 입력하세요:"
        )
        
        if not ok or not name.strip():
            return
        
        # 악보 이미지 선택 (선택사항)
        initial_dir = ""
        if self._main_window:
            initial_dir = self._main_window._project_dir()
            
        image_path, _ = QFileDialog.getOpenFileName(
            self, "악보 이미지 선택 (선택사항)",
            initial_dir, "이미지 (*.jpg *.jpeg *.png *.bmp)"
        )
        
        # 새 악보 생성
        sheet = ScoreSheet(name=name.strip(), image_path=image_path or "")
        self._project.add_score_sheet(sheet)
        self.refresh_list()
        
        # 새로 추가된 곡 선택
        self._list.setCurrentRow(len(self._project.score_sheets) - 1)
        
        self.song_added.emit(sheet)
    
    def _on_remove_clicked(self) -> None:
        """곡 삭제 버튼 클릭"""
        if not self._project:
            return
        
        current = self._list.currentItem()
        if not current:
            return
        
        sheet_id = current.data(Qt.ItemDataRole.UserRole)
        sheet = self._project.find_score_sheet_by_id(sheet_id)
        
        if not sheet:
            return
        
        # 확인 대화상자
        reply = QMessageBox.question(
            self, "곡 삭제",
            f"'{sheet.name}'을(를) 삭제하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self._project.remove_score_sheet(sheet_id)
            self.refresh_list()
            self.song_removed.emit(sheet_id)

    def _on_context_menu(self, pos: QPoint) -> None:
        """[복구] 우클릭 컨텍스트 메뉴"""
        if not self._editable: return
        item = self._list.itemAt(pos)
        if not item: return
        menu = QMenu(self)
        rename_action = QAction("📝 이름 변경", self)
        rename_action.triggered.connect(lambda: self._on_rename_clicked(item))
        menu.addAction(rename_action)
        menu.addSeparator()
        remove_action = QAction("🗑️ 삭제", self)
        remove_action.triggered.connect(self._on_remove_clicked)
        menu.addAction(remove_action)
        menu.exec(self._list.mapToGlobal(pos))

    def _on_rename_clicked(self, item: QListWidgetItem) -> None:
        """[복구] 곡 이름 변경"""
        if not self._project: return
        sheet_id = item.data(Qt.ItemDataRole.UserRole)
        sheet = self._project.find_score_sheet_by_id(sheet_id)
        if not sheet: return
        new_name, ok = QInputDialog.getText(self, "곡 이름 변경", "새 이름을 입력하세요:", text=sheet.name)
        if ok and new_name.strip():
            sheet.name = new_name.strip()
            self.refresh_list()
            self.song_selected.emit(sheet)
