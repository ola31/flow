"""Per-patch reconciliation dialog.

Shows each unreconciled patch in `<song_dir>/.patches.json` with the
original slide body next to the patched body, and per-patch buttons to
apply that single patch to `slides.md` or discard it.
"""
from __future__ import annotations

import difflib
import html
from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from flow.services.markdown import (
    PatchStore,
    PatchType,
    SlidePatch,
    apply_patches_to_text,
    parse,
    slide_hash,
)
from flow.ui import styles
from flow.ui.icons import icon_qicon


def _resolve_status(patch: SlidePatch, slides) -> tuple[str, str | None]:
    """Return (status_label, original_text or None) for a patch.

    status: "정상" | "위치 이동" | "원본 없음" | "추가"
    """
    if patch.type is PatchType.APPEND:
        return ("추가", None)
    if patch.slide_hash is not None:
        for s in slides:
            if slide_hash(s.main) == patch.slide_hash:
                return ("정상", s.main)
    if patch.slide_index is not None and 0 <= patch.slide_index < len(slides):
        return ("위치 이동", slides[patch.slide_index].main)
    return ("원본 없음", None)


def _status_color(status: str) -> str:
    if status == "정상":
        return styles.GREEN if hasattr(styles, "GREEN") else styles.AMBER
    if status == "추가":
        return styles.ACCENT
    return styles.AMBER  # drift / orphan


