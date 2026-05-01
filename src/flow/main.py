"""Flow 애플리케이션 진입점"""

import sys
import signal
import faulthandler


def _prewarm_markdown_pipeline() -> None:
    """첫 마크다운 곡 열기의 cold-start 비용을 splash 동안 미리 지불한다.

    Qt 폰트(Pretendard) lookup, QPainter 초기화, QImage allocate,
    markdown 파서·렌더러 import를 한 번 트리거. 실패해도 무시 — 첫
    곡 로드가 약간 느려질 뿐 기능엔 영향 없음.
    """
    try:
        from pathlib import Path

        from flow.services.markdown import parse, render_all

        spec = parse(
            "---\nmain_size: 56\nsub_size: 18\n---\n\n# warmup\n\n샘플 가사\n"
        )
        render_all(spec, song_dir=Path("/tmp"))
    except Exception:
        pass


def main() -> int:
    """애플리케이션 메인 함수"""
    # Segfault 발생 시 C-level 스택 트레이스를 stderr에 출력
    faulthandler.enable()

    # PySide6 임포트는 여기서 수행 (테스트 시 GUI 의존성 분리)
    from PySide6.QtWidgets import QApplication, QSplashScreen
    from PySide6.QtGui import QPixmap
    from PySide6.QtCore import QTimer, Qt

    from flow.ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("Flow")
    app.setApplicationVersion("0.1.0")

    # Pretendard Variable 폰트 등록 — 한글+영문 통합 가변 폰트
    from flow.ui.styles import ensure_fonts_loaded
    ensure_fonts_loaded()

    # [추가] 로딩 화면(Splash Screen) 설정
    import os
    import time

    start_time = time.time()  # 시작 시간 기록

    if getattr(sys, "frozen", False):
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
                pixmap = pixmap.scaled(
                    500,
                    500,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )

            # [수정] 리눅스/윈도우 공통 렌더링 보장 플래그
            splash = QSplashScreen(
                pixmap,
                Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint,
            )
            splash.show()
            splash.raise_()  # 맨 앞으로 가져오기
            splash.showMessage(
                "프로그램을 불러오는 중...",
                Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter,
                Qt.GlobalColor.white,
            )

            # 초기 강력 렌더링
            for _ in range(50):
                app.processEvents()

    # Ctrl+C로 종료 가능하게 설정
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    # 타이머로 이벤트 루프에서 시그널 처리
    timer = QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None)

    # 워크스페이스 확인/선택
    from flow.services.config_service import ConfigService
    from flow.domain.workspace import Workspace

    config = ConfigService()
    workspace: Workspace | None = None

    current = config.get_current_workspace()
    if current:
        try:
            workspace = Workspace.open(current)
        except Exception:
            workspace = None

    if workspace is None:
        # 스플래시를 잠시 숨기고 다이얼로그 표시
        if splash:
            splash.hide()

        from flow.ui.workspace_dialog import WorkspaceDialog

        recent = config.get_recent_workspaces()
        dlg = WorkspaceDialog(recent_paths=recent)
        if dlg.exec() != dlg.DialogCode.Accepted or dlg.selected_workspace is None:
            return 0
        workspace = dlg.selected_workspace
        config.add_recent_workspace(str(workspace.root))

    # [수정] 무거운 창 생성을 먼저 수행 (로고가 뜬 상태에서)
    window = MainWindow(workspace=workspace)

    # [추가] 첫 곡 열기의 cold-start 비용을 splash 동안 미리 지불.
    #   Qt 폰트/페인터/이미지 + 마크다운 파서·렌더러를 한 번 워밍업해두면
    #   사용자가 처음 곡을 열 때 busy cursor 없이 즉각 떠움.
    _prewarm_markdown_pipeline()

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
