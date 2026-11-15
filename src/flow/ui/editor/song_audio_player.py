from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QSize, Qt, QUrl
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap, QRegion
from PySide6.QtMultimedia import QAudioOutput, QMediaDevices, QMediaPlayer
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSlider, QStyle, QVBoxLayout, QWidget

from flow.domain.song import Song
from flow.ui.icons import icon_qicon
from flow.ui.styles import ACCENT, ACCENT_HOVER, BG_ELEVATED, BG_HOVER, BORDER, FONT_SM, SP_SM, SP_LG, TEXT_PRIMARY, TEXT_SECONDARY


class _RoundButton(QPushButton):
    """Paint the circle with antialiasing, independent of inherited QSS."""

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(ACCENT_HOVER if self.underMouse() else ACCENT))
        painter.drawEllipse(self.rect().adjusted(1, 1, -1, -1))
        size = self.iconSize()
        self.icon().paint(painter, (self.width() - size.width()) // 2,
                          (self.height() - size.height()) // 2,
                          size.width(), size.height())


def _pause_icon() -> QIcon:
    pixmap = QPixmap(44, 44)
    pixmap.setDevicePixelRatio(2)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.fillRect(6, 5, 3, 12, QColor(TEXT_PRIMARY))
    painter.fillRect(13, 5, 3, 12, QColor(TEXT_PRIMARY))
    painter.end()
    return QIcon(pixmap)


