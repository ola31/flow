"""SongListWidget UI 테스트

TDD: UI 위젯 통합 테스트
이 테스트는 무한 재귀 같은 시그널/슬롯 상호작용 버그를 잡기 위함
"""

import pytest
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTreeWidgetItemIterator

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


def _count_sheet_items(tree) -> int:
    """트리에서 ScoreSheet 아이템 개수 세기"""
    count = 0
    it = QTreeWidgetItemIterator(tree)
    while it.value():
        item = it.value()
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(data, ScoreSheet):
            count += 1
        it += 1
    return count


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

        assert _count_sheet_items(song_list._tree) == 0

    def test_project_with_songs(self, song_list):
        """곡이 있는 프로젝트"""
        project = Project(name="테스트")
        project.selected_songs = [
            _make_song("곡1", ["시트1"]),
            _make_song("곡2", ["시트2"]),
        ]

        song_list.set_project(project)

        assert _count_sheet_items(song_list._tree) == 2


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
        """곡 선택 시 시그널 발생"""
        project = Project(name="테스트")
        sheet1 = ScoreSheet(name="테스트곡1", image_path="sheet1.png")
        sheet2 = ScoreSheet(name="테스트곡2", image_path="sheet2.png")
        song1 = Song(name="곡1", folder=Path("songs/곡1"), score_sheets=[sheet1])
        song2 = Song(name="곡2", folder=Path("songs/곡2"), score_sheets=[sheet2])
        project.selected_songs = [song1, song2]

        song_list.set_project(project)

        # 두 번째 곡으로 변경 시 시그널 발생 확인
        with qtbot.waitSignal(song_list.song_selected, timeout=1000) as blocker:
            song_list.set_current_index(1)

        assert blocker.args[0].name == "테스트곡2"
