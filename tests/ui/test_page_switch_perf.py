"""페이지 전환 성능 테스트 — 내용이 안 바뀌면 재구성 생략.

라이브러리(140곡 카드)·홈(최근 목록)은 방문할 때마다 전부 재생성돼
전환이 느렸다. 지문(fingerprint)이 같으면 기존 위젯을 유지한다.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from flow.ui.screens.library_screen import LibraryScreen


class _FakeWorkspace:
    def __init__(self, lib: Path):
        self.library_dir = lib

    def list_library_songs(self):
        return sorted(
            d for d in self.library_dir.iterdir()
            if d.is_dir() and (d / "song.json").exists()
        )


def _make_library(tmp_path: Path, names: list[str]) -> Path:
    lib = tmp_path / "library"
    for name in names:
        d = lib / name
        d.mkdir(parents=True)
        with open(d / "song.json", "w", encoding="utf-8-sig") as f:
            json.dump({"name": name, "sheets": []}, f, ensure_ascii=False)
    return lib


@pytest.fixture
def screen(qtbot, tmp_path):
    lib = _make_library(tmp_path, ["song_one", "song_two"])
    sc = LibraryScreen()
    qtbot.addWidget(sc)
    sc.set_workspace(_FakeWorkspace(lib))
    return sc


def _first_card(screen):
    for i in range(screen._cards_layout.count()):
        w = screen._cards_layout.itemAt(i).widget()
        if w is not None:
            return w
    return None


def _card_titles(screen):
    titles = []
    for i in range(screen._cards_layout.count()):
        w = screen._cards_layout.itemAt(i).widget()
        if w is not None:
            titles.append(w._title_lbl.text())
    return titles


class TestLibraryRefreshSkip:
    def test_unchanged_library_keeps_cards(self, screen):
        card_before = _first_card(screen)
        assert card_before is not None

        screen.refresh()  # 페이지 재방문 시뮬레이션

        assert _first_card(screen) is card_before  # 재생성 없음

    def test_content_change_updates_card_in_place(self, screen, tmp_path):
        """변경 감지 시 카드 위젯은 재사용하되 내용은 갱신된다.

        카드를 통째로 다시 만들면 검색 한 글자마다 수백 개 QFrame이
        재생성돼 타이핑이 밀린다 — 위젯은 유지하고 텍스트만 갈아끼운다.
        """
        card_before = _first_card(screen)
        assert "슬라이드 없음" in card_before._sub_lbl.text()
        time.sleep(0.01)
        # 슬라이드가 생기면 부제가 "슬라이드 없음" → "마크다운"으로 바뀜
        (tmp_path / "library" / "song_one" / "slides.md").write_text(
            "---\n---\n\n# song_one\n", encoding="utf-8"
        )

        screen.refresh()

        assert _first_card(screen) is card_before  # 위젯은 재사용
        assert "마크다운" in card_before._sub_lbl.text()  # 내용은 갱신

    def test_new_song_appears(self, screen, tmp_path):
        titles_before = _card_titles(screen)
        d = tmp_path / "library" / "song_three"
        d.mkdir()
        with open(d / "song.json", "w", encoding="utf-8-sig") as f:
            json.dump({"name": "song_three", "sheets": []}, f)

        screen.refresh()

        assert "song_three" not in titles_before
        assert "song_three" in _card_titles(screen)

    def test_removed_song_disappears(self, screen, tmp_path):
        import shutil

        shutil.rmtree(tmp_path / "library" / "song_one")

        screen.refresh()

        assert "song_one" not in _card_titles(screen)


class TestRecentItemsSkip:
    def test_same_payload_keeps_cards(self, qtbot, tmp_path):
        from flow.ui.project_launcher import ProjectLauncher

        launcher = ProjectLauncher()
        qtbot.addWidget(launcher)

        song_dir = tmp_path / "recent_song"
        song_dir.mkdir()
        launcher.set_recent_items([], [str(song_dir)])
        cards_before = launcher._song_panel._cards[:]
        assert cards_before

        launcher.set_recent_items([], [str(song_dir)])  # 동일 페이로드

        assert launcher._song_panel._cards[0] is cards_before[0]


class TestHotspotPrewarmAtStartup:
    def test_manager_created_shortly_after_init(self, qtbot, monkeypatch):
        from flow.ui.main_window import MainWindow

        monkeypatch.setattr(MainWindow, "_HOTSPOT_PREWARM_DELAY_MS", 10)
        mw = MainWindow()
        qtbot.addWidget(mw)
        try:
            qtbot.waitUntil(lambda: mw._hotspot is not None, timeout=3000)
        finally:
            mw._slide_manager.shutdown()
            mw._clear_dirty()
            mw.close()


class TestWorkspaceItemsSkip:
    def test_unchanged_workspace_keeps_cards(self, qtbot, tmp_path):
        from flow.ui.project_launcher import ProjectLauncher

        lib = _make_library(tmp_path, ["ws_song_a", "ws_song_b"])

        class _WS:
            name = "test_ws"
            library_dir = lib
            projects_dir = tmp_path / "projects"
            root = tmp_path

            def list_library_songs(self):
                return sorted(
                    d for d in lib.iterdir()
                    if d.is_dir() and (d / "song.json").exists()
                )

            def list_projects(self):
                return []

        _WS.projects_dir.mkdir(exist_ok=True)
        launcher = ProjectLauncher()
        qtbot.addWidget(launcher)
        launcher.set_workspace(_WS())
        cards_before = launcher._song_panel._cards[:]
        assert cards_before

        launcher.refresh_workspace_items()  # 재방문 시뮬레이션

        assert launcher._song_panel._cards[0] is cards_before[0]


class TestHotspotCheapStatus:
    class _CountingBackend:
        def __init__(self):
            self.supported_calls = 0
            self.active_calls = 0

        def is_supported(self):
            self.supported_calls += 1
            return True

        def is_active(self):
            self.active_calls += 1
            return False

        def captive_portal_installed(self):
            return True

    def test_is_supported_cached(self, qapp):
        from flow.services.hotspot import HotspotManager

        backend = self._CountingBackend()
        mgr = HotspotManager(backend=backend)
        mgr.is_supported()
        mgr.is_supported()
        assert backend.supported_calls == 1  # 하드웨어는 안 변함 — 1회만

    def test_last_known_active_uses_poller_state(self, qapp):
        from flow.services.hotspot import HotspotManager

        backend = self._CountingBackend()
        mgr = HotspotManager(backend=backend)
        calls_after_init = backend.active_calls

        assert mgr.last_known_active() is False
        assert mgr.last_known_active() is False
        assert backend.active_calls == calls_after_init  # nmcli 재호출 없음


class TestHomePanelPaintCost:
    def test_home_panels_have_no_blur_shadow(self, qtbot, tmp_path):
        """거대 패널의 QGraphicsDropShadowEffect는 페인트마다 전체
        블러(11ms→실화면 수십 ms)를 유발 — 톤 차이로 깊이를 표현하고
        블러 이펙트는 두지 않는다 (실측 11배 차이)."""
        from PySide6.QtWidgets import QFrame

        from flow.ui.project_launcher import ProjectLauncher

        launcher = ProjectLauncher()
        qtbot.addWidget(launcher)

        panels = launcher.findChildren(QFrame, "HomePanel")
        assert panels, "홈 패널이 있어야 함"
        for panel in panels:
            assert panel.graphicsEffect() is None
