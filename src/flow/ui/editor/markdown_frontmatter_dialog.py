"""Frontmatter form modal — edit YAML frontmatter via form fields."""
from __future__ import annotations

import re
from typing import Any

import yaml
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from flow.services.markdown.parser import Frontmatter

_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_DEFAULTS = Frontmatter()
_INT_KEYS = {"main_size", "sub_size"}

_FIELDS: tuple[tuple[str, str], ...] = (
    ("main_font", "메인 폰트"),
    ("main_size", "메인 크기"),
    ("main_color", "메인 색"),
    ("sub_font", "서브 폰트"),
    ("sub_size", "서브 크기"),
    ("sub_color", "서브 색"),
    ("background", "배경"),
    ("slide_inches", "슬라이드 크기 (inch)"),
    ("resolution", "해상도 (px)"),
)

_SLIDE_SIZE_PRESETS: tuple[tuple[str, str], ...] = (
    ("16:9 (28 × 15.75cm)", "11.024x6.201"),
    ("16:9 와이드 (33.87 × 19.05cm)", "13.333x7.5"),
    ("4:3 (25.4 × 19.05cm)", "10x7.5"),
)


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
        self.setWindowTitle("Frontmatter 편집")
        self._original_raw = original_raw or {}
        self._inputs: dict[str, QLineEdit] = {}
        self._slide_size_picker: SlideSizePicker | None = None

        form = QFormLayout()
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
            le = QLineEdit()
            if key in self._original_raw:
                le.setText(str(self._original_raw[key]))
            le.setPlaceholderText(_default_str(key))
            self._inputs[key] = le
            form.addRow(label, le)

        layout = QVBoxLayout(self)
        layout.addLayout(form)

        buttons = QHBoxLayout()
        buttons.addStretch()
        ok = QPushButton("OK")
        cancel = QPushButton("취소")
        buttons.addWidget(cancel)
        buttons.addWidget(ok)
        layout.addLayout(buttons)
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
        if self._slide_size_picker is not None:
            v = self._slide_size_picker.value()
            # Skip if value matches the system default AND wasn't explicitly set
            # in the original markdown — keep file lean.
            default = _default_str("slide_inches")
            originally_present = "slide_inches" in self._original_raw
            if v and (originally_present or _normalize_size(v) != _normalize_size(default)):
                out["slide_inches"] = v
        return out
