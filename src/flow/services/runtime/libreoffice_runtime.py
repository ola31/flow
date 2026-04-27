"""Portable LibreOffice runtime — orchestrates detect / download / extract / locate."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def get_runtime_dir() -> Path:
    """User-data location for Flow's bundled LibreOffice."""
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData/Local")
    elif sys.platform == "darwin":
        base = Path.home() / "Library/Application Support"
    else:
        xdg = os.environ.get("XDG_DATA_HOME")
        base = Path(xdg) if xdg else Path.home() / ".local/share"
    return base / "Flow" / "runtime" / "libreoffice"


class LibreOfficeRuntime:
    """Owns the portable LibreOffice install lifecycle."""

    INSTALLED_VERSION_FILE = "INSTALLED_VERSION"

    def __init__(
        self,
        runtime_dir: Path,
        manifest_version: str,
        soffice_relpath: str = "",
    ) -> None:
        self._dir = runtime_dir
        self._manifest_version = manifest_version
        self._soffice_relpath = soffice_relpath

    def installed_version(self) -> str | None:
        f = self._dir / self.INSTALLED_VERSION_FILE
        if not f.exists():
            return None
        return f.read_text(encoding="utf-8").strip() or None

    def is_current(self) -> bool:
        return self.installed_version() == self._manifest_version

    def get_soffice_path(self) -> Path | None:
        if not self.is_current() or not self._soffice_relpath:
            return None
        candidate = self._dir / self._manifest_version / self._soffice_relpath
        return candidate if candidate.exists() else None
