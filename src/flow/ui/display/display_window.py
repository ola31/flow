"""송출창 (Display Window)

두 번째 모니터에 전체화면으로 표시되는 가사 전용 창
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QApplication
from PySide6.QtGui import QFont, QColor, QPalette, QScreen, QPixmap
from PySide6 import QtGui
from PySide6.QtCore import Qt, Signal


class DisplayWindow(QWidget):
    """송출창
    
    두 번째 모니터에서 전체화면으로 가사를 표시합니다.
    OBS에서 윈도우 캡처 또는 크로마키로 사용할 수 있습니다.
    
    Signals:
        closed: 창이 닫혔을 때
    """
    
    closed = Signal()
    
    # 배경색 옵션
    BG_BLACK = "black"
    BG_CHROMA_GREEN = "chroma"
    
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_lyric = ""
        self._background_mode = self.BG_BLACK
        
        self._setup_ui()
        self._apply_style()
    
    def _setup_ui(self) -> None:
        """UI 초기화"""
        self.setWindowTitle("Flow - 송출")
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.FramelessWindowHint
        )
        
        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(0, 0, 0, 0) # 기본 마진 제거
        
        self._lyric_label = QLabel()
        self._lyric_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lyric_label.setWordWrap(True)
        self._main_layout.addWidget(self._lyric_label)
        
        # 슬라이드 보관용 (리사이즈 시 필요)
        self._current_image = None
        
        # 기본 폰트 설정
        self.set_font_size(72)
    
    def _apply_style(self) -> None:
        """스타일 적용"""
        if self._background_mode == self.BG_BLACK:
            bg_color = "#000000"
        else:  # BG_CHROMA_GREEN
            bg_color = "#00FF00"
        
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {bg_color};
            }}
            QLabel {{
                color: white;
                background-color: transparent;
            }}
        """)
        
        # 크로마키 모드에서는 텍스트 그림자 효과
        if self._background_mode == self.BG_CHROMA_GREEN:
            self._lyric_label.setStyleSheet("""
                color: white;
                background-color: transparent;
            """)
    
    def set_background_mode(self, mode: str) -> None:
        """배경색 모드 설정"""
        self._background_mode = mode
        self._apply_style()
    
    def set_font_size(self, size: int) -> None:
        """폰트 크기 설정 (직접 설정 시)"""
        self._apply_scaled_font(size)

    def _apply_scaled_font(self, base_size: int) -> None:
        """화면 높이에 비례하는 폰트 적용"""
        # 기준 높이를 1080px로 잡고 비율 계산
        screen_height = self.height() or 1080
        scaled_size = max(1, int(base_size * (screen_height / 1080)))
        
        font = QFont("Pretendard", scaled_size) # Pretendard 우선 적용
        if not font.exactMatch():
            font = QFont("Malgun Gothic", scaled_size)
        
        font.setBold(True)
        self._lyric_label.setFont(font)
    
    def show_lyric(self, text: str) -> None:
        """가사 표시"""
        from PySide6.QtGui import QPixmap
        self._current_lyric = text
        self._lyric_label.setText(text)
        self._lyric_label.setPixmap(QPixmap())  # 텍스트 표시 시 이미지는 지움
    
    def show_image(self, image) -> None:
        """슬라이드 이미지 표시"""
        self._current_image = image
        self._current_lyric = ""
        self._main_layout.setContentsMargins(0, 0, 0, 0) # 이미지 시 마진 없음
        
        if image:
            from PySide6.QtGui import QPixmap
            # QImage -> QPixmap 변환
            pixmap = QPixmap.fromImage(image)
            
            # [화질 개선] High-DPI 디스플레이 대응
            ratio = self.devicePixelRatioF()
            # 윈도우의 실제 픽셀 크기에 맞춰 스케일링
            target_size = self.size() * ratio
            
            scaled_pixmap = pixmap.scaled(
                target_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            # 배율 정보 주입하여 QLabel이 올바른 크기로 그리게 함
            scaled_pixmap.setDevicePixelRatio(ratio)
            
            self._lyric_label.setPixmap(scaled_pixmap)
            # setScaledContents(True)는 화질을 떨어뜨릴 수 있으므로 False로 유지 (이미 수동 스케일링함)
            self._lyric_label.setScaledContents(False)
        else:
            self._lyric_label.setPixmap(QtGui.QPixmap())

    def resizeEvent(self, event) -> None:
        """창 크기가 바뀔 때 내용물 재조정 (모니터 크기 대응)"""
        super().resizeEvent(event)
        if self._current_image:
            self.show_image(self._current_image)
        elif self._current_lyric:
            self._apply_scaled_font(72) # 기본 크기 72pt 기준 재계산
    
    def clear(self) -> None:
        """가사 및 이미지 지우기"""
        self._current_lyric = ""
        self._lyric_label.clear()
        self._lyric_label.setPixmap(QPixmap())
    
    def show_fullscreen_on_secondary(self) -> None:
        """두 번째 모니터에 전체화면으로 표시"""
        screens = QApplication.screens()
        
        if len(screens) > 1:
            # 두 번째 모니터에 전체화면
            secondary_screen = screens[1]
            geometry = secondary_screen.geometry()
            self.setGeometry(geometry)
            self.showFullScreen()
        else:
            # 싱글 모니터: 윈도우 모드로 열기 (일반 윈도우처럼 관리 가능하도록)
            self.setWindowFlags(Qt.WindowType.Window)
            self.resize(960, 540)  # 16:9 비율
            self.show()
            # 화면 오른쪽 하단에 배치
            screen = screens[0]
            geo = screen.availableGeometry()
            self.move(geo.width() - self.width() - 20, 
                     geo.height() - self.height() - 20)
    
    def keyPressEvent(self, event) -> None:
        """키보드 이벤트 - ESC로 종료"""
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        super().keyPressEvent(event)
    
    def closeEvent(self, event) -> None:
        """창 닫기"""
        self.closed.emit()
        super().closeEvent(event)
