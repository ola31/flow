"""SongListWidget UI 테스트

TDD: UI 위젯 통합 테스트
이 테스트는 무한 재귀 같은 시그널/슬롯 상호작용 버그를 잡기 위함
"""

import pytest
from pathlib import Path
from PySide6.QtCore import Qt

from flow.domain.project import Project
from flow.domain.score_sheet import ScoreSheet
from flow.domain.song import Song
from flow.ui.editor.song_list_widget import SongListWidget


@pytest.fixture
def song_list(qtbot):
    """SongListWidget 픽스처"""
    widget = SongListWidget()
    qtbot.addWidget(widget)
    return widget


def _make_song(name: str, sheet_names: list[str]) -> Song:
    """테스트용 Song 생성 (시트마다 image_path 포함)"""
    sheets = [ScoreSheet(name=sn, image_path=f"{sn}.png") for sn in sheet_names]
    return Song(name=name, folder=Path(f"songs/{name}"), score_sheets=sheets)


class TestSongListWidgetBasic:
    """기본 기능 테스트"""

    def test_empty_project(self, song_list):
        """빈 프로젝트로 시작"""
        project = Project(name="테스트")
        song_list.set_project(project)

        # 카드 뷰에서는 _cards 리스트로 확인
        assert len(song_list._cards) == 0

    def test_project_with_songs(self, song_list):
        """곡이 있는 프로젝트"""
        project = Project(name="테스트")
        project.selected_songs = [
            _make_song("곡1", ["시트1"]),
            _make_song("곡2", ["시트2"]),
        ]

        song_list.set_project(project)

        assert len(song_list._cards) == 2


class TestSongListWidgetSelection:
    """선택 동작 테스트 - 무한 재귀 버그 방지"""

    def test_select_song_no_recursion(self, song_list):
        """곡 선택 시 무한 재귀가 발생하지 않아야 함"""
        project = Project(name="테스트")
        project.selected_songs = [
            _make_song("곡1", ["시트1"]),
            _make_song("곡2", ["시트2"]),
            _make_song("곡3", ["시트3"]),
        ]

        song_list.set_project(project)

        # 이 동작이 RecursionError 없이 완료되어야 함
        song_list.set_current_index(0)
        song_list.set_current_index(1)
        song_list.set_current_index(2)
        song_list.set_current_index(0)

        # 현재 인덱스 확인
        assert project.current_sheet_index == 0

    def test_rapid_selection_changes(self, song_list):
        """빠른 선택 변경도 문제없어야 함"""
        project = Project(name="테스트")
        project.selected_songs = [
            _make_song(f"곡{i + 1}", [f"시트{i + 1}"]) for i in range(10)
        ]

        song_list.set_project(project)

        # 빠르게 여러 번 선택 변경
        for _ in range(5):
            for i in range(10):
                song_list.set_current_index(i)

        assert True  # RecursionError 없이 도달하면 성공


class TestSongListWidgetSignals:
    """시그널 발생 테스트"""

    def test_song_selected_signal_emitted(self, song_list, qtbot):
        """카드 클릭으로 곡 선택 시 시그널 발생"""
        project = Project(name="테스트")
        sheet1 = ScoreSheet(name="테스트곡1", image_path="sheet1.png")
        sheet2 = ScoreSheet(name="테스트곡2", image_path="sheet2.png")
        song1 = Song(name="곡1", folder=Path("songs/곡1"), score_sheets=[sheet1])
        song2 = Song(name="곡2", folder=Path("songs/곡2"), score_sheets=[sheet2])
        project.selected_songs = [song1, song2]

        song_list.set_project(project)

        # 카드 클릭을 시뮬레이션 — _on_sheet_selected_direct 직접 호출
        with qtbot.waitSignal(song_list.song_selected, timeout=1000) as blocker:
            song_list._on_sheet_selected_direct(sheet2)

        assert blocker.args[0].name == "테스트곡2"


class TestKeyboardSelectionAutoScroll:
    """방향키 곡 전환 시 선택 카드가 스크롤 밖에 숨지 않아야 함"""

    def _visible_in_viewport(self, song_list, card) -> bool:
        viewport = song_list._scroll.viewport()
        top = card.mapTo(viewport, card.rect().topLeft()).y()
        bottom = card.mapTo(viewport, card.rect().bottomLeft()).y()
        return top < viewport.height() and bottom > 0

    def test_select_next_song_scrolls_selected_card_into_view(
        self, song_list, qtbot
    ):
        project = Project(name="테스트")
        project.selected_songs = [
            _make_song(f"곡{i:02d}", [f"시트{i:02d}"]) for i in range(15)
        ]
        song_list.set_project(project)
        song_list.resize(260, 320)  # 셋리스트가 스크롤될 만큼 낮은 높이
        song_list.show()
        qtbot.waitExposed(song_list)
        song_list.set_current_index(0)
        qtbot.wait(50)

        for _ in range(14):
            assert song_list.select_next_song()
        qtbot.wait(80)  # 선택 시 시트 탭 펼침 → 레이아웃 반영 대기

        assert self._visible_in_viewport(song_list, song_list._cards[14]), (
            "마지막 곡으로 전환했지만 선택 카드가 뷰포트 밖에 있음"
        )

    def test_select_previous_song_scrolls_back_up(self, song_list, qtbot):
        project = Project(name="테스트")
        project.selected_songs = [
            _make_song(f"곡{i:02d}", [f"시트{i:02d}"]) for i in range(15)
        ]
        song_list.set_project(project)
        song_list.resize(260, 320)
        song_list.show()
        qtbot.waitExposed(song_list)
        song_list.set_current_index(14)
        song_list._scroll.verticalScrollBar().setValue(
            song_list._scroll.verticalScrollBar().maximum()
        )
        qtbot.wait(50)

        for _ in range(14):
            assert song_list.select_previous_song()
        qtbot.wait(80)

        assert self._visible_in_viewport(song_list, song_list._cards[0]), (
            "첫 곡으로 전환했지만 선택 카드가 뷰포트 밖에 있음"
        )


