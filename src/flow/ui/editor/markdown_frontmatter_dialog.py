"""Frontmatter form modal — edit YAML frontmatter via form fields."""
from __future__ import annotations

import re
from typing import Any

import yaml
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QFontDatabase, QPainter, QPen
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from flow.services.markdown.parser import Frontmatter
from flow.ui.styles import (
    ACCENT,
    ACCENT_HOVER,
    ACCENT_INTER,
    BG_DEEP,
    BG_ELEVATED,
    BG_INPUT,
    BG_SURFACE,
    BORDER_FOCUS,
    BORDER_STANDARD_RGBA,
    BORDER_SUBTLE_RGBA,
    FONT_FAMILY,
    FONT_MD,
    FONT_SM,
    RADIUS_MD,
    SP_LG,
    SP_MD,
    SP_SM,
    SP_XL,
    SURFACE_GHOST,
    SURFACE_SUBTLE,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TEXT_TERTIARY,
)

_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_DEFAULTS = Frontmatter()
_INT_KEYS = {"main_size", "sub_size", "main_weight", "sub_weight"}

_FIELDS: tuple[tuple[str, str], ...] = (
    ("main_font", "메인 폰트"),
    ("main_size", "메인 크기"),
    ("main_weight", "메인 굵기 (100–900)"),
    ("main_color", "메인 색"),
    ("sub_font", "서브 폰트"),
    ("sub_size", "서브 크기"),
    ("sub_weight", "서브 굵기 (100–900)"),
    ("sub_color", "서브 색"),
    ("background", "배경"),
    ("background_3plus", "3줄 배경"),
    ("background_4plus", "4줄 배경"),
    ("slide_inches", "슬라이드 크기 (inch)"),
    ("resolution", "해상도 (px)"),
)

_SLIDE_SIZE_PRESETS: tuple[tuple[str, str], ...] = (
    ("16:9 (28 × 15.75cm)", "11.024x6.201"),
    ("16:9 와이드 (33.87 × 19.05cm)", "13.333x7.5"),
    ("4:3 (25.4 × 19.05cm)", "10x7.5"),
)

_FONT_KEYS = {"main_font", "sub_font"}

_FONT_PRESETS: tuple[str, ...] = (
    "Pretendard Variable",
    "Pretendard Thin",
    "Pretendard ExtraLight",
    "Pretendard Light",
    "Pretendard Regular",
    "Pretendard Medium",
    "Pretendard SemiBold",
    "Pretendard Bold",
    "Pretendard ExtraBold",
    "Pretendard Black",
)

