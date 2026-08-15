"""라이브러리 목록/카드 뷰 전환.

어떤 뷰로 보고 있었는지는 다음 실행까지 기억한다 — 설정 키가 없는 기존
config.json에서는 목록 뷰가 기본이어야 한다.
"""
from __future__ import annotations

import pytest

from flow.ui.screens._browser_widgets import VIEW_CARDS, VIEW_LIST
from flow.ui.screens.library_screen import LibraryScreen


@pytest.fixture
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    return tmp_path


def test_toolbar_emits_the_selected_view(qtbot, isolated_home):
    screen = LibraryScreen()
    qtbot.addWidget(screen)
    seen = []
    screen._toolbar.view_changed.connect(seen.append)

    screen._toolbar.set_view(VIEW_CARDS)

    assert seen == [VIEW_CARDS]


def test_setting_the_same_view_twice_emits_once(qtbot, isolated_home):
    screen = LibraryScreen()
    qtbot.addWidget(screen)
    screen._toolbar.set_view(VIEW_CARDS)
    seen = []
    screen._toolbar.view_changed.connect(seen.append)

    screen._toolbar.set_view(VIEW_CARDS)

    assert seen == []


def test_screen_starts_in_the_saved_view(qtbot, isolated_home):
    from flow.services.config_service import ConfigService

    ConfigService().set_library_view_mode(VIEW_CARDS)

    screen = LibraryScreen()
    qtbot.addWidget(screen)

    assert screen._view_mode == VIEW_CARDS
    assert screen._toolbar.view() == VIEW_CARDS


def test_switching_view_is_remembered(qtbot, isolated_home):
    from flow.services.config_service import ConfigService

    screen = LibraryScreen()
    qtbot.addWidget(screen)

    screen._toolbar.set_view(VIEW_CARDS)
    assert ConfigService().get_library_view_mode() == VIEW_CARDS
    assert screen._view_mode == VIEW_CARDS

    screen._toolbar.set_view(VIEW_LIST)
    assert ConfigService().get_library_view_mode() == VIEW_LIST
