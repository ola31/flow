# tests/ui/test_confirm_dialog.py
"""Two-option keyboard-only confirm dialog (← → to switch, Enter to choose)."""
from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from flow.ui.live.confirm_dialog import ConfirmDialog


def test_default_focus_is_left_option(qtbot) -> None:
    dlg = ConfirmDialog(
        title="확인",
        message="진행할까요?",
        left_label="예",
        right_label="아니오",
    )
    qtbot.addWidget(dlg)
    dlg.show()
    assert dlg.selected_index() == 0  # left


def test_right_arrow_moves_selection_right(qtbot) -> None:
    dlg = ConfirmDialog(
        title="확인", message="?", left_label="A", right_label="B"
    )
    qtbot.addWidget(dlg)
    dlg.show()
    QTest.keyClick(dlg, Qt.Key.Key_Right)
    assert dlg.selected_index() == 1


def test_left_arrow_moves_selection_left(qtbot) -> None:
    dlg = ConfirmDialog(
        title="확인", message="?", left_label="A", right_label="B"
    )
    qtbot.addWidget(dlg)
    dlg.show()
    QTest.keyClick(dlg, Qt.Key.Key_Right)
    QTest.keyClick(dlg, Qt.Key.Key_Left)
    assert dlg.selected_index() == 0


def test_enter_accepts_with_left_chosen(qtbot) -> None:
    dlg = ConfirmDialog(
        title="확인", message="?", left_label="A", right_label="B"
    )
    qtbot.addWidget(dlg)
    dlg.show()
    QTest.keyClick(dlg, Qt.Key.Key_Return)
    assert dlg.result_choice == "left"


def test_enter_accepts_with_right_chosen(qtbot) -> None:
    dlg = ConfirmDialog(
        title="확인", message="?", left_label="A", right_label="B"
    )
    qtbot.addWidget(dlg)
    dlg.show()
    QTest.keyClick(dlg, Qt.Key.Key_Right)
    QTest.keyClick(dlg, Qt.Key.Key_Return)
    assert dlg.result_choice == "right"


def test_escape_closes_with_no_choice(qtbot) -> None:
    dlg = ConfirmDialog(
        title="확인", message="?", left_label="A", right_label="B"
    )
    qtbot.addWidget(dlg)
    dlg.show()
    QTest.keyClick(dlg, Qt.Key.Key_Escape)
    assert dlg.result_choice is None
