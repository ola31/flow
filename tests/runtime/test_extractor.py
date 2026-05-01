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


def test_extract_tar_gz_strips_single_top_dir(tmp_path: Path) -> None:
    """A single wrapping directory inside the tar is stripped after extract.

    LibreOffice tarballs wrap everything in a build-version-suffixed dir
    (e.g. LibreOffice_26.2.2.2_Linux_x86-64_deb/) that doesn't match the
    marketing version we pin, so callers should see the contents directly.
    """
    archive = _make_tar_gz(tmp_path, {
        "myproj/program/soffice": "#!/bin/sh\n",
        "myproj/README": "hello",
    })
    target = tmp_path / "out"
    extract_archive(archive, target, format="tar_gz")
    assert (target / "program/soffice").exists()
    assert (target / "README").read_text() == "hello"
    assert not (target / "myproj").exists()


def test_extract_tar_gz_keeps_multiple_top_entries(tmp_path: Path) -> None:
    """When the archive doesn't have a single wrapping dir, leave layout as-is."""
    archive = _make_tar_gz(tmp_path, {
        "program/soffice": "#!/bin/sh\n",
        "README": "hello",
    })
    target = tmp_path / "out"
    extract_archive(archive, target, format="tar_gz")
    assert (target / "program/soffice").exists()
    assert (target / "README").read_text() == "hello"


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
    """Tarballs with .. paths must be rejected and leave nothing on disk."""
    archive = tmp_path / "evil.tar.gz"
    payload = tmp_path / "payload"
    payload.write_text("evil", encoding="utf-8")
    with tarfile.open(archive, "w:gz") as tf:
        tf.add(payload, arcname="../escaped")
    target = tmp_path / "out"
    with pytest.raises(ExtractionError):
        extract_archive(archive, target, format="tar_gz")
    assert not (tmp_path / "escaped").exists()


def test_extract_blocks_sibling_prefix_traversal(tmp_path: Path) -> None:
    """`../outX/...` must not escape into a sibling that shares a prefix."""
    archive = tmp_path / "evil.tar.gz"
    payload = tmp_path / "payload"
    payload.write_text("evil", encoding="utf-8")
    with tarfile.open(archive, "w:gz") as tf:
        tf.add(payload, arcname="../outX/escaped")
    target = tmp_path / "out"
    (tmp_path / "outX").mkdir()
    with pytest.raises(ExtractionError):
        extract_archive(archive, target, format="tar_gz")
    assert not (tmp_path / "outX" / "escaped").exists()
