import weakref

import pytest


@pytest.fixture(scope="session")
def qapp_args():
    return ["--platform", "offscreen"]


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
