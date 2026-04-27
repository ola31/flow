from __future__ import annotations

import os

from flow.ui.dialogs import (
    EngineDownloadWorker,
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


def test_download_worker_emits_progress_and_finished(qapp_args, qtbot) -> None:
    """Worker exposes progress/finished signals."""
    def fake_install(*, on_progress, cancel_event):
        on_progress("download", 50, "halfway")
        on_progress("done", 100, "complete")

    worker = EngineDownloadWorker(install_fn=fake_install)
    progress_log: list[tuple[str, int, str]] = []
    finished_log: list[tuple[bool, str]] = []
    worker.progress.connect(
        lambda p, pct, m: progress_log.append((p, pct, m))
    )
    worker.finished_with_status.connect(
        lambda ok, err: finished_log.append((ok, err))
    )

    worker.start()
    worker.wait(2000)

    assert ("download", 50, "halfway") in progress_log
    assert finished_log == [(True, "")]


def test_download_worker_reports_failure(qapp_args, qtbot) -> None:
    def fake_install(*, on_progress, cancel_event):
        raise RuntimeError("network down")

    worker = EngineDownloadWorker(install_fn=fake_install)
    finished_log: list[tuple[bool, str]] = []
    worker.finished_with_status.connect(
        lambda ok, err: finished_log.append((ok, err))
    )
    worker.start()
    worker.wait(2000)
    assert finished_log == [(False, "network down")]
