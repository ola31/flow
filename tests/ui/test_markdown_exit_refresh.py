"""마크다운 에디터 복귀 시 슬라이드 목록 갱신.

에디터에서 슬라이드를 추가/삭제하고 매핑 페이지로 돌아오면 하단
슬라이드 리스트가 그대로였다 — 렌더 캐시 무효화만 하고 재카운트와
오프셋 재계산을 안 했기 때문. 저장된 편집이 있으면 편집된 곡의
카운트를 리셋하고 _on_songs_changed 파이프라인을 태운다.
"""
from __future__ import annotations

from flow.domain.project import Project
from flow.domain.song import Song
from flow.ui.main_window import MainWindow


def test_dirty_exit_recounts_edited_song(qtbot, tmp_path, monkeypatch):
    mw = MainWindow()
    qtbot.addWidget(mw)
    try:
        song_dir = tmp_path / "song_a"
        song_dir.mkdir()
        (song_dir / "slides.md").write_text("# p\n가사 한 줄\n", encoding="utf-8")
        song = Song(name="song_a", folder=song_dir)
        song.set_slide_count(3)
        project = Project(name="p")
        project.selected_songs = [song]
        mw._project = project
        mw._project_path = tmp_path / "project.json"
        mw._is_standalone = False

        mw.show_markdown_editor(song)
        monkeypatch.setattr(
            mw._markdown_editor_screen, "is_dirty", lambda: True
        )
        monkeypatch.setattr(
            mw._markdown_editor_screen, "save_if_dirty", lambda: None
        )
        called = []
        monkeypatch.setattr(mw, "_on_songs_changed", lambda: called.append(1))

        mw._exit_markdown_editor()

        assert called == [1], "편집 후 복귀에 재카운트 파이프라인이 안 탐"
        assert song.get_slide_count() == 0  # skip_counted 재카운트 유도
    finally:
        mw._slide_manager.shutdown()
        mw._clear_dirty()
        mw.close()


def test_clean_exit_skips_pipeline(qtbot, tmp_path, monkeypatch):
    mw = MainWindow()
    qtbot.addWidget(mw)
    try:
        song_dir = tmp_path / "song_a"
        song_dir.mkdir()
        (song_dir / "slides.md").write_text("# p\n가사\n", encoding="utf-8")
        song = Song(name="song_a", folder=song_dir)
        song.set_slide_count(3)
        project = Project(name="p")
        project.selected_songs = [song]
        mw._project = project
        mw._project_path = tmp_path / "project.json"
        mw._is_standalone = False

        mw.show_markdown_editor(song)
        called = []
        monkeypatch.setattr(mw, "_on_songs_changed", lambda: called.append(1))

        mw._exit_markdown_editor()

        assert called == []  # 수정 없이 나가면 재로딩도 없다
        assert song.get_slide_count() == 3
    finally:
        mw._slide_manager.shutdown()
        mw._clear_dirty()
        mw.close()


def test_dirty_exit_recounts_in_standalone_too(qtbot, tmp_path, monkeypatch):
    """단독 곡 편집도 같은 파이프라인 — file_changed는 패널만 다시 그린다."""
    mw = MainWindow()
    qtbot.addWidget(mw)
    try:
        song_dir = tmp_path / "song_a"
        song_dir.mkdir()
        (song_dir / "slides.md").write_text("# p\n가사\n", encoding="utf-8")
        song = Song(name="song_a", folder=song_dir)
        song.set_slide_count(3)
        project = Project(name="[곡 편집] song_a")
        project.selected_songs = [song]
        mw._project = project
        mw._project_path = song_dir
        mw._is_standalone = True

        mw.show_markdown_editor(song)
        monkeypatch.setattr(
            mw._markdown_editor_screen, "is_dirty", lambda: True
        )
        monkeypatch.setattr(
            mw._markdown_editor_screen, "save_if_dirty", lambda: None
        )
        called = []
        monkeypatch.setattr(mw, "_on_songs_changed", lambda: called.append(1))

        mw._exit_markdown_editor()

        assert called == [1]
        assert song.get_slide_count() == 0
    finally:
        mw._slide_manager.shutdown()
        mw._clear_dirty()
        mw.close()
