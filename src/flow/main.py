"""Flow 애플리케이션 진입점"""

import sys
import signal


def main() -> int:
    """애플리케이션 메인 함수"""
    # PySide6 임포트는 여기서 수행 (테스트 시 GUI 의존성 분리)
    from PySide6.QtWidgets import QApplication, QSplashScreen
    from PySide6.QtGui import QPixmap
    from PySide6.QtCore import QTimer, Qt
    
    from flow.ui.main_window import MainWindow
    
    app = QApplication(sys.argv)
    app.setApplicationName("Flow")
    app.setApplicationVersion("0.1.0")
    
    # [추가] 로딩 화면(Splash Screen) 설정
    import os
    import time
    start_time = time.time() # 시작 시간 기록
    
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    
    splash_path = os.path.join(base_path, "assets", "splash.png")
    
    splash = None
    if os.path.exists(splash_path):
        pixmap = QPixmap(splash_path)
        if not pixmap.isNull():
            # [수정] 이미지가 너무 크면 적절한 크기(600px)로 조정
            if pixmap.width() > 500:
                pixmap = pixmap.scaled(500, 500, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                
            # [수정] 리눅스/윈도우 공통 렌더링 보장 플래그
            splash = QSplashScreen(pixmap, Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint)
            splash.show()
            splash.raise_() # 맨 앞으로 가져오기
            splash.showMessage("프로그램을 불러오는 중...", Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter, Qt.GlobalColor.white)
            
            # 초기 강력 렌더링
            for _ in range(50):
                app.processEvents()
    
    # Ctrl+C로 종료 가능하게 설정
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    
    # 타이머로 이벤트 루프에서 시그널 처리
    timer = QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None)
    
    # [수정] 무거운 창 생성을 먼저 수행 (로고가 뜬 상태에서)
    window = MainWindow()
    
    # [수정] 최소 1.5초 대기를 sleep 대신 이벤트 루프를 돌리며 수행 (화면 프리징 방지)
    while time.time() - start_time < 1.5:
        app.processEvents()
        time.sleep(0.01)
    
    window.show()
    
    # [추가] 로딩 화면 종료
    if splash:
        splash.finish(window)
    
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