class TestArrowSwitchCost:
    """방향키 곡 전환 시 바뀐 카드(이전/새 선택)만 재스타일해야 한다 —
    카드 전체 setStyleSheet는 전환마다 ~28ms를 먹는다."""

    def test_only_changed_cards_restyled(self, song_list, monkeypatch):
        from flow.ui.editor.song_list_widget import _SongCard

        project = Project(name="테스트")
        project.selected_songs = [
            _make_song(f"곡{i}", [f"시트{i}"]) for i in range(5)
        ]
        song_list.set_project(project)
        song_list.set_current_index(0)

        calls = []
        orig = _SongCard.set_selected

        def spy(self, *a, **k):
            calls.append(self._song.name)
            return orig(self, *a, **k)

        monkeypatch.setattr(_SongCard, "set_selected", spy)

        song_list.select_next_song()

        assert sorted(calls) == ["곡0", "곡1"], (
            f"바뀐 카드 2장만 재스타일해야 함: {calls}"
        )


class TestSheetPrefetch:
    """방향키 전환 시 처음 가는 곡은 악보 디코드(~100ms)로 느리다 —
    이웃 시트를 백그라운드에서 미리 디코드해 캐시에 넣는다."""

    def test_prefetch_fills_canvas_cache(self, qtbot, tmp_path):
        from PySide6.QtGui import QColor, QImage

        from flow.ui.editor.score_canvas import ScoreCanvas

        img_path = tmp_path / "page_next.png"
        img = QImage(16, 16, QImage.Format.Format_RGB32)
        img.fill(QColor("#204060"))
        img.save(str(img_path))

        canvas = ScoreCanvas()
        qtbot.addWidget(canvas)
        key = str(img_path)
        assert key not in canvas._pixmap_cache

        canvas.prefetch_images([key])

        qtbot.waitUntil(lambda: key in canvas._pixmap_cache, timeout=3000)
        assert not canvas._pixmap_cache[key].isNull()

    def test_prefetch_skips_cached_and_invalid(self, qtbot, tmp_path):
        from flow.ui.editor.score_canvas import ScoreCanvas

        canvas = ScoreCanvas()
        qtbot.addWidget(canvas)

        # 존재하지 않는 경로·빈 경로는 조용히 무시돼야 함
        canvas.prefetch_images(["", str(tmp_path / "no.png")])
        qtbot.wait(200)
        assert str(tmp_path / "no.png") not in canvas._pixmap_cache


class TestSheetTabsReuse:
    """시트가 많은 곡은 탭 재생성(setStyleSheet ~40ms)이 방향키 전환을
    끊는다 — 시트 구성이 같으면 탭을 재사용하고 활성 상태만 갱신한다."""

    def _card(self, qtbot, song_list):
        project = Project(name="테스트")
        project.selected_songs = [
            _make_song("곡0", [f"시트{i}" for i in range(5)]),
        ]
        song_list.set_project(project)
        return song_list._cards[0], project.selected_songs[0]

    def test_same_structure_reuses_tabs(self, qtbot, song_list):
        card, song = self._card(qtbot, song_list)
        card.set_selected(True, song.score_sheets[0].id)
        tabs_before = card._sheet_tabs[:]
        assert len(tabs_before) == 5

        card.set_selected(True, song.score_sheets[1].id)  # 같은 곡 내 이동

        assert card._sheet_tabs[0] is tabs_before[0]  # 재생성 없음
        assert not card._sheet_tabs[0].isChecked()
        assert card._sheet_tabs[1].isChecked()

    def test_structure_change_rebuilds(self, qtbot, song_list):
        from flow.domain.score_sheet import ScoreSheet

        card, song = self._card(qtbot, song_list)
        card.set_selected(True, song.score_sheets[0].id)
        tabs_before = card._sheet_tabs[:]

        song.score_sheets.append(ScoreSheet(name="새시트", image_path="n.png"))
        card.set_selected(True, song.score_sheets[0].id)

        assert card._sheet_tabs[0] is not tabs_before[0]
        assert len(card._sheet_tabs) == 6
