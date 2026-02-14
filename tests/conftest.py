import pytest


@pytest.fixture(scope="session")
def qapp_args():
    return ["--platform", "offscreen"]
