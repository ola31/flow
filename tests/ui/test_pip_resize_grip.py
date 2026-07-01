from __future__ import annotations

from flow.ui.main_window import MainWindow


def test_pip_panel_boundary_is_not_collapsible(qapp):
    """PREVIEW/LIVE 패널 경계를 끝까지 드래그해도 폭 0으로 완전히 사라지면
    안 된다 (Qt QSplitter의 기본 collapsible 동작을 막아야 함)."""
    mw = MainWindow()
    try:
        screen = mw._project_screen
        pip_index = screen.h_splitter.indexOf(screen._pip)
        assert not screen.h_splitter.isCollapsible(pip_index)
    finally:
        mw.close()


def test_grip_hidden_when_not_live(qapp):
    mw = MainWindow()
    try:
        assert not mw._project_screen._pip_grip.isVisible()
    finally:
        mw.close()


def test_grip_visible_after_entering_live_mode(qapp):
    mw = MainWindow()
    try:
        mw.show_project()
        mw.show()
        screen = mw._project_screen
        screen.set_live_mode(True)
        assert screen._pip_grip.isVisible()
    finally:
        mw.close()


def test_grip_hidden_after_leaving_live_mode(qapp):
    mw = MainWindow()
    try:
        mw.show_project()
        mw.show()
        screen = mw._project_screen
        screen.set_live_mode(True)
        screen.set_live_mode(False)
        assert not screen._pip_grip.isVisible()
    finally:
        mw.close()


def test_grip_drag_resizes_but_never_shrinks_pip_below_minimum(qapp):
    mw = MainWindow()
    try:
        screen = mw._project_screen
        grip = screen._pip_grip
        idx = screen.h_splitter.indexOf(screen._pip)
        sizes = [240, 800, 420, 0]

        # 오른쪽(패널 방향)으로 크게 당겨서 최소 폭보다 작아지려 해도
        # min_width 밑으로는 내려가지 않아야 한다.
        huge_drag = 1000
        new_sizes = grip.compute_resized_sizes(sizes, huge_drag)
        assert new_sizes[idx] == screen._pip.minimumWidth()

        # 정상 범위의 드래그는 dx만큼 정확히 반영되어야 한다.
        small_drag = 30
        new_sizes = grip.compute_resized_sizes(sizes, small_drag)
        assert new_sizes[idx] == sizes[idx] - small_drag
        assert new_sizes[idx - 1] == sizes[idx - 1] + small_drag
    finally:
        mw.close()
