"""크래시 로그 설정 테스트 — segfault 스택이 영구 파일에 남아야 한다."""
from __future__ import annotations

import faulthandler


def test_setup_crash_log_writes_to_persistent_file(tmp_path, monkeypatch):
    from pathlib import Path

    import flow.main as flow_main

    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
    try:
        flow_main._setup_crash_log()

        crash_file = tmp_path / ".flow" / "crash.log"
        assert crash_file.exists()
        content = crash_file.read_text(encoding="utf-8")
        assert "Flow" in content and "시작" in content  # 세션 헤더
        assert faulthandler.is_enabled()
        assert flow_main._CRASH_LOG_HANDLE is not None
    finally:
        # 전역 상태 원복 — 이후 테스트의 크래시 덤프가 임시 파일로 가지 않게
        if flow_main._CRASH_LOG_HANDLE is not None:
            flow_main._CRASH_LOG_HANDLE.close()
            flow_main._CRASH_LOG_HANDLE = None
        import sys

        if sys.stderr is not None:
            faulthandler.enable()
