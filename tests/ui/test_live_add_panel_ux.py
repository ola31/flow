"""라이브 곡 추가 패널 UX 테스트

- 좁은 패널(320px)에서도 참조/복사 버튼이 잘리지 않아야 한다
  (긴 곡명 라벨이 카드 최소 폭을 밀어올려 버튼이 화면 밖으로 나가던 버그)
- 검색 입력은 디바운스로 키 입력마다 전체 카드 재생성을 하지 않는다
- 포커스 토글(set_active/set_focus_active)은 전체 하위 위젯 스타일
  재계산을 유발하는 setStyleSheet를 반복 호출하지 않는다
"""
from __future__ import annotations

from pathlib import Path

import pytest


def _make_library(tmp_path: Path, names: list[str]) -> Path:
    import json

    lib = tmp_path / "library"
    for name in names:
        d = lib / name
        d.mkdir(parents=True)
        (d / "slides.md").write_text(f"# {name}\n\n가락 한 줄\n", encoding="utf-8")
        with open(d / "song.json", "w", encoding="utf-8-sig") as f:
            json.dump({"name": name, "sheets": []}, f, ensure_ascii=False)
    return lib


@pytest.fixture
def browser(qtbot, tmp_path):
    from flow.ui.editor.song_list_widget import SongLibraryBrowser

    class _FakeWorkspace:
        def __init__(self, lib):
            self.library_dir = lib

    lib = _make_library(
        tmp_path,
        ["엄청나게 길고 긴 제목의 노래 이름 테스트용", "짧은곡", "중간 길이 제목"],
    )
    br = SongLibraryBrowser(tmp_path / "unused", set(), workspace=_FakeWorkspace(lib))
    qtbot.addWidget(br)
    br.setFixedWidth(300)
    br.resize(300, 500)
    br.show()
    qtbot.waitExposed(br)
    return br


class TestNarrowPanelButtons:
    def test_buttons_inside_viewport_for_long_names(self, browser, qtbot):
        vp_w = browser._scroll.viewport().width()
        assert browser._list_widget.width() <= vp_w, (
            "카드 리스트가 뷰포트보다 넓으면 버튼이 화면 밖으로 잘린다"
        )
        for card in browser._cards:
            for btn in card._add_buttons:
                right = btn.geometry().x() + btn.geometry().width()
                assert right <= card.width(), (
                    f"'{card._name}' 카드의 '{btn.text()}' 버튼이 잘림"
                )


class TestSearchDebounce:
    def test_keystrokes_render_once_after_debounce(self, browser, qtbot, monkeypatch):
        renders = []
        monkeypatch.setattr(
            browser, "_render",
            lambda infos, query="": renders.append(query),
        )

        browser._search.setText("짧")
        browser._search.setText("짧은")
        browser._search.setText("짧은곡")
        assert renders == []  # 디바운스 창 안에서는 즉시 렌더 없음

        qtbot.waitUntil(lambda: len(renders) >= 1, timeout=2000)
        assert renders == ["짧은곡"]  # 마지막 입력으로 1회만


class TestFocusToggleCheap:
    def test_panel_set_active_does_not_reset_stylesheet(self, qtbot, tmp_path):
        from flow.ui.live.live_song_add_panel import LiveSongAddPanel

        panel = LiveSongAddPanel(tmp_path, set(), workspace=None)
        qtbot.addWidget(panel)

        calls = []
        original = panel.setStyleSheet
        panel.setStyleSheet = lambda s: (calls.append(1), original(s))

        panel.set_active(True)
        panel.set_active(False)
        panel.set_active(True)

        assert calls == [], (
            "포커스 토글마다 setStyleSheet하면 하위 위젯 전체가 리폴리시됨"
        )
        assert panel.property("activePanel") is True

    def test_project_screen_focus_active_uses_property(self, qtbot):
        from flow.services.config_service import ConfigService
        from flow.services.slide_manager import SlideManager
        from flow.ui.screens.project_screen import ProjectScreen

        mgr = SlideManager(converter=None)
        try:
            screen = ProjectScreen(mgr, ConfigService())
            qtbot.addWidget(screen)

            calls = []
            original = screen.setStyleSheet
            screen.setStyleSheet = lambda s: (calls.append(1), original(s))

            screen.set_focus_active(True)
            screen.set_focus_active(False)

            assert calls == []
            assert screen.property("focusActive") is False
        finally:
            mgr.shutdown()
