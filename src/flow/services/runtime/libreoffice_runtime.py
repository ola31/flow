"""Portable LibreOffice runtime — orchestrates detect / download / extract / locate."""
from __future__ import annotations

import hashlib
import os
import shutil
import sys
import threading
import urllib.request
from pathlib import Path
from typing import Callable

from flow.services.runtime.extractor import extract_archive
from flow.services.runtime.manifest import BuildEntry


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
    DOWNLOAD_DIR = ".download"

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

    def cleanup_partial_downloads(self) -> None:
        """Remove any leftover .download/ from interrupted runs.

        Safe to call at startup."""
        d = self._dir / self.DOWNLOAD_DIR
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)

    def install(
        self,
        build: BuildEntry,
        *,
        on_progress: PhaseProgressCallback,
        cancel_event: threading.Event,
    ) -> None:
        """Run the full install: download → verify → extract → atomic finalize."""
        self._dir.mkdir(parents=True, exist_ok=True)
        download_dir = self._dir / self.DOWNLOAD_DIR
        download_dir.mkdir(exist_ok=True)
        archive = download_dir / f"libreoffice-{self._manifest_version}.archive"

        # Phase 1: download
        def _dl_progress(received: int, total: int) -> None:
            pct = int(received * 85 / total) if total > 0 else 0
            on_progress(
                "download",
                pct,
                f"{received // (1 << 20)} / {total // (1 << 20)} MB",
            )

        try:
            download_with_progress(
                url=build.url,
                dest=archive,
                chunk_size=1 << 16,
                on_progress=_dl_progress,
                cancel_event=cancel_event,
            )

            # Phase 2: verify
            on_progress("verify", 87, "무결성 검증 중...")
            verify_sha256(archive, build.sha256)

            # Phase 3: extract into staging, then atomic rename
            on_progress("extract", 90, "압축 해제 중...")
            staging = download_dir / "staging"
            if staging.exists():
                shutil.rmtree(staging)
            extract_archive(archive, staging, format=build.format)

            final_version_dir = self._dir / self._manifest_version
            if final_version_dir.exists():
                shutil.rmtree(final_version_dir)
            staging.rename(final_version_dir)

            # Phase 4: atomic INSTALLED_VERSION write
            on_progress("finalize", 99, "마무리 중...")
            tmp = self._dir / (self.INSTALLED_VERSION_FILE + ".tmp")
            tmp.write_text(self._manifest_version, encoding="utf-8")
            os.replace(tmp, self._dir / self.INSTALLED_VERSION_FILE)

            on_progress("done", 100, "완료")
        finally:
            shutil.rmtree(download_dir, ignore_errors=True)


PhaseProgressCallback = Callable[[str, int, str], None]
"""(phase, percent_0_100, human_message)"""

ProgressCallback = Callable[[int, int], None]


class DownloadCancelledError(RuntimeError):
    """Download was cancelled via the cancel_event."""


# Alias for backwards compatibility and plan references
DownloadCancelled = DownloadCancelledError


def download_with_progress(
    *,
    url: str,
    dest: Path,
    chunk_size: int,
    on_progress: ProgressCallback,
    cancel_event: threading.Event,
) -> None:
    """Stream URL → dest, calling on_progress(received, total) each chunk.

    Raises DownloadCancelled if cancel_event is set; partial file deleted.
    """
    if not url.startswith("https://"):
        raise ValueError("Only HTTPS URLs allowed")
    dest.parent.mkdir(parents=True, exist_ok=True)
    response = urllib.request.urlopen(url)
    total = int(response.headers.get("Content-Length", 0))
    received = 0
    try:
        with open(dest, "wb") as f:
            while True:
                if cancel_event.is_set():
                    raise DownloadCancelled()
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                received += len(chunk)
                on_progress(received, total)
    except DownloadCancelled:
        if dest.exists():
            dest.unlink()
        raise
    except Exception:
        if dest.exists():
            dest.unlink()
        raise


class Sha256MismatchError(RuntimeError):
    """Downloaded file failed integrity check."""


def verify_sha256(path: Path, expected_hex: str) -> None:
    """Compute SHA256 of file, compare with expected. Deletes file on mismatch."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    actual = h.hexdigest()
    if actual.lower() != expected_hex.lower():
        if path.exists():
            path.unlink()
        raise Sha256MismatchError(
            f"hash mismatch for {path.name}: expected {expected_hex}, got {actual}"
        )
