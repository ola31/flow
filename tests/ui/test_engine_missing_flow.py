from __future__ import annotations

import os

from flow.ui.dialogs import (
    PreflightChoice,
    flow_show_engine_preflight,
)


def test_preflight_enum_values() -> None:
    """Enum members have expected stable string values."""
    assert PreflightChoice.DOWNLOAD.value == "download"
    assert PreflightChoice.INSTALL_GUIDE.value == "install_guide"
    assert PreflightChoice.CANCEL.value == "cancel"


def test_preflight_returns_value_under_pytest(qapp_args) -> None:
    """Function callable + returns a PreflightChoice (auto-accept under PYTEST)."""
    os.environ["PYTEST_CURRENT_TEST"] = "test_preflight_returns_value_under_pytest"
    try:
        result = flow_show_engine_preflight(
            parent=None, manifest_version="25.2.5.2", size_mb=290
        )
        assert isinstance(result, PreflightChoice)
    finally:
        os.environ.pop("PYTEST_CURRENT_TEST", None)
