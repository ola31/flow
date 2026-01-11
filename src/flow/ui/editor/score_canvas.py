"""악보 캔버스 위젯

악보 이미지를 표시하고 핫스팟을 생성/편집하는 UI
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QScrollArea, QMenu
from PySide6.QtGui import QPixmap, QPainter, QColor, QPen, QMouseEvent, QAction
from PySide6.QtCore import Signal, Qt, QPoint, QRect

from flow.domain.score_sheet import ScoreSheet
from flow.domain.hotspot import Hotspot


class ScoreCanvas(QWidget):
    """악보 캔버스
    
    악보 이미지 위에 핫스팟을 표시하고 클릭으로 새 핫스팟을 생성
    
    Signals:
        hotspot_created: 새 핫스팟이 생성됨 (Hotspot)
        hotspot_selected: 핫스팟이 선택됨 (Hotspot)
        hotspot_removed: 핫스팟이 삭제됨 (str: hotspot_id)
    """
    
    hotspot_created = Signal(object)  # Hotspot
    hotspot_selected = Signal(object)  # Hotspot
    hotspot_removed = Signal(str)  # hotspot_id
    
    HOTSPOT_RADIUS = 20  # 15에서 20으로 확대
    HOTSPOT_COLOR = QColor(255, 100, 100, 200)
    HOTSPOT_SELECTED_COLOR = QColor(100, 255, 100, 240)
    
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._score_sheet: ScoreSheet | None = None
        self._pixmap: QPixmap | None = None
        self._selected_hotspot_id: str | None = None
        self._edit_mode = True  # 편집 모드 활성화
        
        self.setMinimumSize(400, 300)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus) # 클릭 시 포커스를 가져오도록 설정
    
    def set_score_sheet(self, sheet: ScoreSheet | None) -> None:
        """악보 설정"""
        self._score_sheet = sheet
        self._selected_hotspot_id = None
        
        if sheet and sheet.image_path:
            self._pixmap = QPixmap(sheet.image_path)
            if self._pixmap.isNull():
                self._pixmap = None
        else:
            self._pixmap = None
        
        self.update()
    
    def set_edit_mode(self, enabled: bool) -> None:
        """편집 모드 설정"""
        self._edit_mode = enabled
    
    def select_hotspot(self, hotspot_id: str | None) -> None:
        """핫스팟 선택"""
        self._selected_hotspot_id = hotspot_id
        self.update()
    
    def get_selected_hotspot(self) -> Hotspot | None:
        """현재 선택된 핫스팟 반환"""
        if not self._score_sheet or not self._selected_hotspot_id:
            return None
        return self._score_sheet.find_hotspot_by_id(self._selected_hotspot_id)
    
    def paintEvent(self, event) -> None:
        """그리기"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 배경
        painter.fillRect(self.rect(), QColor(40, 40, 40))
        
        if not self._score_sheet:
            self._draw_placeholder(painter, "곡을 선택하세요")
            return
        
        if self._pixmap:
            # 악보 이미지 그리기 (중앙 정렬, 비율 유지)
            scaled = self._pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)
        else:
            self._draw_placeholder(painter, f"악보: {self._score_sheet.name}\n(이미지를 추가하세요)")
        
        # 핫스팟 그리기
        self._draw_hotspots(painter)
    
    def _draw_placeholder(self, painter: QPainter, text: str) -> None:
        """플레이스홀더 텍스트 그리기"""
        painter.setPen(QColor(150, 150, 150))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, text)
    
    def _draw_hotspots(self, painter: QPainter) -> None:
        """핫스팟들 그리기"""
        if not self._score_sheet:
            return
        
        for i, hotspot in enumerate(self._score_sheet.get_ordered_hotspots()):
            # 좌표 변환 (이미지 좌표 → 위젯 좌표)
            pos = self._image_to_widget_coords(hotspot.x, hotspot.y)
            
            # 색상 결정
            if hotspot.id == self._selected_hotspot_id:
                color = self.HOTSPOT_SELECTED_COLOR
            else:
                color = self.HOTSPOT_COLOR
            
            # 원 그리기
            painter.setBrush(color)
            painter.setPen(QPen(Qt.GlobalColor.white, 2))
            painter.drawEllipse(pos, self.HOTSPOT_RADIUS, self.HOTSPOT_RADIUS)
            
            # 텍스트 드로잉 (잘림 방지를 위해 범위 확대 및 폰트 설정)
            painter.setPen(Qt.GlobalColor.white)
            font = painter.font()
            font.setBold(True)
            font.setPointSize(9)
            painter.setFont(font)
            
            label = str(i + 1)
            if hasattr(hotspot, 'slide_index') and hotspot.slide_index >= 0:
                label = f"{i + 1}-S{hotspot.slide_index + 1}"
                
            # 원 안의 중앙에 텍스트 배치
            text_rect = QRect(
                pos.x() - self.HOTSPOT_RADIUS, 
                pos.y() - self.HOTSPOT_RADIUS, 
                self.HOTSPOT_RADIUS * 2, 
                self.HOTSPOT_RADIUS * 2
            )
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, label)
    
    def _image_to_widget_coords(self, img_x: int, img_y: int) -> QPoint:
        """이미지 좌표를 위젯 좌표로 변환"""
        if not self._pixmap:
            return QPoint(img_x, img_y)
        
        # 스케일 계산
        scaled = self._pixmap.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        
        scale_x = scaled.width() / self._pixmap.width()
        scale_y = scaled.height() / self._pixmap.height()
        
        offset_x = (self.width() - scaled.width()) // 2
        offset_y = (self.height() - scaled.height()) // 2
        
        return QPoint(
            int(img_x * scale_x + offset_x),
            int(img_y * scale_y + offset_y)
        )
    
    def _widget_to_image_coords(self, widget_x: int, widget_y: int) -> tuple[int, int] | None:
        """위젯 좌표를 이미지 좌표로 변환"""
        if not self._pixmap:
            return widget_x, widget_y
        
        scaled = self._pixmap.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        
        offset_x = (self.width() - scaled.width()) // 2
        offset_y = (self.height() - scaled.height()) // 2
        
        # 이미지 영역 밖 클릭 체크
        if (widget_x < offset_x or widget_x >= offset_x + scaled.width() or
            widget_y < offset_y or widget_y >= offset_y + scaled.height()):
            return None
        
        scale_x = self._pixmap.width() / scaled.width()
        scale_y = self._pixmap.height() / scaled.height()
        
        return (
            int((widget_x - offset_x) * scale_x),
            int((widget_y - offset_y) * scale_y)
        )
    
    def mousePressEvent(self, event: QMouseEvent) -> None:
        """마우스 클릭"""
        self.setFocus() # 클릭 시 키보드 포커스 획득
        if not self._score_sheet:
            return
        
        pos = event.position().toPoint()
        
        # 기존 핫스팟 클릭 체크
        clicked_hotspot = self._find_hotspot_at(pos)
        
        if event.button() == Qt.MouseButton.LeftButton:
            if clicked_hotspot:
                # 기존 핫스팟 선택
                self._selected_hotspot_id = clicked_hotspot.id
                self.hotspot_selected.emit(clicked_hotspot)
            elif self._edit_mode:
                # 새 핫스팟 생성
                img_coords = self._widget_to_image_coords(pos.x(), pos.y())
                if img_coords:
                    order = len(self._score_sheet.hotspots)
                    hotspot = Hotspot(x=img_coords[0], y=img_coords[1], order=order)
                    self._score_sheet.add_hotspot(hotspot)
                    self._selected_hotspot_id = hotspot.id
                    self.hotspot_created.emit(hotspot)
            
            self.update()
        
        elif event.button() == Qt.MouseButton.RightButton and clicked_hotspot:
            # 우클릭 컨텍스트 메뉴
            self._show_context_menu(pos, clicked_hotspot)
    
    def _find_hotspot_at(self, pos: QPoint) -> Hotspot | None:
        """해당 위치의 핫스팟 찾기"""
        if not self._score_sheet:
            return None
        
        for hotspot in self._score_sheet.hotspots:
            hotspot_pos = self._image_to_widget_coords(hotspot.x, hotspot.y)
            distance = ((pos.x() - hotspot_pos.x()) ** 2 + 
                       (pos.y() - hotspot_pos.y()) ** 2) ** 0.5
            
            if distance <= self.HOTSPOT_RADIUS + 5:
                return hotspot
        
        return None
    
    def _show_context_menu(self, pos: QPoint, hotspot: Hotspot) -> None:
        """컨텍스트 메뉴 표시"""
        menu = QMenu(self)
        
        delete_action = QAction("🗑️ 삭제", self)
        delete_action.triggered.connect(lambda: self._delete_hotspot(hotspot))
        menu.addAction(delete_action)
        
        menu.exec(self.mapToGlobal(pos))
    
    def _delete_hotspot(self, hotspot: Hotspot) -> None:
        """핫스팟 삭제"""
        if self._score_sheet:
            self._score_sheet.remove_hotspot(hotspot.id)
            if self._selected_hotspot_id == hotspot.id:
                self._selected_hotspot_id = None
            self.hotspot_removed.emit(hotspot.id)
            self.update()
