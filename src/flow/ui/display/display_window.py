"""송출창 (Display Window)

두 번째 모니터에 전체화면으로 표시되는 슬라이드 전용 창
"""

import ctypes
import sys

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QApplication
from PySide6.QtGui import QFont, QColor, QPalette, QScreen, QPixmap
from PySide6 import QtGui
from PySide6.QtCore import Qt, QTimer, Signal


# macOS: NSWindow.collectionBehavior 비트값
# 창이 "어느 Space에나 뜨는 풀스크린 보조 오버레이"가 되게 한다.
_NS_CAN_JOIN_ALL_SPACES = 1 << 0
_NS_FULLSCREEN_AUXILIARY = 1 << 8


def _mark_window_as_overlay(win_id: int) -> bool:
    """macOS NSWindow를 풀스크린 보조 오버레이로 표시.

    Qt의 winId()는 NSView 포인터다. 그 view의 window(NSWindow)에
    collectionBehavior = CanJoinAllSpaces | FullScreenAuxiliary 를 준다.

    이유: 메인 창이 네이티브 풀스크린(자체 Space)일 때, 그 위에서
    테두리 없는 송출 창을 처음 realize하면 macOS가 그 창을 주화면에
    '새 풀스크린 Space'로 밀어넣어 가둔다(좌표는 외부 모니터인데 실제로는
    주화면 새 데스크탑에 뜬다). 이 collectionBehavior는 그 가둠을 막고,
    송출 창이 자신이 놓인(외부) 화면의 현재 Space에 그대로 뜨게 한다.

    pyobjc 의존성 없이 libobjc의 objc_msgSend를 ctypes로 직접 호출한다.
    실패하면 조용히 False (다른 플랫폼·구조에서도 앱이 죽지 않게).
    """
    if sys.platform != "darwin" or not win_id:
        return False
    try:
        libobjc = ctypes.cdll.LoadLibrary("/usr/lib/libobjc.dylib")
        libobjc.sel_registerName.restype = ctypes.c_void_p
        libobjc.sel_registerName.argtypes = [ctypes.c_char_p]

        def send(recv, selector, *args, argtypes=None, restype=ctypes.c_void_p):
            libobjc.objc_msgSend.restype = restype
            libobjc.objc_msgSend.argtypes = [
                ctypes.c_void_p,
                ctypes.c_void_p,
            ] + (argtypes or [])
            sel = libobjc.sel_registerName(selector)
            return libobjc.objc_msgSend(ctypes.c_void_p(recv), sel, *args)

        nswindow = send(int(win_id), b"window")
        if not nswindow:
            return False
        behavior = _NS_CAN_JOIN_ALL_SPACES | _NS_FULLSCREEN_AUXILIARY
        send(
            nswindow,
            b"setCollectionBehavior:",
            ctypes.c_ulong(behavior),
            argtypes=[ctypes.c_ulong],
            restype=None,
        )
        return True
    except Exception:
        return False


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
    
    # 전체화면 진입 뒤 배치를 다시 확인할 시각들(ms). 첫 배치 직후 macOS가
    # 프레임리스 창을 활성(주) 화면으로 되끌어당기는 레이스가 있어, 한 번이
    # 아니라 여러 박자에 걸쳐 대상 모니터로 재적용해야 확실히 눌러앉는다.
    _SETTLE_DELAYS = (0, 60, 150, 300, 500, 800, 1200)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_lyric = ""
        self._background_mode = self.BG_BLACK
        self._settle_screen = None
        self._settle_index = 0

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
    
    @staticmethod
    def _use_native_fullscreen() -> bool:
        """showFullScreen()으로 전체화면에 들어갈지.

        macOS에서는 쓰지 않는다. 네이티브 전체화면은 창을 전용 Space로
        옮기는데, 그 전환이 비동기라 어느 디스플레이에 Space가 생길지
        확정할 수 없다 — 외부 화면을 골라도 Mac 화면에 새 데스크탑이
        만들어지곤 했다. 대신 대상 모니터 크기의 테두리 없는 창을 그대로
        덮어 씌운다. Space가 생기지 않으니 데스크탑이 튀지도 않는다.
        """
        return sys.platform != "darwin"

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
            if not self._use_native_fullscreen():
                # 네이티브 전체화면을 안 쓰는 플랫폼에서는 이 창이 메뉴
                # 막대·Dock 위에 와야 화면을 온전히 덮는다.
                flags |= Qt.WindowType.WindowStaysOnTopHint
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
        # 이전 전체화면 송출이 예약해 둔 재확인 루프가 남아 새 배치를
        # 되돌리지 않도록 멈춘다.
        self._settle_screen = None

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
        #   4) 전체화면 진입
        # 2를 건너뛰고 숨김 상태에서 옮기면 Windows가 무시해서 첫 송출이
        # 주 모니터에 뜬다 (껐다 켜면 그제야 외부 모니터로 가던 증상).
        self._apply_window_flags(frameless=True)
        # macOS: showNormal 전에 오버레이 동작을 걸어야 한다. 가둠은
        # showNormal(창 매핑) '도중'에 일어나므로, winId()로 네이티브 창을
        # 먼저 만들고(매핑 없이) collectionBehavior를 세팅한 뒤 매핑한다.
        # 이게 없으면 메인 창이 네이티브 풀스크린일 때 첫 송출이 주화면
        # 새 데스크탑(풀스크린 Space)에 갇힌다.
        _mark_window_as_overlay(int(self.winId()))
        self.showNormal()
        self._fill_screen(target_screen)
        if self._use_native_fullscreen():
            self.showFullScreen()
        self.raise_()
        # 창 이동/화면 연결이 한 번에 안 먹는 경우가 있어 여러 박자에 걸쳐
        # 대상 모니터로 다시 맞춘다 (레이스 방지). 아래 _resettle 참고.
        self._begin_settle(target_screen)

    def _begin_settle(self, screen) -> None:
        """전체화면 배치 재확인 루프 시작."""
        self._settle_screen = screen
        self._settle_index = 0
        self._resettle()

    def _resettle(self) -> None:
        """대상 모니터를 제대로 덮고 있는지 확인하고, 아니면 다시 맞춘다.

        한 번으로는 부족하다: 전체화면 진입 직후 macOS는 프레임리스 창을
        활성(주) 화면으로 되끌어당기며, 음수 좌표의 외부/Sidecar 화면으로
        보낸 창을 주화면 경계 안으로 클램프해 버린다(그 결과 주화면을 꽉
        채운 검은 창 = "새 데스크탑처럼 보임"). 그래서 _SETTLE_DELAYS의 여러
        시각마다 좌표·화면 연결을 다시 적용해, 되끌린 창을 매번 대상
        모니터로 되돌린다.

        좌표만 다시 잡는다. 예전에는 여기서 전체화면을 껐다 켰는데,
        QScreen 래퍼는 같은 모니터라도 다른 객체로 올 수 있어 `is` 비교가
        늘 어긋났고, 그때마다 macOS가 (이동이 반영되기 전에) 현재 화면에
        새 Space를 만들어 송출이 매번 Mac 화면으로 갔다.
        """
        screen = self._settle_screen
        if screen is None or not self.isVisible():
            return
        if self.geometry() != screen.geometry():
            self._fill_screen(screen)
            self.raise_()
        # 이미 맞았어도 계속 확인한다 — 처음엔 맞았다가 뒤늦게 되끌리는
        # 경우가 있어, 정해진 시각을 끝까지 훑어야 안정적으로 눌러앉는다.
        self._settle_index += 1
        if self._settle_index < len(self._SETTLE_DELAYS):
            QTimer.singleShot(
                self._SETTLE_DELAYS[self._settle_index], self, self._resettle
            )

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
        self._settle_screen = None  # 예약된 재확인 루프 중단
        self.closed.emit()
        super().closeEvent(event)
