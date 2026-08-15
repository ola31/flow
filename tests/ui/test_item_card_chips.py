"""곡 카드의 상태를 문장 대신 칩으로 보여준다.

"악보 4장 · .md · 매핑 12"를 한 줄 문장으로 두면 훑을 때 눈이 매번 문장을
읽어야 한다. 칩으로 끊으면 같은 자리에 같은 정보가 오므로 열로 읽힌다.
문제 있는 항목만 앰버로 남긴다.
"""
from __future__ import annotations

from flow.ui.screens._browser_widgets import ItemCard


def _card(qtbot) -> ItemCard:
    card = ItemCard(path="/tmp/song_a", title="song_a", subtitle="악보 4장")
    qtbot.addWidget(card)
    return card


def test_chips_replace_the_subtitle_sentence(qtbot):
    card = _card(qtbot)

    card.set_chips([("악보 4장", False), (".md", False), ("매핑 12", False)])

    assert card.chip_texts() == ["악보 4장", ".md", "매핑 12"]
    assert card._sub_lbl.isHidden()


def test_a_problem_chip_is_marked(qtbot):
    card = _card(qtbot)

    card.set_chips([("악보 없음", True), (".md", False)])

    assert card.warned_chips() == ["악보 없음"]


def test_fewer_chips_hide_the_leftovers(qtbot):
    """칩 위젯은 재사용한다 — 개수가 줄면 남는 칩은 숨긴다."""
    card = _card(qtbot)
    card.set_chips([("a", False), ("b", False), ("c", False)])

    card.set_chips([("a", False)])

    assert card.chip_texts() == ["a"]


def test_no_chips_restores_the_subtitle(qtbot):
    card = _card(qtbot)
    card.set_chips([("악보 4장", False)])

    card.set_chips([])

    assert card.chip_texts() == []
    assert not card._sub_lbl.isHidden()


def test_path_hint_can_be_hidden(qtbot):
    """분류 안 목록에서는 경로가 소음이다."""
    card = ItemCard(
        path="/tmp/song_a", title="song_a", subtitle="악보 4장", show_path=False
    )
    qtbot.addWidget(card)

    assert card._path_lbl.isHidden()
