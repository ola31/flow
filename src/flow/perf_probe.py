"""FLOW_PERF=1 환경변수로 켜는 경량 성능 프로브.

페이지 전환이 "실사용 세션에서만" 느려지는 문제는 새 프로세스로 재현이
안 된다. 사용자 세션에서 직접 증거를 잡기 위해:

- 페이지 전환 메서드 소요 시간 + 호출 후 첫 페인트까지의 시간
- 이벤트 루프 정지(스톨) — 100ms 주기 하트비트가 300ms 이상 밀리면 기록

을 ~/.flow/perf.log 에 남긴다. 평상시(env 미설정)에는 아무것도 하지 않는다.
"""

from __future__ import annotations

import sys
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, QTimer

# 파일 핸들이 GC로 닫히지 않게 모듈 전역으로 유지 (crash.log와 같은 패턴)
_LOG_HANDLE = None

_SWITCH_METHODS = (
    "show_home",
    "_show_library_screen",
    "_show_projects_screen",
    "_show_web_broadcast_screen",
)

_STALL_INTERVAL_MS = 100
_STALL_THRESHOLD_MS = 300


class _PaintWatcher(QObject):
    """전환 직후 첫 Paint 이벤트까지의 시간을 기록한다."""

    def __init__(self, window: QObject, log) -> None:
        super().__init__(window)
        self._log = log
        self._pending_label: str | None = None
        self._pending_since = 0.0
        window.installEventFilter(self)

    def arm(self, label: str) -> None:
        self._pending_label = label
        self._pending_since = time.time()

    def eventFilter(  # noqa: N802 — Qt 오버라이드
        self, obj: QObject, event: QEvent
    ) -> bool:
        if (
            self._pending_label is not None
            and event.type() == QEvent.Type.Paint
        ):
            elapsed = (time.time() - self._pending_since) * 1000
            self._log(f"{self._pending_label} 첫 페인트까지 {elapsed:.0f}ms")
            self._pending_label = None
        return False


def install(window, log_path: Path | None = None) -> None:
    """window의 페이지 전환 메서드를 계측하고 스톨 감지 타이머를 건다."""
    global _LOG_HANDLE
    path = log_path or (Path.home() / ".flow" / "perf.log")
    path.parent.mkdir(exist_ok=True)
    try:
        if path.stat().st_size > 1_000_000:  # 무한 성장 방지
            path.rename(path.with_suffix(".log.1"))
    except OSError:
        pass
    f = open(path, "a", buffering=1, encoding="utf-8")
    _LOG_HANDLE = f
    f.write(
        f"\n=== 성능 프로브 시작: "
        f"{datetime.now().isoformat(timespec='seconds')} ===\n"
    )

    def log(msg: str) -> None:
        f.write(f"{datetime.now().strftime('%H:%M:%S.%f')[:-3]} {msg}\n")

    watcher = _PaintWatcher(window, log)

    def wrap(name: str):
        original = getattr(window, name)

        def timed(*args, **kwargs):
            t0 = time.time()
            try:
                return original(*args, **kwargs)
            finally:
                elapsed = (time.time() - t0) * 1000
                log(f"{name} 본체 {elapsed:.0f}ms")
                watcher.arm(name)

        return timed

    for name in _SWITCH_METHODS:
        if hasattr(window, name):
            setattr(window, name, wrap(name))

    # 이벤트 루프 스톨 감지 — 하트비트 지연이 곧 UI 멈춤 시간이다
    state = {"last": time.time()}

    def heartbeat() -> None:
        now = time.time()
        gap_ms = (now - state["last"]) * 1000
        if gap_ms > _STALL_THRESHOLD_MS:
            log(f"이벤트 루프 정지 {gap_ms:.0f}ms")
        state["last"] = now

    timer = QTimer(window)
    timer.setInterval(_STALL_INTERVAL_MS)
    timer.timeout.connect(heartbeat)
    timer.start()

    # 워치독 스레드 — 스톨이 진행 중일 때 메인 스레드가 "지금 뭘 하고
    # 있는지" 스택을 채집한다. 하트비트만으로는 멈춘 시간은 알아도
    # 원인은 알 수 없다.
    main_thread_id = threading.get_ident()

    def watchdog() -> None:
        in_stall = False
        while True:
            time.sleep(0.05)
            gap = time.time() - state["last"]
            if gap > 0.25 and not in_stall:
                in_stall = True
                frame = sys._current_frames().get(main_thread_id)
                if frame is not None:
                    stack = "".join(traceback.format_stack(frame))
                    log(
                        f"스톨 진행 중(하트비트 {gap * 1000:.0f}ms 지연)"
                        f" — 메인 스레드 스택:\n{stack}"
                    )
            elif gap < 0.15:
                in_stall = False

    threading.Thread(target=watchdog, daemon=True, name="perf-watchdog").start()
