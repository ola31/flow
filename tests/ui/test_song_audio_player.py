from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QObject, Qt, QUrl, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import QLineEdit, QVBoxLayout, QWidget

from flow.domain.song import Song
from flow.ui.editor import song_audio_player as audio


class FakePlayer(QObject):
    PlaybackState = QMediaPlayer.PlaybackState
    MediaStatus = QMediaPlayer.MediaStatus
    playbackStateChanged = Signal(object)
    durationChanged = Signal(int)
    positionChanged = Signal(int)
    seekableChanged = Signal(bool)
    errorOccurred = Signal(object, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.state = self.PlaybackState.StoppedState
        self.url = QUrl()
        self.position = 0

    def setAudioOutput(self, output):
        pass

    def playbackState(self):
        return self.state

    def _set_state(self, state):
        self.state = state
        self.playbackStateChanged.emit(state)

    def play(self):
        self._set_state(self.PlaybackState.PlayingState)

    def pause(self):
        self._set_state(self.PlaybackState.PausedState)

    def stop(self):
        self.setPosition(0)
        self._set_state(self.PlaybackState.StoppedState)

    def source(self):
        return self.url

    def setSource(self, source):
        self.url = source
        self.durationChanged.emit(125000 if not source.isEmpty() else 0)
        self.seekableChanged.emit(not source.isEmpty())

    def mediaStatus(self):
        return self.MediaStatus.LoadedMedia

    def isSeekable(self):
        return not self.url.isEmpty()

    def setPosition(self, position):
        self.position = position
        self.positionChanged.emit(position)


def song_at(tmp_path: Path, name="song", files=("MR.mp3",)):
    folder = tmp_path / name
    folder.mkdir(exist_ok=True)
    for filename in files:
        (folder / filename).write_bytes(b"audio fixture")
    return Song(name=name, folder=folder)


@pytest.fixture
def player(qtbot, monkeypatch, tmp_path):
    monkeypatch.setattr(audio, "QMediaPlayer", FakePlayer)
    monkeypatch.setattr(audio, "QAudioOutput", QObject)
    widget = audio.SongAudioPlayer()
    qtbot.addWidget(widget)
    widget.set_song(song_at(tmp_path))
    widget.set_expanded(True)
    return widget


def test_detect_audio_relative_paths_and_case(tmp_path):
    song_at(tmp_path, files=("z.WAV", "a.MP3", "lyrics.txt"))
    (tmp_path / "song" / "directory.mp3").mkdir()
    song = Song(name="song", folder=Path("song"), project_dir=tmp_path)
    assert [p.name for p in song.audio_files] == ["a.MP3", "z.WAV"]
    assert Song(name="missing", folder=tmp_path / "missing").audio_files == []


def test_lazy_play_pause_stop_and_time(player, qtbot):
    assert player._player is None
    qtbot.mouseClick(player._play, Qt.MouseButton.LeftButton)
    backend = player._player
    assert backend.playbackState() == FakePlayer.PlaybackState.PlayingState
    assert player._time.text() == "0:00 / 2:05"
    backend.setPosition(65000)
    assert player._time.text() == "1:05 / 2:05"
    assert player._seek.value() == 65000
    qtbot.mouseClick(player._play, Qt.MouseButton.LeftButton)
    assert backend.playbackState() == FakePlayer.PlaybackState.PausedState
    qtbot.mouseClick(player._play, Qt.MouseButton.LeftButton)
    assert backend.position == 65000
    player.stop()
    assert backend.position == 0
    assert backend.source().isEmpty()
    assert player._play.toolTip() == "재생"


def test_seek_and_drag_not_overwritten_by_playback(player, qtbot):
    qtbot.mouseClick(player._play, Qt.MouseButton.LeftButton)
    player._seek.setSliderDown(True)
    player._seek.setSliderPosition(90000)
    player._player.setPosition(5000)
    assert player._seek.sliderPosition() == 90000
    player._seek.setSliderDown(False)
    assert player._player.position == 90000


def test_restart_button_plays_from_start_even_when_paused(player, qtbot):
    qtbot.mouseClick(player._play, Qt.MouseButton.LeftButton)
    player._player.setPosition(65000)
    qtbot.mouseClick(player._play, Qt.MouseButton.LeftButton)
    assert player._player.position == 65000
    qtbot.mouseClick(player._stop, Qt.MouseButton.LeftButton)
    assert player._player.position == 0
    assert player._player.playbackState() == FakePlayer.PlaybackState.PlayingState
    assert player._play.text() == ""
    assert player._stop.toolTip() == "처음부터 재생"


def test_same_song_keeps_playback_new_song_stops(player, qtbot, tmp_path):
    qtbot.mouseClick(player._play, Qt.MouseButton.LeftButton)
    player._player.setPosition(12000)
    player.set_song(Song(name="song", folder=tmp_path / "song"))
    assert player._player.position == 12000
    player.set_song(song_at(tmp_path, "second"))
    assert player._player.source().isEmpty()
    assert player._play.toolTip() == "재생"
    player.set_song(song_at(tmp_path, "silent", files=()))
    assert player.isHidden()


def test_track_selection_stops_and_does_not_autoplay(player, qtbot, tmp_path):
    player.set_song(song_at(tmp_path, "multi", files=("a.mp3", "b.mp3")))
    qtbot.mouseClick(player._play, Qt.MouseButton.LeftButton)
    qtbot.mouseClick(player._next, Qt.MouseButton.LeftButton)
    assert player._name.toolTip() == "b.mp3"
    assert player._player.source().isEmpty()


def test_hiding_stops_and_releases_file(player, qtbot):
    qtbot.mouseClick(player._play, Qt.MouseButton.LeftButton)
    player.hide()
    assert player._player.source().isEmpty()


def test_errors_reset_controls_without_modal(player, qtbot):
    qtbot.mouseClick(player._play, Qt.MouseButton.LeftButton)
    player._player.errorOccurred.emit(None, "unsupported format")
    assert player._message.text() == "재생 실패"
    assert player._play.toolTip() == "재생"
    assert not player._seek.isEnabled()


def test_missing_file_does_not_play(player, qtbot):
    player._files[0].unlink()
    qtbot.mouseClick(player._play, Qt.MouseButton.LeftButton)
    assert player._player.source().isEmpty()
    assert player._message.text() == "재생 실패"


def test_mouse_controls_do_not_take_focus_or_consume_shortcuts(player, qtbot):
    host = QWidget()
    qtbot.addWidget(host)
    layout = QVBoxLayout(host)
    focus_target = QLineEdit()
    layout.addWidget(focus_target)
    layout.addWidget(player)
    host.show()
    host.activateWindow()
    focus_target.setFocus()
    qtbot.waitUntil(focus_target.hasFocus)
    shortcut = QShortcut(QKeySequence("F5"), host)
    triggered = []
    shortcut.activated.connect(lambda: triggered.append(True))
    qtbot.mouseClick(player._play, Qt.MouseButton.LeftButton)
    assert focus_target.hasFocus()
    qtbot.keyClick(focus_target, Qt.Key.Key_F5)
    assert triggered == [True]
    for control in (player._play, player._stop, player._seek,
                    player._previous, player._next):
        assert control.focusPolicy() == Qt.FocusPolicy.NoFocus
        qtbot.keyClick(control, Qt.Key.Key_Space)
        qtbot.keyClick(control, Qt.Key.Key_Right)
    assert player._player.playbackState() == FakePlayer.PlaybackState.PlayingState
    assert player._player.position == 0

    # Keep the fixture-owned widget alive until pytest-qt tears it down.
    layout.removeWidget(player)
    player.setParent(None)


def test_main_window_selection_sync(qtbot, tmp_path):
    from flow.domain.project import Project
    from flow.domain.score_sheet import ScoreSheet
    from flow.ui.main_window import MainWindow

    window = MainWindow()
    qtbot.addWidget(window)
    song = song_at(tmp_path)
    sheet = ScoreSheet(name="page")
    song.score_sheets.append(sheet)
    window._project = Project(name="test", selected_songs=[song])
    window._sync_song_audio(sheet)
    assert window._project_screen.audio_player._files == song.audio_files
    window._project.selected_songs.clear()
    window._sync_song_audio(sheet)
    assert window._project_screen.audio_player.isHidden()
    window._is_dirty = False
    window.close()


def test_real_backend_loads_audio_and_reports_duration(qtbot, tmp_path):
    """Exercise Qt's real decoder, muted and offscreen; no manual GUI smoke."""
    import wave

    song = song_at(tmp_path, files=())
    with wave.open(str(song.folder / "MR.wav"), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(8000)
        stream.writeframes(b"\x00\x00" * 80000)
    widget = audio.SongAudioPlayer()
    qtbot.addWidget(widget)
    widget.set_song(song)
    widget.set_expanded(True)
    widget._ensure_player()
    widget._output.setMuted(True)
    qtbot.mouseClick(widget._play, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: widget._duration == 10000, timeout=10000)
    assert Path(widget._player.source().toLocalFile()) == song.folder / "MR.wav"
    qtbot.waitUntil(widget._player.isSeekable)
    widget._seek.setSliderPosition(4000)
    widget._seek_to_position()
    assert widget._player.position() >= 4000
    widget.stop()
    assert widget._player.source().isEmpty()


def test_markdown_screen_detects_song_audio(qtbot, tmp_path):
    from flow.ui.screens.markdown_editor_screen import MarkdownEditorScreen

    song = song_at(tmp_path)
    song.markdown_path.write_text("# Song\n\nLyrics", encoding="utf-8")
    screen = MarkdownEditorScreen()
    qtbot.addWidget(screen)
    screen.load_song(song)
    assert screen.audio_player._files == song.audio_files
    silent = song_at(tmp_path, "silent", files=())
    silent.markdown_path.write_text("# Silent", encoding="utf-8")
    screen.load_song(silent)
    assert screen.audio_player.isHidden()


def test_collapsing_keeps_playback_and_position(player, qtbot):
    qtbot.mouseClick(player._play, Qt.MouseButton.LeftButton)
    player._player.setPosition(12000)
    qtbot.mouseClick(player._fab, Qt.MouseButton.LeftButton)
    assert not player._expanded
    assert player.size().width() == player.size().height() == 44
    assert player._panel.isHidden()
    assert player._player.position == 12000
    assert player._player.playbackState() == FakePlayer.PlaybackState.PlayingState
    qtbot.mouseClick(player._fab, Qt.MouseButton.LeftButton)
    assert player._expanded
    assert not player._panel.isHidden()
    assert player._fab.focusPolicy() == Qt.FocusPolicy.NoFocus


def test_overlay_anchors_without_consuming_layout_space(qtbot, tmp_path):
    host = QWidget()
    qtbot.addWidget(host)
    host.resize(800, 600)
    layout = QVBoxLayout(host)
    canvas = QWidget()
    layout.addWidget(canvas)
    overlay = audio.SongAudioPlayer(host)
    host.show()
    before = canvas.geometry()
    overlay.set_song(song_at(tmp_path))
    assert layout.indexOf(overlay) == -1
    assert overlay.x() == 800 - 44 - 12
    assert overlay.y() == 600 - 44 - 12
    overlay.set_expanded(True)
    assert canvas.geometry() == before
    host.resize(640, 480)
    assert overlay.x() + overlay.width() == 640 - 12
    assert overlay.y() + overlay.height() == 480 - 12
    assert not overlay.mask().contains(overlay.rect().bottomLeft())