class SongAudioPlayer(QWidget):
    """Mouse-only local audio controls; never capture slide navigation focus."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        self._expanded = False
        self._files: list[Path] = []
        self._index = 0
        self._player: QMediaPlayer | None = None
        self._output: QAudioOutput | None = None
        self._devices: QMediaDevices | None = None
        self._duration = 0
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(SP_SM)
        self._panel = QFrame(self)
        self._panel.setObjectName("songAudioPanel")
        self._panel.setStyleSheet(
            f"QFrame#songAudioPanel {{ background: {BG_ELEVATED}; "
            f"border: 1px solid {BORDER}; border-radius: 12px; }}"
            f"QLabel {{ background: transparent; border: none; color: {TEXT_SECONDARY}; "
            f"font-size: {FONT_SM}px; }}"
            "QSlider { background: transparent; border: none; }"
            f"QPushButton {{ background: transparent; border: none; "
            "border-radius: 16px; padding: 0px; }"
            f"QPushButton:hover {{ background: {BG_HOVER}; }}"
        )
        panel_layout = QVBoxLayout(self._panel)
        panel_layout.setContentsMargins(SP_LG, SP_LG, SP_LG, SP_LG)
        panel_layout.setSpacing(SP_SM)
        tracks = QHBoxLayout()
        transport = QHBoxLayout()
        progress = QHBoxLayout()
        timing = QHBoxLayout()
        for row in (tracks, progress, timing, transport):
            row.setSpacing(SP_SM)
            panel_layout.addLayout(row)
        root.addWidget(self._panel)
        self._fab = _RoundButton(self)
        self._fab.setFixedSize(44, 44)
        self._fab.setIconSize(QSize(22, 22))
        self._fab.setStyleSheet(
            "QPushButton { background: transparent; border: none; padding: 0px; }"
        )
        self._fab.setAccessibleName("음원 플레이어 펼치기 또는 접기")
        self._fab.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._fab.installEventFilter(self)
        self._fab.clicked.connect(lambda: self.set_expanded(not self._expanded))
        root.addWidget(self._fab, 0, Qt.AlignmentFlag.AlignRight)
        self._previous = QPushButton()
        self._next = QPushButton()
        self._name = QLabel()
        self._name.setMinimumWidth(0)
        self._name.setStyleSheet(f"background: transparent; color: {TEXT_PRIMARY}; border: none;")
        self._play = _RoundButton()
        self._stop = QPushButton()
        for button in (self._previous, self._next, self._play, self._stop):
            button.setFixedSize(32, 32)
            button.setIconSize(QSize(18, 18))
        self._play.setFixedSize(40, 40)
        self._play.setIconSize(QSize(22, 22))
        self._previous.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaSkipBackward))
        self._next.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaSkipForward))
        self._stop.setIcon(icon_qicon("refresh", 18, TEXT_SECONDARY))
        for button, title in ((self._previous, "이전 음원"),
                              (self._next, "다음 음원"),
                              (self._stop, "처음부터 재생")):
            button.setToolTip(title)
            button.setAccessibleName(title)
        self._seek = QSlider(Qt.Orientation.Horizontal)
        self._seek.setRange(0, 0)
        self._seek.setEnabled(False)
        self._seek.setFixedHeight(18)
        self._seek.setStyleSheet(
            "QSlider { background: transparent; border: none; }"
            f"QSlider::groove:horizontal {{ height: 3px; background: {BORDER}; border-radius: 1px; }}"
            f"QSlider::sub-page:horizontal {{ background: {ACCENT}; border-radius: 1px; }}"
            f"QSlider::handle:horizontal {{ background: {TEXT_PRIMARY}; width: 10px; "
            "height: 10px; margin: -4px 0; border-radius: 5px; }"
        )
        self._time = QLabel("0:00 / 0:00")
        self._message = QLabel()
        self._message.setStyleSheet(f"color: {TEXT_SECONDARY};")
        volume_row = QHBoxLayout()
        volume_row.setSpacing(SP_SM)
        volume_label = QLabel("볼륨")
        self._volume = QSlider(Qt.Orientation.Horizontal)
        self._volume.setRange(0, 100)
        self._volume.setValue(100)
        self._volume.setFixedHeight(18)
        self._volume.setStyleSheet(self._seek.styleSheet())
        self._volume.setAccessibleName("음원 볼륨")
        self._volume.setToolTip("Flow 음원 볼륨 · 시스템 볼륨은 유지됩니다")
        self._volume_value = QLabel("100%")
        self._volume_value.setFixedWidth(40)
        self._volume_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        volume_row.addWidget(volume_label)
        volume_row.addWidget(self._volume, 1)
        volume_row.addWidget(self._volume_value)
        panel_layout.addLayout(volume_row)
        self._volume.valueChanged.connect(self._set_volume)
        for control in (self._previous, self._name, self._next, self._play,
                        self._stop, self._seek, self._time, self._message,
                        self._volume):
            control.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            control.installEventFilter(self)
        tracks.addWidget(self._name, 1)
        transport.addStretch()
        transport.addWidget(self._previous)
        transport.addWidget(self._play)
        transport.addWidget(self._stop)
        transport.addWidget(self._next)
        transport.addStretch()
        progress.addWidget(self._seek, 1)
        timing.addWidget(self._message, 1)
        timing.addWidget(self._time)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._previous.clicked.connect(lambda: self._change_track(-1))
        self._next.clicked.connect(lambda: self._change_track(1))
        self._play.clicked.connect(self._toggle_play)
        self._stop.clicked.connect(self._restart)
        self._seek.sliderMoved.connect(self._preview_position)
        self._seek.sliderReleased.connect(self._seek_to_position)
        self._seek.actionTriggered.connect(self._seek_action)
        if parent is not None:
            parent.installEventFilter(self)
        self._state_changed(QMediaPlayer.PlaybackState.StoppedState)
        self.set_expanded(False)
        self.hide()

    def set_expanded(self, expanded: bool) -> None:
        # Hide only the panel, never the player: collapsing must keep playback.
        self._expanded = expanded
        self._panel.setVisible(expanded)
        self._place_overlay()

    def _place_overlay(self) -> None:
        parent = self.parentWidget()
        width = min(320, max(44, parent.width() - 24)) if parent else 320
        height = self._panel.sizeHint().height() + SP_SM + 44
        self.setFixedSize(width if self._expanded else 44,
                          height if self._expanded else 44)
        self.layout().activate()
        # The transparent area beside the round button must pass clicks through.
        # Keep the antialiased edge intact; an elliptical QRegion is pixelated.
        mask = QRegion(self._fab.geometry())
        if self._expanded:
            mask |= QRegion(self._panel.geometry())
        self.setMask(mask)
        if parent is not None:
            self.move(max(0, parent.width() - self.width() - 12),
                      max(0, parent.height() - self.height() - 12))
            self.raise_()
        self._update_track_title()

    def _update_track_title(self) -> None:
        title = self._files[self._index].stem if self._files else ""
        self._name.setText(self._name.fontMetrics().elidedText(
            title, Qt.TextElideMode.ElideRight, max(0, self.width() - 2 * SP_LG)
        ))

    def eventFilter(self, watched, event) -> bool:
        if watched is self.parentWidget():
            if event.type() in (QEvent.Type.Resize, QEvent.Type.Show):
                self._place_overlay()
            return False
        # No keyboard activation even if a control receives a synthetic key.
        # ShortcutOverride is deliberately untouched: application shortcuts win.
        if event.type() in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease,
                            QEvent.Type.Wheel):
            return True
        return super().eventFilter(watched, event)

    def set_song(self, song: Song | None) -> None:
        files = song.audio_files if song else []
        if files != self._files:
            self.stop()
            self._files = files
            self._index = 0
            self._refresh_track()
            self.set_expanded(False)
        self.setVisible(bool(files))
        self._place_overlay()

    def _refresh_track(self) -> None:
        self._name.setToolTip(self._files[self._index].name if self._files else "")
        self._update_track_title()
        self._previous.setVisible(len(self._files) > 1)
        self._next.setVisible(len(self._files) > 1)
        self._message.clear()

    def _change_track(self, offset: int) -> None:
        if not self._files:
            return
        self.stop()
        self._index = (self._index + offset) % len(self._files)
        self._refresh_track()

    def _ensure_player(self) -> QMediaPlayer:
        # No audio device/backend is opened until the user clicks Play.
        if self._player is None:
            self._devices = QMediaDevices(self)
            self._devices.audioOutputsChanged.connect(self._sync_output_device)
            self._output = QAudioOutput(self)
            self._sync_output_device()
            self._set_volume(self._volume.value())
            self._player = QMediaPlayer(self)
            self._player.setAudioOutput(self._output)
            self._player.playbackStateChanged.connect(self._state_changed)
            self._player.durationChanged.connect(self._duration_changed)
            self._player.positionChanged.connect(self._position_changed)
            self._player.seekableChanged.connect(self._seek.setEnabled)
            self._player.errorOccurred.connect(self._error)
        return self._player

    def _sync_output_device(self) -> None:
        """Follow system output changes (Bluetooth/USB) without changing volume."""
        if self._output is not None:
            device = QMediaDevices.defaultAudioOutput()
            if self._output.device() != device:
                self._output.setDevice(device)

    def _set_volume(self, value: int) -> None:
        self._volume_value.setText(f"{value}%")
        if self._output is not None:
            # Adjust only this media output's gain, never the system mixer.
            self._output.setVolume(value / 100.0)

    def _toggle_play(self) -> None:
        if not self._files:
            return
        player = self._ensure_player()
        self._sync_output_device()
        if player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            player.pause()
            return
        path = self._files[self._index]
        if not path.is_file():
            self._error(None, "음원 파일이 없습니다. 곡 폴더를 확인하세요.")
            return
        self._message.clear()
        source = QUrl.fromLocalFile(str(path))
        if player.source() != source:
            player.setSource(source)
        if player.mediaStatus() == QMediaPlayer.MediaStatus.EndOfMedia:
            player.setPosition(0)
        player.play()

    def stop(self) -> None:
        if self._player is not None:
            self._player.stop()
            self._player.setSource(QUrl())
        self._state_changed(QMediaPlayer.PlaybackState.StoppedState)
        self._duration_changed(0)
        self._position_changed(0)
        self._seek.setEnabled(False)

    def _restart(self) -> None:
        self.stop()
        self._toggle_play()

    def _state_changed(self, state) -> None:
        playing = state == QMediaPlayer.PlaybackState.PlayingState
        self._fab.setIcon(icon_qicon("play" if playing else "music_note", 22, TEXT_PRIMARY))
        self._fab.setToolTip("음원 재생 중 · 플레이어 펼치기/접기" if playing else "음원 플레이어 펼치기/접기")
        title = "일시정지" if playing else "재생"
        self._play.setToolTip(title)
        self._play.setAccessibleName(title)
        self._play.setIcon(
            _pause_icon()
            if playing else icon_qicon("play", 22, TEXT_PRIMARY)
        )

    @staticmethod
    def _clock(milliseconds: int) -> str:
        seconds = max(0, milliseconds) // 1000
        return f"{seconds // 60}:{seconds % 60:02d}"

    def _duration_changed(self, duration: int) -> None:
        self._duration = duration
        self._seek.setRange(0, duration)
        self._preview_position(self._seek.value())

    def _preview_position(self, position: int) -> None:
        self._time.setText(f"{self._clock(position)} / {self._clock(self._duration)}")

    def _position_changed(self, position: int) -> None:
        if not self._seek.isSliderDown():
            self._seek.setValue(position)
            self._preview_position(position)

    def _seek_to_position(self) -> None:
        if self._player is not None and self._player.isSeekable():
            self._player.setPosition(self._seek.sliderPosition())

    def _seek_action(self, action: int) -> None:
        if not self._seek.isSliderDown():
            self._seek_to_position()

    def _error(self, error, message: str) -> None:
        self.stop()
        self._message.setText("재생 실패")
        self._message.setToolTip(message)

    def hideEvent(self, event) -> None:
        self.stop()
        super().hideEvent(event)
