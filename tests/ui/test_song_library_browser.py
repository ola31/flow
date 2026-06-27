from __future__ import annotations

from PySide6.QtWidgets import QPushButton

from flow.ui.editor.song_list_widget import _LibrarySongCard

_INFO = {
    "name": "곡A", "sheet_count": 1, "has_ppt": False, "has_md": True,
    "total_hotspots": 0, "mapped_hotspots": 0,
}


def test_card_added_state_disables_add_buttons(qtbot):
    card = _LibrarySongCard(_INFO, workspace_mode=True, added=True)
    qtbot.addWidget(card)
    add_buttons = [
        b for b in card.findChildren(QPushButton)
        if b.text() in ("참조", "복사")
    ]
    assert add_buttons, "참조/복사 버튼이 있어야 함"
    assert all(not b.isEnabled() for b in add_buttons)
    from PySide6.QtWidgets import QLabel
    labels = [lbl.text() for lbl in card.findChildren(QLabel)]
    assert any("이미 추가" in t for t in labels)


def test_card_set_added_toggles_state(qtbot):
    card = _LibrarySongCard(_INFO, workspace_mode=True, added=False)
    qtbot.addWidget(card)
    add_buttons = [
        b for b in card.findChildren(QPushButton)
        if b.text() in ("참조", "복사")
    ]
    assert all(b.isEnabled() for b in add_buttons)
    card.set_added(True)
    assert all(not b.isEnabled() for b in add_buttons)
