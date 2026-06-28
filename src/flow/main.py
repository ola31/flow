"""Flow 애플리케이션 진입점"""

from __future__ import annotations

import faulthandler
import os
import signal
import sys


def _append_qt_logging_rules(*rules: str) -> None:
    """Qt 로그 필터를 기존 사용자 설정을 보존하며 추가한다."""
    existing = os.environ.get("QT_LOGGING_RULES", "").strip()
    parts = [part.strip() for part in existing.split(";") if part.strip()]
    for rule in rules:
        if rule not in parts:
            parts.append(rule)
    if parts:
        os.environ["QT_LOGGING_RULES"] = ";".join(parts)


def _prefer_xcb_on_linux() -> None:
    """Linux에서는 XWayland(xcb)를 기본 Qt 플랫폼으로 사용한다.

    GNOME/Wayland + Qt 6.11 네이티브 Wayland 플러그인 조합에서, 프로젝트를 열어
    에디터 표면이 렌더된 슬라이드로 채워진 직후 컴포지터(mutter)의 busy 스피너
    커서가 표면에 멈춰 붙어 앱 프로세스가 끝난 뒤에도 한동안 남는 문제가 있다.
    측정 결과 앱이 거는 커서(override=None)도, 자식 프로세스도, 메인 스레드
    블로킹도 아니며 순수한 플랫폼 플러그인 이슈로, XWayland(xcb)에서는 재현되지
    않는다. 사용자가 QT_QPA_PLATFORM을 명시한 경우에는 그 값을 존중한다.
    """
    if not sys.platform.startswith("linux"):
        return
    if os.environ.get("QT_QPA_PLATFORM"):
        return
    os.environ["QT_QPA_PLATFORM"] = "xcb"


def _prewarm_markdown_pipeline() -> None:
    """첫 곡 열기의 cold-start 비용을 splash 동안 미리 지불한다.

    Qt 폰트(Pretendard) lookup, QPainter 초기화, QImage allocate, QPixmap
    변환, markdown 파서·렌더러 import, 그리고 SlideWorker QThread 첫
    시작을 모두 트리거. 실패해도 무시 — 첫 곡 로드가 약간 느려질 뿐
    기능엔 영향 없음.
    """
    try:
        from pathlib import Path

        from PySide6.QtGui import QImage, QPixmap

        from flow.services.markdown import parse, render_all

        # 마크다운 파서 + Qt 폰트/페인터 워밍
        spec = parse(
            "---\nmain_size: 56\nsub_size: 18\n---\n\n# warmup\n\n샘플 가사\n"
        )
        images = render_all(spec, song_dir=Path("/tmp"))

        # 디스플레이 path 워밍 — QImage→QPixmap 변환은
        # 슬라이드 미리보기 썸네일에서 매번 호출됨
        if images:
            QPixmap.fromImage(images[0])

        # 이미지 로더 워밍 — 악보 시트가 보통 jpg/png. 더미 1px 이미지로
        # 디코더 path 트리거.
        dummy = QImage(1, 1, QImage.Format.Format_RGB32)
        dummy.fill(0xFF000000)
        QPixmap.fromImage(dummy)

        # SlideWorker QThread 워밍 — SlideManager 인스턴스를 만들고 즉시
        # 정리. 첫 워커 스레드 spawn / 시그널 wiring을 splash 동안 처리.
        from flow.services.slide_manager import SlideManager
        sm_warmup = SlideManager()
        sm_warmup.shutdown()
    except Exception:
        pass


def main() -> int:
    """애플리케이션 메인 함수"""
    # Wayland busy-cursor 회피를 위해 PySide 임포트 전에 플랫폼을 고정한다.
    _prefer_xcb_on_linux()

    # Segfault 발생 시 C-level 스택 트레이스를 stderr에 출력
    faulthandler.enable()

    _append_qt_logging_rules(
        "qt.qpa.services.warning=false",
        "qt.qpa.wayland.textinput.warning=false",
    )

    # PySide6 임포트는 여기서 수행 (테스트 시 GUI 의존성 분리)
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtGui import QGuiApplication, QPixmap
    from PySide6.QtWidgets import QApplication, QSplashScreen

    from flow.ui.main_window import MainWindow

    # Wayland/X11 컴포지터에 desktop entry 식별자 등록 — startup-notification
    # 타임아웃 동안 busy cursor가 길게 남는 현상을 줄여준다.
    try:
        QGuiApplication.setDesktopFileName("flow")
    except Exception:
        pass

    app = QApplication(sys.argv)
    app.setApplicationName("Flow")
    app.setApplicationVersion("0.1.0")

    # Pretendard Variable 폰트 등록 — 한글+영문 통합 가변 폰트
    from flow.ui.styles import ensure_fonts_loaded
    ensure_fonts_loaded()

    # [추가] 로딩 화면(Splash Screen) 설정
    import time

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
    from flow.domain.workspace import Workspace
    from flow.services.config_service import ConfigService

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

    # [추가] ProjectScreen 위젯 트리 사전 realize — 첫 곡/프로젝트 열기 때
    # QSplitter / Canvas / 패널들이 처음으로 layout+paint되면 컴포지터가
    # "새 view 로딩"으로 인식해 busy cursor를 잡는 현상 완화.
    try:
        project_screen = window._project_screen
        project_screen.ensurePolished()
        project_screen.adjustSize()
        # 자식 위젯도 polish (canvas, slide_preview, song_list 등)
        for child in project_screen.findChildren(object):
            if hasattr(child, "ensurePolished"):
                child.ensurePolished()
    except Exception:
        pass

    # 스플래시 최소 노출 시간. 무거운 MainWindow 생성·프리워밍 동안에는 이벤트
    # 루프가 멈춰 xcb에서 스플래시가 실제로 그려지지 않으므로, 생성이 끝난
    # '지금'을 기준으로 능동적으로 이벤트를 돌리며 1.8초를 보장한다.
    splash_visible_seconds = 1.8
    splash_floor_start = time.time()
    while time.time() - splash_floor_start < splash_visible_seconds:
        app.processEvents()
        time.sleep(0.01)

    # X11(xcb)은 클라이언트가 위치를 못 정하면 창을 좌측 상단에 붙인다. Wayland
    # 에서 저장된 geometry의 위치도 신뢰할 수 없으므로, 저장된 크기는 유지하되
    # 실행 시 항상 현재 화면 중앙에 배치한다. (show 전에 옮겨 WM 경쟁을 피함)
    screen = app.primaryScreen()
    if screen is not None:
        frame = window.frameGeometry()
        frame.moveCenter(screen.availableGeometry().center())
        window.move(frame.topLeft())

    window.show()
    window.activateWindow()
    window.raise_()

    # [추가] 로딩 화면 종료
    if splash:
        splash.finish(window)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
