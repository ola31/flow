# LibreOffice Auto-Download Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable Flow to lazily download a portable LibreOffice runtime into the user data directory when neither PowerPoint nor system LibreOffice is available, so PPT conversion and external editing work without forcing system-level installs.

**Architecture:** New `src/flow/services/runtime/` package owns detection/download/extract/locate of an app-local LibreOffice. A pinned manifest (`src/flow/resources/libreoffice_manifest.json`) maps OS×arch → official TDF mirror URL + SHA256. UI flow: `engine_missing` signal → `PreflightDialog` → `DownloadProgressDialog` (QThread worker) → resume conversion. `slide_converter.create_slide_converter()` adds bundled-LO detection with priority `PowerPoint > bundled LO > system LO`. Edit button in song list falls back to bundled LO when `QDesktopServices.openUrl` fails.

**Tech Stack:** Python 3.10+, PySide6 (QThread, signals/slots), stdlib `urllib.request` (HTTP), `tarfile` / `subprocess` (extraction), `hashlib` (SHA256). No new third-party deps.

**Spec:** `docs/superpowers/specs/2026-04-27-libreoffice-auto-download-design.md`

---

## File Structure

**New files:**
```
src/flow/services/runtime/
├── __init__.py              # public exports
├── manifest.py              # JSON parsing + OS×arch matching
├── extractor.py             # tar.gz / dmg / msi extraction
└── libreoffice_runtime.py   # orchestrator (detect / download / verify / extract / locate)

src/flow/resources/
└── libreoffice_manifest.json

tests/runtime/
├── __init__.py
├── test_manifest.py
├── test_extractor.py
└── test_libreoffice_runtime.py
tests/ui/
└── test_engine_missing_flow.py
tests/services/
└── test_slide_converter_bundled.py
```

**Modified files:**
- `src/flow/services/slide_converter.py` — add `_detect_bundled_libreoffice()`, thread `bundled_lo_path` into platform converters, update `create_slide_converter()` priority
- `src/flow/services/slide_manager.py` — keep `engine_missing` semantics; cleanup of stale `.download/` at construction
- `src/flow/ui/dialogs.py` — add `PreflightDialog`, `DownloadProgressDialog`, `EngineDownloadErrorDialog`
- `src/flow/ui/main_window.py` — `_on_engine_missing` routes to PreflightDialog flow instead of direct install-guide
- `src/flow/ui/editor/song_list_widget.py` — edit button fallback to bundled LO when shell open fails
- `pyproject.toml` — add `src/flow/resources/libreoffice_manifest.json` to wheel package data (verify glob already covers)

**Boundaries:**
- `runtime/manifest.py` knows JSON shape only. Returns typed objects.
- `runtime/extractor.py` knows file formats only. Stateless functions.
- `runtime/libreoffice_runtime.py` owns the install lifecycle (paths, version compare, download orchestration). Single public class `LibreOfficeRuntime`.
- `slide_converter.py` consumes only `LibreOfficeRuntime.get_soffice_path()` — does not import manifest or extractor directly.
- UI dialogs do not import `urllib` or `tarfile` — they instantiate the worker which wraps `LibreOfficeRuntime`.

---

## Task 1: Manifest schema + parser

**Files:**
- Create: `src/flow/services/runtime/__init__.py`
- Create: `src/flow/services/runtime/manifest.py`
- Create: `src/flow/resources/libreoffice_manifest.json`
- Create: `tests/runtime/__init__.py`
- Create: `tests/runtime/test_manifest.py`

- [ ] **Step 1: Create empty package init files**

```python
# src/flow/services/runtime/__init__.py
"""LibreOffice portable runtime — download/extract/locate."""
from __future__ import annotations
```

```python
# tests/runtime/__init__.py
```

- [ ] **Step 2: Write failing tests for manifest parsing**

```python
# tests/runtime/test_manifest.py
from __future__ import annotations

import json
from pathlib import Path

import pytest

from flow.services.runtime.manifest import (
    BuildEntry,
    Manifest,
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


def test_detect_platform_key_rejects_unknown_arch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setattr("platform.machine", lambda: "riscv64")
    with pytest.raises(UnsupportedPlatformError):
        detect_platform_key()


def test_get_build_for_current_platform(sample_manifest: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setattr("platform.machine", lambda: "x86_64")
    m = load_manifest(sample_manifest)
    build = m.get_build_for_current_platform()
    assert build.format == "tar_gz"


def test_get_build_for_unsupported_platform(sample_manifest: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setattr("platform.machine", lambda: "aarch64")  # not in sample manifest
    m = load_manifest(sample_manifest)
    with pytest.raises(UnsupportedPlatformError):
        m.get_build_for_current_platform()
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `QT_QPA_PLATFORM=offscreen PYTHONNOUSERSITE=1 PYTHONPATH= pytest tests/runtime/test_manifest.py -v`
Expected: All FAIL with `ModuleNotFoundError` or similar.

- [ ] **Step 4: Implement `manifest.py`**

```python
# src/flow/services/runtime/manifest.py
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
    for field in ("version", "source_url", "license_url", "builds"):
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
```

- [ ] **Step 5: Create resource manifest skeleton**

```json
// src/flow/resources/libreoffice_manifest.json
{
  "version": "25.2.5.2",
  "source_url": "https://www.libreoffice.org/download/",
  "license_url": "https://www.libreoffice.org/about-us/licenses/",
  "builds": {
    "linux-x86_64": {
      "url": "https://download.documentfoundation.org/libreoffice/stable/25.2.5/deb/x86_64/LibreOffice_25.2.5.2_Linux_x86-64_deb.tar.gz",
      "sha256": "0000000000000000000000000000000000000000000000000000000000000000",
      "size_bytes": 290000000,
      "format": "tar_gz",
      "soffice_relpath": "LibreOffice_25.2.5.2_Linux_x86-64_deb/program/soffice"
    },
    "linux-aarch64": {
      "url": "https://download.documentfoundation.org/libreoffice/stable/25.2.5/deb/aarch64/LibreOffice_25.2.5.2_Linux_aarch64_deb.tar.gz",
      "sha256": "0000000000000000000000000000000000000000000000000000000000000000",
      "size_bytes": 280000000,
      "format": "tar_gz",
      "soffice_relpath": "LibreOffice_25.2.5.2_Linux_aarch64_deb/program/soffice"
    },
    "macos-x86_64": {
      "url": "https://download.documentfoundation.org/libreoffice/stable/25.2.5/mac/x86_64/LibreOffice_25.2.5.2_MacOS_x86-64.dmg",
      "sha256": "0000000000000000000000000000000000000000000000000000000000000000",
      "size_bytes": 310000000,
      "format": "dmg",
      "soffice_relpath": "LibreOffice.app/Contents/MacOS/soffice"
    },
    "macos-aarch64": {
      "url": "https://download.documentfoundation.org/libreoffice/stable/25.2.5/mac/aarch64/LibreOffice_25.2.5.2_MacOS_aarch64.dmg",
      "sha256": "0000000000000000000000000000000000000000000000000000000000000000",
      "size_bytes": 305000000,
      "format": "dmg",
      "soffice_relpath": "LibreOffice.app/Contents/MacOS/soffice"
    },
    "windows-x86_64": {
      "url": "https://download.documentfoundation.org/libreoffice/stable/25.2.5/win/x86_64/LibreOffice_25.2.5.2_Win_x86-64.msi",
      "sha256": "0000000000000000000000000000000000000000000000000000000000000000",
      "size_bytes": 360000000,
      "format": "msi",
      "soffice_relpath": "program/soffice.exe"
    },
    "windows-aarch64": {
      "url": "https://download.documentfoundation.org/libreoffice/stable/25.2.5/win/aarch64/LibreOffice_25.2.5.2_Win_aarch64.msi",
      "sha256": "0000000000000000000000000000000000000000000000000000000000000000",
      "size_bytes": 355000000,
      "format": "msi",
      "soffice_relpath": "program/soffice.exe"
    }
  }
}
```

> **Note:** SHA256 values are placeholders. Real values must be filled before release by downloading each artifact and computing `sha256sum`. See Task 21.

- [ ] **Step 6: Run tests to verify they pass**

Run: `QT_QPA_PLATFORM=offscreen PYTHONNOUSERSITE=1 PYTHONPATH= pytest tests/runtime/test_manifest.py -v`
Expected: All PASS.

- [ ] **Step 7: Commit**

```bash
git add src/flow/services/runtime/__init__.py src/flow/services/runtime/manifest.py \
  src/flow/resources/libreoffice_manifest.json tests/runtime/
git commit -m "feat(runtime): manifest schema + OS/arch matching"
```

---

## Task 2: Runtime paths + version detection

**Files:**
- Create: `src/flow/services/runtime/libreoffice_runtime.py`
- Create: `tests/runtime/test_libreoffice_runtime.py`

- [ ] **Step 1: Write failing tests for path/version helpers**

```python
# tests/runtime/test_libreoffice_runtime.py
from __future__ import annotations

import os
from pathlib import Path

import pytest

from flow.services.runtime.libreoffice_runtime import (
    LibreOfficeRuntime,
    get_runtime_dir,
)


