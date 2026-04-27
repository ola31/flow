"""LibreOffice runtime manifest — schema + OS×arch matching."""
from __future__ import annotations

import json
import platform
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

BuildFormat = Literal["tar_gz", "dmg", "msi"]


class UnsupportedPlatformError(RuntimeError):
    """Current OS×arch is not in the manifest."""

    def __init__(self, key: str) -> None:
        super().__init__(f"Unsupported platform: {key}")
        self.key = key


@dataclass(frozen=True)
class BuildEntry:
    url: str
    sha256: str
    size_bytes: int
    format: BuildFormat
    soffice_relpath: str


@dataclass(frozen=True)
class Manifest:
    version: str
    source_url: str
    license_url: str
    builds: dict[str, BuildEntry]

    def get_build_for_current_platform(self) -> BuildEntry:
        key = detect_platform_key()
        build = self.builds.get(key)
        if build is None:
            raise UnsupportedPlatformError(key)
        return build


def detect_platform_key() -> str:
    """Return e.g. 'linux-x86_64', 'macos-aarch64', 'windows-x86_64'."""
    machine = platform.machine().lower()
    arch = {
        "amd64": "x86_64",
        "x86_64": "x86_64",
        "arm64": "aarch64",
        "aarch64": "aarch64",
    }.get(machine)
    if arch is None:
        raise UnsupportedPlatformError(f"unknown-arch:{machine}")

    os_key = {"linux": "linux", "darwin": "macos", "win32": "windows"}.get(sys.platform)
    if os_key is None:
        raise UnsupportedPlatformError(f"unknown-os:{sys.platform}")

    return f"{os_key}-{arch}"


def load_manifest(path: Path) -> Manifest:
    """Load and validate manifest JSON. Raises ValueError on schema violation."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    if "builds" not in raw:
        raise ValueError("manifest missing required field: builds")
    for field in ("version", "source_url", "license_url"):
        if field not in raw:
            raise ValueError(f"manifest missing required field: {field}")
    if not isinstance(raw["builds"], dict) or not raw["builds"]:
        raise ValueError("manifest builds must be non-empty dict")

    builds: dict[str, BuildEntry] = {}
    for key, b in raw["builds"].items():
        for field in ("url", "sha256", "size_bytes", "format", "soffice_relpath"):
            if field not in b:
                raise ValueError(f"build {key} missing field: {field}")
        if not b["url"].startswith("https://"):
            raise ValueError(f"build {key}: only HTTPS URLs allowed")
        if len(b["sha256"]) != 64:
            raise ValueError(f"build {key}: sha256 must be 64 hex chars")
        if b["format"] not in ("tar_gz", "dmg", "msi"):
            raise ValueError(f"build {key}: unknown format {b['format']}")
        builds[key] = BuildEntry(
            url=b["url"],
            sha256=b["sha256"],
            size_bytes=int(b["size_bytes"]),
            format=b["format"],
            soffice_relpath=b["soffice_relpath"],
        )

    return Manifest(
        version=raw["version"],
        source_url=raw["source_url"],
        license_url=raw["license_url"],
        builds=builds,
    )
