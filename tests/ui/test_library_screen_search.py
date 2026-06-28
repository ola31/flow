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
