"""빌드 산출물 실행 스모크 스크립트(scripts/smoke_launch.py)의 경로 규칙.

OS마다 PyInstaller가 놓는 자리가 다르다. 여기가 틀리면 릴리즈 검증이
엉뚱한 파일을 보게 되므로 세 플랫폼을 모두 고정해 둔다.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "smoke_launch.py"


def _load():
    spec = importlib.util.spec_from_file_location("smoke_launch", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_windows_binary_lives_in_the_onedir_folder():
    smoke = _load()
    assert smoke.binary_path("win32", Path("dist")) == Path("dist/Flow/Flow.exe")


def test_macos_binary_lives_inside_the_app_bundle():
    smoke = _load()
    assert smoke.binary_path("darwin", Path("dist")) == Path(
        "dist/Flow.app/Contents/MacOS/Flow"
    )


def test_linux_binary_lives_in_the_onedir_folder():
    smoke = _load()
    assert smoke.binary_path("linux", Path("dist")) == Path("dist/Flow/Flow")
