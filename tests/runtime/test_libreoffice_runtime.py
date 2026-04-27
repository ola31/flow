from __future__ import annotations

import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from flow.services.runtime.libreoffice_runtime import (
    DownloadCancelled,
    LibreOfficeRuntime,
    download_with_progress,
    get_runtime_dir,
)


def test_get_runtime_dir_linux(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert get_runtime_dir() == tmp_path / "Flow" / "runtime" / "libreoffice"


def test_get_runtime_dir_linux_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert get_runtime_dir() == tmp_path / ".local/share/Flow/runtime/libreoffice"


def test_get_runtime_dir_macos(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("sys.platform", "darwin")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    expected = tmp_path / "Library/Application Support/Flow/runtime/libreoffice"
    assert get_runtime_dir() == expected


def test_get_runtime_dir_windows(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert get_runtime_dir() == tmp_path / "Flow/runtime/libreoffice"


def test_runtime_not_installed(tmp_path: Path) -> None:
    rt = LibreOfficeRuntime(runtime_dir=tmp_path, manifest_version="25.2.5.2")
    assert rt.installed_version() is None
    assert not rt.is_current()
    assert rt.get_soffice_path() is None


def test_runtime_installed_current(tmp_path: Path) -> None:
    (tmp_path / "INSTALLED_VERSION").write_text("25.2.5.2", encoding="utf-8")
    version_dir = tmp_path / "25.2.5.2"
    version_dir.mkdir()
    soffice = version_dir / "program" / "soffice"
    soffice.parent.mkdir()
    soffice.write_text("#!/bin/sh", encoding="utf-8")

    rt = LibreOfficeRuntime(
        runtime_dir=tmp_path,
        manifest_version="25.2.5.2",
        soffice_relpath="program/soffice",
    )
    assert rt.installed_version() == "25.2.5.2"
    assert rt.is_current()
    assert rt.get_soffice_path() == soffice


def test_runtime_installed_outdated(tmp_path: Path) -> None:
    (tmp_path / "INSTALLED_VERSION").write_text("25.2.4.0", encoding="utf-8")
    rt = LibreOfficeRuntime(runtime_dir=tmp_path, manifest_version="25.2.5.2")
    assert rt.installed_version() == "25.2.4.0"
    assert not rt.is_current()


def test_download_writes_file_and_reports_progress(tmp_path: Path) -> None:
    chunks = [b"x" * 1000, b"y" * 1000, b"z" * 500]
    response = MagicMock()
    response.headers = {"Content-Length": "2500"}
    response.read = MagicMock(side_effect=chunks + [b""])

    progress_calls: list[tuple[int, int]] = []

    def on_progress(received: int, total: int) -> None:
        progress_calls.append((received, total))

    target = tmp_path / "out.bin"
    with patch("urllib.request.urlopen", return_value=response):
        download_with_progress(
            url="https://example/x",
            dest=target,
            chunk_size=1000,
            on_progress=on_progress,
            cancel_event=threading.Event(),
        )

    assert target.read_bytes() == b"x" * 1000 + b"y" * 1000 + b"z" * 500
    assert progress_calls[-1] == (2500, 2500)
    assert (1000, 2500) in progress_calls


def test_download_cancellation(tmp_path: Path) -> None:
    chunks = [b"x" * 1000] * 100
    response = MagicMock()
    response.headers = {"Content-Length": "100000"}
    response.read = MagicMock(side_effect=chunks + [b""])

    cancel = threading.Event()
    target = tmp_path / "out.bin"

    def on_progress(received: int, total: int) -> None:
        if received >= 3000:
            cancel.set()

    with patch("urllib.request.urlopen", return_value=response):
        with pytest.raises(DownloadCancelled):
            download_with_progress(
                url="https://example/x",
                dest=target,
                chunk_size=1000,
                on_progress=on_progress,
                cancel_event=cancel,
            )
    # Partial file should be cleaned up
    assert not target.exists()


def test_download_rejects_non_https() -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        download_with_progress(
            url="http://example/x",
            dest=Path("/tmp/x"),
            chunk_size=1000,
            on_progress=lambda r, t: None,
            cancel_event=threading.Event(),
        )