_DIALOG_QSS = f"""
QDialog#FmDialog {{ background: {BG_DEEP}; }}

QFrame#FmHeader {{
    background: {BG_SURFACE};
    border-bottom: 1px solid {BORDER_SUBTLE_RGBA};
}}
QLabel#FmTitle {{
    color: {TEXT_PRIMARY};
    font-family: {FONT_FAMILY};
    font-size: 18px;
    font-weight: 600;
}}
QLabel#FmSub {{
    color: {TEXT_TERTIARY};
    font-family: {FONT_FAMILY};
    font-size: {FONT_SM}px;
}}

QScrollArea#FmScroll {{ background: {BG_DEEP}; border: none; }}
QWidget#FmFormWrap {{ background: {BG_DEEP}; }}
QWidget#FmFormWrap QLabel {{
    color: {TEXT_SECONDARY};
    font-family: {FONT_FAMILY};
    font-size: {FONT_MD}px;
}}

QWidget#FmFormWrap QLineEdit,
QWidget#FmFormWrap QComboBox {{
    background: {BG_INPUT};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_STANDARD_RGBA};
    border-radius: {RADIUS_MD}px;
    padding: 6px 10px;
    font-family: {FONT_FAMILY};
    font-size: {FONT_MD}px;
    selection-background-color: {ACCENT};
    selection-color: #FFFFFF;
    min-height: 18px;
}}
QWidget#FmFormWrap QLineEdit:focus,
QWidget#FmFormWrap QComboBox:focus {{
    border-color: {ACCENT};
}}
QWidget#FmFormWrap QComboBox {{
    padding-right: 30px;  /* 우측 chevron 영역 확보 */
}}
QWidget#FmFormWrap QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 26px;
    border: none;
    border-left: 1px solid {BORDER_STANDARD_RGBA};
    background: {SURFACE_GHOST};
    border-top-right-radius: {RADIUS_MD}px;
    border-bottom-right-radius: {RADIUS_MD}px;
}}
QWidget#FmFormWrap QComboBox::drop-down:hover {{
    background: {SURFACE_SUBTLE};
}}
/* down-arrow 는 FontPicker.paintEvent 에서 직접 그린다 — image: none 으로
   Qt 가 기본 화살표를 그리려는 시도를 차단. */
QWidget#FmFormWrap QComboBox::down-arrow {{
    image: none;
    width: 0;
    height: 0;
}}
QWidget#FmFormWrap QComboBox QAbstractItemView {{
    background: {BG_ELEVATED};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_STANDARD_RGBA};
    selection-background-color: {SURFACE_SUBTLE};
    selection-color: {ACCENT_INTER};
    outline: 0;
    padding: 4px;
}}

QWidget#FmFormWrap QRadioButton {{
    color: {TEXT_SECONDARY};
    font-family: {FONT_FAMILY};
    font-size: {FONT_MD}px;
    spacing: 8px;
    padding: 2px 0;
}}
QWidget#FmFormWrap QRadioButton::indicator {{
    width: 14px;
    height: 14px;
    border-radius: 8px;
    border: 1.5px solid {BORDER_FOCUS};
    background: {BG_INPUT};
}}
QWidget#FmFormWrap QRadioButton::indicator:hover {{
    border-color: {ACCENT_INTER};
}}
QWidget#FmFormWrap QRadioButton::indicator:checked {{
    border: 4px solid {ACCENT_INTER};
    background: {BG_DEEP};
}}

QFrame#FmFooter {{
    background: {BG_SURFACE};
    border-top: 1px solid {BORDER_SUBTLE_RGBA};
}}
QPushButton#FmOk {{
    background: {ACCENT};
    color: #FFFFFF;
    border: none;
    border-radius: {RADIUS_MD}px;
    padding: 8px 22px;
    font-family: {FONT_FAMILY};
    font-size: {FONT_MD}px;
    font-weight: 500;
}}
QPushButton#FmOk:hover {{ background: {ACCENT_HOVER}; }}
QPushButton#FmCancel {{
    background: {SURFACE_GHOST};
    color: {TEXT_SECONDARY};
    border: 1px solid {BORDER_STANDARD_RGBA};
    border-radius: {RADIUS_MD}px;
    padding: 8px 18px;
    font-family: {FONT_FAMILY};
    font-size: {FONT_MD}px;
}}
QPushButton#FmCancel:hover {{
    background: {SURFACE_SUBTLE};
    color: {TEXT_PRIMARY};
}}

QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: rgba(255, 255, 255, 0.18);
    min-height: 24px;
    border-radius: 5px;
}}
QScrollBar::handle:vertical:hover {{ background: rgba(255, 255, 255, 0.30); }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
"""


def extract_raw_frontmatter(text: str) -> dict[str, Any]:
    """Return the raw frontmatter dict from markdown text (only explicit keys)."""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}
    try:
        raw = yaml.safe_load(m.group(1))
    except yaml.YAMLError:
        return {}
    return raw if isinstance(raw, dict) else {}


def _default_str(key: str) -> str:
    v = getattr(_DEFAULTS, key)
    if isinstance(v, tuple):
        return f"{v[0]}x{v[1]}"
    return str(v)


def _coerce(key: str, v: str) -> Any:
    if key in _INT_KEYS:
        try:
            return int(v)
        except ValueError:
            return v
    return v


def _normalize_size(s: str) -> str:
    """Normalize a 'WxH' string for comparison: strip spaces, lowercase x."""
    return re.sub(r"\s+", "", s).replace("X", "x")