class PatchDetailsDialog(QDialog):
    """Modal dialog listing every patch in `.patches.json` with diff + actions."""

    # Emitted whenever a patch is applied or discarded so the parent editor
    # can refresh the notification bar count.
    patches_changed = Signal()

    def __init__(self, md_path: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("긴급 수정 자세히 보기")
        self.setModal(True)
        self.resize(900, 600)
        self._md_path = md_path

        root = QVBoxLayout(self)
        root.setContentsMargins(
            styles.SP_LG, styles.SP_LG, styles.SP_LG, styles.SP_LG
        )
        root.setSpacing(styles.SP_MD)

        self._summary_label = QLabel("")
        self._summary_label.setStyleSheet(
            f"color: {styles.TEXT_PRIMARY}; font-size: {styles.FONT_MD}px; "
            "font-weight: 600;"
        )
        root.addWidget(self._summary_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._list_host = QWidget()
        self._list_layout = QVBoxLayout(self._list_host)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(styles.SP_MD)
        self._list_layout.addStretch(1)
        scroll.setWidget(self._list_host)
        root.addWidget(scroll, 1)

        footer = QHBoxLayout()
        footer.addStretch(1)
        close_btn = QPushButton("닫기")
        close_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        close_btn.clicked.connect(self.accept)
        footer.addWidget(close_btn)
        root.addLayout(footer)

        self._reload()

    # ---------------------------------------------------------------- internals

    def _reload(self) -> None:
        # Tear down existing patch rows (keep the trailing stretch)
        while self._list_layout.count() > 1:
            item = self._list_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        store = PatchStore(self._md_path.parent / ".patches.json")
        try:
            spec = parse(self._md_path.read_text(encoding="utf-8"))
        except Exception:
            spec = None
        slides = spec.slides if spec else []

        patches = store.patches
        self._summary_label.setText(
            f"긴급 수정 {len(patches)}건"
            if patches
            else "남아 있는 긴급 수정 없음"
        )

        for patch in patches:
            status, original = _resolve_status(patch, slides)
            row = self._build_row(patch, status, original)
            self._list_layout.insertWidget(self._list_layout.count() - 1, row)

    def _build_row(
        self, patch: SlidePatch, status: str, original: str | None
    ) -> QWidget:
        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame {{ background-color: {styles.BG_ELEVATED}; "
            f"border: 1px solid {styles.BORDER_SUBTLE_RGBA}; "
            f"border-radius: 6px; }}"
        )
        outer = QVBoxLayout(frame)
        outer.setContentsMargins(
            styles.SP_MD, styles.SP_MD, styles.SP_MD, styles.SP_MD
        )
        outer.setSpacing(styles.SP_SM)

        # Header: title + status chip
        header = QHBoxLayout()
        title_text = (
            f"슬라이드 #{(patch.slide_index or 0) + 1}"
            if patch.type is PatchType.EDIT
            else "새 슬라이드 (추가)"
        )
        title = QLabel(title_text)
        title.setStyleSheet(
            f"color: {styles.TEXT_PRIMARY}; font-size: {styles.FONT_SM}px; "
            "font-weight: 600;"
        )
        header.addWidget(title)
        chip = QLabel(status)
        chip.setStyleSheet(
            f"background-color: transparent; color: {_status_color(status)}; "
            f"border: 1px solid {_status_color(status)}; "
            f"border-radius: 4px; padding: 2px 6px; "
            f"font-size: {styles.FONT_XS}px;"
        )
        header.addWidget(chip)
        header.addStretch(1)
        outer.addLayout(header)

        # Side-by-side diff with highlighting
        original_text = original or ""
        left_html, right_html = self._build_diff_html(
            original_text, patch.patched_main
        )
        diff = QHBoxLayout()
        diff.setSpacing(styles.SP_SM)
        if original is None:
            # Orphan / append — nothing to diff against, show placeholder.
            placeholder = (
                "(추가된 슬라이드 — 원본 없음)"
                if patch.type is PatchType.APPEND
                else "(원본 없음)"
            )
            diff.addWidget(
                self._diff_pane("원본", f"<i style='color:{styles.TEXT_TERTIARY}'>"
                                f"{html.escape(placeholder)}</i>")
            )
        else:
            diff.addWidget(self._diff_pane("원본", left_html))
        diff.addWidget(self._diff_pane("패치", right_html))
        outer.addLayout(diff)

        # Per-patch actions
        actions = QHBoxLayout()
        actions.addStretch(1)
        apply_btn = QPushButton("  원본에 반영")
        apply_btn.setIcon(icon_qicon("save", size=14, color=styles.AMBER))
        apply_btn.setIconSize(QSize(14, 14))
        apply_btn.setStyleSheet(
            f"QPushButton {{ background-color: transparent; "
            f"color: {styles.AMBER}; border: 1px solid {styles.AMBER}; "
            f"border-radius: 4px; padding: 4px 8px; "
            f"font-size: {styles.FONT_XS}px; }}"
        )
        # Disable apply for orphans — there's no slide to write to.
        if status == "원본 없음":
            apply_btn.setEnabled(False)
            apply_btn.setToolTip("매칭되는 원본 슬라이드가 없어 반영할 수 없습니다.")
        apply_btn.clicked.connect(lambda _=False, p=patch: self._apply_one(p))
        discard_btn = QPushButton("  폐기")
        discard_btn.setIcon(icon_qicon("delete", size=14, color=styles.AMBER))
        discard_btn.setIconSize(QSize(14, 14))
        discard_btn.setStyleSheet(apply_btn.styleSheet())
        discard_btn.clicked.connect(lambda _=False, p=patch: self._discard_one(p))
        actions.addWidget(apply_btn)
        actions.addWidget(discard_btn)
        outer.addLayout(actions)

        return frame

    @staticmethod
    def _build_diff_html(original: str, patched: str) -> tuple[str, str]:
        """Compute per-char diff and return (left_html, right_html).

        Removed chars are tinted RED_MUTED in the left pane; inserted
        chars are tinted GREEN_MUTED in the right pane. Replaced regions
        show the old text on the left (red) and the new text on the right
        (green).
        """
        matcher = difflib.SequenceMatcher(a=original, b=patched, autojunk=False)
        left_parts: list[str] = []
        right_parts: list[str] = []
        del_style = (
            f"background-color: {styles.RED_MUTED}; color: {styles.RED};"
        )
        ins_style = (
            f"background-color: {styles.GREEN_MUTED}; color: {styles.GREEN};"
        )
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            left_chunk = html.escape(original[i1:i2]).replace("\n", "<br>")
            right_chunk = html.escape(patched[j1:j2]).replace("\n", "<br>")
            if tag == "equal":
                left_parts.append(left_chunk)
                right_parts.append(right_chunk)
            elif tag == "delete":
                left_parts.append(f"<span style='{del_style}'>{left_chunk}</span>")
            elif tag == "insert":
                right_parts.append(f"<span style='{ins_style}'>{right_chunk}</span>")
            elif tag == "replace":
                left_parts.append(f"<span style='{del_style}'>{left_chunk}</span>")
                right_parts.append(f"<span style='{ins_style}'>{right_chunk}</span>")
        return "".join(left_parts), "".join(right_parts)

    def _diff_pane(self, header: str, body_html: str) -> QWidget:
        wrap = QFrame()
        wrap.setStyleSheet(
            f"QFrame {{ background-color: {styles.BG_DEEP}; "
            f"border: 1px solid {styles.BORDER_SUBTLE_RGBA}; "
            f"border-radius: 4px; }}"
        )
        v = QVBoxLayout(wrap)
        v.setContentsMargins(
            styles.SP_SM, styles.SP_SM, styles.SP_SM, styles.SP_SM
        )
        v.setSpacing(styles.SP_XS)

        label = QLabel(header)
        label.setStyleSheet(
            f"color: {styles.TEXT_TERTIARY}; font-size: {styles.FONT_XS}px;"
        )
        v.addWidget(label)

        text = QTextEdit()
        text.setReadOnly(True)
        text.setHtml(
            f"<div style=\"font-family: '{styles.FONT_FAMILY}'; "
            f"font-size: {styles.FONT_SM}px; color: {styles.TEXT_PRIMARY}; "
            f"line-height: 1.4;\">{body_html}</div>"
        )
        text.setStyleSheet(
            f"QTextEdit {{ background-color: transparent; "
            f"color: {styles.TEXT_PRIMARY}; border: none; "
            f"font-family: '{styles.FONT_FAMILY}'; "
            f"font-size: {styles.FONT_SM}px; }}"
        )
        text.setMinimumHeight(80)
        v.addWidget(text, 1)
        return wrap

    def _apply_one(self, patch: SlidePatch) -> None:
        text = self._md_path.read_text(encoding="utf-8")
        new_text = apply_patches_to_text(text, [patch])
        self._md_path.write_text(new_text, encoding="utf-8")
        self._remove_from_store(patch.id)
        self.patches_changed.emit()
        self._reload()

    def _discard_one(self, patch: SlidePatch) -> None:
        self._remove_from_store(patch.id)
        self.patches_changed.emit()
        self._reload()

    def _remove_from_store(self, patch_id: str) -> None:
        store = PatchStore(self._md_path.parent / ".patches.json")
        store.remove(patch_id)
        store.save()
