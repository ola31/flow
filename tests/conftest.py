import os

# 테스트는 반드시 offscreen으로 돈다 — qapp_args로 넘기던 "--platform
# offscreen"은 실제로는 적용되지 않아 로컬 스위트가 세션 플랫폼(wayland)
# 으로 돌았고, offscreen인 CI와 코드 경로가 갈라져 "로컬만 통과"가
# 반복됐다. 환경변수는 QApplication 생성 전에 확실히 먹는다.
# (실화면으로 돌리고 싶으면 QT_QPA_PLATFORM=wayland pytest ...)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import weakref  # noqa: E402

import pytest  # noqa: E402

# 셧다운 없이 만들어진 MainWindow/SlideManager 추적용 — 실행 중인
# QThread(슬라이드 워커)를 가진 객체가 뒤늦은 GC로 파괴되면 크래시가
# 날 수 있어, 테스트가 끝날 때마다 워커를 정지시킨다.
_live_slide_managers: "weakref.WeakSet" = weakref.WeakSet()


@pytest.fixture(autouse=True, scope="session")
def _track_slide_managers():
    from flow.services.slide_manager import SlideManager

    orig_init = SlideManager.__init__

    def tracked_init(self, *args, **kwargs):
        orig_init(self, *args, **kwargs)
        _live_slide_managers.add(self)

    SlideManager.__init__ = tracked_init
    yield
    SlideManager.__init__ = orig_init


@pytest.fixture(autouse=True)
def _stop_leaked_workers(_track_slide_managers):
    """테스트마다 살아남은 슬라이드 워커 스레드를 정지한다.

    다수 테스트가 MainWindow를 셧다운 없이 만들어 실행 중인 QThread를
    남긴다. 그 소유 객체가 이후 임의 시점의 GC에서 파괴되면 '실행 중인
    QThread 파괴' 크래시가 될 수 있다 — 스레드를 즉시 세워 위험을
    제거한다. (주의: 여기서 gc.collect()를 강제하면 PySide teardown
    크래시가 오히려 악화된다 — 실측 기준.)
    """
    yield
    for sm in list(_live_slide_managers):
        try:
            sm.shutdown()
        except Exception:
            pass

    # 이 테스트가 남긴 posted 이벤트·deferred delete를 지금(소유 객체가
    # 아직 살아있을 때) 소화한다. 미루면 다음 테스트의 이벤트 처리에서
    # 파괴된 객체를 향해 터진다 — CI 워커 segfault가 "다음 테스트 시작
    # 순간"에 몰리던 이유.
    from PySide6.QtCore import QEvent
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is not None:
        app.sendPostedEvents()
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()
