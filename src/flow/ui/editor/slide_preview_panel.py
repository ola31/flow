"""SlidePreviewPanel - PPT 슬라이드 목록을 썸네일로 표시하는 패널"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, 
                             QListWidget, QListWidgetItem, QLabel, QPushButton)
from PySide6.QtCore import Qt, Signal, QSize
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
        self._setup_ui()
        
    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 제목 및 버튼 레이아웃
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(5, 5, 5, 5)
        
        self._title = QLabel("PPT 슬라이드 (0)")
        self._title.setStyleSheet("font-weight: bold;")
        header_layout.addWidget(self._title, 1)
        
        self._btn_load = QPushButton("📁")
        self._btn_load.setFixedSize(24, 24)
        self._btn_load.setToolTip("PPT 로드")
        self._btn_load.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        header_layout.addWidget(self._btn_load)
        
        self._btn_close = QPushButton("❌")
        self._btn_close.setFixedSize(24, 24)
        self._btn_close.setToolTip("PPT 닫기")
        self._btn_close.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        header_layout.addWidget(self._btn_close)
        
        layout.addWidget(header_widget)
        
        # 목록 (수평 아이콘 모드)
        self._list = QListWidget()
        self._list.setViewMode(QListWidget.ViewMode.IconMode)
        self._list.setFlow(QListWidget.Flow.LeftToRight) # 수평 흐름
        self._list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn) # 항상 표시
        self._list.setIconSize(QSize(160, 90))
        self._list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self._list.setWrapping(False) # [핵심] 다음 줄로 넘어가지 않도록 설정
        self._list.setMovement(QListWidget.Movement.Static)
        self._list.setSpacing(10)
        self._list.setUniformItemSizes(True) # [성능 최적화]
        self._list.setHorizontalScrollMode(QListWidget.ScrollMode.ScrollPerPixel) # 부드러운 스크롤
        self._list.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self._list.setFixedHeight(160)
        self._list.setStyleSheet("""
            QListWidget { background-color: #2a2a2a; border: none; }
            QListWidget::item { border: 1px solid #444; border-radius: 4px; padding: 2px; }
            QListWidget::item:selected { background-color: #3d3d3d; border: 2px solid #2196f3; }
            
            /* 스크롤바 스타일링 */
            QScrollBar:horizontal {
                height: 10px;
                background: #1a1a1a;
                margin: 0px;
            }
            QScrollBar::handle:horizontal {
                background: #555;
                min-width: 20px;
                border-radius: 5px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #2196f3;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
        """)
        self._list.itemClicked.connect(self._on_item_clicked)
        self._list.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._show_context_menu)
        
        layout.addWidget(self._list)
        
        # [NEW] 로딩 오버레이 레이아웃 (목록 위에 겹치게 배치)
        self._loading_overlay = QWidget(self._list)
        overlay_layout = QVBoxLayout(self._loading_overlay)
        
        self._loading_label = QLabel("📽 PPT 변환 및 이미지 생성 중...\n잠시만 기다려주세요.")
        self._loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._loading_label.setStyleSheet("""
            QLabel {
                color: #2196f3;
                font-weight: bold;
                background-color: rgba(30, 30, 30, 200);
                border-radius: 10px;
                padding: 20px;
                font-size: 13px;
            }
        """)
        overlay_layout.addWidget(self._loading_label)
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
        self._loading_overlay.resize(self._list.size())
        self._loading_overlay.show()
        self._loading_overlay.raise_()
        self._list.setEnabled(False)

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
        self._btn_load.setEnabled(editable)
        # 닫기 버튼은 PPT가 로드된 경우에만 활성화되어야 하므로 추가 조건 확인
        has_ppt = self._slide_manager and self._slide_manager._pptx_path is not None
        self._btn_close.setEnabled(editable and has_ppt)
        
    def select_slide(self, index: int) -> None:
        """특정 인덱스의 슬라이드를 선택하고 목록 중앙으로 스크롤"""
        if 0 <= index < self._list.count():
            self._list.setCurrentRow(index)
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
            
            target_color = QtGui.QColor("#1e3a5f") if is_mapped else QtGui.QColor("transparent")
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
                item.setBackground(QtGui.QColor("#1e3a5f"))
            
            self._list.addItem(item)
            
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
        item = self._list.itemAt(pos)
        if not item:
            return
            
        index = item.data(Qt.ItemDataRole.UserRole)
        
        from PySide6.QtWidgets import QMenu
        menu = QMenu(self)
        
        unlink_action = menu.addAction("🔗 매핑 해제")
        unlink_action.triggered.connect(lambda: self.slide_unlink_all_requested.emit(index))
        
        menu.exec(self._list.mapToGlobal(pos))
