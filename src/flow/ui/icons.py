"""Material Symbols Rounded 아이콘 헬퍼

앱 전체에서 아이콘을 일관되게 사용하기 위한 모듈.
폰트를 한 번만 로드하고, 아이콘 이름으로 글리프 문자열을 반환한다.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase

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
    "slideshow":    0xef6e,
    "circle":       0xe3c9,
    "arrow_back":   0xe5c4,
    "edit":         0xe254,
    "search":       0xe8f4,
    "music":        0xef76,
    "queue_music":  0xe2c4,
    "folder_open":  0xe8d4,
    "drag":         0xe5f9,
    "more_vert":    0xe5d5,
    "library":      0xe028,
    "refresh":      0xe627,
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


def icon_text(name: str, text: str, spacing: int = 2) -> str:
    """아이콘 + 텍스트 조합 문자열 반환 (단일 폰트에서는 사용 불가 — 레이아웃용)."""
    return f"{icon(name)}{' ' * spacing}{text}"
