"""곡 관리 다이얼로그 - 체크박스 기반 곡 선택"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QInputDialog,
    QMessageBox,
    QLabel,
    QFileDialog,
)
from PySide6.QtCore import Signal, Qt
from pptx import Presentation

from flow.domain.song import Song
from flow.domain.score_sheet import ScoreSheet

if TYPE_CHECKING:
    from flow.domain.project import Project


class SongManagerDialog(QDialog):
    """곡 추가/제거/순서 변경 다이얼로그 (체크박스 기반)"""

    songs_changed = Signal()

    def __init__(self, project_dir: Path, project: Project, parent=None):
        super().__init__(parent)
        self.project_dir = project_dir
        self.project = project
        self.songs_dir = project_dir / "songs"
        self.selected_songs = project.selected_songs
        self._selected_names: set[str] = {s.name for s in self.selected_songs}

        self.setWindowTitle("곡 관리")
        self.setMinimumWidth(500)
        self.setMinimumHeight(450)

        self._setup_ui()
        self._scan_and_load()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        label = QLabel("songs/ 폴더 내 곡 목록 (체크된 곡이 프로젝트에 포함됨):")
        layout.addWidget(label)

        self.song_list = QListWidget()
        self.song_list.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.song_list)

        btn_row1 = QHBoxLayout()

        self.btn_add_new = QPushButton("+ 새 곡 만들기")
        self.btn_add_new.clicked.connect(self._on_add_new_song)
        btn_row1.addWidget(self.btn_add_new)

        self.btn_import = QPushButton("📂 외부에서 가져오기")
        self.btn_import.clicked.connect(self._on_import_song)
        btn_row1.addWidget(self.btn_import)

        self.btn_refresh = QPushButton("🔄 새로고침")
        self.btn_refresh.clicked.connect(self._scan_and_load)
        btn_row1.addWidget(self.btn_refresh)

        layout.addLayout(btn_row1)

        btn_row2 = QHBoxLayout()

        self.btn_up = QPushButton("⬆ 위로")
        self.btn_up.clicked.connect(self._on_move_up)
        btn_row2.addWidget(self.btn_up)

        self.btn_down = QPushButton("⬇ 아래로")
        self.btn_down.clicked.connect(self._on_move_down)
        btn_row2.addWidget(self.btn_down)

        btn_row2.addStretch()

        self.btn_close = QPushButton("닫기")
        self.btn_close.clicked.connect(self._on_close)
        btn_row2.addWidget(self.btn_close)

        layout.addLayout(btn_row2)

    def _scan_and_load(self):
        """songs/ 폴더 스캔하여 모든 곡 표시"""
        self.song_list.blockSignals(True)
        self.song_list.clear()

        if not self.songs_dir.exists():
            self.songs_dir.mkdir(parents=True, exist_ok=True)

        actual_folders = {
            f.name
            for f in self.songs_dir.iterdir()
            if f.is_dir() and (f / "song.json").exists()
        }

        ordered_list = [
            name for name in self.project.song_order if name in actual_folders
        ]
        new_folders = sorted(list(actual_folders - set(ordered_list)))
        ordered_list.extend(new_folders)

        self.project.song_order = ordered_list

        for name in ordered_list:
            item = QListWidgetItem(name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked
                if name in self._selected_names
                else Qt.CheckState.Unchecked
            )
            self.song_list.addItem(item)

        self.song_list.blockSignals(False)

    def _on_item_changed(self, item: QListWidgetItem):
        name = item.text()
        is_checked = item.checkState() == Qt.CheckState.Checked

        if is_checked and name not in self._selected_names:
            song = self._load_song_from_folder(name)
            if song:
                self.selected_songs.append(song)
                self._selected_names.add(name)
                self._sync_selected_order()

        elif not is_checked and name in self._selected_names:
            self.selected_songs = [s for s in self.selected_songs if s.name != name]
            self.project.selected_songs = self.selected_songs
            self._selected_names.discard(name)
            self._reorder_songs()

    def _load_song_from_folder(self, name: str) -> Song | None:
        """폴더에서 Song 객체 로드"""
        song_dir = self.songs_dir / name
        song_json = song_dir / "song.json"

        if not song_json.exists():
            return None

        try:
            with open(song_json, "r", encoding="utf-8-sig") as f:
                data = json.load(f)

            sheets_data = data.get("sheets", [])
            if not sheets_data and data.get("sheet"):
                sheets_data = [data["sheet"]]

            score_sheets = []
            for sd in sheets_data:
                if sd:
                    score_sheets.append(ScoreSheet.from_dict(sd))

            if not score_sheets:
                score_sheets.append(ScoreSheet(name=name))

            song = Song(
                name=name,
                folder=Path("songs") / name,
                score_sheets=score_sheets,
                project_dir=self.project_dir,
            )
            return song

        except Exception as e:
            print(f"곡 로드 실패: {name} - {e}")
            return None

    def _reorder_songs(self):
        """선택된 곡들의 순서 재조정"""
        for i, song in enumerate(self.selected_songs):
            song.order = i + 1

    def _on_add_new_song(self):
        """새 곡 폴더 생성"""
        name, ok = QInputDialog.getText(self, "새 곡", "곡 이름:")
        if not ok or not name.strip():
            return

        name = name.strip()
        song_dir = self.songs_dir / name

        if song_dir.exists():
            QMessageBox.warning(self, "오류", f"'{name}' 폴더가 이미 존재합니다.")
            return

        self.songs_dir.mkdir(exist_ok=True)
        song_dir.mkdir(parents=True)

        self._create_empty_pptx(song_dir / "slides.pptx")
        (song_dir / "sheets").mkdir(exist_ok=True)

        song_data = {"name": name, "sheets": []}
        with open(song_dir / "song.json", "w", encoding="utf-8-sig") as f:
            json.dump(song_data, f, ensure_ascii=False, indent=2)

        self._scan_and_load()
        QMessageBox.information(
            self,
            "완료",
            f"'{name}' 곡이 생성되었습니다.\n체크하여 프로젝트에 추가하세요.",
        )

    def _create_empty_pptx(self, path: Path):
        prs = Presentation()
        blank_layout = prs.slide_layouts[6]
        prs.slides.add_slide(blank_layout)
        prs.save(str(path))

    def _on_import_song(self):
        """외부 곡 폴더를 songs/로 복사"""
        folder = QFileDialog.getExistingDirectory(
            self, "곡 폴더 선택", str(Path.home()), QFileDialog.Option.ShowDirsOnly
        )
        if not folder:
            return

        src = Path(folder)
        name = src.name

        if not (src / "song.json").exists():
            QMessageBox.warning(
                self,
                "오류",
                f"선택한 폴더에 song.json이 없습니다.\n유효한 곡 폴더를 선택하세요.",
            )
            return

        dest = self.songs_dir / name
        self.songs_dir.mkdir(exist_ok=True)

        if dest.exists():
            reply = QMessageBox.question(
                self,
                "확인",
                f"'{name}' 폴더가 이미 존재합니다. 덮어쓰시겠습니까?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            shutil.rmtree(dest)

        shutil.copytree(src, dest)
        self._scan_and_load()

        QMessageBox.information(
            self,
            "완료",
            f"'{name}' 곡을 가져왔습니다.\n체크하여 프로젝트에 추가하세요.",
        )

    def _on_move_up(self):
        """곡 순서를 위로 이동"""
        row = self.song_list.currentRow()
        if row <= 0:
            return

        order = self.project.song_order
        order[row], order[row - 1] = order[row - 1], order[row]

        self._sync_selected_order()
        self._scan_and_load()
        self.song_list.setCurrentRow(row - 1)

    def _on_move_down(self):
        """곡 순서를 아래로 이동"""
        row = self.song_list.currentRow()
        if row < 0 or row >= self.song_list.count() - 1:
            return

        order = self.project.song_order
        order[row], order[row + 1] = order[row + 1], order[row]

        self._sync_selected_order()
        self._scan_and_load()
        self.song_list.setCurrentRow(row + 1)

    def _sync_selected_order(self):
        """song_order에 맞춰 selected_songs 순서 동기화"""
        selected_map = {s.name: s for s in self.selected_songs}

        new_selected = []
        for name in self.project.song_order:
            if name in selected_map:
                new_selected.append(selected_map[name])

        self.project.selected_songs = new_selected
        self.selected_songs = new_selected
        self._reorder_songs()

    def _on_close(self):
        self.songs_changed.emit()
        self.accept()
