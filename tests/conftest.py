"""pytest 공통 픽스처 및 설정"""

import pytest

# ROS2 플러그인 비활성화 (시스템 레벨 충돌 방지)
collect_ignore_glob = ["**/ros2_*/**", "**/colcon_ws/**"]


def pytest_configure(config):
    """pytest 초기 설정"""
    # launch_testing_ros 플러그인 언로드 시도 (ROS2 충돌 방지)
    pm = config.pluginmanager
    for name in ["launch_testing_ros"]:
        try:
            if pm.has_plugin(name):
                pm.unregister(name=name)
        except Exception:
            pass


@pytest.fixture(scope="session")
def qapp_args():
    """QApplication 인자 설정 - headless 모드"""
    return ["--platform", "offscreen"]
