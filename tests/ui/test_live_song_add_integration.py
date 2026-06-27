from __future__ import annotations

from flow.ui.main_window import MainWindow


def test_add_lib_button_enabled_during_live(qapp):
    mw = MainWindow()
    try:
        mw._set_project_editable(False)  # simulate live (edit disabled)
        assert mw._song_list._btn_add_lib.isEnabled()
        assert mw._song_list._btn_new_song.isEnabled() is False
    finally:
        mw.close()
