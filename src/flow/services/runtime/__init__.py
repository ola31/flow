"""LibreOffice portable runtime — download/extract/locate."""
from __future__ import annotations

from pathlib import Path

from flow.services.runtime.libreoffice_runtime import (
    DownloadCancelledError,
    InstallLock,
    InstallLockError,
    InsufficientDiskSpaceError,
    LibreOfficeRuntime,
    PhaseProgressCallback,
    ProgressCallback,
    Sha256MismatchError,
    check_disk_space,
    download_with_progress,
    get_runtime_dir,
    verify_sha256,
)
from flow.services.runtime.manifest import (
    BuildEntry,
    Manifest,
    UnsupportedPlatformError,
    detect_platform_key,
    load_manifest,
)


def get_manifest_for_resources() -> Manifest:
    """Load the manifest shipped with Flow."""
    resource_path = (
        Path(__file__).parent.parent.parent
        / "resources"
        / "libreoffice_manifest.json"
    )
    return load_manifest(resource_path)


__all__ = [
    "BuildEntry",
    "DownloadCancelledError",
    "InsufficientDiskSpaceError",
    "InstallLock",
    "InstallLockError",
    "LibreOfficeRuntime",
    "Manifest",
    "PhaseProgressCallback",
    "ProgressCallback",
    "Sha256MismatchError",
    "UnsupportedPlatformError",
    "check_disk_space",
    "detect_platform_key",
    "download_with_progress",
    "get_manifest_for_resources",
    "get_runtime_dir",
    "load_manifest",
    "verify_sha256",
]
