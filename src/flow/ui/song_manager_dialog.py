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
    QTreeWidget,
    QTreeWidgetItem,
    QInputDialog,
    QMessageBox,
    QLabel,
    QFileDialog,
    QTreeWidgetItemIterator,
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

        # 1. 초기 상태 백업 (취소 기능용)
        self._original_song_order = list(project.song_order)
        self._original_selected_names = {s.name for s in project.selected_songs}
        self._song_backups = {}  # song_name -> list of score_sheets (copies)
        for song in project.selected_songs:
            self._song_backups[song.name] = list(song.score_sheets)

        self.selected_songs = list(project.selected_songs)
        self._selected_names = set(self._original_selected_names)
        self._modified_songs = set()  # 변경된 곡 목록 추적

        self.setWindowTitle("곡 관리")
        self.setMinimumWidth(550)
        self.setMinimumHeight(500)

        self._setup_ui()
        self._scan_and_load()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        label = QLabel("곡 및 시트 관리 (체크된 곡이 프로젝트에 포함됨):")
        layout.addWidget(label)

        self.song_tree = QTreeWidget()
        self.song_tree.setHeaderHidden(True)
        self.song_tree.setIndentation(20)
        self.song_tree.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.song_tree)

        btn_row1 = QHBoxLayout()

        self.btn_add_new = QPushButton("+ 새 곡 만들기")
        self.btn_add_new.clicked.connect(self._on_add_new_song)
        btn_row1.addWidget(self.btn_add_new)

        self.btn_import = QPushButton("📂 외부 가져오기")
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

        self.btn_rename = QPushButton("📝 이름 변경")
        self.btn_rename.clicked.connect(self._on_rename_clicked)
        btn_row2.addWidget(self.btn_rename)

        self.btn_delete = QPushButton("🗑 삭제")
        self.btn_delete.clicked.connect(self._on_delete_clicked)
        btn_row2.addWidget(self.btn_delete)

        layout.addLayout(btn_row2)

        layout.addStretch()

        # 하단 확인/취소 버튼
        footer_layout = QHBoxLayout()
        footer_layout.addStretch()

        self.btn_ok = QPushButton("확인")
        self.btn_ok.setFixedWidth(100)
        self.btn_ok.setStyleSheet(
            "background-color: #2196f3; color: white; font-weight: bold;"
        )
        self.btn_ok.clicked.connect(self._on_ok_clicked)
        footer_layout.addWidget(self.btn_ok)

        self.btn_cancel = QPushButton("취소")
        self.btn_cancel.setFixedWidth(100)
        self.btn_cancel.clicked.connect(self._on_cancel_clicked)
        footer_layout.addWidget(self.btn_cancel)

        layout.addLayout(footer_layout)

    def _scan_and_load(self):
        """songs/ 폴더 스캔하여 모든 곡 및 시트 표시"""
        self.song_tree.blockSignals(True)
        self.song_tree.clear()

        if not self.songs_dir.exists():
            self.songs_dir.mkdir(parents=True, exist_ok=True)

        # 1. 실제 폴더에 존재하는 곡들 스캔
        actual_folders = {
            f.name
            for f in self.songs_dir.iterdir()
            if f.is_dir() and (f / "song.json").exists()
        }

        # 2. 저장된 순서 기반 정렬
        ordered_list = [
            name for name in self.project.song_order if name in actual_folders
        ]
        new_folders = sorted(list(actual_folders - set(ordered_list)))
        ordered_list.extend(new_folders)

        self.project.song_order = ordered_list

        # 3. 트리 리스트 생성
        for name in ordered_list:
            song = next((s for s in self.selected_songs if s.name == name), None)
            if not song:
                song = self._load_song_from_folder(name)

            if not song:
                continue

            # 곡 노드 생성
            song_item = QTreeWidgetItem([song.name])
            song_item.setFlags(song_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            song_item.setData(0, Qt.ItemDataRole.UserRole, song)
            song_item.setCheckState(
                0,
                Qt.CheckState.Checked
                if name in self._selected_names
                else Qt.CheckState.Unchecked,
            )
            font = song_item.font(0)
            font.setBold(True)
            song_item.setFont(0, font)
            self.song_tree.addTopLevelItem(song_item)

            for i, sheet in enumerate(song.score_sheets):
                display_name = sheet.name
                prefix = f"{song.name} -"
                if display_name.startswith(prefix):
                    display_name = display_name[len(prefix) :].strip()

                sheet_item = QTreeWidgetItem([f"  📄 P{i + 1}: {display_name}"])
                sheet_item.setData(0, Qt.ItemDataRole.UserRole, sheet)
                song_item.addChild(sheet_item)

            if name in self._selected_names:
                song_item.setExpanded(True)

        self.song_tree.blockSignals(False)

    def _on_item_changed(self, item: QTreeWidgetItem, column: int):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(data, Song):
            return

        name = data.name
        is_checked = item.checkState(0) == Qt.CheckState.Checked

        if is_checked and name not in self._selected_names:
            self.selected_songs.append(data)
            self._selected_names.add(name)
            self._sync_selected_order()
            item.setExpanded(True)

        elif not is_checked and name in self._selected_names:
            self.selected_songs = [s for s in self.selected_songs if s.name != name]
            self.project.selected_songs = self.selected_songs
            self._selected_names.discard(name)
            self._reorder_songs()
            item.setExpanded(False)

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
        item = self.song_tree.currentItem()
        if not item:
            return

        parent = item.parent()
        if parent:
            idx = parent.indexOfChild(item)
            if idx > 0:
                parent.takeChild(idx)
                parent.insertChild(idx - 1, item)
                self.song_tree.setCurrentItem(item)
                self._sync_sheets_to_song(parent, auto_save=False)
        else:
            idx = self.song_tree.indexOfTopLevelItem(item)
            if idx > 0:
                self.song_tree.takeTopLevelItem(idx)
                self.song_tree.insertTopLevelItem(idx - 1, item)
                self.song_tree.setCurrentItem(item)

                order = self.project.song_order
                order[idx], order[idx - 1] = order[idx - 1], order[idx]
                self._sync_selected_order()

    def _on_move_down(self):
        item = self.song_tree.currentItem()
        if not item:
            return

        parent = item.parent()
        if parent:
            idx = parent.indexOfChild(item)
            if idx < parent.childCount() - 1:
                parent.takeChild(idx)
                parent.insertChild(idx + 1, item)
                self.song_tree.setCurrentItem(item)
                self._sync_sheets_to_song(parent, auto_save=False)
        else:
            idx = self.song_tree.indexOfTopLevelItem(item)
            if idx < self.song_tree.topLevelItemCount() - 1:
                self.song_tree.takeTopLevelItem(idx)
                self.song_tree.insertTopLevelItem(idx + 1, item)
                self.song_tree.setCurrentItem(item)

                order = self.project.song_order
                order[idx], order[idx + 1] = order[idx + 1], order[idx]
                self._sync_selected_order()

    def _sync_sheets_to_song(self, song_item: QTreeWidgetItem, auto_save: bool = True):
        song = song_item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(song, Song):
            return

        new_sheets = []
        for i in range(song_item.childCount()):
            sheet = song_item.child(i).data(0, Qt.ItemDataRole.UserRole)
            if isinstance(sheet, ScoreSheet):
                new_sheets.append(sheet)

        song.score_sheets = new_sheets
        self._modified_songs.add(song)

        if auto_save:
            self._save_song_metadata(song)
            self.songs_changed.emit()

    def _on_ok_clicked(self):
        for song in self._modified_songs:
            self._save_song_metadata(song)

        self.songs_changed.emit()
        self.accept()

    def _on_cancel_clicked(self):
        self.project.song_order = list(self._original_song_order)

        for song_name, sheets in self._song_backups.items():
            song = next(
                (s for s in self.project.selected_songs if s.name == song_name), None
            )
            if song:
                song.score_sheets = list(sheets)

        restored_selected = []
        for name in self.project.song_order:
            if name in self._original_selected_names:
                song = next((s for s in self.selected_songs if s.name == name), None)
                if not song:
                    song = self._load_song_from_folder(name)
                if song:
                    restored_selected.append(song)

        self.project.selected_songs = restored_selected
        self.reject()

    def _on_rename_clicked(self):
        item = self.song_tree.currentItem()
        if not item:
            return

        data = item.data(0, Qt.ItemDataRole.UserRole)
        old_name = data.name if hasattr(data, "name") else item.text(0)

        new_name, ok = QInputDialog.getText(
            self, "이름 변경", "새 이름:", text=old_name
        )
        if ok and new_name.strip():
            data.name = new_name.strip()
            # 곡 이름 변경인 경우 song_order도 업데이트
            if isinstance(data, Song) and old_name in self.project.song_order:
                idx = self.project.song_order.index(old_name)
                self.project.song_order[idx] = data.name
                if old_name in self._selected_names:
                    self._selected_names.discard(old_name)
                    self._selected_names.add(data.name)

            self._save_changes_for_item(item, auto_save=False)
            self._scan_and_load()

    def _save_changes_for_item(self, item: QTreeWidgetItem, auto_save: bool = True):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(data, Song):
            self._modified_songs.add(data)
            if auto_save:
                self._save_song_metadata(data)
        elif isinstance(data, ScoreSheet):
            parent_item = item.parent()
            if parent_item:
                parent_song = parent_item.data(0, Qt.ItemDataRole.UserRole)
                self._modified_songs.add(parent_song)
                if auto_save:
                    self._save_song_metadata(parent_song)

    def _on_close(self):
        # 더 이상 사용되지 않음 (ok/cancel로 대체)
        self.accept()
