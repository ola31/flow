from __future__ import annotations

from pathlib import Path
from unittest.mock import patch


def test_edit_falls_back_to_bundled_lo_when_shell_fails(
    qapp_args, tmp_path: Path
) -> None:
    """openUrl returning False triggers bundled LO Popen fallback."""
    from flow.ui.editor.song_list_widget import _open_pptx_for_edit

    pptx = tmp_path / "x.pptx"
    pptx.write_bytes(b"")
    bundled = tmp_path / "soffice"
    bundled.write_text("#!/bin/sh", encoding="utf-8")

    with patch(
        "PySide6.QtGui.QDesktopServices.openUrl", return_value=False
    ), patch(
        "flow.ui.editor.song_list_widget._detect_bundled_libreoffice",
        return_value=bundled,
    ), patch("subprocess.Popen") as mock_popen:
        result = _open_pptx_for_edit(pptx, parent=None)
        mock_popen.assert_called_once()
        args = mock_popen.call_args[0][0]
        assert str(bundled) in args
        assert "--impress" in args
        assert str(pptx) in args
        assert result is True


def test_edit_returns_false_when_neither_shell_nor_bundled(
    qapp_args, tmp_path: Path
) -> None:
    from flow.ui.editor.song_list_widget import _open_pptx_for_edit

    pptx = tmp_path / "x.pptx"
    pptx.write_bytes(b"")
    with patch(
        "PySide6.QtGui.QDesktopServices.openUrl", return_value=False
    ), patch(
        "flow.ui.editor.song_list_widget._detect_bundled_libreoffice",
        return_value=None,
    ):
        assert _open_pptx_for_edit(pptx, parent=None) is False


def test_edit_succeeds_when_shell_open_succeeds(
    qapp_args, tmp_path: Path
) -> None:
    """If OS shell open succeeds, no bundled LO call needed."""
    from flow.ui.editor.song_list_widget import _open_pptx_for_edit

    pptx = tmp_path / "x.pptx"
    pptx.write_bytes(b"")
    with patch(
        "PySide6.QtGui.QDesktopServices.openUrl", return_value=True
    ), patch("subprocess.Popen") as mock_popen:
        assert _open_pptx_for_edit(pptx, parent=None) is True
        mock_popen.assert_not_called()