class FontPicker(QComboBox):
    """폰트 선택 드롭다운 — 프리셋 + 직접 입력 가능."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setEditable(True)
        for f in _FONT_PRESETS:
            self.addItem(f)
        # 구분선 다음에 시스템 설치 폰트 전체. 사용자가 입력하면 editable
        # 콤보의 자동완성으로 빠르게 찾을 수 있다. Pretendard 항목은 위에서
        # 이미 노출했으므로 시스템 목록에서는 제외해 중복을 줄인다.
        system_fonts = sorted(
            f for f in QFontDatabase.families()
            if not f.startswith("Pretendard")
        )
        if system_fonts:
            self.insertSeparator(self.count())
            for f in system_fonts:
                self.addItem(f)
        # Combo 가 첫 항목을 자동 선택하지 않도록 초기 상태를 빈 값으로 둔다.
        # (빈 값 = "지정 안 함, 시스템 기본 사용")
        self.setCurrentIndex(-1)
        self.setEditText("")

    def set_value(self, s: str | None) -> None:
        if not s:
            self.setEditText("")
            return
        idx = self.findText(s, Qt.MatchFlag.MatchFixedString)
        if idx >= 0:
            self.setCurrentIndex(idx)
        else:
            self.setEditText(s)

    def value(self) -> str:
        return self.currentText().strip()

    def set_placeholder(self, text: str) -> None:
        self.lineEdit().setPlaceholderText(text)

    def paintEvent(self, event) -> None:  # noqa: N802
        # Qt QSS 의 down-arrow URL 렌더링이 환경별로 불안정해서, chevron 을
        # 직접 그려준다. (드롭다운 영역 자체의 배경/보더는 QSS 가 처리.)
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(QColor("#D0D6E0"))
        pen.setWidthF(1.6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        # 드롭다운 영역(우측 26px) 의 가운데. 화살표 폭 8px / 높이 4px.
        cx = self.width() - 13
        cy = self.height() / 2 + 1
        painter.drawLine(QPointF(cx - 4, cy - 2), QPointF(cx, cy + 2))
        painter.drawLine(QPointF(cx, cy + 2), QPointF(cx + 4, cy - 2))
        painter.end()


class SlideSizePicker(QWidget):
    """Radio group for slide size (presets + custom WxH input)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._group = QButtonGroup(self)
        self._radios: list[tuple[QRadioButton, str]] = []
        for label, value in _SLIDE_SIZE_PRESETS:
            rb = QRadioButton(label)
            self._group.addButton(rb)
            layout.addWidget(rb)
            self._radios.append((rb, value))

        custom_row = QHBoxLayout()
        custom_row.setContentsMargins(0, 0, 0, 0)
        self._rb_custom = QRadioButton("사용자 정의")
        self._group.addButton(self._rb_custom)
        custom_row.addWidget(self._rb_custom)
        self._custom_input = QLineEdit()
        self._custom_input.setPlaceholderText("WxH (예: 12x9)")
        self._custom_input.setEnabled(False)
        custom_row.addWidget(self._custom_input, 1)
        layout.addLayout(custom_row)

        self._rb_custom.toggled.connect(self._custom_input.setEnabled)

    def set_value(self, s: str | None) -> None:
        if not s:
            self._radios[0][0].setChecked(True)
            return
        norm = _normalize_size(str(s))
        for rb, value in self._radios:
            if norm == value:
                rb.setChecked(True)
                return
        self._rb_custom.setChecked(True)
        self._custom_input.setText(s)

    def value(self) -> str:
        if self._rb_custom.isChecked():
            return self._custom_input.text().strip()
        for rb, value in self._radios:
            if rb.isChecked():
                return value
        return ""


def apply_frontmatter_to_text(text: str, raw: dict[str, Any]) -> str:
    """Replace or insert frontmatter block. Only writes keys present in `raw`."""
    m = _FRONTMATTER_RE.match(text)
    if not raw:
        return text[m.end():] if m else text
    yaml_body = yaml.safe_dump(raw, allow_unicode=True, sort_keys=False).rstrip() + "\n"
    block = f"---\n{yaml_body}---\n"
    if m:
        return block + text[m.end():]
    return block + "\n" + text


