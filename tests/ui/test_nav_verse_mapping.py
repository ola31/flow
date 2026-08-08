"""라이브 상단 절 버튼 — 매핑이 있는 절과 없는 절을 구분해 보여준다."""
from __future__ import annotations

import pytest

from flow.services.config_service import ConfigService
from flow.services.slide_manager import SlideManager
from flow.ui.screens.project_screen import ProjectScreen


class _NullConverter:
    """변환은 쓰지 않는다. None을 주면 SlideManager가 PowerPoint COM 탐지를
    돌려 테스트가 20초씩 걸리고 콘솔에 예외 덤프를 뱉는다."""


@pytest.fixture
def screen(qtbot):
    mgr = SlideManager(converter=_NullConverter())
    try:
        widget = ProjectScreen(mgr, ConfigService())
        qtbot.addWidget(widget)
        yield widget
    finally:
        mgr.stop_workers()


def _btn(screen: ProjectScreen, verse_index: int):
    """절 인덱스(0~4=1~5절, 5=후렴)로 버튼을 찾는다."""
    return screen._nav_verse_group.button(verse_index)


def _avg_lightness(button) -> float:
    """실제로 그려진 픽셀의 평균 밝기.

    버튼끼리 비교하면 글자가 달라('1절' vs '4절') 안티에일리어싱만으로도
    값이 갈리므로, 반드시 '같은 버튼'의 상태 전후로만 비교할 것.
    """
    button.setFixedSize(48, 26)
    image = button.grab().toImage()
    total = 0
    for y in range(image.height()):
        for x in range(image.width()):
            total += image.pixelColor(x, y).lightness()
    return total / (image.width() * image.height())


class TestNavVerseMappingState:
    def test_all_mapped_by_default(self, screen) -> None:
        """아직 곡 정보를 못 받은 상태에서 멋대로 죽이지 않는다."""
        for button in screen._nav_verse_btns:
            assert button.property("mapped") is True

    def test_unmapped_verses_are_marked(self, screen) -> None:
        # 1~3절만 쓰는 곡 (+ 후렴 있음)
        screen.update_nav_verse_mapping(
            {0: True, 1: True, 2: True, 3: False, 4: False, 5: True}
        )

        assert _btn(screen, 0).property("mapped") is True
        assert _btn(screen, 2).property("mapped") is True
        assert _btn(screen, 3).property("mapped") is False
        assert _btn(screen, 4).property("mapped") is False

    def test_chorus_is_addressed_by_group_id_not_list_position(self, screen) -> None:
        """후렴 버튼은 목록 끝에 있지만 절 인덱스는 5다.

        목록 위치로 짚으면 5절 자리에 후렴 값이 들어가 엉뚱한 버튼이 죽는다.
        """
        screen.update_nav_verse_mapping(
            {0: True, 1: True, 2: True, 3: True, 4: True, 5: False}
        )

        chorus = _btn(screen, 5)
        assert chorus.toolTip() == "후렴"
        assert chorus.property("mapped") is False
        assert _btn(screen, 4).property("mapped") is True, "5절은 멀쩡해야 한다"

    def test_state_flips_back_when_mappings_appear(self, screen) -> None:
        screen.update_nav_verse_mapping({i: False for i in range(6)})
        assert _btn(screen, 3).property("mapped") is False

        screen.update_nav_verse_mapping({i: True for i in range(6)})

        assert _btn(screen, 3).property("mapped") is True

    def test_missing_key_counts_as_unmapped(self, screen) -> None:
        screen.update_nav_verse_mapping({0: True})

        assert _btn(screen, 0).property("mapped") is True
        assert _btn(screen, 4).property("mapped") is False


def _song_with_two_sheets():
    """1·2절은 첫 악보에, 3절은 둘째 악보에 매핑된 곡."""
    from pathlib import Path

    from flow.domain.hotspot import Hotspot
    from flow.domain.project import Project
    from flow.domain.score_sheet import ScoreSheet
    from flow.domain.song import Song

    sheet_a = ScoreSheet(
        name="a", hotspots=[Hotspot(x=10, y=10, slide_mappings={"0": 0, "1": 1})]
    )
    sheet_b = ScoreSheet(
        name="b", hotspots=[Hotspot(x=10, y=10, slide_mappings={"2": 2})]
    )
    song = Song(
        name="곡", folder=Path("songs/곡"), score_sheets=[sheet_a, sheet_b]
    )
    return Project(name="P", selected_songs=[song]), sheet_a


class TestNavVerseMappingSource:
    """판단 단위는 '지금 보는 악보'가 아니라 '곡 전체'다."""

    def test_counts_every_sheet_of_the_song(self, qapp) -> None:
        from flow.ui.main_window import MainWindow

        mw = MainWindow()
        try:
            project, sheet_a = _song_with_two_sheets()
            mw._project = project
            mw._canvas.set_score_sheet(sheet_a)

            mw._update_nav_verse_state()

            group = mw._project_screen._nav_verse_group
            assert group.button(0).property("mapped") is True
            assert group.button(1).property("mapped") is True
            # 3절은 지금 보고 있는 악보가 아니라 둘째 악보에 있다. 시트
            # 단위로 판단하면 여기서 죽어버려 "2절까지 쓰는 곡"으로 보인다.
            assert group.button(2).property("mapped") is True
            assert group.button(3).property("mapped") is False
            assert group.button(4).property("mapped") is False
        finally:
            mw.close()


class TestNavVerseMappingIsVisible:
    def test_marking_a_verse_unmapped_actually_dims_it(self, screen) -> None:
        """프로퍼티만 바뀌고 화면은 그대로면 아무 의미가 없다.

        동적 프로퍼티는 unpolish/polish 없이는 스타일시트에 반영되지 않고,
        스타일 규칙 자체가 없어도 프로퍼티 단언은 그대로 통과한다.
        """
        button = _btn(screen, 3)
        screen.update_nav_verse_mapping({i: True for i in range(6)})
        before = _avg_lightness(button)

        screen.update_nav_verse_mapping({i: i < 3 for i in range(6)})
        after = _avg_lightness(button)

        assert after < before, f"흐려져야 한다 (before={before}, after={after})"

    def test_checked_state_still_readable_when_unmapped(self, screen) -> None:
        """매핑이 없어도 지금 선택된 절이라면 어느 것인지는 보여야 한다."""
        button = _btn(screen, 3)
        screen.update_nav_verse_mapping({i: i < 3 for i in range(6)})

        idle = _avg_lightness(button)
        button.setChecked(True)
        checked = _avg_lightness(button)

        assert checked > idle
