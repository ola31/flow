from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget

from flow.ui.project_launcher import ProjectLauncher


class HomeScreen(QWidget):
    project_selected = Signal(str)
    song_selected = Signal(str)
    new_project_requested = Signal()
    new_song_requested = Signal()
    open_project_requested = Signal()
    remove_recent_requested = Signal(str, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._launcher = ProjectLauncher()
        layout.addWidget(self._launcher)

        self._launcher.project_selected.connect(self.project_selected)
        self._launcher.song_selected.connect(self.song_selected)
        self._launcher.new_project_requested.connect(self.new_project_requested)
        self._launcher.new_song_requested.connect(self.new_song_requested)
        self._launcher.open_project_requested.connect(self.open_project_requested)
        self._launcher.remove_recent_requested.connect(self.remove_recent_requested)

    @property
    def launcher(self) -> ProjectLauncher:
        return self._launcher

    def set_recent_items(
        self,
        projects: list[tuple[str, str]],
        songs: list[tuple[str, str]],
    ) -> None:
        self._launcher.set_recent_items(projects, songs)
