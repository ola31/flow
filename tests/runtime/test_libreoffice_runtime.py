from __future__ import annotations

from pathlib import Path

import pytest

from flow.services.runtime.libreoffice_runtime import (
    LibreOfficeRuntime,
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
