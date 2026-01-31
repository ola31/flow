"""pytest 공통 픽스처 및 설정"""

import os
import sys

# ROS2 환경 변수 제거 (pytest 플러그인 충돌 방지)
for key in list(os.environ.keys()):
    if "ROS" in key or "AMENT" in key or "COLCON" in key:
        del os.environ[key]

# ROS2 관련 경로 제거
sys.path = [
    p for p in sys.path if "ros2" not in p.lower() and "colcon" not in p.lower()
]

import pytest

# ROS2 플러그인 비활성화 (시스템 레벨 충돌 방지)
collect_ignore_glob = ["**/ros2_*/**", "**/colcon_ws/**", "**/launch_testing*/**"]


def pytest_configure(config):
    """pytest 초기 설정"""
    # ROS2 관련 모든 플러그인 언로드 시도
    pm = config.pluginmanager
    ros2_plugins = [
        "launch_testing_ros",
        "launch_testing",
        "launch_pytest",
        "ament_xmllint",
        "ament_pep257",
        "ament_mypy",
        "ament_flake8",
        "ament_copyright",
        "ament_lint",
        "launch_testing_ros_pytest_entrypoint",
    ]
    for name in ros2_plugins:
        try:
            if pm.has_plugin(name):
                pm.unregister(name=name)
        except Exception:
            pass


@pytest.fixture(scope="session")
def qapp_args():
    """QApplication 인자 설정 - headless 모드"""
    return ["--platform", "offscreen"]
