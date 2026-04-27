"""Format-specific extractors for LibreOffice runtime archives."""
from __future__ import annotations

import shutil
import subprocess
import sys
import tarfile
from pathlib import Path
from typing import Literal

ArchiveFormat = Literal["tar_gz", "dmg", "msi"]


class ExtractionError(RuntimeError):
    """Failure during archive extraction (corrupt file, format mismatch, etc.)."""


def extract_archive(
    archive: Path, target_dir: Path, *, format: ArchiveFormat
) -> None:
    """Extract an archive into target_dir. Creates target_dir if missing."""
    target_dir.mkdir(parents=True, exist_ok=True)
    if format == "tar_gz":
        _extract_tar_gz(archive, target_dir)
    elif format == "dmg":
        _extract_dmg(archive, target_dir)
    elif format == "msi":
        _extract_msi(archive, target_dir)
    else:
        raise ExtractionError(f"unknown format: {format}")


def _extract_tar_gz(archive: Path, target_dir: Path) -> None:
    try:
        with tarfile.open(archive, "r:gz") as tf:
            for member in tf.getmembers():
                # Block path traversal: name must resolve inside target_dir
                resolved = (target_dir / member.name).resolve()
                if not str(resolved).startswith(str(target_dir.resolve())):
                    raise ExtractionError(f"path traversal blocked: {member.name}")
            tf.extractall(target_dir)  # noqa: S202
    except tarfile.TarError as exc:
        raise ExtractionError(f"tar.gz extraction failed: {exc}") from exc


def _extract_dmg(archive: Path, target_dir: Path) -> None:
    """Mount .dmg, copy LibreOffice.app into target_dir, unmount."""
    if sys.platform != "darwin":
        raise ExtractionError("dmg extraction requires macOS")
    mount_point = target_dir / ".dmg_mount"
    mount_point.mkdir(exist_ok=True)
    try:
        subprocess.run(
            [
                "hdiutil",
                "attach",
                "-nobrowse",
                "-mountpoint",
                str(mount_point),
                str(archive),
            ],
            check=True,
            capture_output=True,
            timeout=120,
        )
        app_src = mount_point / "LibreOffice.app"
        if not app_src.exists():
            raise ExtractionError("LibreOffice.app not found in dmg")
        shutil.copytree(app_src, target_dir / "LibreOffice.app", symlinks=True)
    except subprocess.CalledProcessError as exc:
        raise ExtractionError(
            f"hdiutil failed: {exc.stderr.decode(errors='replace')}"
        ) from exc
    finally:
        subprocess.run(
            ["hdiutil", "detach", str(mount_point)],
            capture_output=True,
            timeout=30,
        )
        shutil.rmtree(mount_point, ignore_errors=True)


def _extract_msi(archive: Path, target_dir: Path) -> None:
    """Use msiexec /a (administrative install) to extract MSI without installing."""
    if sys.platform != "win32":
        raise ExtractionError("msi extraction requires Windows")
    try:
        subprocess.run(
            [
                "msiexec",
                "/a",
                str(archive),
                "/qn",
                f"TARGETDIR={target_dir.resolve()}",
            ],
            check=True,
            capture_output=True,
            timeout=300,
        )
    except subprocess.CalledProcessError as exc:
        raise ExtractionError(
            f"msiexec failed: {exc.stderr.decode(errors='replace')}"
        ) from exc