class FrontmatterDialog(QDialog):
    """Modal: edit frontmatter via form fields.

    Only keys explicitly present in the original markdown are pre-filled.
    Other fields show the system default as placeholder text — leaving them
    empty means "use default (don't write to file)".
    """

    def __init__(
        self,
        original_raw: dict[str, Any] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("FmDialog")
        self.setWindowTitle("Frontmatter 편집")
        self.setStyleSheet(_DIALOG_QSS)
        self.resize(560, 680)
        self._original_raw = original_raw or {}
        self._inputs: dict[str, QLineEdit] = {}
        self._font_pickers: dict[str, FontPicker] = {}
        self._slide_size_picker: SlideSizePicker | None = None

        # ── Header ───────────────────────────────────────────
        header = QFrame()
        header.setObjectName("FmHeader")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(SP_XL, SP_LG, SP_XL, SP_LG)
        header_layout.setSpacing(2)
        title = QLabel("Frontmatter 편집")
        title.setObjectName("FmTitle")
        sub = QLabel("이 곡 전체에 적용되는 기본값을 설정합니다.")
        sub.setObjectName("FmSub")
        header_layout.addWidget(title)
        header_layout.addWidget(sub)

        # ── Body (scrollable form) ───────────────────────────
        form_wrap = QWidget()
        form_wrap.setObjectName("FmFormWrap")
        form = QFormLayout(form_wrap)
        form.setContentsMargins(SP_XL, SP_LG, SP_XL, SP_LG)
        form.setSpacing(12)
        form.setLabelAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        for key, label in _FIELDS:
            if key == "slide_inches":
                picker = SlideSizePicker()
                picker.set_value(
                    str(self._original_raw.get(key)) if key in self._original_raw
                    else _default_str(key)
                )
                self._slide_size_picker = picker
                form.addRow(label, picker)
                continue
            if key in _FONT_KEYS:
                fp = FontPicker()
                if key in self._original_raw:
                    fp.set_value(str(self._original_raw[key]))
                fp.set_placeholder(_default_str(key))
                self._font_pickers[key] = fp
                form.addRow(label, fp)
                continue
            le = QLineEdit()
            if key in self._original_raw:
                le.setText(str(self._original_raw[key]))
            le.setPlaceholderText(_default_str(key))
            self._inputs[key] = le
            form.addRow(label, le)

        scroll = QScrollArea()
        scroll.setObjectName("FmScroll")
        scroll.setWidget(form_wrap)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        # ── Footer ───────────────────────────────────────────
        footer = QFrame()
        footer.setObjectName("FmFooter")
        footer_row = QHBoxLayout(footer)
        footer_row.setContentsMargins(SP_LG, SP_MD, SP_LG, SP_MD)
        footer_row.setSpacing(SP_SM)
        footer_row.addStretch(1)
        cancel = QPushButton("취소")
        cancel.setObjectName("FmCancel")
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        ok = QPushButton("저장")
        ok.setObjectName("FmOk")
        ok.setCursor(Qt.CursorShape.PointingHandCursor)
        footer_row.addWidget(cancel)
        footer_row.addWidget(ok)

        # ── Root ─────────────────────────────────────────────
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(header)
        root.addWidget(scroll, 1)
        root.addWidget(footer)

        ok.setDefault(True)
        ok.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)

    def result_raw(self) -> dict[str, Any]:
        """Return only fields the user filled in (non-empty)."""
        out: dict[str, Any] = {}
        for key, le in self._inputs.items():
            v = le.text().strip()
            if v:
                out[key] = _coerce(key, v)
        for key, fp in self._font_pickers.items():
            v = fp.value()
            if v:
                out[key] = v
        if self._slide_size_picker is not None:
            v = self._slide_size_picker.value()
            # Skip if value matches the system default AND wasn't explicitly set
            # in the original markdown — keep file lean.
            default = _default_str("slide_inches")
            originally_present = "slide_inches" in self._original_raw
            if v and (
                originally_present or _normalize_size(v) != _normalize_size(default)
            ):
                out["slide_inches"] = v
        return out
