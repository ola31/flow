"""SlidePreviewPanel - PPT 슬라이드 목록을 썸네일로 표시하는 패널"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, 
                             QListWidget, QListWidgetItem, QLabel, QPushButton,
                             QProgressBar)
from PySide6.QtCore import Qt, Signal, QSize, QEvent
from PySide6 import QtGui
from PySide6.QtGui import QPixmap, QIcon
from flow.services.slide_manager import SlideManager

class SlidePreviewPanel(QWidget):
    """PPT 슬라이드 썸네일 목록 뷰"""
    
    slide_selected = Signal(int)        # 슬라이드 선택 (싱글클릭: 탐색/프리뷰)
    slide_double_clicked = Signal(int)  # 슬라이드 더블클릭 (매핑)
    slide_unlink_all_requested = Signal(int) # 슬라이드 매핑 해제 요청
    
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._slide_manager = None
        self._editable = True # [복구] 편집 가능 상태 보관
        self._setup_ui()
        
    def _setup_ui(self) -> None:
        self.setStyleSheet("background-color: #1a1a1a; ")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(4)
        
        # 제목 및 버튼 레이아웃
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(5, 0, 5, 0)
        
        self._title = QLabel("PPT 슬라이드 (0)")
        self._title.setStyleSheet("""
            font-weight: 800; 
            font-size: 12px; 
            color: #2196f3;
            letter-spacing: 0.2px;
        """)
        header_layout.addWidget(self._title, 1)
        
        self._btn_load = QPushButton("📁 로드")
        self._btn_load.setFixedSize(70, 24)
        self._btn_load.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_load.setToolTip("PPT 로드")
        self._btn_load.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_load.setStyleSheet("""
            QPushButton {
                background-color: #333; color: #ccc; border: 1px solid #444; border-radius: 4px; font-size: 10px; font-weight: bold;
            }
            QPushButton:hover { background-color: #444; color: white; border: 1px solid #2196f3; }
            QPushButton:disabled { color: #555; background-color: #222; border: 1px solid #333; }
        """)
        header_layout.addWidget(self._btn_load)
        
        self._btn_close = QPushButton("✕ 닫기")
        self._btn_close.setFixedSize(70, 24)
        self._btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_close.setToolTip("PPT 닫기")
        self._btn_close.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_close.setStyleSheet("""
            QPushButton {
                background-color: #333; color: #888; border: 1px solid #444; border-radius: 4px; font-size: 10px;
            }
            QPushButton:hover { background-color: #444; color: #ff5555; border: 1px solid #ff5555; }
            QPushButton:disabled { color: #444; background-color: #222; border: 1px solid #333; }
        """)
        header_layout.addWidget(self._btn_close)
        
        layout.addWidget(header_widget)
        
        # 목록 (수평 아이콘 모드)
        self._list = QListWidget()
        self._list.setViewMode(QListWidget.ViewMode.IconMode)
        self._list.setFlow(QListWidget.Flow.LeftToRight) # 수평 흐름
        self._list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self._list.setIconSize(QSize(112, 63))
        self._list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self._list.setWrapping(False)
        self._list.setMovement(QListWidget.Movement.Static)
        self._list.setSpacing(10)
        self._list.setUniformItemSizes(True)
        self._list.setHorizontalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self._list.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self._list.setFixedHeight(135)
        self._list.setStyleSheet("""
            QListWidget { 
                background-color: #222; 
                border: 1px solid #333; 
                border-radius: 8px;
                padding: 5px;
            }
            QListWidget::item { 
                background-color: #2a2a2a;
                border: 1px solid #444; 
                border-radius: 6px; 
                padding: 4px; 
                color: #888;
                font-size: 10px;
            }
            QListWidget::item:hover { 
                background-color: #333;
                border: 1px solid #2196f3;
            }
            QListWidget::item:selected { 
                background-color: #2d3d50; 
                border: 2px solid #2196f3;
                color: #2196f3;
                font-weight: bold;
            }
            
            /* 스크롤바 스타일링 고도화 */
            QScrollBar:horizontal {
                height: 12px;
                background: #1a1a1a;
                margin: 2px 10px 2px 10px;
                border-radius: 4px;
            }
            QScrollBar::handle:horizontal {
                background: #444;
                min-width: 40px;
                border-radius: 4px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #2196f3;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
        """)
        self._list.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._list.itemClicked.connect(self._on_item_clicked)
        self._list.currentItemChanged.connect(self._on_current_item_changed)
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._show_context_menu)
        
        layout.addWidget(self._list)
        
        # [NEW] 로딩 오버레이 레이아웃 (목록 위에 겹치게 배치)
        self._loading_overlay = QWidget(self._list)
        overlay_layout = QVBoxLayout(self._loading_overlay)
        overlay_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 엔진 정보 라벨
        self._engine_label = QLabel("📽 PPT 변환 엔진")
        self._engine_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._engine_label.setStyleSheet("""
            QLabel {
                color: #888;
                font-size: 10px;
                background: transparent;
            }
        """)
        overlay_layout.addWidget(self._engine_label)
        
        # 메인 로딩 라벨
        self._loading_label = QLabel("이미지 생성 중...")
        self._loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._loading_label.setStyleSheet("""
            QLabel {
                color: #2196f3;
                font-weight: bold;
                background-color: transparent;
                font-size: 13px;
            }
        """)
        overlay_layout.addWidget(self._loading_label)
        
        # 프로그레스 바
        self._progress_bar = QProgressBar()
        self._progress_bar.setMinimum(0)
        self._progress_bar.setMaximum(100)
        self._progress_bar.setValue(0)
        self._progress_bar.setFixedWidth(200)
        self._progress_bar.setFixedHeight(16)
        self._progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #333;
                border: 1px solid #444;
                border-radius: 6px;
                text-align: center;
                color: white;
                font-size: 10px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #2196f3, stop:1 #64b5f6);
                border-radius: 5px;
            }
        """)
        overlay_layout.addWidget(self._progress_bar, 0, Qt.AlignmentFlag.AlignCenter)
        
        # 진행률 텍스트 (예: "12 / 28 슬라이드")
        self._progress_text = QLabel("0 / 0 슬라이드")
        self._progress_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._progress_text.setStyleSheet("""
            QLabel {
                color: #aaa;
                font-size: 11px;
                background: transparent;
            }
        """)
        overlay_layout.addWidget(self._progress_text)
        
        self._loading_overlay.setStyleSheet("""
            QWidget {
                background-color: rgba(30, 30, 30, 230);
                border-radius: 10px;
            }
        """)
        self._loading_overlay.hide() # 초기에는 숨김
        
    def resizeEvent(self, event) -> None:
        """창 크기 변경 시 로딩 오버레이 크기 조정"""
        super().resizeEvent(event)
        if hasattr(self, '_loading_overlay'):
            self._loading_overlay.resize(self._list.size())

    def show_loading(self, message: str = None) -> None:
        """로딩 오버레이 표시"""
        if message:
            self._loading_label.setText(message)
        else:
            self._loading_label.setText("이미지 생성 중...")
        
        # 프로그레스 바 초기화
        self._progress_bar.setValue(0)
        self._progress_text.setText("준비 중...")
        self._engine_label.setText("📽 PPT 변환 엔진")
        
        self._loading_overlay.resize(self._list.size())
        self._loading_overlay.show()
        self._loading_overlay.raise_()
        self._list.setEnabled(False)

    def update_progress(self, current: int, total: int, engine_name: str) -> None:
        """진행률 업데이트"""
        if total > 0:
            percent = int((current / total) * 100)
            self._progress_bar.setValue(percent)
            self._progress_text.setText(f"{current} / {total} 슬라이드")
            self._engine_label.setText(f"📽 엔진: {engine_name}")
            self._loading_label.setText("이미지 생성 중...")

    def hide_loading(self) -> None:
        """로딩 오버레이 숨김"""
        self._loading_overlay.hide()
        self._list.setEnabled(True)

    def wheelEvent(self, event) -> None:
        """마우스 휠 이벤트를 수평 스크롤로 변환 (감도 개선)"""
        if self._list.underMouse():
            # 휠 델타 값을 수평 스크롤바에 전달 (반응성 향상)
            delta = event.angleDelta().y() or event.angleDelta().x()
            current = self._list.horizontalScrollBar().value()
            self._list.horizontalScrollBar().setValue(current - delta)
            event.accept()
        else:
            super().wheelEvent(event)
        
    def set_slide_manager(self, manager: SlideManager) -> None:
        """SlideManager 연결 및 초기화"""
        self._slide_manager = manager
        self._slide_manager.file_changed.connect(self.refresh_slides)
        self.refresh_slides()
        
    def set_editable(self, editable: bool) -> None:
        """편집 모드 활성/비활성 제어"""
        self._editable = editable
        self._btn_load.setEnabled(editable)
        # 닫기 버튼은 PPT가 로드된 경우에만 활성화되어야 하므로 추가 조건 확인
        has_ppt = self._slide_manager and self._slide_manager._pptx_path is not None
        self._btn_close.setEnabled(editable and has_ppt)
        
    def select_slide(self, index: int) -> None:
        """특정 인덱스의 슬라이드를 선택하고 목록 중앙으로 스크롤"""
        if 0 <= index < self._list.count():
            self._list.blockSignals(True)
            self._list.setCurrentRow(index)
            self._list.blockSignals(False)
            item = self._list.item(index)
            from PySide6.QtWidgets import QAbstractItemView
            self._list.scrollToItem(item, QAbstractItemView.ScrollHint.PositionAtCenter)

    def set_mapped_slides(self, mapped_indices: set[int]) -> None:
        """매핑된 슬라이드 인덱스 목록 업데이트 및 UI 부분 갱신"""
        self._mapped_indices = mapped_indices
        self.update_mapping_indicators()

    def update_mapping_indicators(self) -> None:
        """리스트 전체를 지우지 않고 매핑 인디케이터(🔗)만 업데이트 (성능 최적화)"""
        mapped_indices = getattr(self, '_mapped_indices', set())
        
        for i in range(self._list.count()):
            item = self._list.item(i)
            idx = item.data(Qt.ItemDataRole.UserRole)
            
            is_mapped = idx in mapped_indices
            label = f"Slide {idx + 1}"
            if is_mapped:
                label += " (🔗)"
            
            # 텍스트와 배경색만 변경 (아이콘 유지)
            if item.text() != label:
                item.setText(label)
            
            target_color = QtGui.QColor("#2a3a4f") if is_mapped else QtGui.QColor("transparent")
            if item.background().color() != target_color:
                item.setBackground(target_color)

    def refresh_slides(self) -> None:
        """목록 완전 갱신 (PPT가 바뀌었을 때만 호출 권장)"""
        self._list.clear()
        if not self._slide_manager:
            return
            
        count = self._slide_manager.get_slide_count()
        ppt_path = self._slide_manager._pptx_path
        ppt_name = ppt_path.name if ppt_path else "로드된 PPT 없음"
        
        self._title.setText(f"PPT 슬라이드 ({count})")
        self._title.setToolTip(f"{ppt_name}\n{str(ppt_path) if ppt_path else ''}")
        
        # PPT가 없으면 닫기 버튼 비활성화
        self._btn_close.setEnabled(ppt_path is not None)
        
        # 현재 매핑 정보 가져오기
        mapped_indices = getattr(self, '_mapped_indices', set())
        
        for i in range(count):
            qimg = self._slide_manager.get_slide_image(i)
            pixmap = QPixmap.fromImage(qimg)
            
            is_mapped = i in mapped_indices
            label = f"Slide {i+1}"
            if is_mapped:
                label += " (🔗)"
                
            item = QListWidgetItem(label)
            # 고품질 스케일링을 미리 수행하여 리스트 렌더링 부하 감소
            scaled_pixmap = pixmap.scaled(160, 90, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            item.setIcon(QIcon(scaled_pixmap))
            item.setData(Qt.ItemDataRole.UserRole, i)
            
            if is_mapped:
                item.setBackground(QtGui.QColor("#2a3a4f"))
            
            self._list.addItem(item)
            
    def _on_current_item_changed(self, current: QListWidgetItem, previous: QListWidgetItem) -> None:
        """방향키 등을 통한 선택 변경 대응"""
        if current:
            index = current.data(Qt.ItemDataRole.UserRole)
            self.slide_selected.emit(index)

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        index = item.data(Qt.ItemDataRole.UserRole)
        self.slide_selected.emit(index)
        # 아이템 클릭 후에는 화살표 키가 가사 탐색으로 가기 쉽도록 포커스 제어 고려 가능
        # (하지만 사용자가 명시적으로 화살표로 슬라이드를 이동하고 싶을 수도 있으므로 
        #  여기서는 강제로 뺏지는 않고 MainWindow에서 분기 처리)

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        index = item.data(Qt.ItemDataRole.UserRole)
        self.slide_double_clicked.emit(index)

    def _show_context_menu(self, pos) -> None:
        """우측 클릭 컨텍스트 메뉴 표시"""
        if not self._editable: return # [복구] 비편집 모드 차단
        item = self._list.itemAt(pos)
        if not item:
            return
            
        index = item.data(Qt.ItemDataRole.UserRole)
        
        from PySide6.QtWidgets import QMenu
        menu = QMenu(self)
        
        unlink_action = menu.addAction("🔗 매핑 해제")
        unlink_action.triggered.connect(lambda: self.slide_unlink_all_requested.emit(index))
        
        menu.exec(self._list.mapToGlobal(pos))
