"""FLOW_PERF 성능 프로브 테스트"""
from __future__ import annotations

import time

from PySide6.QtWidgets import QWidget

from flow.perf_probe import install


class _FakeWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.calls = 0

    def show_home(self):
        self.calls += 1
        time.sleep(0.01)


class TestPerfProbe:
    def test_switch_method_logged_and_still_works(self, qtbot, tmp_path):
        w = _FakeWindow()
        qtbot.addWidget(w)
        log = tmp_path / "perf.log"

        install(w, log_path=log)
        w.show_home()

        assert w.calls == 1  # 원래 동작 유지
        text = log.read_text(encoding="utf-8")
        assert "show_home 본체" in text

    def test_stall_detector_logs_long_block(self, qtbot, tmp_path):
        w = _FakeWindow()
        qtbot.addWidget(w)
        log = tmp_path / "perf.log"

        install(w, log_path=log)
        qtbot.wait(150)  # 하트비트 1회 이상
        time.sleep(0.45)  # 이벤트 루프 블로킹 시뮬레이션
        qtbot.wait(150)  # 다음 하트비트가 지연을 감지

        text = log.read_text(encoding="utf-8")
        assert "이벤트 루프 정지" in text

    def test_missing_methods_ignored(self, qtbot, tmp_path):
        w = QWidget()
        qtbot.addWidget(w)

        install(w, log_path=tmp_path / "perf.log")  # 전환 메서드 없어도 무해
