from __future__ import annotations

import io
import sys

import flow.main as flow_main


def test_harden_std_streams_replaces_none(monkeypatch):
    """windowed PyInstaller 빌드 시뮬레이션: stdout/stderr가 None이어도
    크래시 없이 안전한 스트림으로 대체되고, faulthandler가 쓸 수 있도록
    실제 fileno를 가진다."""
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)

    flow_main._harden_std_streams()

    assert sys.stdout is not None
    assert sys.stderr is not None
    # print()/stderr 쓰기가 예외 없이 동작해야 함
    sys.stdout.write("x")
    sys.stderr.write("y")
    # faulthandler.enable()이 요구하는 실제 파일 디스크립터
    assert sys.stdout.fileno() >= 0


def test_harden_std_streams_keeps_valid_streams(monkeypatch):
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr(sys, "stdout", out)
    monkeypatch.setattr(sys, "stderr", err)

    flow_main._harden_std_streams()

    assert sys.stdout is out
    assert sys.stderr is err
