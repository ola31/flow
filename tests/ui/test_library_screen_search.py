from __future__ import annotations

from pathlib import Path

from flow.domain.workspace import Workspace
from flow.ui.screens._browser_widgets import ItemCard
from flow.ui.screens.library_screen import LibraryScreen


def _add_song(ws: Workspace, name: str, slides_md: str) -> None:
    d = ws.library_song_dir(name)
    d.mkdir(parents=True, exist_ok=True)
    (d / "song.json").write_text(
        f'{{"name":"{name}","sheets":[]}}', encoding="utf-8"
    )
    (d / "slides.md").write_text(slides_md, encoding="utf-8")


def _card_names(screen: LibraryScreen) -> list[str]:
    names = []
    for i in range(screen._cards_layout.count()):
        w = screen._cards_layout.itemAt(i).widget()
        if isinstance(w, ItemCard):
            names.append(Path(w._path).name)
    return names


def _card_for(screen: LibraryScreen, name: str) -> ItemCard:
    for i in range(screen._cards_layout.count()):
        w = screen._cards_layout.itemAt(i).widget()
        if isinstance(w, ItemCard) and Path(w._path).name == name:
            return w
    raise AssertionError(f"card {name!r} not found")


def test_library_screen_searches_lyrics_and_title(qtbot, tmp_path):
    ws = Workspace.create(tmp_path / "ws")
    _add_song(ws, "곡하나", "---\n---\n\n# 곡하나\n\n푸른 바다가 보이네\n")
    _add_song(ws, "곡둘", "---\n---\n\n# 곡둘\n\n노을이 물든다\n")
    screen = LibraryScreen()
    qtbot.addWidget(screen)
    screen.set_workspace(ws)

    # 제목엔 없고 가사에만 있는 단어 → 해당 곡이 보임
    screen._on_search_changed("바다")
    assert _card_names(screen) == ["곡하나"]

    # 제목 검색은 그대로 동작
    screen._on_search_changed("곡둘")
    assert _card_names(screen) == ["곡둘"]


def test_library_screen_shows_lyric_snippet(qtbot, tmp_path):
    ws = Workspace.create(tmp_path / "ws")
    _add_song(ws, "곡하나", "---\n---\n\n# 곡하나\n\n푸른 바다가 보이네\n")
    screen = LibraryScreen()
    qtbot.addWidget(screen)
    screen.set_workspace(ws)

    # 가사로 매칭 → 매칭된 가사 줄이 카드에 표시됨
    screen._on_search_changed("바다")
    assert "바다가 보이네" in _card_for(screen, "곡하나")._match_snippet

    # 제목으로 매칭 → 스니펫 없음
    screen._on_search_changed("곡하나")
    assert _card_for(screen, "곡하나")._match_snippet == ""


class TestSearchDebounce:
    """한글 IME는 자모마다 textChanged를 쏜다 — 입력이 멎은 뒤 한 번만 렌더."""

    def test_typing_does_not_refilter_per_keystroke(self, qtbot, tmp_path):
        ws = Workspace.create(tmp_path / "ws")
        _add_song(ws, "곡하나", "---\n---\n\n# 곡하나\n")
        screen = LibraryScreen()
        qtbot.addWidget(screen)
        screen.set_workspace(ws)

        emitted: list[str] = []
        screen._toolbar.search_changed.connect(emitted.append)

        for text in ("ㄱ", "고", "곡", "곡하"):
            screen._toolbar._search.setText(text)

        assert emitted == [], "입력 중에는 아직 필터링하지 않는다"

        qtbot.waitUntil(lambda: emitted == ["곡하"], timeout=2000)

    def test_clear_search_emits_immediately(self, qtbot, tmp_path):
        ws = Workspace.create(tmp_path / "ws")
        screen = LibraryScreen()
        qtbot.addWidget(screen)
        screen.set_workspace(ws)
        emitted: list[str] = []
        screen._toolbar.search_changed.connect(emitted.append)

        screen._toolbar.clear_search()

        assert emitted == [""]  # 프로그램 호출 경로는 디바운스 없이 즉시


class TestCardReuseAcrossSearch:
    def test_filtering_reuses_card_widgets(self, qtbot, tmp_path):
        ws = Workspace.create(tmp_path / "ws")
        _add_song(ws, "곡하나", "---\n---\n\n# 곡하나\n\n푸른 바다\n")
        _add_song(ws, "곡둘", "---\n---\n\n# 곡둘\n\n노을\n")
        screen = LibraryScreen()
        qtbot.addWidget(screen)
        screen.set_workspace(ws)
        card_before = _card_for(screen, "곡하나")

        screen._on_search_changed("바다")
        assert _card_names(screen) == ["곡하나"]
        screen._on_search_changed("")

        assert _card_for(screen, "곡하나") is card_before
        assert set(_card_names(screen)) == {"곡하나", "곡둘"}


class TestForceRefresh:
    """앱 밖에서 폴더를 고쳤을 때 즉시 반영할 수단 (새로고침 버튼 / F5)."""

    def test_reflects_external_rename(self, qtbot, tmp_path):
        ws = Workspace.create(tmp_path / "ws")
        _add_song(ws, "옛이름", "---\n---\n\n# 옛이름\n")
        screen = LibraryScreen()
        qtbot.addWidget(screen)
        screen.set_workspace(ws)
        assert _card_names(screen) == ["옛이름"]

        # 파일 관리자에서 직접 폴더명을 바꾼 상황
        ws.library_song_dir("옛이름").rename(ws.library_song_dir("새이름"))

        screen.force_refresh()

        assert _card_names(screen) == ["새이름"]

    def test_drops_cached_metadata(self, qtbot, tmp_path):
        from flow.services import song_index

        ws = Workspace.create(tmp_path / "ws")
        _add_song(ws, "곡하나", "---\n---\n\n# 곡하나\n")
        screen = LibraryScreen()
        qtbot.addWidget(screen)
        screen.set_workspace(ws)
        song_dir = ws.library_song_dir("곡하나")
        song_index.song_info(song_dir)  # 캐시 채움
        song_index._INDEX._cache[song_dir][1]["sheet_count"] = 999  # 오염

        screen.force_refresh()

        assert song_index.song_info(song_dir)["sheet_count"] == 0

    def test_rebuilds_even_when_fingerprint_unchanged(self, qtbot, tmp_path):
        ws = Workspace.create(tmp_path / "ws")
        _add_song(ws, "곡하나", "---\n---\n\n# 곡하나\n")
        screen = LibraryScreen()
        qtbot.addWidget(screen)
        screen.set_workspace(ws)

        # 일반 refresh는 지문이 같으면 건너뛴다
        screen.refresh()
        assert screen._last_fingerprint is not None

        screen.force_refresh()

        assert screen._last_fingerprint is not None  # 다시 계산됨
        assert _card_names(screen) == ["곡하나"]

    def test_toolbar_button_triggers_refresh(self, qtbot, tmp_path):
        ws = Workspace.create(tmp_path / "ws")
        _add_song(ws, "곡하나", "---\n---\n\n# 곡하나\n")
        screen = LibraryScreen()
        qtbot.addWidget(screen)
        screen.set_workspace(ws)

        ws.library_song_dir("곡하나").rename(ws.library_song_dir("곡둘"))
        screen._toolbar._btn_refresh.click()

        assert _card_names(screen) == ["곡둘"]
