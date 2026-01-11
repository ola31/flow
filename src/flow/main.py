"""Flow 애플리케이션 진입점"""

import sys
import signal


def main() -> int:
    """애플리케이션 메인 함수"""
    # PySide6 임포트는 여기서 수행 (테스트 시 GUI 의존성 분리)
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QTimer
    
    from flow.ui.main_window import MainWindow
    
    app = QApplication(sys.argv)
    app.setApplicationName("Flow")
    app.setApplicationVersion("0.1.0")
    
    # Ctrl+C로 종료 가능하게 설정
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    
    # 타이머로 이벤트 루프에서 시그널 처리
    timer = QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None)
    
    window = MainWindow()
    window.show()
    
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
