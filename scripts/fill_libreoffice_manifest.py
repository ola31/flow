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

MANIFEST_PATH = (
    Path(__file__).parent.parent
    / "src/flow/resources/libreoffice_manifest.json"
)


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
