from __future__ import annotations

import json
from pathlib import Path

import pytest

from flow.services.runtime.manifest import (
    UnsupportedPlatformError,
    detect_platform_key,
    load_manifest,
)


@pytest.fixture
def sample_manifest(tmp_path: Path) -> Path:
    data = {
        "version": "25.2.5.2",
        "source_url": "https://www.libreoffice.org/download/",
        "license_url": "https://www.libreoffice.org/about-us/licenses/",
        "builds": {
            "linux-x86_64": {
                "url": "https://download.documentfoundation.org/x.tar.gz",
                "sha256": "a" * 64,
                "size_bytes": 100,
                "format": "tar_gz",
                "soffice_relpath": "x/program/soffice",
            },
            "macos-aarch64": {
                "url": "https://download.documentfoundation.org/x.dmg",
                "sha256": "b" * 64,
                "size_bytes": 200,
                "format": "dmg",
                "soffice_relpath": "LibreOffice.app/Contents/MacOS/soffice",
            },
        },
    }
    p = tmp_path / "manifest.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def test_load_manifest_parses_valid_json(sample_manifest: Path) -> None:
    m = load_manifest(sample_manifest)
    assert m.version == "25.2.5.2"
    assert "linux-x86_64" in m.builds
    assert m.builds["linux-x86_64"].sha256 == "a" * 64
    assert m.builds["linux-x86_64"].format == "tar_gz"


def test_load_manifest_rejects_missing_required_field(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"version": "1.0"}), encoding="utf-8")  # no builds
    with pytest.raises(ValueError, match="builds"):
        load_manifest(bad)


def test_load_manifest_rejects_http_url(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text(
        json.dumps({
            "version": "1.0",
            "source_url": "x",
            "license_url": "x",
            "builds": {
                "linux-x86_64": {
                    "url": "http://insecure.example/x.tar.gz",
                    "sha256": "a" * 64,
                    "size_bytes": 1,
                    "format": "tar_gz",
                    "soffice_relpath": "x",
                }
            },
        }),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="HTTPS"):
        load_manifest(bad)


def test_detect_platform_key_normalizes_arch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setattr("platform.machine", lambda: "x86_64")
    assert detect_platform_key() == "linux-x86_64"

    monkeypatch.setattr("platform.machine", lambda: "aarch64")
    assert detect_platform_key() == "linux-aarch64"

    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.setattr("platform.machine", lambda: "AMD64")
    assert detect_platform_key() == "windows-x86_64"

    monkeypatch.setattr("sys.platform", "darwin")
    monkeypatch.setattr("platform.machine", lambda: "arm64")
    assert detect_platform_key() == "macos-aarch64"


def test_detect_platform_key_rejects_unknown_arch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setattr("platform.machine", lambda: "riscv64")
    with pytest.raises(UnsupportedPlatformError):
        detect_platform_key()


def test_get_build_for_current_platform(
    sample_manifest: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setattr("platform.machine", lambda: "x86_64")
    m = load_manifest(sample_manifest)
    build = m.get_build_for_current_platform()
    assert build.format == "tar_gz"


def test_get_build_for_unsupported_platform(
    sample_manifest: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sys.platform", "linux")
    # aarch64 is not in the sample manifest
    monkeypatch.setattr("platform.machine", lambda: "aarch64")
    m = load_manifest(sample_manifest)
    with pytest.raises(UnsupportedPlatformError):
        m.get_build_for_current_platform()
