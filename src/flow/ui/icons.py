"""Material Symbols Rounded 아이콘 헬퍼

앱 전체에서 아이콘을 일관되게 사용하기 위한 모듈.
폰트를 한 번만 로드하고, 아이콘 이름으로 글리프 문자열을 반환한다.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QGuiApplication,
    QIcon,
    QImage,
    QPainter,
    QPixmap,
)
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

_FONT_FAMILY: str | None = None
_FONT_PATH = Path(__file__).parent.parent / "resources" / "MaterialSymbolsRounded-Subset.ttf"

# Material Symbols 코드포인트 맵
_CODEPOINTS: dict[str, int] = {
    "home":         0xe88a,
    "save":         0xe161,
    "settings":     0xe8b8,
    "undo":         0xe166,
    "redo":         0xe15a,
    "play":         0xe037,
    "stop":         0xe047,
    "tv":           0xe063,
    "close":        0xe5cd,
    "add":          0xe145,
    "delete":       0xe872,
    "image":        0xe3f4,
    "slideshow":    0xe41b,
    "circle":       0xe3c9,
    "arrow_back":   0xe5c4,
    "edit":         0xe254,
    "edit_note":    0xe745,
    "search":       0xe8f4,
    "music":        0xe3a1,
    "queue_music":  0xe2c4,
    "folder":       0xe2c7,
    "folder_open":  0xe2c8,
    "more_vert":    0xe5d5,
    "library":      0xe028,
    "library_music":0xe030,
    "refresh":      0xe627,
    "music_note":   0xe3a1,
    "view_list":    0xe8ef,
    "link":         0xe157,
}


def _ensure_loaded() -> str:
    """폰트가 로드되지 않았으면 로드하고 family name을 반환."""
    global _FONT_FAMILY
    if _FONT_FAMILY is not None:
        return _FONT_FAMILY

    font_id = QFontDatabase.addApplicationFont(str(_FONT_PATH))
    if font_id < 0:
        _FONT_FAMILY = ""
        return _FONT_FAMILY

    families = QFontDatabase.applicationFontFamilies(font_id)
    _FONT_FAMILY = families[0] if families else ""
    return _FONT_FAMILY


def icon_font(size: int = 18) -> QFont:
    """아이콘 폰트 QFont 객체 반환."""
    family = _ensure_loaded()
    f = QFont(family)
    f.setPixelSize(size)
    return f


def icon(name: str) -> str:
    """아이콘 이름으로 유니코드 문자 반환.

    Usage:
        label.setFont(icon_font(16))
        label.setText(icon("home"))
    """
    cp = _CODEPOINTS.get(name)
    if cp is None:
        return "?"
    return chr(cp)


def icon_pixmap(name: str, size: int = 18, color: str = "#a0a0a0") -> QPixmap:
    """아이콘을 QPixmap으로 렌더링.

    아이콘 폰트는 작은 사이즈에서 힌팅이 약해 흐릿하게 보이므로,
    충분히 큰 사이즈(>=64px)로 한 번 그린 뒤 SmoothTransformation으로
    물리 픽셀 크기까지 다운스케일하여 선명도를 확보한다. devicePixelRatio
    역시 반영하여 고DPI 화면에서도 정확한 픽셀 밀도를 갖는다.
    """
    _ensure_loaded()
    app = QGuiApplication.instance()
    dpr = app.devicePixelRatio() if app else 1.0
    phys = max(1, int(round(size * dpr)))

    # Super-sample: 적어도 물리 크기의 4배, 최소 96px 이상으로 렌더링.
    super_size = max(96, phys * 4)
    img = QImage(super_size, super_size, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)

    painter = QPainter(img)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    painter.setFont(icon_font(super_size))
    painter.setPen(QColor(color))
    painter.drawText(
        QRect(0, 0, super_size, super_size),
        Qt.AlignmentFlag.AlignCenter,
        icon(name),
    )
    painter.end()

    scaled = img.scaled(
        phys,
        phys,
        Qt.AspectRatioMode.IgnoreAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    px = QPixmap.fromImage(scaled)
    px.setDevicePixelRatio(dpr)
    return px


def icon_qicon(name: str, size: int = 18, color: str = "#a0a0a0") -> QIcon:
    """아이콘을 QIcon으로 반환 (QAction/QToolButton용)."""
    return QIcon(icon_pixmap(name, size, color))


def icon_label(name: str, size: int = 16, color: str = "#a0a0a0", parent=None) -> QLabel:
    """아이콘 QLabel 생성. 아이콘 폰트로 단일 글리프를 표시."""
    lbl = QLabel(icon(name), parent)
    lbl.setFont(icon_font(size))
    lbl.setStyleSheet(f"color: {color}; background: transparent;")
    lbl.setFixedSize(size + 4, size + 4)
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return lbl


def icon_text_label(
    name: str, text: str, icon_size: int = 14, color: str = "#a0a0a0",
    font_size: int = 12, parent=None,
) -> QWidget:
    """아이콘 + 텍스트를 나란히 배치한 위젯."""
    w = QWidget(parent)
    w.setStyleSheet("background: transparent;")
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(4)

    ic = icon_label(name, icon_size, color, w)
    lay.addWidget(ic)

    t = QLabel(text, w)
    t.setStyleSheet(f"font-size: {font_size}px; color: {color}; background: transparent;")
    lay.addWidget(t)

    return w
