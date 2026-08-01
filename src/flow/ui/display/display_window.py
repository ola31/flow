"""송출창 (Display Window)

두 번째 모니터에 전체화면으로 표시되는 슬라이드 전용 창
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QApplication
from PySide6.QtGui import QFont, QColor, QPalette, QScreen, QPixmap
from PySide6 import QtGui
from PySide6.QtCore import Qt, Signal


class DisplayWindow(QWidget):
    """송출창
    
    두 번째 모니터에서 전체화면으로 슬라이드를 표시합니다.
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
        """텍스트 표시"""
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
        """텍스트 및 이미지 지우기"""
        self._current_lyric = ""
        self._lyric_label.clear()
        self._lyric_label.setPixmap(QPixmap())
    
    def _apply_window_flags(self, *, frameless: bool) -> None:
        """창 테두리 유무를 모드에 맞춘다.

        윈도우 모드는 제목표시줄이 있어야 옮기고 닫을 수 있고, 전체화면은
        테두리가 없어야 한다. 예전에는 윈도우 모드가 FramelessWindowHint를
        떼기만 하고 되돌리지 않아, 한 번 윈도우 모드로 띄우면 이후 전체화면
        송출에도 제목표시줄이 남았다.
        """
        flags = Qt.WindowType.Window
        if frameless:
            flags |= Qt.WindowType.FramelessWindowHint
        if self.windowFlags() != flags:
            # setWindowFlags는 네이티브 창을 다시 만들며 창을 숨긴다 —
            # 호출한 쪽에서 반드시 다시 show해야 한다.
            self.setWindowFlags(flags)

    def _attach_to_screen(self, screen) -> None:
        """대상 모니터로 창을 옮긴다.

        windowHandle()은 네이티브 창이 만들어진 뒤에야 생긴다. 한 번도 띄운
        적 없는 창에서는 None이라 setScreen이 조용히 건너뛰어졌고, 그 결과
        첫 송출이 대상 모니터가 아닌 곳에서 전체화면이 되거나 작은 창으로
        떴다. winId()로 네이티브 창을 먼저 만들어 둔다.
        """
        if screen is None:
            return
        self.winId()  # 네이티브 창 강제 생성 → windowHandle() 확보
        handle = self.windowHandle()
        if handle is not None:
            handle.setScreen(screen)
        # showFullScreen은 창이 놓인 모니터를 기준으로 펼쳐진다 —
        # 좌표를 먼저 대상 모니터로 옮겨야 그 모니터에서 전체화면이 된다.
        self.move(screen.geometry().topLeft())

    @staticmethod
    def _resolve_screen(screen):
        if screen is not None:
            return screen
        primary = QApplication.primaryScreen()
        if primary is not None:
            return primary
        screens = QApplication.screens()
        return screens[0] if screens else None

    def show_on_screen(self, screen, *, windowed: bool = False) -> None:
        """지정한 QScreen에 표시.

        Args:
            screen: 표시할 QScreen. None이면 주 모니터.
            windowed: True면 작은 창 모드(960×540, 우측 하단), False면 전체화면.
        """
        target_screen = self._resolve_screen(screen)

        if windowed:
            self._apply_window_flags(frameless=False)
            self._attach_to_screen(target_screen)
            self.setWindowState(Qt.WindowState.WindowNoState)
            self.resize(960, 540)
            if target_screen is not None:
                geo = target_screen.availableGeometry()
                self.move(
                    geo.x() + geo.width() - self.width() - 20,
                    geo.y() + geo.height() - self.height() - 20,
                )
            self.showNormal()
            self.raise_()
            return

        # 전체화면 모드 — 플래그를 먼저 맞춘 뒤 화면에 붙인다.
        # setWindowFlags가 네이티브 창을 다시 만들어 windowHandle을
        # 무효화하므로 순서를 바꾸면 안 된다.
        self._apply_window_flags(frameless=True)
        self._attach_to_screen(target_screen)
        if target_screen is not None:
            self.setGeometry(target_screen.geometry())
        self.showFullScreen()
        self.raise_()

    def show_fullscreen_on_secondary(self) -> None:
        """레거시 호환 — 두 번째 모니터(없으면 윈도우)에 표시."""
        screens = QApplication.screens()
        if len(screens) > 1:
            self.show_on_screen(screens[1])
        else:
            self.show_on_screen(None)
    
    def keyPressEvent(self, event) -> None:
        """키보드 이벤트 - ESC로 종료"""
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        super().keyPressEvent(event)
    
    def closeEvent(self, event) -> None:
        """창 닫기"""
        self.closed.emit()
        super().closeEvent(event)
