"""QR 코드 픽스맵 생성 헬퍼 (웹 송출 URL 공유용)."""

from __future__ import annotations

import io

from PySide6.QtGui import QPixmap


def build_qr_pixmap(url: str) -> QPixmap | None:
    """URL의 QR 코드 QPixmap 생성. qrcode 미설치 등 실패 시 None."""
    try:
        import qrcode

        img = qrcode.make(url)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        pixmap = QPixmap()
        pixmap.loadFromData(buf.getvalue())
        return pixmap
    except Exception:
        return None
