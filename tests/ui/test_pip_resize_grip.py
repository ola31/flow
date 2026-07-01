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
