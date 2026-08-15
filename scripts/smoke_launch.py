#!/usr/bin/env python3
"""빌드된 Flow가 실제로 뜨는지 확인한다 (릴리즈 게이트).

패키징이 깨지는 사고 — 번들에서 빠진 모듈, 지나치게 걷어낸 Qt 플러그인 —
는 개발 환경에서는 멀쩡하고 **설치본에서만** 드러난다. 여기서 산출물을
직접 띄워 보고, 뜨지 않으면 릴리즈를 세운다.

워크스페이스를 미리 만들어 두고 HOME을 임시 폴더로 돌린 뒤 실행한다.
그래야 첫 실행 다이얼로그에서 멈추지 않고 메인 창 생성까지 지나가며,
개발자 PC에서 돌려도 실제 ~/.flow 설정을 건드리지 않는다.

사용법:
    python scripts/smoke_launch.py [--seconds 15] [--dist dist]
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def binary_path(platform_name: str, dist_dir: Path) -> Path:
    """PyInstaller가 산출물을 놓는 자리."""
    if platform_name.startswith("win"):
        return dist_dir / "Flow" / "Flow.exe"
    if platform_name == "darwin":
        return dist_dir / "Flow.app" / "Contents" / "MacOS" / "Flow"
    return dist_dir / "Flow" / "Flow"


def prepare_home(root: Path) -> Path:
    """워크스페이스와 설정이 준비된 임시 HOME을 만든다."""
    home = root / "home"
    workspace = root / "workspace"
    (workspace / "library").mkdir(parents=True)
    (workspace / "projects").mkdir(parents=True)
    (workspace / ".flow-workspace").write_text('{"version": 1}\n', encoding="utf-8")

    config_dir = home / ".flow"
    config_dir.mkdir(parents=True)
    (config_dir / "config.json").write_text(
        json.dumps({"current_workspace": str(workspace)}, ensure_ascii=False),
        encoding="utf-8",
    )
    return home


def run(binary: Path, home: Path, seconds: float) -> int:
    env = dict(os.environ)
    env["HOME"] = str(home)          # POSIX
    env["USERPROFILE"] = str(home)   # Windows (Path.home()이 보는 값)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["FLOW_PERF"] = "0"

    proc = subprocess.Popen(
        [str(binary)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
        text=True,
    )

    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            break
        time.sleep(0.25)

    if proc.poll() is None:
        # 살아서 이벤트 루프를 돌고 있다 = 정상 기동
        proc.terminate()
        try:
            proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        print(f"OK: {seconds:.0f}초 동안 실행 유지")
        return 0

    output = proc.communicate()[0] or ""
    if proc.returncode == 0:
        print("OK: 깨끗하게 종료됨")
        return 0

    print(f"FAIL: 종료 코드 {proc.returncode}")
    if output.strip():
        print("--- 출력 ---")
        print(output.strip()[-4000:])
    crash_log = home / ".flow" / "crash.log"
    if crash_log.exists():
        print("--- crash.log ---")
        print(crash_log.read_text(encoding="utf-8", errors="replace")[-4000:])
    return 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist", default="dist", type=Path)
    parser.add_argument("--seconds", default=15.0, type=float)
    args = parser.parse_args()

    binary = binary_path(sys.platform, args.dist)
    if not binary.exists():
        print(f"FAIL: 산출물이 없습니다: {binary}")
        return 1

    print(f"실행: {binary}")
    with tempfile.TemporaryDirectory(prefix="flow-smoke-") as tmp:
        return run(binary, prepare_home(Path(tmp)), args.seconds)


if __name__ == "__main__":
    sys.exit(main())
