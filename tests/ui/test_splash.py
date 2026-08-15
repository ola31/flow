"""시작 로고 창.

Qt의 QSplashScreen은 이 버전에서 show() 한 번에 ~1초를 블로킹한다
(내용·플랫폼과 무관하게 재현). 시작 시간의 큰 몫이라 같은 모양의
프레임리스 위젯으로 대체했고, 아래 테스트가 그 성질을 지킨다.
"""
from __future__ import annotations

import time

from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QSplashScreen

from flow.ui.splash import Splash

# 실측: QSplashScreen 1010ms vs 프레임리스 QWidget <7ms.
# 회귀를 잡되 느린 CI에서 흔들리지 않을 자리.
_SHOW_BUDGET_MS = 300


def _pixmap() -> QPixmap:
    pm = QPixmap(120, 80)
    pm.fill()
    return pm


def test_show_does_not_block(qtbot):
    splash = Splash(_pixmap(), "불러오는 중...")
    qtbot.addWidget(splash)

    start = time.perf_counter()
    splash.show()
    elapsed_ms = (time.perf_counter() - start) * 1000

    assert elapsed_ms < _SHOW_BUDGET_MS, f"show()가 {elapsed_ms:.0f}ms 걸림"


def test_is_not_a_qsplashscreen(qtbot):
    """QSplashScreen으로 되돌아가면 1초가 조용히 돌아온다."""
    splash = Splash(_pixmap(), "불러오는 중...")
    qtbot.addWidget(splash)

    assert not isinstance(splash, QSplashScreen)


def test_shows_the_image_and_the_message(qtbot):
    pm = _pixmap()
    splash = Splash(pm, "프로그램을 불러오는 중...")
    qtbot.addWidget(splash)
    splash.show()

    assert splash._image.pixmap().size() == pm.size()
    assert splash._message.text() == "프로그램을 불러오는 중..."


def test_finish_closes_it(qtbot):
    splash = Splash(_pixmap(), "불러오는 중...")
    qtbot.addWidget(splash)
    splash.show()

    splash.finish()

    assert not splash.isVisible()
