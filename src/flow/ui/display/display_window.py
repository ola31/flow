"""송출창 (Display Window)

두 번째 모니터에 전체화면으로 표시되는 슬라이드 전용 창
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QApplication
from PySide6.QtGui import QFont, QColor, QPalette, QScreen, QPixmap
from PySide6 import QtGui
from PySide6.QtCore import Qt, QTimer, Signal


class _SlideLabel(QLabel):
    """슬라이드를 그리는 라벨 — 크기가 바뀌면 알린다.

    창이 아니라 이 라벨이 실제로 그림을 담는 면이다. 전체화면 진입 때
    창은 즉시 커져 resizeEvent가 한 번 뜨지만 그 시점에 라벨은 아직 옛
    크기이고, 이후 레이아웃이 라벨만 키울 때는 창 쪽에 아무 신호도 오지
    않는다. 그러면 큰 픽스맵이 작은 라벨에 남아 가장자리가 잘린다.
    """

    resized = Signal()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self.resized.emit()


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
        
        self._lyric_label = _SlideLabel()
        self._lyric_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lyric_label.setWordWrap(True)
        self._main_layout.addWidget(self._lyric_label)
        # 그리는 면의 크기가 바뀌면 다시 맞춘다 — 창 resizeEvent만 보면
        # 레이아웃이 라벨만 키우는 경우를 놓쳐 그림이 잘린 채 남는다.
        self._lyric_label.resized.connect(self._rerender_current)
        
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

            # [화질 개선] High-DPI 디스플레이 대응.
            # 기준은 창이 아니라 실제로 그리는 라벨의 크기다. 창 크기로
            # 맞추면 레이아웃이 아직 반영되지 않았을 때 라벨보다 큰
            # 픽스맵이 들어가고, QLabel은 축소하지 않고 잘라낸다
            # (송출 화면에서 슬라이드 가장자리가 잘려 보이던 원인).
            ratio = self.devicePixelRatioF()
            target_size = self._lyric_label.size() * ratio

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

    def _rerender_current(self) -> None:
        if self._current_image:
            self.show_image(self._current_image)

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

    def _bind_screen(self, screen) -> None:
        """창을 대상 모니터에 붙인다 (크기는 건드리지 않는다)."""
        if screen is None:
            return
        handle = self.windowHandle()
        if handle is not None:
            handle.setScreen(screen)
        self.move(screen.geometry().topLeft())

    def _fill_screen(self, screen) -> None:
        """대상 모니터를 덮도록 좌표·크기를 맞춘다 (전체화면 진입 직전용).

        Windows에서는 숨겨진 창에 대한 setGeometry/QWindow.setScreen이
        먹지 않는다 — 네이티브 창이 아직 어느 모니터에도 매핑되지 않았기
        때문이다. 그래서 showNormal로 먼저 띄운 뒤 옮겨야 하고, 그다음에야
        showFullScreen이 그 모니터에서 펼쳐진다.

        (실측: 숨김 상태에서 옮기면 첫 송출이 노트북 화면에 뜨고, 껐다
        다시 켜야 외부 모니터로 갔다.)

        윈도우 모드에서는 절대 부르지 말 것 — 작은 창으로 띄워야 하는데
        화면 전체 크기를 먼저 먹이면 그 순간 창이 화면을 덮는다.
        """
        if screen is None:
            return
        handle = self.windowHandle()
        if handle is not None:
            handle.setScreen(screen)
        self.setGeometry(screen.geometry())

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
            # macOS는 전체화면 창을 별도 Space에 둔다 — 플래그를 바꾸기
            # 전에 먼저 빠져나와야 그 데스크탑에 창이 남지 않는다.
            if self.isFullScreen():
                self.showNormal()
            self._apply_window_flags(frameless=False)
            self.setWindowState(Qt.WindowState.WindowNoState)
            self.showNormal()  # 옮기기 전에 실체화 — 숨김 상태 이동은 무시된다
            # 크기를 먼저 줄이고 옮긴다. 화면 전체 크기를 거치면 그 순간
            # 창이 모니터를 덮어, 작은 창을 골랐는데 전체화면처럼 보인다.
            self.resize(960, 540)
            self._bind_screen(target_screen)
            if target_screen is not None:
                geo = target_screen.availableGeometry()
                self.move(
                    geo.x() + geo.width() - self.width() - 20,
                    geo.y() + geo.height() - self.height() - 20,
                )
            self.raise_()
            return

        # 전체화면 모드. 순서가 전부다:
        #   1) 플래그 — setWindowFlags는 네이티브 창을 다시 만든다
        #   2) showNormal — 창을 실제로 띄워야 이동이 먹는다
        #   3) 대상 모니터로 이동
        #   4) showFullScreen — 창이 놓인 모니터에서 펼쳐진다
        # 2를 건너뛰고 숨김 상태에서 옮기면 Windows가 무시해서 첫 송출이
        # 주 모니터에 뜬다 (껐다 켜면 그제야 외부 모니터로 가던 증상).
        self._apply_window_flags(frameless=True)
        self.showNormal()
        self._fill_screen(target_screen)
        self.showFullScreen()
        self.raise_()
        # macOS는 창 이동을 다음 이벤트 루프 turn에서 반영한다. 이동이 아직
        # 적용되지 않은 상태로 전체화면이 확정되면 엉뚱한 디스플레이에
        # 전용 Space가 만들어진다 (첫 송출만 Mac 화면에 뜨고, 껐다 켜면
        # 그제야 외부 화면으로 가던 증상). 한 박자 뒤에 확인해 바로잡는다.
        QTimer.singleShot(0, self, lambda: self._settle_on_screen(target_screen))

    def _settle_on_screen(self, screen) -> None:
        """전체화면이 대상 모니터에 잡혔는지 확인하고, 아니면 다시 잡는다.

        이미 제대로 놓여 있으면 아무것도 하지 않는다 — 옮길 필요가 없는
        플랫폼(Windows)에서는 그대로 통과한다.
        """
        if screen is None or not self.isVisible():
            return
        handle = self.windowHandle()
        on_target = handle is not None and handle.screen() is screen
        if on_target and self.isFullScreen():
            return
        # 전체화면을 풀어야 창을 다른 디스플레이로 옮길 수 있다
        self.showNormal()
        self._fill_screen(screen)
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
