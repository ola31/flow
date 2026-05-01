"""Frontmatter form modal — edit YAML frontmatter via form fields."""
from __future__ import annotations

import re

import yaml
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from flow.services.markdown.parser import Frontmatter, _build_frontmatter

_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def parse_form_values(values: dict[str, str]) -> Frontmatter:
    """Convert form string values into a Frontmatter, falling back to defaults."""
    raw: dict[str, object] = {}
    for k, v in values.items():
        if v == "":
            continue
        raw[k] = v
    return _build_frontmatter(raw)


def _frontmatter_to_yaml(fm: Frontmatter) -> str:
    """Serialize a Frontmatter to YAML for embedding."""
    d = {
        "main_font": fm.main_font,
        "main_size": fm.main_size,
        "main_color": fm.main_color,
        "sub_font": fm.sub_font,
        "sub_size": fm.sub_size,
        "sub_color": fm.sub_color,
        "background": fm.background,
        "slide_inches": f"{fm.slide_inches[0]}x{fm.slide_inches[1]}",
        "resolution": f"{fm.resolution[0]}x{fm.resolution[1]}",
    }
    return yaml.safe_dump(d, allow_unicode=True, sort_keys=False).rstrip() + "\n"


def apply_frontmatter_to_text(text: str, fm: Frontmatter) -> str:
    """Replace or insert frontmatter block in markdown text."""
    yaml_body = _frontmatter_to_yaml(fm)
    block = f"---\n{yaml_body}---\n"
    m = _FRONTMATTER_RE.match(text)
    if m:
        return block + text[m.end():]
    return block + "\n" + text


class FrontmatterDialog(QDialog):
    """Modal: edit frontmatter via form fields."""

    def __init__(self, current: Frontmatter, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Frontmatter 편집")
        self._fm = current
        self._inputs: dict[str, QLineEdit] = {}

        form = QFormLayout()
        for key, label in (
            ("main_font", "메인 폰트"),
            ("main_size", "메인 크기"),
            ("main_color", "메인 색"),
            ("sub_font", "서브 폰트"),
            ("sub_size", "서브 크기"),
            ("sub_color", "서브 색"),
            ("background", "배경"),
            ("slide_inches", "슬라이드 크기 (inch)"),
            ("resolution", "해상도 (px)"),
        ):
            le = QLineEdit(self._initial_value(key))
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

    def _initial_value(self, key: str) -> str:
        v = getattr(self._fm, key)
        if isinstance(v, tuple):
            return f"{v[0]}x{v[1]}"
        return str(v)

    def result_frontmatter(self) -> Frontmatter:
        return parse_form_values({k: le.text() for k, le in self._inputs.items()})
