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
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(50, 50, 50, 50)
        
        # 가사 라벨
        self._lyric_label = QLabel()
        self._lyric_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lyric_label.setWordWrap(True)
        layout.addWidget(self._lyric_label)
        
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
        """폰트 크기 설정"""
        font = QFont("Malgun Gothic", size)  # Windows 기본 한글 폰트
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
        from PySide6.QtGui import QPixmap
        if image:
            pixmap = QPixmap.fromImage(image)
            # 라벨 크기에 맞춰 이미지 스케일링
            self._lyric_label.setPixmap(pixmap.scaled(
                self._lyric_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            ))
        else:
            self._lyric_label.setPixmap(QPixmap())
    
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
            # 싱글 모니터: 윈도우 모드로 열기 (제어 가능하게)
            self.setWindowFlags(
                Qt.WindowType.Window |
                Qt.WindowType.WindowStaysOnTopHint  # 항상 위에
            )
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