def test_get_runtime_dir_linux(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert get_runtime_dir() == tmp_path / "Flow" / "runtime" / "libreoffice"


def test_get_runtime_dir_linux_default(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert get_runtime_dir() == tmp_path / ".local/share/Flow/runtime/libreoffice"


def test_get_runtime_dir_macos(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("sys.platform", "darwin")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert get_runtime_dir() == tmp_path / "Library/Application Support/Flow/runtime/libreoffice"


def test_get_runtime_dir_windows(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `QT_QPA_PLATFORM=offscreen PYTHONNOUSERSITE=1 PYTHONPATH= pytest tests/runtime/test_libreoffice_runtime.py -v`
Expected: All FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement paths + LibreOfficeRuntime skeleton**

```python
# src/flow/services/runtime/libreoffice_runtime.py
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `QT_QPA_PLATFORM=offscreen PYTHONNOUSERSITE=1 PYTHONPATH= pytest tests/runtime/test_libreoffice_runtime.py -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add src/flow/services/runtime/libreoffice_runtime.py tests/runtime/test_libreoffice_runtime.py
git commit -m "feat(runtime): runtime paths + installed-version detection"
```

---

## Task 3: Tar.gz extractor

**Files:**
- Create: `src/flow/services/runtime/extractor.py`
- Create: `tests/runtime/test_extractor.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/runtime/test_extractor.py
from __future__ import annotations

import tarfile
from pathlib import Path

import pytest

from flow.services.runtime.extractor import (
    ExtractionError,
    extract_archive,
)


def _make_tar_gz(tmp_path: Path, files: dict[str, str]) -> Path:
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    for name, content in files.items():
        f = src_dir / name
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(content, encoding="utf-8")

    archive = tmp_path / "test.tar.gz"
    with tarfile.open(archive, "w:gz") as tf:
        for name in files:
            tf.add(src_dir / name, arcname=name)
    return archive


def test_extract_tar_gz(tmp_path: Path) -> None:
    archive = _make_tar_gz(tmp_path, {
        "myproj/program/soffice": "#!/bin/sh\n",
        "myproj/README": "hello",
    })
    target = tmp_path / "out"
    extract_archive(archive, target, format="tar_gz")
    assert (target / "myproj/program/soffice").exists()
    assert (target / "myproj/README").read_text() == "hello"


def test_extract_corrupted_tar_gz_raises(tmp_path: Path) -> None:
    bad = tmp_path / "bad.tar.gz"
    bad.write_bytes(b"not a real archive")
    with pytest.raises(ExtractionError):
        extract_archive(bad, tmp_path / "out", format="tar_gz")


def test_extract_unknown_format_raises(tmp_path: Path) -> None:
    f = tmp_path / "f.zip"
    f.write_bytes(b"")
    with pytest.raises(ExtractionError, match="format"):
        extract_archive(f, tmp_path / "out", format="zip")  # type: ignore[arg-type]


def test_extract_blocks_path_traversal(tmp_path: Path) -> None:
    """Tarballs with .. paths must be rejected."""
    archive = tmp_path / "evil.tar.gz"
    payload = tmp_path / "payload"
    payload.write_text("evil", encoding="utf-8")
    with tarfile.open(archive, "w:gz") as tf:
        tf.add(payload, arcname="../escaped")
    with pytest.raises(ExtractionError, match="traversal"):
        extract_archive(archive, tmp_path / "out", format="tar_gz")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `QT_QPA_PLATFORM=offscreen PYTHONNOUSERSITE=1 PYTHONPATH= pytest tests/runtime/test_extractor.py -v`
Expected: All FAIL.

- [ ] **Step 3: Implement extractor**

```python
# src/flow/services/runtime/extractor.py
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


def extract_archive(archive: Path, target_dir: Path, *, format: ArchiveFormat) -> None:
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
            tf.extractall(target_dir)
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
            ["hdiutil", "attach", "-nobrowse", "-mountpoint", str(mount_point), str(archive)],
            check=True, capture_output=True, timeout=120,
        )
        app_src = mount_point / "LibreOffice.app"
        if not app_src.exists():
            raise ExtractionError("LibreOffice.app not found in dmg")
        shutil.copytree(app_src, target_dir / "LibreOffice.app", symlinks=True)
    except subprocess.CalledProcessError as exc:
        raise ExtractionError(f"hdiutil failed: {exc.stderr.decode(errors='replace')}") from exc
    finally:
        subprocess.run(
            ["hdiutil", "detach", str(mount_point)], capture_output=True, timeout=30,
        )
        shutil.rmtree(mount_point, ignore_errors=True)


def _extract_msi(archive: Path, target_dir: Path) -> None:
    """Use msiexec /a (administrative install) to extract MSI contents without installing."""
    if sys.platform != "win32":
        raise ExtractionError("msi extraction requires Windows")
    try:
        subprocess.run(
            ["msiexec", "/a", str(archive), "/qn", f"TARGETDIR={target_dir.resolve()}"],
            check=True, capture_output=True, timeout=300,
        )
    except subprocess.CalledProcessError as exc:
        raise ExtractionError(f"msiexec failed: {exc.stderr.decode(errors='replace')}") from exc
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `QT_QPA_PLATFORM=offscreen PYTHONNOUSERSITE=1 PYTHONPATH= pytest tests/runtime/test_extractor.py -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add src/flow/services/runtime/extractor.py tests/runtime/test_extractor.py
git commit -m "feat(runtime): tar.gz extractor with path-traversal guard"
```

---

## Task 4: HTTP downloader with progress + cancellation

**Files:**
- Modify: `src/flow/services/runtime/libreoffice_runtime.py`
- Modify: `tests/runtime/test_libreoffice_runtime.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/runtime/test_libreoffice_runtime.py`:

```python
import threading
from unittest.mock import patch, MagicMock

from flow.services.runtime.libreoffice_runtime import (
    DownloadCancelled,
    download_with_progress,
)


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
            url="https://example/x", dest=target,
            chunk_size=1000, on_progress=on_progress,
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
                url="https://example/x", dest=target,
                chunk_size=1000, on_progress=on_progress,
                cancel_event=cancel,
            )
    # Partial file should be cleaned up
    assert not target.exists()


def test_download_rejects_non_https() -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        download_with_progress(
            url="http://example/x", dest=Path("/tmp/x"),
            chunk_size=1000, on_progress=lambda r, t: None,
            cancel_event=threading.Event(),
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `QT_QPA_PLATFORM=offscreen PYTHONNOUSERSITE=1 PYTHONPATH= pytest tests/runtime/test_libreoffice_runtime.py::test_download_writes_file_and_reports_progress -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Add downloader to libreoffice_runtime.py**

Append to `src/flow/services/runtime/libreoffice_runtime.py`:

```python
import threading
import urllib.request
from typing import Callable

ProgressCallback = Callable[[int, int], None]


class DownloadCancelled(RuntimeError):
    """Download was cancelled via the cancel_event."""


def download_with_progress(
    *,
    url: str,
    dest: Path,
    chunk_size: int,
    on_progress: ProgressCallback,
    cancel_event: threading.Event,
) -> None:
    """Stream URL → dest, calling on_progress(received, total) each chunk.
    
    Raises DownloadCancelled if cancel_event is set; partial file deleted."""
    if not url.startswith("https://"):
        raise ValueError("Only HTTPS URLs allowed")
    dest.parent.mkdir(parents=True, exist_ok=True)
    response = urllib.request.urlopen(url)  # noqa: S310
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `QT_QPA_PLATFORM=offscreen PYTHONNOUSERSITE=1 PYTHONPATH= pytest tests/runtime/test_libreoffice_runtime.py -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add src/flow/services/runtime/libreoffice_runtime.py tests/runtime/test_libreoffice_runtime.py
git commit -m "feat(runtime): HTTPS streaming download with progress + cancellation"
```

---

## Task 5: SHA256 verification

**Files:**
- Modify: `src/flow/services/runtime/libreoffice_runtime.py`
- Modify: `tests/runtime/test_libreoffice_runtime.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/runtime/test_libreoffice_runtime.py`:

```python
import hashlib

from flow.services.runtime.libreoffice_runtime import (
    Sha256MismatchError,
    verify_sha256,
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `QT_QPA_PLATFORM=offscreen PYTHONNOUSERSITE=1 PYTHONPATH= pytest tests/runtime/test_libreoffice_runtime.py::test_verify_sha256_matching -v`
Expected: FAIL.

- [ ] **Step 3: Implement verify_sha256**

Append to `src/flow/services/runtime/libreoffice_runtime.py`:

```python
import hashlib


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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `QT_QPA_PLATFORM=offscreen PYTHONNOUSERSITE=1 PYTHONPATH= pytest tests/runtime/test_libreoffice_runtime.py -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add src/flow/services/runtime/libreoffice_runtime.py tests/runtime/test_libreoffice_runtime.py
git commit -m "feat(runtime): SHA256 verification"
```

---

## Task 6: Install orchestration (download + verify + extract + finalize)

**Files:**
- Modify: `src/flow/services/runtime/libreoffice_runtime.py`
- Modify: `tests/runtime/test_libreoffice_runtime.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/runtime/test_libreoffice_runtime.py`:

```python
from unittest.mock import patch, MagicMock

from flow.services.runtime.manifest import BuildEntry


def _make_build(tmp_path: Path, content: bytes, soffice_relpath: str) -> BuildEntry:
    return BuildEntry(
        url="https://example/lo.tar.gz",
        sha256=hashlib.sha256(content).hexdigest(),
        size_bytes=len(content),
        format="tar_gz",
        soffice_relpath=soffice_relpath,
    )


def test_install_full_flow(tmp_path: Path) -> None:
    """Happy path: download → verify → extract → INSTALLED_VERSION written."""
    # Build a real tar.gz to "download"
    src = tmp_path / "src"
    src.mkdir()
    soffice = src / "myproj" / "program" / "soffice"
    soffice.parent.mkdir(parents=True)
    soffice.write_text("#!/bin/sh", encoding="utf-8")
    archive_bytes_path = tmp_path / "archive.tar.gz"
    with tarfile.open(archive_bytes_path, "w:gz") as tf:
        tf.add(src / "myproj", arcname="myproj")
    archive_bytes = archive_bytes_path.read_bytes()

    build = _make_build(tmp_path, archive_bytes, "myproj/program/soffice")
    runtime_dir = tmp_path / "rt"

    progress_log: list[tuple[str, int, int]] = []

    def progress(phase: str, pct: int, msg: str) -> None:
        progress_log.append((phase, pct, msg))

    rt = LibreOfficeRuntime(
        runtime_dir=runtime_dir,
        manifest_version="9.9.9",
        soffice_relpath="myproj/program/soffice",
    )

    response = MagicMock()
    response.headers = {"Content-Length": str(len(archive_bytes))}
    chunks = [archive_bytes[i:i + 1024] for i in range(0, len(archive_bytes), 1024)]
    response.read = MagicMock(side_effect=chunks + [b""])

    with patch("urllib.request.urlopen", return_value=response):
        rt.install(build, on_progress=progress, cancel_event=threading.Event())

    assert (runtime_dir / "INSTALLED_VERSION").read_text() == "9.9.9"
    assert (runtime_dir / "9.9.9" / "myproj" / "program" / "soffice").exists()
    assert rt.is_current()
    assert rt.get_soffice_path() is not None
    # phases observed
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

    build = _make_build(tmp_path, archive_bytes, "f")
    runtime_dir = tmp_path / "rt"
    cancel = threading.Event()

    response = MagicMock()
    response.headers = {"Content-Length": str(len(archive_bytes))}
    chunks = [archive_bytes[i:i + 100] for i in range(0, len(archive_bytes), 100)]
    response.read = MagicMock(side_effect=chunks + [b""])

    def progress(phase: str, pct: int, msg: str) -> None:
        if phase == "download" and pct >= 50:
            cancel.set()

    rt = LibreOfficeRuntime(
        runtime_dir=runtime_dir, manifest_version="1.0",
        soffice_relpath="f",
    )
    with patch("urllib.request.urlopen", return_value=response):
        with pytest.raises(DownloadCancelled):
            rt.install(build, on_progress=progress, cancel_event=cancel)

    # Partial download dir cleaned, INSTALLED_VERSION NOT written
    assert not (runtime_dir / "INSTALLED_VERSION").exists()
    assert not (runtime_dir / ".download").exists() or not any((runtime_dir / ".download").iterdir())


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
        runtime_dir=runtime_dir, manifest_version="1.0", soffice_relpath="f",
    )
    response = MagicMock()
    response.headers = {"Content-Length": "5"}
    response.read = MagicMock(side_effect=[b"abcde", b""])

    with patch("urllib.request.urlopen", return_value=response):
        with pytest.raises(Sha256MismatchError):
            rt.install(bad_build, on_progress=lambda *a: None, cancel_event=threading.Event())

    assert not (runtime_dir / "INSTALLED_VERSION").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `QT_QPA_PLATFORM=offscreen PYTHONNOUSERSITE=1 PYTHONPATH= pytest tests/runtime/test_libreoffice_runtime.py::test_install_full_flow -v`
Expected: FAIL — `LibreOfficeRuntime.install` doesn't exist.

- [ ] **Step 3: Implement install()**

This step **replaces** the `LibreOfficeRuntime` class added in Task 2 with an expanded version that includes the install lifecycle. Add the new top-level imports/types (if not already present), then replace the entire class body.

Add at top of `src/flow/services/runtime/libreoffice_runtime.py` (consolidate with existing imports):

```python
import os
import shutil
from typing import Callable

from flow.services.runtime.extractor import extract_archive
from flow.services.runtime.manifest import BuildEntry

PhaseProgressCallback = Callable[[str, int, str], None]
"""(phase, percent_0_100, human_message)"""
```

Then replace the existing `class LibreOfficeRuntime:` block (everything from `class LibreOfficeRuntime:` down to the end of `get_soffice_path`) with:

```python
class LibreOfficeRuntime:
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
        """Remove any leftover .download/ from interrupted runs. Safe to call at startup."""
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
            on_progress("download", pct, f"{received // (1 << 20)} / {total // (1 << 20)} MB")

        try:
            download_with_progress(
                url=build.url, dest=archive, chunk_size=1 << 16,
                on_progress=_dl_progress, cancel_event=cancel_event,
            )

            # Phase 2: verify
            on_progress("verify", 87, "무결성 검증 중...")
            verify_sha256(archive, build.sha256)

            # Phase 3: extract into a temp version dir, then atomic rename
            on_progress("extract", 90, "압축 해제 중...")
            staging = download_dir / "staging"
            if staging.exists():
                shutil.rmtree(staging)
            extract_archive(archive, staging, format=build.format)

            final_version_dir = self._dir / self._manifest_version
            if final_version_dir.exists():
                shutil.rmtree(final_version_dir)
            staging.rename(final_version_dir)

            # Phase 4: atomic INSTALLED_VERSION write (write to temp, rename)
            on_progress("finalize", 99, "마무리 중...")
            tmp = self._dir / (self.INSTALLED_VERSION_FILE + ".tmp")
            tmp.write_text(self._manifest_version, encoding="utf-8")
            os.replace(tmp, self._dir / self.INSTALLED_VERSION_FILE)

            on_progress("done", 100, "완료")
        finally:
            shutil.rmtree(download_dir, ignore_errors=True)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `QT_QPA_PLATFORM=offscreen PYTHONNOUSERSITE=1 PYTHONPATH= pytest tests/runtime/test_libreoffice_runtime.py -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add src/flow/services/runtime/libreoffice_runtime.py tests/runtime/test_libreoffice_runtime.py
git commit -m "feat(runtime): install orchestration with atomic finalize"
```

---

## Task 7: Bundled LO detection in slide_converter

**Files:**
- Modify: `src/flow/services/slide_converter.py`
- Create: `tests/services/test_slide_converter_bundled.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/services/test_slide_converter_bundled.py
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from flow.services.slide_converter import (
    _detect_bundled_libreoffice,
    create_slide_converter,
    NoConverterAvailableError,
)


def test_detect_bundled_returns_path_when_runtime_current(tmp_path: Path) -> None:
    runtime_dir = tmp_path / "Flow/runtime/libreoffice"
    runtime_dir.mkdir(parents=True)
    (runtime_dir / "INSTALLED_VERSION").write_text("25.2.5.2", encoding="utf-8")
    soffice = runtime_dir / "25.2.5.2" / "program" / "soffice"
    soffice.parent.mkdir(parents=True)
    soffice.write_text("#!/bin/sh", encoding="utf-8")

    with patch("flow.services.slide_converter.get_runtime_dir", return_value=runtime_dir), \
         patch("flow.services.slide_converter.get_manifest_for_resources",
               return_value=_FakeManifest(version="25.2.5.2", soffice_relpath="program/soffice")):
        result = _detect_bundled_libreoffice()
        assert result == soffice


def test_detect_bundled_returns_none_when_not_installed(tmp_path: Path) -> None:
    with patch("flow.services.slide_converter.get_runtime_dir", return_value=tmp_path), \
         patch("flow.services.slide_converter.get_manifest_for_resources",
               return_value=_FakeManifest(version="25.2.5.2", soffice_relpath="program/soffice")):
        assert _detect_bundled_libreoffice() is None


def test_create_slide_converter_uses_bundled_when_no_system_engine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sys.platform", "linux")
    bundled = tmp_path / "soffice"
    bundled.write_text("#!/bin/sh", encoding="utf-8")

    with patch("flow.services.slide_converter._detect_powerpoint", return_value=False), \
         patch("flow.services.slide_converter._detect_libreoffice", return_value=None), \
         patch("flow.services.slide_converter._detect_bundled_libreoffice", return_value=bundled):
        conv = create_slide_converter()
        assert conv is not None  # bundled LO satisfied the priority check


def test_create_slide_converter_raises_when_nothing_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.platform", "linux")
    with patch("flow.services.slide_converter._detect_powerpoint", return_value=False), \
         patch("flow.services.slide_converter._detect_libreoffice", return_value=None), \
         patch("flow.services.slide_converter._detect_bundled_libreoffice", return_value=None), \
         patch("flow.services.slide_converter._find_bundled_onlyoffice", return_value=None):
        with pytest.raises(NoConverterAvailableError):
            create_slide_converter()


class _FakeManifest:
    def __init__(self, version: str, soffice_relpath: str) -> None:
        self.version = version
        self._sr = soffice_relpath

    def get_build_for_current_platform(self) -> object:
        from flow.services.runtime.manifest import BuildEntry
        return BuildEntry(
            url="https://example/x", sha256="a" * 64, size_bytes=1,
            format="tar_gz", soffice_relpath=self._sr,
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `QT_QPA_PLATFORM=offscreen PYTHONNOUSERSITE=1 PYTHONPATH= pytest tests/services/test_slide_converter_bundled.py -v`
Expected: FAIL — `_detect_bundled_libreoffice` and `get_manifest_for_resources` don't exist.

- [ ] **Step 3: Add manifest loader helper**

Append to `src/flow/services/runtime/__init__.py`:

```python
from pathlib import Path

from flow.services.runtime.libreoffice_runtime import (
    DownloadCancelled,
    LibreOfficeRuntime,
    Sha256MismatchError,
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
    resource_path = Path(__file__).parent.parent.parent / "resources" / "libreoffice_manifest.json"
    return load_manifest(resource_path)


__all__ = [
    "BuildEntry",
    "DownloadCancelled",
    "LibreOfficeRuntime",
    "Manifest",
    "Sha256MismatchError",
    "UnsupportedPlatformError",
    "detect_platform_key",
    "download_with_progress",
    "get_manifest_for_resources",
    "get_runtime_dir",
    "load_manifest",
    "verify_sha256",
]
```

- [ ] **Step 4: Add `_detect_bundled_libreoffice` to slide_converter.py**

Insert near `_detect_libreoffice()`:

```python
# add to slide_converter.py imports
from flow.services.runtime import (
    LibreOfficeRuntime,
    UnsupportedPlatformError,
    get_manifest_for_resources,
    get_runtime_dir,
)


def _detect_bundled_libreoffice() -> Path | None:
    """Return path to Flow's app-local LibreOffice if installed and current."""
    try:
        manifest = get_manifest_for_resources()
        build = manifest.get_build_for_current_platform()
    except (UnsupportedPlatformError, ValueError, FileNotFoundError):
        return None
    runtime = LibreOfficeRuntime(
        runtime_dir=get_runtime_dir(),
        manifest_version=manifest.version,
        soffice_relpath=build.soffice_relpath,
    )
    return runtime.get_soffice_path()
```

Update `create_slide_converter()` to consult bundled LO:

```python
def create_slide_converter() -> SlideConverter:
    has_pp = _detect_powerpoint()
    has_system_lo = _detect_libreoffice() is not None
    has_bundled_lo = _detect_bundled_libreoffice() is not None
    bundled = _find_bundled_onlyoffice()

    if sys.platform == "win32":
        if has_pp or has_bundled_lo or has_system_lo:
            return WindowsSlideConverter()
        if bundled is not None:
            return OnlyOfficeSlideConverter(bundled)
    elif sys.platform == "darwin":
        if has_pp or has_bundled_lo or has_system_lo:
            return MacOSSlideConverter()
        if bundled is not None:
            return OnlyOfficeSlideConverter(bundled)
    else:
        if has_bundled_lo or has_system_lo:
            return LinuxSlideConverter()
        if bundled is not None:
            return OnlyOfficeSlideConverter(bundled)

    raise NoConverterAvailableError(sys.platform)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `QT_QPA_PLATFORM=offscreen PYTHONNOUSERSITE=1 PYTHONPATH= pytest tests/services/test_slide_converter_bundled.py -v`
Expected: All PASS.

- [ ] **Step 6: Verify no regressions in existing tests**

Run: `QT_QPA_PLATFORM=offscreen PYTHONNOUSERSITE=1 PYTHONPATH= pytest tests/services/ -v`
Expected: PASS (or maintains existing 239/2 baseline).

- [ ] **Step 7: Commit**

```bash
git add src/flow/services/slide_converter.py src/flow/services/runtime/__init__.py \
  tests/services/test_slide_converter_bundled.py
git commit -m "feat(slide_converter): detect and prefer bundled LibreOffice runtime"
```

---

## Task 8: Wire bundled LO path through platform converters

**Files:**
- Modify: `src/flow/services/slide_converter.py`

`_find_libreoffice()` inside each platform converter must consult bundled-LO first.

- [ ] **Step 1: Update `WindowsSlideConverter._find_libreoffice`**

```python
def _find_libreoffice(self) -> str | None:
    bundled = _detect_bundled_libreoffice()
    if bundled is not None:
        return str(bundled)
    common_paths = [
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    ]
    for path in common_paths:
        if Path(path).exists():
            return path
    return shutil.which("soffice")
```

- [ ] **Step 2: Update `MacOSSlideConverter._find_libreoffice`**

```python
def _find_libreoffice(self) -> str | None:
    if self._soffice_path is not None:
        return self._soffice_path or None
    bundled = _detect_bundled_libreoffice()
    if bundled is not None:
        self._soffice_path = str(bundled)
        return self._soffice_path
    candidates = [
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
        str(Path.home() / "Applications/LibreOffice.app/Contents/MacOS/soffice"),
    ]
    for c in candidates:
        if Path(c).exists():
            self._soffice_path = c
            return c
    from_path = shutil.which("soffice") or shutil.which("libreoffice")
    self._soffice_path = from_path or ""
    return from_path
```

- [ ] **Step 3: Update `LinuxSlideConverter` to use bundled when present**

Replace `convert_slide` body:

```python
def convert_slide(
    self, pptx_path: Path, index: int, status_callback=None
) -> QImage:
    bundled = _detect_bundled_libreoffice()
    soffice_cmd = str(bundled) if bundled is not None else "libreoffice"
    return _convert_with_libreoffice(
        pptx_path, index, self._cache_dir, soffice_cmd,
        status_callback=status_callback,
    )
```

- [ ] **Step 4: Run all tests**

Run: `QT_QPA_PLATFORM=offscreen PYTHONNOUSERSITE=1 PYTHONPATH= pytest -v`
Expected: existing baseline maintained.

- [ ] **Step 5: Commit**

```bash
git add src/flow/services/slide_converter.py
git commit -m "feat(slide_converter): route platform converters through bundled LO when available"
```

---

## Task 9: PreflightDialog (download / install-guide / cancel)

**Files:**
- Modify: `src/flow/ui/dialogs.py`
- Create: `tests/ui/test_engine_missing_flow.py`

- [ ] **Step 1: Write failing test**

```python
# tests/ui/test_engine_missing_flow.py
from __future__ import annotations

from unittest.mock import patch

import pytest

from flow.ui.dialogs import (
    PreflightChoice,
    flow_show_engine_preflight,
)


def test_preflight_returns_download(qapp_args) -> None:
    """In test mode the dialog auto-accepts; verify enum is exposed."""
    # Verify enum has expected members (used by callers)
    assert PreflightChoice.DOWNLOAD.value == "download"
    assert PreflightChoice.INSTALL_GUIDE.value == "install_guide"
    assert PreflightChoice.CANCEL.value == "cancel"


def test_preflight_callable(qapp_args) -> None:
    """Smoke test that the function exists and can be called (auto-accepts under PYTEST)."""
    # Will return DOWNLOAD via the test auto-accept path
    import os
    os.environ["PYTEST_CURRENT_TEST"] = "test_preflight_callable"
    try:
        result = flow_show_engine_preflight(parent=None, manifest_version="25.2.5.2", size_mb=290)
        assert result in (PreflightChoice.DOWNLOAD, PreflightChoice.INSTALL_GUIDE, PreflightChoice.CANCEL)
    finally:
        os.environ.pop("PYTEST_CURRENT_TEST", None)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen PYTHONNOUSERSITE=1 PYTHONPATH= pytest tests/ui/test_engine_missing_flow.py -v`
Expected: FAIL (`PreflightChoice` not defined).

- [ ] **Step 3: Add PreflightDialog to dialogs.py**

Look up the existing `_FlowDialog` base + `flow_show_install_guide` location in `src/flow/ui/dialogs.py` to mirror the pattern. Then append:

```python
# src/flow/ui/dialogs.py — append near other public flow_show_* helpers
from enum import Enum


class PreflightChoice(Enum):
    DOWNLOAD = "download"
    INSTALL_GUIDE = "install_guide"
    CANCEL = "cancel"


def flow_show_engine_preflight(
    parent,
    *,
    manifest_version: str,
    size_mb: int,
) -> PreflightChoice:
    """Modal: ask user how to obtain LibreOffice. Returns one of PreflightChoice."""
    import os
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return PreflightChoice.DOWNLOAD  # auto-accept in tests

    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QDesktopServices
    from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout

    dlg = _FlowDialog(parent)
    dlg.setWindowTitle("PPT 변환 엔진 필요")
    layout = QVBoxLayout(dlg.body)

    title = QLabel(f"PPT 슬라이드를 열려면 LibreOffice {manifest_version}이 필요해요")
    title.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: {FONT_HEAD}px; font-weight: {FW_SEMI};")
    layout.addWidget(title)

    body = QLabel(
        f"Flow가 자동으로 다운로드해서 앱 폴더 안에 보관할 수 있어요 (~{size_mb}MB).\n"
        "시스템에는 설치되지 않아요."
    )
    body.setWordWrap(True)
    body.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: {FONT_MD}px;")
    layout.addWidget(body)

    license_note = QLabel(
        "LibreOffice는 The Document Foundation의 자유 소프트웨어 (MPL 2.0)입니다."
    )
    license_note.setStyleSheet(f"color: {TEXT_TERTIARY}; font-size: {FONT_XS}px;")
    license_note.setWordWrap(True)
    layout.addWidget(license_note)

    btn_row = QHBoxLayout()
    btn_license = QPushButton("라이선스 보기")
    btn_license.clicked.connect(
        lambda: QDesktopServices.openUrl(QUrl("https://www.libreoffice.org/about-us/licenses/"))
    )
    btn_row.addWidget(btn_license)
    btn_row.addStretch()
    btn_cancel = QPushButton("취소")
    btn_install = QPushButton("수동 설치 안내")
    btn_download = QPushButton("지금 다운로드")
    btn_download.setDefault(True)
    btn_row.addWidget(btn_cancel)
    btn_row.addWidget(btn_install)
    btn_row.addWidget(btn_download)
    layout.addLayout(btn_row)

    choice = {"value": PreflightChoice.CANCEL}
    btn_cancel.clicked.connect(lambda: (choice.update(value=PreflightChoice.CANCEL), dlg.accept()))
    btn_install.clicked.connect(lambda: (choice.update(value=PreflightChoice.INSTALL_GUIDE), dlg.accept()))
    btn_download.clicked.connect(lambda: (choice.update(value=PreflightChoice.DOWNLOAD), dlg.accept()))

    dlg.exec()
    return choice["value"]
```

> **Note:** `TEXT_PRIMARY/SECONDARY/TERTIARY`, `FONT_*`, `FW_SEMI` come from `flow.ui.styles` — check existing imports in `dialogs.py` and add any missing.

- [ ] **Step 4: Run tests to verify they pass**

Run: `QT_QPA_PLATFORM=offscreen PYTHONNOUSERSITE=1 PYTHONPATH= pytest tests/ui/test_engine_missing_flow.py -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add src/flow/ui/dialogs.py tests/ui/test_engine_missing_flow.py
git commit -m "feat(dialogs): PreflightDialog for engine download choice"
```

---

## Task 10: DownloadProgressDialog with QThread worker

**Files:**
- Modify: `src/flow/ui/dialogs.py`
- Modify: `tests/ui/test_engine_missing_flow.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/ui/test_engine_missing_flow.py`:

```python
import threading
import time
from pathlib import Path

from PySide6.QtCore import QCoreApplication

from flow.ui.dialogs import EngineDownloadWorker


def test_download_worker_emits_progress_and_finished(qapp_args, qtbot, tmp_path: Path) -> None:
    """Worker exposes progress/finished signals; cancel via flag."""

    def fake_install(*, on_progress, cancel_event):
        on_progress("download", 50, "halfway")
        on_progress("done", 100, "complete")

    worker = EngineDownloadWorker(install_fn=fake_install)
    progress_log: list[tuple[str, int, str]] = []
    finished_log: list[tuple[bool, str]] = []
    worker.progress.connect(lambda p, pct, m: progress_log.append((p, pct, m)))
    worker.finished_with_status.connect(lambda ok, err: finished_log.append((ok, err)))

    worker.start()
    worker.wait(2000)

    assert ("download", 50, "halfway") in progress_log
    assert finished_log == [(True, "")]


def test_download_worker_reports_failure(qapp_args, qtbot) -> None:
    def fake_install(*, on_progress, cancel_event):
        raise RuntimeError("network down")

    worker = EngineDownloadWorker(install_fn=fake_install)
    finished_log: list[tuple[bool, str]] = []
    worker.finished_with_status.connect(lambda ok, err: finished_log.append((ok, err)))
    worker.start()
    worker.wait(2000)
    assert finished_log == [(False, "network down")]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `QT_QPA_PLATFORM=offscreen PYTHONNOUSERSITE=1 PYTHONPATH= pytest tests/ui/test_engine_missing_flow.py::test_download_worker_emits_progress_and_finished -v`
Expected: FAIL.

- [ ] **Step 3: Add EngineDownloadWorker + DownloadProgressDialog**

Append to `src/flow/ui/dialogs.py`:

```python
import threading
from typing import Callable

from PySide6.QtCore import QThread, Signal


class EngineDownloadWorker(QThread):
    """Run LibreOfficeRuntime.install() on a background thread."""

    progress = Signal(str, int, str)              # (phase, percent, message)
    finished_with_status = Signal(bool, str)      # (success, error_message)

    def __init__(
        self,
        install_fn: Callable[..., None],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._install_fn = install_fn
        self._cancel = threading.Event()

    def cancel(self) -> None:
        self._cancel.set()

    def run(self) -> None:
        def _on_progress(phase: str, pct: int, msg: str) -> None:
            self.progress.emit(phase, pct, msg)

        try:
            self._install_fn(on_progress=_on_progress, cancel_event=self._cancel)
            self.finished_with_status.emit(True, "")
        except Exception as exc:
            self.finished_with_status.emit(False, str(exc))


def flow_run_engine_download(
    parent,
    *,
    install_fn: Callable[..., None],
) -> tuple[bool, str]:
    """Modal progress dialog. Returns (success, error_msg)."""
    import os
    if os.environ.get("PYTEST_CURRENT_TEST"):
        try:
            install_fn(on_progress=lambda *a: None, cancel_event=threading.Event())
            return True, ""
        except Exception as exc:
            return False, str(exc)

    from PySide6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout

    dlg = _FlowDialog(parent)
    dlg.setWindowTitle("LibreOffice 다운로드 중")
    layout = QVBoxLayout(dlg.body)

    title = QLabel("PPT 변환 엔진을 받아오는 중...")
    title.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: {FONT_HEAD}px; font-weight: {FW_SEMI};")
    layout.addWidget(title)

    msg = QLabel("준비 중...")
    msg.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: {FONT_MD}px;")
    layout.addWidget(msg)

    bar = QProgressBar()
    bar.setRange(0, 100)
    layout.addWidget(bar)

    btn_row = QHBoxLayout()
    btn_row.addStretch()
    btn_cancel = QPushButton("취소")
    btn_row.addWidget(btn_cancel)
    layout.addLayout(btn_row)

    worker = EngineDownloadWorker(install_fn=install_fn, parent=dlg)
    result = {"ok": False, "err": "cancelled"}

    def on_progress(phase: str, pct: int, msg_text: str) -> None:
        bar.setValue(pct)
        msg.setText(msg_text)

    def on_finished(ok: bool, err: str) -> None:
        result["ok"] = ok
        result["err"] = err
        dlg.accept()

    worker.progress.connect(on_progress)
    worker.finished_with_status.connect(on_finished)
    btn_cancel.clicked.connect(worker.cancel)

    worker.start()
    dlg.exec()
    worker.wait(5000)
    return result["ok"], result["err"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `QT_QPA_PLATFORM=offscreen PYTHONNOUSERSITE=1 PYTHONPATH= pytest tests/ui/test_engine_missing_flow.py -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add src/flow/ui/dialogs.py tests/ui/test_engine_missing_flow.py
git commit -m "feat(dialogs): DownloadProgressDialog + EngineDownloadWorker"
```

---

## Task 11: ErrorDialog (retry / install-guide / close)

**Files:**
- Modify: `src/flow/ui/dialogs.py`
- Modify: `tests/ui/test_engine_missing_flow.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/ui/test_engine_missing_flow.py`:

```python
from flow.ui.dialogs import EngineErrorChoice


def test_engine_error_choice_enum() -> None:
    assert EngineErrorChoice.RETRY.value == "retry"
    assert EngineErrorChoice.INSTALL_GUIDE.value == "install_guide"
    assert EngineErrorChoice.CLOSE.value == "close"
```

- [ ] **Step 2: Run to verify failure**

Run: `QT_QPA_PLATFORM=offscreen PYTHONNOUSERSITE=1 PYTHONPATH= pytest tests/ui/test_engine_missing_flow.py::test_engine_error_choice_enum -v`
Expected: FAIL.

- [ ] **Step 3: Implement EngineErrorChoice + dialog**

Append to `src/flow/ui/dialogs.py`:

```python
class EngineErrorChoice(Enum):
    RETRY = "retry"
    INSTALL_GUIDE = "install_guide"
    CLOSE = "close"


def flow_show_engine_error(parent, *, error_message: str) -> EngineErrorChoice:
    """Modal: show download error and offer retry / manual install / close."""
    import os
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return EngineErrorChoice.CLOSE

    from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout

    dlg = _FlowDialog(parent)
    dlg.setWindowTitle("다운로드 실패")
    layout = QVBoxLayout(dlg.body)

    title = QLabel("LibreOffice 다운로드에 실패했어요")
    title.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: {FONT_HEAD}px; font-weight: {FW_SEMI};")
    layout.addWidget(title)

    detail = QLabel(error_message or "알 수 없는 오류")
    detail.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: {FONT_SM}px;")
    detail.setWordWrap(True)
    layout.addWidget(detail)

    btn_row = QHBoxLayout()
    btn_row.addStretch()
    btn_close = QPushButton("닫기")
    btn_install = QPushButton("수동 설치 안내")
    btn_retry = QPushButton("재시도")
    btn_retry.setDefault(True)
    btn_row.addWidget(btn_close)
    btn_row.addWidget(btn_install)
    btn_row.addWidget(btn_retry)
    layout.addLayout(btn_row)

    choice = {"value": EngineErrorChoice.CLOSE}
    btn_close.clicked.connect(lambda: (choice.update(value=EngineErrorChoice.CLOSE), dlg.accept()))
    btn_install.clicked.connect(lambda: (choice.update(value=EngineErrorChoice.INSTALL_GUIDE), dlg.accept()))
    btn_retry.clicked.connect(lambda: (choice.update(value=EngineErrorChoice.RETRY), dlg.accept()))

    dlg.exec()
    return choice["value"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `QT_QPA_PLATFORM=offscreen PYTHONNOUSERSITE=1 PYTHONPATH= pytest tests/ui/test_engine_missing_flow.py -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add src/flow/ui/dialogs.py tests/ui/test_engine_missing_flow.py
git commit -m "feat(dialogs): EngineErrorChoice + retry/install-guide/close dialog"
```

---

## Task 12: Wire MainWindow engine_missing → new flow

**Files:**
- Modify: `src/flow/ui/main_window.py`
- Modify: `src/flow/services/slide_manager.py`
- Modify: `tests/ui/test_engine_missing_flow.py`

The existing `_on_engine_missing` in `main_window.py` shows the install-guide directly. Replace with: PreflightDialog → if DOWNLOAD then run worker → if SUCCESS then re-create slide_manager engine; if FAILURE then ErrorDialog (retry loop).

- [ ] **Step 1: Write failing integration test**

Append to `tests/ui/test_engine_missing_flow.py`:

```python
from unittest.mock import patch, MagicMock


def test_main_window_routes_engine_missing_through_preflight(qapp_args, qtbot, tmp_path) -> None:
    """When engine_missing fires, MainWindow shows preflight; on DOWNLOAD success it retries."""
    from flow.ui.main_window import MainWindow

    # Patch heavy deps
    with patch("flow.ui.main_window.SlideManager") as MockSM, \
         patch("flow.ui.dialogs.flow_show_engine_preflight",
               return_value=PreflightChoice.DOWNLOAD) as mock_pre, \
         patch("flow.ui.dialogs.flow_run_engine_download",
               return_value=(True, "")) as mock_dl:
        sm_inst = MagicMock()
        sm_inst.engine_missing = MagicMock()
        sm_inst.engine_missing.connect = MagicMock()
        sm_inst.is_engine_available = MagicMock(return_value=False)
        MockSM.return_value = sm_inst

        win = MainWindow()
        # Trigger handler directly (signal is mocked)
        win._on_engine_missing()

        mock_pre.assert_called_once()
        mock_dl.assert_called_once()
```

- [ ] **Step 2: Run to verify failure**

Run: `QT_QPA_PLATFORM=offscreen PYTHONNOUSERSITE=1 PYTHONPATH= pytest tests/ui/test_engine_missing_flow.py::test_main_window_routes_engine_missing_through_preflight -v`
Expected: FAIL — handler still calls `flow_show_install_guide`.

- [ ] **Step 3: Replace `_on_engine_missing` in `main_window.py`**

Read the existing handler at `src/flow/ui/main_window.py:286-295` and replace:

```python
def _on_engine_missing(self) -> None:
    if self._install_guide_shown:
        return
    self._install_guide_shown = True

    from flow.services.runtime import (
        LibreOfficeRuntime,
        UnsupportedPlatformError,
        get_manifest_for_resources,
        get_runtime_dir,
    )
    from flow.ui.dialogs import (
        EngineErrorChoice,
        PreflightChoice,
        flow_run_engine_download,
        flow_show_engine_error,
        flow_show_engine_preflight,
        flow_show_install_guide,
    )

    try:
        manifest = get_manifest_for_resources()
        build = manifest.get_build_for_current_platform()
    except (UnsupportedPlatformError, ValueError, FileNotFoundError):
        # No supported build for this platform → fall through to install guide
        flow_show_install_guide(self)
        return

    while True:
        choice = flow_show_engine_preflight(
            self,
            manifest_version=manifest.version,
            size_mb=build.size_bytes // (1 << 20),
        )
        if choice == PreflightChoice.CANCEL:
            self._install_guide_shown = False  # allow retry on next engine_missing
            return
        if choice == PreflightChoice.INSTALL_GUIDE:
            flow_show_install_guide(self)
            return

        # DOWNLOAD: run worker
        runtime = LibreOfficeRuntime(
            runtime_dir=get_runtime_dir(),
            manifest_version=manifest.version,
            soffice_relpath=build.soffice_relpath,
        )

        def _install_fn(*, on_progress, cancel_event):
            runtime.install(build, on_progress=on_progress, cancel_event=cancel_event)

        ok, err = flow_run_engine_download(self, install_fn=_install_fn)
        if ok:
            # Re-create slide_manager so it picks up the bundled LO
            self._slide_manager.rebuild_engine()
            return

        err_choice = flow_show_engine_error(self, error_message=err)
        if err_choice == EngineErrorChoice.CLOSE:
            self._install_guide_shown = False
            return
        if err_choice == EngineErrorChoice.INSTALL_GUIDE:
            flow_show_install_guide(self)
            return
        # RETRY → loop
```

- [ ] **Step 4: Add `rebuild_engine()` to SlideManager**

In `src/flow/services/slide_manager.py`, find the constructor section that does:

```python
try:
    self._converter = converter or create_slide_converter()
except NoConverterAvailableError:
    self._converter = None
```

Add a new method below the constructor:

```python
def rebuild_engine(self) -> None:
    """Re-detect engine after a successful runtime install. UI calls this after download."""
    from flow.services.slide_converter import create_slide_converter, NoConverterAvailableError
    try:
        self._converter = create_slide_converter()
    except NoConverterAvailableError:
        self._converter = None
        return
    # Recreate the worker too (was None when no engine was available)
    if self._converter is not None and self._worker is None:
        from flow.services.slide_manager import SlideWorker  # adjust import path if SlideWorker is elsewhere
        self._worker = SlideWorker(self._converter)

def is_engine_available(self) -> bool:
    return self._converter is not None
```

> **Note:** `is_engine_available` may already exist — check the file. If present, leave it; if absent, add. Adjust `SlideWorker` import to whatever module it lives in.

- [ ] **Step 5: Run tests**

Run: `QT_QPA_PLATFORM=offscreen PYTHONNOUSERSITE=1 PYTHONPATH= pytest tests/ui/test_engine_missing_flow.py tests/services/test_slide_manager.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/flow/ui/main_window.py src/flow/services/slide_manager.py \
  tests/ui/test_engine_missing_flow.py
git commit -m "feat(main_window): route engine_missing through preflight + download flow"
```

---

## Task 13: Edit button bundled-LO fallback

**Files:**
- Modify: `src/flow/ui/editor/song_list_widget.py`
- Create: `tests/ui/test_song_list_edit_fallback.py`

The existing edit handler at `song_list_widget.py:1460-1469` calls `QDesktopServices.openUrl` and warns on failure. Add bundled-LO fallback before warning.

- [ ] **Step 1: Write failing test**

```python
# tests/ui/test_song_list_edit_fallback.py
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch


def test_edit_falls_back_to_bundled_lo_when_shell_fails(qapp_args, tmp_path: Path) -> None:
    """When QDesktopServices.openUrl returns False, bundled LO Popen should be invoked."""
    from flow.ui.editor.song_list_widget import _open_pptx_for_edit

    pptx = tmp_path / "x.pptx"
    pptx.write_bytes(b"")
    bundled = tmp_path / "soffice"
    bundled.write_text("#!/bin/sh", encoding="utf-8")

    with patch("PySide6.QtGui.QDesktopServices.openUrl", return_value=False), \
         patch("flow.ui.editor.song_list_widget._detect_bundled_libreoffice",
               return_value=bundled), \
         patch("subprocess.Popen") as mock_popen:
        result = _open_pptx_for_edit(pptx, parent=None)
        mock_popen.assert_called_once()
        args = mock_popen.call_args[0][0]
        assert str(bundled) in args
        assert "--impress" in args
        assert str(pptx) in args
        assert result is True


def test_edit_returns_false_when_neither_shell_nor_bundled(qapp_args, tmp_path: Path) -> None:
    from flow.ui.editor.song_list_widget import _open_pptx_for_edit

    pptx = tmp_path / "x.pptx"
    pptx.write_bytes(b"")
    with patch("PySide6.QtGui.QDesktopServices.openUrl", return_value=False), \
         patch("flow.ui.editor.song_list_widget._detect_bundled_libreoffice", return_value=None):
        assert _open_pptx_for_edit(pptx, parent=None) is False
```

- [ ] **Step 2: Run test to verify failure**

Run: `QT_QPA_PLATFORM=offscreen PYTHONNOUSERSITE=1 PYTHONPATH= pytest tests/ui/test_song_list_edit_fallback.py -v`
Expected: FAIL — `_open_pptx_for_edit` doesn't exist.

- [ ] **Step 3: Extract a helper + add fallback in song_list_widget.py**

Locate `song_list_widget.py:1460-1469`. Refactor the current inline `QDesktopServices.openUrl` block into a module-level helper, then have the existing edit handler call it:

```python
# Add near other module-level imports/helpers in song_list_widget.py
import subprocess
from flow.services.slide_converter import _detect_bundled_libreoffice


def _open_pptx_for_edit(pptx_path: Path, *, parent) -> bool:
    """Try OS-shell open; fall back to bundled LibreOffice. Returns True on success."""
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QDesktopServices

    url = QUrl.fromLocalFile(str(pptx_path))
    if QDesktopServices.openUrl(url):
        return True

    bundled = _detect_bundled_libreoffice()
    if bundled is not None:
        try:
            subprocess.Popen([str(bundled), "--impress", str(pptx_path)])
            return True
        except OSError:
            return False
    return False
```

Replace the existing block at line 1460-1469:

```python
# old:
url = QUrl.fromLocalFile(str(pptx_path))
if not QDesktopServices.openUrl(url):
    QMessageBox.warning(self, "열기 실패", f"PPT 파일을 여는 데 실패했습니다:\n{pptx_path}")

# new:
if not _open_pptx_for_edit(pptx_path, parent=self):
    QMessageBox.warning(self, "열기 실패", f"PPT 파일을 여는 데 실패했습니다:\n{pptx_path}")
```

- [ ] **Step 4: Run tests**

Run: `QT_QPA_PLATFORM=offscreen PYTHONNOUSERSITE=1 PYTHONPATH= pytest tests/ui/test_song_list_edit_fallback.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/flow/ui/editor/song_list_widget.py tests/ui/test_song_list_edit_fallback.py
git commit -m "feat(song_list): fall back to bundled LibreOffice when shell open fails"
```

---

## Task 14: Cleanup partial downloads on SlideManager init

**Files:**
- Modify: `src/flow/services/slide_manager.py`
- Modify: `tests/services/test_slide_manager.py` (or create supplementary test file)

- [ ] **Step 1: Write failing test**

Append to existing `tests/services/test_slide_manager.py` (or create a new test file `tests/services/test_slide_manager_cleanup.py` if you can't easily edit the existing one):

```python
# tests/services/test_slide_manager_cleanup.py
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch


def test_slide_manager_cleans_partial_downloads_on_init(tmp_path: Path) -> None:
    runtime_dir = tmp_path / "rt"
    download_dir = runtime_dir / ".download"
    download_dir.mkdir(parents=True)
    (download_dir / "leftover.partial").write_bytes(b"x")

    with patch("flow.services.slide_manager.get_runtime_dir", return_value=runtime_dir), \
         patch("flow.services.slide_manager.create_slide_converter", side_effect=Exception):
        from flow.services.slide_manager import SlideManager
        try:
            SlideManager()
        except Exception:
            pass  # converter raise is expected

    assert not download_dir.exists() or not any(download_dir.iterdir())
```

- [ ] **Step 2: Run to verify failure**

Run: `QT_QPA_PLATFORM=offscreen PYTHONNOUSERSITE=1 PYTHONPATH= pytest tests/services/test_slide_manager_cleanup.py -v`
Expected: FAIL.

- [ ] **Step 3: Add cleanup call to SlideManager.__init__**

In `src/flow/services/slide_manager.py`, near the top of `__init__`:

```python
def __init__(self, converter=None) -> None:
    # Cleanup any partial downloads from previous interrupted run
    try:
        from flow.services.runtime import (
            LibreOfficeRuntime,
            get_manifest_for_resources,
            get_runtime_dir,
        )
        manifest = get_manifest_for_resources()
        rt = LibreOfficeRuntime(
            runtime_dir=get_runtime_dir(),
            manifest_version=manifest.version,
        )
        rt.cleanup_partial_downloads()
    except Exception:
        pass  # cleanup is best-effort

    # ... existing __init__ body
```

Add `from flow.services.runtime import get_runtime_dir` import line at the top of the module so the test patch path resolves.

- [ ] **Step 4: Run tests**

Run: `QT_QPA_PLATFORM=offscreen PYTHONNOUSERSITE=1 PYTHONPATH= pytest tests/services/test_slide_manager_cleanup.py tests/services/test_slide_manager.py -v`
Expected: PASS, no regressions.

- [ ] **Step 5: Commit**

```bash
git add src/flow/services/slide_manager.py tests/services/test_slide_manager_cleanup.py
git commit -m "feat(slide_manager): clean up stale .download/ on init"
```

---

## Task 15: Disk space pre-check

**Files:**
- Modify: `src/flow/services/runtime/libreoffice_runtime.py`
- Modify: `tests/runtime/test_libreoffice_runtime.py`

- [ ] **Step 1: Write failing test**

Append to `tests/runtime/test_libreoffice_runtime.py`:

```python
from flow.services.runtime.libreoffice_runtime import (
    InsufficientDiskSpaceError,
    check_disk_space,
)
from unittest.mock import patch


def test_check_disk_space_passes_when_enough(tmp_path: Path) -> None:
    check_disk_space(tmp_path, required_bytes=100)  # 100 bytes is trivially available


def test_check_disk_space_raises_when_insufficient(tmp_path: Path) -> None:
    fake_usage = type("U", (), {"free": 50})()
    with patch("shutil.disk_usage", return_value=fake_usage):
        with pytest.raises(InsufficientDiskSpaceError):
            check_disk_space(tmp_path, required_bytes=1000)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `QT_QPA_PLATFORM=offscreen PYTHONNOUSERSITE=1 PYTHONPATH= pytest tests/runtime/test_libreoffice_runtime.py::test_check_disk_space_passes_when_enough -v`
Expected: FAIL.

- [ ] **Step 3: Implement disk space check + integrate into install()**

Append to `src/flow/services/runtime/libreoffice_runtime.py`:

```python
class InsufficientDiskSpaceError(RuntimeError):
    """Not enough free disk space for the install."""

    def __init__(self, required: int, available: int) -> None:
        super().__init__(
            f"Need {required // (1 << 20)} MB, only {available // (1 << 20)} MB available"
        )
        self.required = required
        self.available = available


def check_disk_space(target_dir: Path, *, required_bytes: int) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    usage = shutil.disk_usage(target_dir)
    if usage.free < required_bytes:
        raise InsufficientDiskSpaceError(required=required_bytes, available=usage.free)
```

Then add a precondition at the top of `LibreOfficeRuntime.install()`:

```python
def install(self, build: BuildEntry, *, on_progress, cancel_event) -> None:
    self._dir.mkdir(parents=True, exist_ok=True)
    # Need archive + extracted (≈ 2.5x archive size to be safe)
    check_disk_space(self._dir, required_bytes=int(build.size_bytes * 2.5))
    # ... rest of method
```

- [ ] **Step 4: Run tests**

Run: `QT_QPA_PLATFORM=offscreen PYTHONNOUSERSITE=1 PYTHONPATH= pytest tests/runtime/ -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/flow/services/runtime/libreoffice_runtime.py tests/runtime/test_libreoffice_runtime.py
git commit -m "feat(runtime): pre-check disk space before download"
```

---

## Task 16: Concurrent install lock

**Files:**
- Modify: `src/flow/services/runtime/libreoffice_runtime.py`
- Modify: `tests/runtime/test_libreoffice_runtime.py`

- [ ] **Step 1: Write failing test**

Append to `tests/runtime/test_libreoffice_runtime.py`:

```python
from flow.services.runtime.libreoffice_runtime import (
    InstallLockError,
    InstallLock,
)


def test_install_lock_blocks_second_acquirer(tmp_path: Path) -> None:
    lock_path = tmp_path / ".lock"
    with InstallLock(lock_path):
        with pytest.raises(InstallLockError):
            with InstallLock(lock_path):
                pass


def test_install_lock_releases_on_exit(tmp_path: Path) -> None:
    lock_path = tmp_path / ".lock"
    with InstallLock(lock_path):
        pass
    # Now should be acquirable again
    with InstallLock(lock_path):
        pass
```

- [ ] **Step 2: Run to verify failure**

Run: `QT_QPA_PLATFORM=offscreen PYTHONNOUSERSITE=1 PYTHONPATH= pytest tests/runtime/test_libreoffice_runtime.py::test_install_lock_blocks_second_acquirer -v`
Expected: FAIL.

- [ ] **Step 3: Implement InstallLock**

Append to `src/flow/services/runtime/libreoffice_runtime.py`:

```python
class InstallLockError(RuntimeError):
    """Another install is already in progress."""


class InstallLock:
    """Cross-process file lock. Use as context manager."""

    def __init__(self, lock_path: Path) -> None:
        self._path = lock_path
        self._fh = None

    def __enter__(self) -> "InstallLock":
        self._path.parent.mkdir(parents=True, exist_ok=True)
        try:
            # O_CREAT | O_EXCL — fails if exists
            fd = os.open(str(self._path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            self._fh = os.fdopen(fd, "w")
            self._fh.write(str(os.getpid()))
            self._fh.flush()
            return self
        except FileExistsError:
            raise InstallLockError(f"Install already in progress (lock: {self._path})") from None

    def __exit__(self, *_exc) -> None:
        if self._fh is not None:
            self._fh.close()
        try:
            self._path.unlink()
        except FileNotFoundError:
            pass
```

Wrap `install()` body in the lock:

```python
def install(self, build: BuildEntry, *, on_progress, cancel_event) -> None:
    self._dir.mkdir(parents=True, exist_ok=True)
    with InstallLock(self._dir / ".lock"):
        check_disk_space(self._dir, required_bytes=int(build.size_bytes * 2.5))
        # ... rest of existing body
```

- [ ] **Step 4: Run tests**

Run: `QT_QPA_PLATFORM=offscreen PYTHONNOUSERSITE=1 PYTHONPATH= pytest tests/runtime/ -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/flow/services/runtime/libreoffice_runtime.py tests/runtime/test_libreoffice_runtime.py
git commit -m "feat(runtime): cross-process install lock"
```

---

## Task 17: Linux soffice executable bit

**Files:**
- Modify: `src/flow/services/runtime/libreoffice_runtime.py`

After extraction on Linux/macOS, the soffice binary may not have the executable bit set depending on tar permissions. Add `chmod +x` after extract.

- [ ] **Step 1: Add post-extract chmod step**

In `LibreOfficeRuntime.install()`, after the `staging.rename(final_version_dir)` line:

```python
staging.rename(final_version_dir)

# Ensure soffice is executable (Linux/macOS)
if sys.platform != "win32":
    soffice = final_version_dir / build.soffice_relpath
    if soffice.exists():
        st = soffice.stat()
        soffice.chmod(st.st_mode | 0o111)
```

Add `import sys` to the top of the file if not already imported.

- [ ] **Step 2: Verify existing tests still pass**

Run: `QT_QPA_PLATFORM=offscreen PYTHONNOUSERSITE=1 PYTHONPATH= pytest tests/runtime/ -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add src/flow/services/runtime/libreoffice_runtime.py
git commit -m "feat(runtime): chmod +x soffice after extract on Linux/macOS"
```

---

## Task 18: Remove stale `_install_guide_shown` rename

**Files:**
- Modify: `src/flow/ui/main_window.py`

The flag was named for the old install-guide flow. Rename to `_engine_dialog_shown` for clarity (or keep — judgment call).

- [ ] **Step 1: Rename in main_window.py**

Replace `_install_guide_shown` with `_engine_dialog_shown` everywhere it appears in `main_window.py`. Update the constructor init line and the handler.

- [ ] **Step 2: Run tests**

Run: `QT_QPA_PLATFORM=offscreen PYTHONNOUSERSITE=1 PYTHONPATH= pytest tests/ -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add src/flow/ui/main_window.py
git commit -m "refactor(main_window): rename install-guide flag to engine-dialog flag"
```

---

## Task 19: Manifest SHA256 fill script

**Files:**
- Create: `scripts/fill_libreoffice_manifest.py`

A one-shot script for filling SHA256 hashes in the manifest by downloading each artifact and computing the hash.

- [ ] **Step 1: Create the script**

```python
# scripts/fill_libreoffice_manifest.py
"""Fill SHA256 hashes in libreoffice_manifest.json by downloading each artifact.

Run from project root:
    python scripts/fill_libreoffice_manifest.py

Updates src/flow/resources/libreoffice_manifest.json in place.
"""
from __future__ import annotations

import hashlib
import json
import sys
import urllib.request
from pathlib import Path

MANIFEST_PATH = Path(__file__).parent.parent / "src/flow/resources/libreoffice_manifest.json"


def download_and_hash(url: str) -> tuple[str, int]:
    print(f"  downloading {url} ...", flush=True)
    h = hashlib.sha256()
    size = 0
    with urllib.request.urlopen(url) as response:
        while True:
            chunk = response.read(1 << 20)
            if not chunk:
                break
            h.update(chunk)
            size += len(chunk)
            print(f"    {size // (1 << 20)} MB", end="\r", flush=True)
    print()
    return h.hexdigest(), size


def main() -> int:
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    for key, build in data["builds"].items():
        print(f"\n[{key}]")
        sha, size = download_and_hash(build["url"])
        build["sha256"] = sha
        build["size_bytes"] = size
        print(f"  sha256: {sha}")
        print(f"  size:   {size} bytes ({size // (1 << 20)} MB)")
    MANIFEST_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"\nUpdated {MANIFEST_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Verify the script imports cleanly**

Run: `python -c "import ast; ast.parse(open('scripts/fill_libreoffice_manifest.py').read())"`
Expected: no output, no error.

- [ ] **Step 3: Commit**

```bash
git add scripts/fill_libreoffice_manifest.py
git commit -m "tools: script to fill SHA256 hashes in LibreOffice manifest"
```

> **Note:** Running the script for real downloads ~1.8 GB across 6 builds. Run only when bumping LibreOffice version.

---

## Task 20: Manual smoke test instructions

**Files:**
- Create: `docs/superpowers/plans/2026-04-27-libreoffice-smoke-test.md`

A checklist for manually verifying the full flow on Linux (the only OS we can test in this env).

- [ ] **Step 1: Write the doc**

````markdown
# LibreOffice Auto-Download Smoke Test (manual)

**Prerequisite:** Linux machine with NEITHER `soffice` in PATH NOR `/usr/bin/libreoffice`. To simulate, temporarily rename:

```bash
sudo mv /usr/bin/soffice /usr/bin/soffice.bak  # or whichever path exists
```

(Restore after the test: `sudo mv /usr/bin/soffice.bak /usr/bin/soffice`)

**Steps:**

1. Fill the manifest (one-time):
   ```bash
   python scripts/fill_libreoffice_manifest.py
   ```
2. Wipe any previous runtime:
   ```bash
   rm -rf ~/.local/share/Flow/runtime/libreoffice
   ```
3. Launch Flow and open a project containing a `.pptx`.
4. **Expect:** PreflightDialog appears with version + size + license note.
5. Click "지금 다운로드".
6. **Expect:** Progress dialog shows download → verify → extract phases. Total time ~1–3 min on broadband.
7. **Expect:** Dialog closes, slide preview populates.
8. Click the PPT edit button (in song list).
9. **Expect:** LibreOffice Impress GUI opens with the .pptx.
10. Restart Flow. Open the same .pptx.
11. **Expect:** No download dialog (runtime already installed).

**Failure modes to verify:**

- Cancel during download → dialog closes, `.download/` empty.
- Disconnect network mid-download → ErrorDialog with retry option.
- Manually corrupt INSTALLED_VERSION → next PPT load triggers re-download.
- Bump manifest version → next PPT load triggers upgrade dialog.
````

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/plans/2026-04-27-libreoffice-smoke-test.md
git commit -m "docs: manual smoke-test checklist for LibreOffice auto-download"
```

---

## Self-Review Notes

After all tasks complete, run the full test suite:

```bash
QT_QPA_PLATFORM=offscreen PYTHONNOUSERSITE=1 PYTHONPATH= pytest -v
```

Expected: prior baseline (239 pass / 2 unrelated failures) + new tests (~30+ added).

**Spec coverage check:**
- ✅ runtime/ package (Tasks 1–6, 15, 16, 17)
- ✅ resources/libreoffice_manifest.json (Task 1)
- ✅ slide_converter.py bundled detection + priority (Tasks 7, 8)
- ✅ slide_manager.py engine_missing semantics + cleanup (Tasks 12, 14)
- ✅ dialogs.py: Preflight + Progress + Error (Tasks 9, 10, 11)
- ✅ song_list_widget.py edit fallback (Task 13)
- ✅ Disk space + lock + chmod (Tasks 15, 16, 17)
- ✅ Manifest fill script (Task 19)
- ✅ Smoke test docs (Task 20)
- ⏸ About/Credits LibreOffice attribution — covered by PreflightDialog license note (per spec note: "Flow에 별도 About 화면이 없다면 PreflightDialog 하단 표기로 대체"). No separate task needed.
- ⏸ macOS quarantine and Windows .msi extraction — present in extractor.py (Task 3) but cannot be verified on Linux. Smoke test on those OSes is in the smoke test doc.

**Risks (from spec, unchanged):**
- macOS quarantine attribute may block first launch — verify in real macOS, add `xattr -d com.apple.quarantine` if needed.
- Windows .msi extraction via `msiexec /a` — tested only by msiexec exit code in current implementation; verify on real Windows that extracted layout matches `soffice_relpath`.
