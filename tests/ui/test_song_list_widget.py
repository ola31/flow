"""SongListWidget UI 테스트

TDD: UI 위젯 통합 테스트
이 테스트는 무한 재귀 같은 시그널/슬롯 상호작용 버그를 잡기 위함
"""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from flow.domain.project import Project
from flow.domain.score_sheet import ScoreSheet
from flow.ui.editor.song_list_widget import SongListWidget


@pytest.fixture
def app():
    """QApplication 픽스처"""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def song_list(app):
    """SongListWidget 픽스처"""
    widget = SongListWidget()
    return widget


class TestSongListWidgetBasic:
    """기본 기능 테스트"""
    
    def test_empty_project(self, song_list):
        """빈 프로젝트로 시작"""
        project = Project(name="테스트")
        song_list.set_project(project)
        
        assert song_list._list.count() == 0
    
    def test_project_with_songs(self, song_list):
        """곡이 있는 프로젝트"""
        project = Project(name="테스트")
        project.add_score_sheet(ScoreSheet(name="곡1"))
        project.add_score_sheet(ScoreSheet(name="곡2"))
        
        song_list.set_project(project)
        
        assert song_list._list.count() == 2


class TestSongListWidgetSelection:
    """선택 동작 테스트 - 무한 재귀 버그 방지"""
    
    def test_select_song_no_recursion(self, song_list):
        """곡 선택 시 무한 재귀가 발생하지 않아야 함"""
        project = Project(name="테스트")
        project.add_score_sheet(ScoreSheet(name="곡1"))
        project.add_score_sheet(ScoreSheet(name="곡2"))
        project.add_score_sheet(ScoreSheet(name="곡3"))
        
        song_list.set_project(project)
        
        # 이 동작이 RecursionError 없이 완료되어야 함
        song_list._list.setCurrentRow(0)
        song_list._list.setCurrentRow(1)
        song_list._list.setCurrentRow(2)
        song_list._list.setCurrentRow(0)
        
        # 현재 인덱스 확인
        assert song_list._list.currentRow() == 0
    
    def test_rapid_selection_changes(self, song_list):
        """빠른 선택 변경도 문제없어야 함"""
        project = Project(name="테스트")
        for i in range(10):
            project.add_score_sheet(ScoreSheet(name=f"곡{i+1}"))
        
        song_list.set_project(project)
        
        # 빠르게 여러 번 선택 변경
        for _ in range(5):
            for i in range(10):
                song_list._list.setCurrentRow(i)
        
        assert True  # RecursionError 없이 도달하면 성공


class TestSongListWidgetSignals:
    """시그널 발생 테스트"""
    
    def test_song_selected_signal_emitted(self, song_list, qtbot):
        """곡 선택 시 시그널 발생"""
        project = Project(name="테스트")
        sheet1 = ScoreSheet(name="테스트곡1")
        sheet2 = ScoreSheet(name="테스트곡2")
        project.add_score_sheet(sheet1)
        project.add_score_sheet(sheet2)
        
        song_list.set_project(project)
        
        # 두 번째 곡으로 변경 시 시그널 발생 확인
        # (set_project에서 blockSignals 사용하므로 첫 선택 후 변경 시 테스트)
        with qtbot.waitSignal(song_list.song_selected, timeout=1000) as blocker:
            song_list._list.setCurrentRow(1)
        
        assert blocker.args[0].name == "테스트곡2"
