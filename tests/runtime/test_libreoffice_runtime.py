from __future__ import annotations

import hashlib
import tarfile
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from flow.services.runtime.libreoffice_runtime import (
    DownloadCancelledError,
    LibreOfficeRuntime,
    Sha256MismatchError,
    download_with_progress,
    get_runtime_dir,
    verify_sha256,
)
from flow.services.runtime.manifest import BuildEntry


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
        with pytest.raises(DownloadCancelledError):
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


def test_verify_sha256_matching(tmp_path: Path) -> None:
    f = tmp_path / "a"
    f.write_bytes(b"hello")
    expected = hashlib.sha256(b"hello").hexdigest()
    verify_sha256(f, expected)  # no exception


def test_verify_sha256_mismatch_deletes_file(tmp_path: Path) -> None:
    f = tmp_path / "a"
    f.write_bytes(b"hello")
    with pytest.raises(Sha256MismatchError):
        verify_sha256(f, "0" * 64)
    assert not f.exists()


def _make_build(content: bytes, soffice_relpath: str) -> BuildEntry:
    return BuildEntry(
        url="https://example/lo.tar.gz",
        sha256=hashlib.sha256(content).hexdigest(),
        size_bytes=len(content),
        format="tar_gz",
        soffice_relpath=soffice_relpath,
    )


def test_install_full_flow(tmp_path: Path) -> None:
    """Happy path: download → verify → extract → INSTALLED_VERSION written."""
    src = tmp_path / "src"
    src.mkdir()
    soffice = src / "myproj" / "program" / "soffice"
    soffice.parent.mkdir(parents=True)
    soffice.write_text("#!/bin/sh", encoding="utf-8")
    archive_bytes_path = tmp_path / "archive.tar.gz"
    with tarfile.open(archive_bytes_path, "w:gz") as tf:
        tf.add(src / "myproj", arcname="myproj")
    archive_bytes = archive_bytes_path.read_bytes()

    build = _make_build(archive_bytes, "myproj/program/soffice")
    runtime_dir = tmp_path / "rt"

    progress_log: list[tuple[str, int, str]] = []

    def progress(phase: str, pct: int, msg: str) -> None:
        progress_log.append((phase, pct, msg))

    rt = LibreOfficeRuntime(
        runtime_dir=runtime_dir,
        manifest_version="9.9.9",
        soffice_relpath="myproj/program/soffice",
    )

    response = MagicMock()
    response.headers = {"Content-Length": str(len(archive_bytes))}
    chunks = [archive_bytes[i : i + 1024] for i in range(0, len(archive_bytes), 1024)]
    response.read = MagicMock(side_effect=chunks + [b""])

    with patch("urllib.request.urlopen", return_value=response):
        rt.install(build, on_progress=progress, cancel_event=threading.Event())

    assert (runtime_dir / "INSTALLED_VERSION").read_text() == "9.9.9"
    assert (runtime_dir / "9.9.9" / "myproj" / "program" / "soffice").exists()
    assert rt.is_current()
    assert rt.get_soffice_path() is not None
    phases = {p for p, _, _ in progress_log}
    assert "download" in phases and "verify" in phases and "extract" in phases


def test_install_cleans_up_on_cancel(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "f").write_text("x" * 5000, encoding="utf-8")
    archive_path = tmp_path / "a.tar.gz"
    with tarfile.open(archive_path, "w:gz") as tf:
        tf.add(src / "f", arcname="f")
    archive_bytes = archive_path.read_bytes()

    build = _make_build(archive_bytes, "f")
    runtime_dir = tmp_path / "rt"
    cancel = threading.Event()

    response = MagicMock()
    response.headers = {"Content-Length": str(len(archive_bytes))}
    chunks = [archive_bytes[i : i + 100] for i in range(0, len(archive_bytes), 100)]
    response.read = MagicMock(side_effect=chunks + [b""])

    def progress(phase: str, pct: int, msg: str) -> None:
        if phase == "download" and pct >= 50:
            cancel.set()

    rt = LibreOfficeRuntime(
        runtime_dir=runtime_dir,
        manifest_version="1.0",
        soffice_relpath="f",
    )
    with patch("urllib.request.urlopen", return_value=response):
        with pytest.raises(DownloadCancelledError):
            rt.install(build, on_progress=progress, cancel_event=cancel)

    assert not (runtime_dir / "INSTALLED_VERSION").exists()
    assert not (runtime_dir / ".download").exists()


def test_install_cleans_up_on_sha_mismatch(tmp_path: Path) -> None:
    bad_build = BuildEntry(
        url="https://example/x.tar.gz",
        sha256="0" * 64,  # won't match
        size_bytes=10,
        format="tar_gz",
        soffice_relpath="f",
    )
    runtime_dir = tmp_path / "rt"
    rt = LibreOfficeRuntime(
        runtime_dir=runtime_dir,
        manifest_version="1.0",
        soffice_relpath="f",
    )
    response = MagicMock()
    response.headers = {"Content-Length": "5"}
    response.read = MagicMock(side_effect=[b"abcde", b""])

    with patch("urllib.request.urlopen", return_value=response):
        with pytest.raises(Sha256MismatchError):
            rt.install(
                bad_build,
                on_progress=lambda *a: None,
                cancel_event=threading.Event(),
            )

    assert not (runtime_dir / "INSTALLED_VERSION").exists()
