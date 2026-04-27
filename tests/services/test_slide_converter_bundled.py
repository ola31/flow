from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from flow.services.runtime.manifest import BuildEntry
from flow.services.slide_converter import _detect_bundled_libreoffice


class _FakeManifest:
    def __init__(self, version: str, soffice_relpath: str) -> None:
        self.version = version
        self._sr = soffice_relpath

    def get_build_for_current_platform(self) -> BuildEntry:
        return BuildEntry(
            url="https://example/x",
            sha256="a" * 64,
            size_bytes=1,
            format="tar_gz",
            soffice_relpath=self._sr,
        )


def test_detect_bundled_returns_path_when_runtime_current(tmp_path: Path) -> None:
    runtime_dir = tmp_path / "Flow/runtime/libreoffice"
    runtime_dir.mkdir(parents=True)
    (runtime_dir / "INSTALLED_VERSION").write_text("25.2.5.2", encoding="utf-8")
    soffice = runtime_dir / "25.2.5.2" / "program" / "soffice"
    soffice.parent.mkdir(parents=True)
    soffice.write_text("#!/bin/sh", encoding="utf-8")

    fake_manifest = _FakeManifest(
        version="25.2.5.2", soffice_relpath="program/soffice"
    )
    with patch(
        "flow.services.slide_converter.get_runtime_dir", return_value=runtime_dir
    ), patch(
        "flow.services.slide_converter.get_manifest_for_resources",
        return_value=fake_manifest,
    ):
        result = _detect_bundled_libreoffice()
        assert result == soffice


def test_detect_bundled_returns_none_when_not_installed(tmp_path: Path) -> None:
    fake_manifest = _FakeManifest(
        version="25.2.5.2", soffice_relpath="program/soffice"
    )
    with patch(
        "flow.services.slide_converter.get_runtime_dir", return_value=tmp_path
    ), patch(
        "flow.services.slide_converter.get_manifest_for_resources",
        return_value=fake_manifest,
    ):
        assert _detect_bundled_libreoffice() is None


def test_detect_bundled_returns_none_on_unsupported_platform(tmp_path: Path) -> None:
    """When the manifest doesn't have an entry for current platform, return None
    instead of crashing."""
    from flow.services.runtime.manifest import UnsupportedPlatformError

    bad_manifest = _FakeManifest(
        version="25.2.5.2", soffice_relpath="program/soffice"
    )
    bad_manifest.get_build_for_current_platform = (  # type: ignore[method-assign]
        lambda: (_ for _ in ()).throw(UnsupportedPlatformError("test"))
    )
    with patch(
        "flow.services.slide_converter.get_runtime_dir", return_value=tmp_path
    ), patch(
        "flow.services.slide_converter.get_manifest_for_resources",
        return_value=bad_manifest,
    ):
        assert _detect_bundled_libreoffice() is None
