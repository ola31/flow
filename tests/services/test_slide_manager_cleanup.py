from __future__ import annotations

from pathlib import Path
from unittest.mock import patch


def test_slide_manager_cleans_partial_downloads_on_init(tmp_path: Path) -> None:
    runtime_dir = tmp_path / "rt"
    download_dir = runtime_dir / ".download"
    download_dir.mkdir(parents=True)
    (download_dir / "leftover.partial").write_bytes(b"x")

    with patch(
        "flow.services.slide_manager.get_runtime_dir", return_value=runtime_dir
    ), patch(
        "flow.services.slide_manager.create_slide_converter",
        side_effect=Exception,
    ):
        from flow.services.slide_manager import SlideManager

        try:
            SlideManager()
        except Exception:
            pass  # converter raise is expected

    assert not download_dir.exists() or not any(download_dir.iterdir())
