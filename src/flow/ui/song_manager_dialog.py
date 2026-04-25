"""곡 관리 다이얼로그 - 체크박스 및 트리 기반 곡/시트 관리"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QDialog,
    QWidget,
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
    QSizePolicy,
)
from PySide6.QtCore import Signal, Qt, QTimer
from PySide6.QtGui import QColor
from pptx import Presentation

from flow.domain.song import Song
from flow.domain.score_sheet import ScoreSheet

if TYPE_CHECKING:
    from flow.domain.project import Project


class SongManagerDialog(QDialog):
    """곡 추가/제거/순서 변경 다이얼로그 (트리 기반 통합 관리)"""

    songs_changed = Signal()

    def __init__(
        self,
        project_dir: Path,
        project: Project,
        is_standalone: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self.project_dir = project_dir
        self.project = project
        self.songs_dir = project_dir / "songs"
        self.is_standalone = is_standalone

        # 1. 초기 상태 전체 백업 (취소 기능용)
        self._original_song_order = list(project.song_order)
        self._original_selected_names = {s.name for s in project.selected_songs}

        # 모든 곡 객체의 상세 상태 저장 (이름, 시트 목록)
        self._song_snapshots = {}  # id(song_obj) -> {name, sheets}
        # 프로젝트에 포함된 곡뿐만 아니라 로드될 수 있는 모든 곡에 대해 스냅샷을 찍어야 함
        # 하지만 일단은 현재 선택된 곡들과 로드된 곡들 위주로 관리
        for song in project.selected_songs:
            self._song_snapshots[id(song)] = {
                "name": song.name,
                "sheets": list(song.score_sheets),
            }

        self.selected_songs = list(project.selected_songs)
        self._selected_names = set(self._original_selected_names)
        self._modified_songs = {}  # name -> song_obj

        self.setWindowTitle("곡 관리")
        self.setMinimumWidth(550)
        self.setMinimumHeight(500)

        self._setup_ui()
        self._scan_and_load()

    def _setup_ui(self):
        from flow.ui.styles import (
            BG_DEEP, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_TERTIARY,
            ACCENT_INTER, BORDER_SUBTLE_RGBA, BORDER_STANDARD_RGBA,
            SURFACE_SUBTLE, SURFACE_RAISED,
            FONT_MD, FONT_LG, FW_MEDIUM, FW_SEMI,
            RADIUS_MD, SP_SM,
        )

        layout = QVBoxLayout(self)
        layout.setSpacing(SP_SM + 2)

        # 1. 안내 문구
        label = QLabel("곡 및 시트 관리 (순서 변경 및 편집)")
        label.setStyleSheet(
            f"font-weight: {FW_SEMI}; color: {TEXT_PRIMARY}; font-size: {FONT_LG}px;"
        )
        layout.addWidget(label)

        # 2. 트리 위젯 (2열 구조: 0=체크박스, 1=이름 및 버튼)
        self.song_tree = QTreeWidget()
        self.song_tree.setColumnCount(2)
        self.song_tree.setHeaderHidden(True)
        self.song_tree.setIndentation(20)
        self.song_tree.setAlternatingRowColors(False)
        self.song_tree.setDragEnabled(False)
        self.song_tree.setAcceptDrops(False)
        self.song_tree.setColumnWidth(0, 40)

        self.song_tree.setStyleSheet(f"""
            QTreeWidget {{
                background-color: {BG_DEEP};
                border: 1px solid {BORDER_STANDARD_RGBA};
                border-radius: {RADIUS_MD}px;
                outline: none;
                color: {TEXT_SECONDARY};
            }}
            QTreeWidget::item {{
                height: 32px;
                border-bottom: 1px solid {BORDER_SUBTLE_RGBA};
            }}
            QTreeWidget::item:hover {{ background-color: {SURFACE_SUBTLE}; }}
            QTreeWidget::item:selected {{
                background-color: {SURFACE_RAISED};
                color: {ACCENT_INTER};
                font-weight: {FW_SEMI};
            }}
        """)
        self.song_tree.itemChanged.connect(self._on_item_changed)
        self.song_tree.itemDoubleClicked.connect(lambda: self._on_rename_clicked())
        self.song_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.song_tree.customContextMenuRequested.connect(self._on_context_menu)
        layout.addWidget(self.song_tree)

        # 3. 상단 툴바 스타일의 버튼 그룹 — 글로벌 스타일 + variant 사용
        btn_row1 = QHBoxLayout()
        btn_row1.setSpacing(6)

        def create_btn(text, style=""):
            btn = QPushButton(text)
            btn.setFixedHeight(30)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            if style == "primary":
                btn.setProperty("variant", "primary")
            elif style == "danger":
                btn.setProperty("variant", "danger")
            return btn

        self.btn_add_new = create_btn("+ 새 곡", "primary")
        self.btn_add_new.clicked.connect(self._on_add_new_song)
        self.btn_add_new.setEnabled(not self.is_standalone)
        btn_row1.addWidget(self.btn_add_new)

        self.btn_import = create_btn("가져오기")
        self.btn_import.clicked.connect(self._on_import_song)
        self.btn_import.setEnabled(not self.is_standalone)
        btn_row1.addWidget(self.btn_import)

        btn_row1.addStretch()

        self.btn_refresh = create_btn("새로고침")
        self.btn_refresh.setFixedWidth(80)
        self.btn_refresh.clicked.connect(self._scan_and_load)
        self.btn_refresh.setEnabled(not self.is_standalone)
        btn_row1.addWidget(self.btn_refresh)

        layout.insertLayout(1, btn_row1)

        # 4. 하단 확인/취소 버튼
        footer_layout = QHBoxLayout()
        footer_layout.addStretch()

        self.btn_ok = create_btn("변경사항 적용 (확인)", "primary")
        self.btn_ok.setFixedWidth(160)
        self.btn_ok.clicked.connect(self._on_ok_clicked)
        footer_layout.addWidget(self.btn_ok)

        self.btn_cancel = create_btn("취소")
        self.btn_cancel.setFixedWidth(80)
        self.btn_cancel.clicked.connect(self._on_cancel_clicked)
        footer_layout.addWidget(self.btn_cancel)

        layout.addLayout(footer_layout)

    def keyPressEvent(self, event):
        """키보드 단축키 지원"""
        key = event.key()
        modifiers = event.modifiers()
        item = self.song_tree.currentItem()

        if not item:
            super().keyPressEvent(event)
            return

        # 1. 이동 (Ctrl + Up/Down)
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            if key == Qt.Key.Key_Up:
                self._on_move_up()
                return
            elif key == Qt.Key.Key_Down:
                self._on_move_down()
                return

        # 2. 이름 변경 (F2)
        if key == Qt.Key.Key_F2:
            self._on_rename_clicked()
            return

        # 3. 삭제 (Delete)
        if key == Qt.Key.Key_Delete:
            self._on_delete_clicked()
            return

        super().keyPressEvent(event)

    def _scan_and_load(self):
        """곡 및 시트 목록 표시 (단독 모드 및 프로젝트 모드 통합)"""
        self.song_tree.blockSignals(True)
        self.song_tree.clear()

        if self.is_standalone:
            # 1. 단독 모드: 현재 로드된 단일 곡만 표시
            if self.project.selected_songs:
                song = self.project.selected_songs[0]
                self._add_song_to_tree(song, is_checked=True, is_fixed=True)
        else:
            # 2. 프로젝트 모드: songs/ 폴더 스캔
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
                song = next((s for s in self.selected_songs if s.name == name), None)
                if not song:
                    song = self._load_song_from_folder(name)

                if song:
                    is_checked = name in self._selected_names
                    self._add_song_to_tree(song, is_checked=is_checked)

        self.song_tree.blockSignals(False)

    def _add_song_to_tree(self, song: Song, is_checked: bool, is_fixed: bool = False):
        """곡 항목과 자식 시트들을 트리에 추가 (공통 로직)"""
        song_item = QTreeWidgetItem()

        # 체크박스 설정
        if is_fixed:
            # 단독 모드에서는 체크박스 기능은 보이되 조작은 불가능하게 (강제 체크)
            song_item.setFlags(song_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            song_item.setFlags(song_item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
        else:
            song_item.setFlags(song_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)

        song_item.setData(0, Qt.ItemDataRole.UserRole, song)
        song_item.setCheckState(
            0, Qt.CheckState.Checked if is_checked else Qt.CheckState.Unchecked
        )

        # 1번 열에 곡 이름과 버튼 배치
        song_text = song.name
        self.song_tree.addTopLevelItem(song_item)
        self._create_inline_buttons(song_item, song_text, is_bold=True)

        for i, sheet in enumerate(song.score_sheets):
            display_name = sheet.name
            prefix = f"{song.name} -"
            if display_name.startswith(prefix):
                display_name = display_name[len(prefix) :].strip()

            # 시트 노드 생성
            sheet_item = QTreeWidgetItem()
            sheet_item.setData(0, Qt.ItemDataRole.UserRole, sheet)
            song_item.addChild(sheet_item)

            # 1번 열에 시트 이름과 버튼 배치
            sheet_text = f"📄  P{i + 1}: {display_name}"
            self._create_inline_buttons(sheet_item, sheet_text)

        song_item.setExpanded(True)

    def _create_inline_buttons(
        self, item: QTreeWidgetItem, text: str, is_bold: bool = False
    ):
        """1번 열에 텍스트와 상하 이동 버튼 세트 주입 (텍스트 겹침 방지 보강)"""
        # [중요] 텍스트가 겹치지 않도록 아이템 자체의 텍스트와 위젯 텍스트를 철저히 분리
        item.setText(0, "")  # 0번 열(체크박스) 비움
        item.setText(1, "")  # 1번 열(버튼/텍스트) 비움

        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(6)

        label = QLabel(text)
        label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        style = "color: #ccc; font-size: 11px;"
        if is_bold:
            style = "color: #eee; font-weight: bold; font-size: 12px;"
        label.setStyleSheet(style)

        # 라벨이 가용 공간을 모두 차지하도록 설정
        label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(label)

        btn_container = QWidget()
        btn_layout = QHBoxLayout(btn_container)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(2)

        btn_style = """
            QPushButton {
                background-color: #333; color: #888; border: 1px solid #444; border-radius: 2px;
                font-size: 8px; min-width: 18px; max-width: 18px; min-height: 18px; max-height: 18px; padding: 0px;
            }
            QPushButton:hover { background-color: #444; color: #ff9800; border: 1px solid #f57c00; }
        """

        up_btn = QPushButton("▲")
        up_btn.setStyleSheet(btn_style)
        up_btn.clicked.connect(lambda: self._on_move_up_item(item))

        down_btn = QPushButton("▼")
        down_btn.setStyleSheet(btn_style)
        down_btn.clicked.connect(lambda: self._on_move_down_item(item))

        btn_layout.addWidget(up_btn)
        btn_layout.addWidget(down_btn)
        layout.addWidget(btn_container)

        self.song_tree.setItemWidget(item, 1, container)  # 1번 열에 주입

    def _on_move_up_item(self, item: QTreeWidgetItem):
        """인라인 버튼을 통한 위로 이동"""
        self.song_tree.setCurrentItem(item)
        self._on_move_up()

    def _on_move_down_item(self, item: QTreeWidgetItem):
        """인라인 버튼을 통한 아래로 이동"""
        self.song_tree.setCurrentItem(item)
        self._on_move_down()

    def _on_context_menu(self, pos: QPoint):
        """곡 관리 트리 우클릭 메뉴"""
        item = self.song_tree.itemAt(pos)
        if not item:
            return

        data = item.data(0, Qt.ItemDataRole.UserRole)
        from PySide6.QtGui import QAction, QMenu

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background-color: #2a2a2a; color: #ccc; border: 1px solid #444; }
            QMenu::item { padding: 6px 20px; }
            QMenu::item:selected { background-color: #3d3d3d; color: white; }
        """)

        if isinstance(data, Song):
            import_ppt_act = QAction("📥 PPT 파일 가져오기", self)
            import_ppt_act.triggered.connect(lambda: self._import_song_ppt(data))
            menu.addAction(import_ppt_act)

            menu.addSeparator()

            rename_act = QAction("📝 이름 변경 (F2)", self)
            rename_act.triggered.connect(self._on_rename_clicked)
            menu.addAction(rename_act)

            delete_act = QAction("🗑 삭제 (Del)", self)
            delete_act.triggered.connect(self._on_delete_clicked)
            menu.addAction(delete_act)

        elif isinstance(data, ScoreSheet):
            rename_act = QAction("📝 이름 변경 (F2)", self)
            rename_act.triggered.connect(self._on_rename_clicked)
            menu.addAction(rename_act)

            delete_act = QAction("🗑 삭제 (Del)", self)
            delete_act.triggered.connect(self._on_delete_clicked)
            menu.addAction(delete_act)

        menu.exec(self.song_tree.mapToGlobal(pos))

    def _import_song_ppt(self, song: Song):
        """외부 PPT 파일을 곡 폴더의 slides.pptx로 복사"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "가져올 PPT 파일 선택", "", "PowerPoint 파일 (*.pptx)"
        )
        if not file_path:
            return

        import shutil

        dest_path = song.abs_slides_path

        if dest_path.exists():
            reply = QMessageBox.question(
                self,
                "파일 덮어쓰기",
                "이미 슬라이드 파일이 존재합니다. 덮어쓰시겠습니까?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        try:
            shutil.copy2(file_path, dest_path)
            # 메인 윈도우에 새로고침 요청 (다이얼로그 닫힌 후 반영됨)
            self.songs_changed.emit()
            QMessageBox.information(self, "완료", "PPT 파일을 성공적으로 가져왔습니다.")
        except Exception as e:
            QMessageBox.critical(self, "오류", f"파일을 가져오는데 실패했습니다: {e}")

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
        for i, song in enumerate(self.selected_songs):
            song.order = i + 1

    def _on_add_new_song(self):
        name, ok = QInputDialog.getText(self, "새 곡", "곡 이름:")
        if not ok or not name.strip():
            return

        name = name.strip()
        song_dir = self.songs_dir / name

        try:
            main_repo = getattr(self.parent(), "_repo", None)
            if main_repo:
                main_repo.init_song_folder(song_dir, name)
            else:
                song_dir.mkdir(parents=True)
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
        except Exception as e:
            QMessageBox.warning(self, "오류", f"곡 생성 실패: {e}")

    def _on_import_song(self):
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
                QTimer.singleShot(10, lambda: self._finalize_item_move(item))
        else:
            idx = self.song_tree.indexOfTopLevelItem(item)
            if idx > 0:
                self.song_tree.takeTopLevelItem(idx)
                self.song_tree.insertTopLevelItem(idx - 1, item)

                order = self.project.song_order
                order[idx], order[idx - 1] = order[idx - 1], order[idx]
                QTimer.singleShot(10, lambda: self._finalize_item_move(item))

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
                QTimer.singleShot(10, lambda: self._finalize_item_move(item))
        else:
            idx = self.song_tree.indexOfTopLevelItem(item)
            if idx < self.song_tree.topLevelItemCount() - 1:
                self.song_tree.takeTopLevelItem(idx)
                self.song_tree.insertTopLevelItem(idx + 1, item)

                order = self.project.song_order
                order[idx], order[idx + 1] = order[idx + 1], order[idx]
                QTimer.singleShot(10, lambda: self._finalize_item_move(item))

    def _finalize_item_move(self, item: QTreeWidgetItem):
        """이동 완료 후 전체 트리의 버튼 위젯 및 라벨 복구 (Segfault 방지)"""
        self.song_tree.blockSignals(True)

        # 현재 선택된 항목 유지
        self.song_tree.setCurrentItem(item)

        # 전체 트리를 순회하며 모든 버튼과 텍스트를 최신 상태로 재부착
        # (부모 이동 시 자식 위젯들이 유실되는 Qt 특성 대응)
        for i in range(self.song_tree.topLevelItemCount()):
            song_item = self.song_tree.topLevelItem(i)
            song_data = song_item.data(0, Qt.ItemDataRole.UserRole)

            if not isinstance(song_data, Song):
                continue

            # 1. 곡 제목 버튼 재부착
            song_text = song_data.name
            self._create_inline_buttons(song_item, song_text, is_bold=True)

            # 2. 자식 시트들 버튼 재부착 및 P번호 갱신
            for j in range(song_item.childCount()):
                sheet_item = song_item.child(j)
                sheet_data = sheet_item.data(0, Qt.ItemDataRole.UserRole)

                if isinstance(sheet_data, ScoreSheet):
                    display_name = sheet_data.name
                    prefix = f"{song_data.name} -"
                    if display_name.startswith(prefix):
                        display_name = display_name[len(prefix) :].strip()

                    sheet_text = f"📄  P{j + 1}: {display_name}"
                    self._create_inline_buttons(sheet_item, sheet_text)

            # 곡은 항상 펼쳐진 상태 유지 (사용자 편의)
            song_item.setExpanded(True)

        # 데이터 모델 순서 동기화
        parent = item.parent()
        if parent:
            self._sync_sheets_to_song(parent, auto_save=False)
        else:
            self._sync_selected_order()

        self.song_tree.blockSignals(False)

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
        self._modified_songs[song.name] = song  # Set 대신 Dict 사용

        if auto_save:
            self._save_song_metadata(song)
            self.songs_changed.emit()

    def _on_ok_clicked(self):
        for song in self._modified_songs.values():
            self._save_song_metadata(song)

        if self._modified_songs:
            self.songs_changed.emit()
        self.accept()

    def _on_cancel_clicked(self):
        """변경 사항 무시 및 초기 상태 복구 (이름 변경 포함)"""
        # 1. 모든 곡 객체의 상세 데이터(이름, 시트 목록) 복구
        # (객체 자체의 데이터를 이전 상태로 되돌림)
        for song_id, snapshot in self._song_snapshots.items():
            # 프로젝트가 관리하는 모든 선택된 곡들 중 해당 객체 찾기
            for song in self.selected_songs:
                if id(song) == song_id:
                    song.name = snapshot["name"]
                    song.score_sheets = list(snapshot["sheets"])
                    break

        # 2. 프로젝트 전역 설정 복구
        self.project.song_order = list(self._original_song_order)

        # 3. 프로젝트의 선택된 곡 리스트 복구 (객체 매칭)
        restored_selected = []
        for name in self._original_selected_names:
            # 이름이 복구된 상태이므로 이름으로 매칭 가능
            song = next((s for s in self.selected_songs if s.name == name), None)
            if not song:
                song = self._load_song_from_folder(name)
            if song:
                restored_selected.append(song)

        # 순서 보정 (original_song_order 기준)
        final_selected = []
        for name in self._original_song_order:
            if name in self._original_selected_names:
                match = next((s for s in restored_selected if s.name == name), None)
                if match:
                    final_selected.append(match)

        self.project.selected_songs = final_selected
        self.reject()

    def _on_delete_clicked(self):
        item = self.song_tree.currentItem()
        if not item:
            return

        data = item.data(0, Qt.ItemDataRole.UserRole)

        if isinstance(data, ScoreSheet):
            parent_item = item.parent()
            if not parent_item:
                return

            reply = QMessageBox.question(
                self, "삭제 확인", f"시트 '{data.name}'을(를) 삭제하시겠습니까?"
            )
            if reply == QMessageBox.StandardButton.Yes:
                parent_song = parent_item.data(0, Qt.ItemDataRole.UserRole)
                parent_song.score_sheets.remove(data)
                self._modified_songs[parent_song.name] = parent_song
                self._scan_and_load()

        elif isinstance(data, Song):
            if self.is_standalone:
                QMessageBox.information(
                    self, "정보", "단독 편집 모드에서는 현재 곡을 삭제할 수 없습니다."
                )
                return

            reply = QMessageBox.question(
                self,
                "곡 삭제 경고",
                f"곡 '{data.name}' 폴더를 디스크에서 완전히 삭제하시겠습니까?\n이 작업은 되돌릴 수 없습니다.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                if data.name in self._selected_names:
                    self.selected_songs = [
                        s for s in self.selected_songs if s.name != data.name
                    ]
                    self._selected_names.discard(data.name)
                    self.project.selected_songs = self.selected_songs

                if data.name in self.project.song_order:
                    self.project.song_order.remove(data.name)

                try:
                    shutil.rmtree(self.project_dir / data.folder)
                except Exception as e:
                    QMessageBox.warning(
                        self, "삭제 실패", f"폴더를 삭제할 수 없습니다: {e}"
                    )

                self._scan_and_load()

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
            self._modified_songs[data.name] = data
            if auto_save:
                self._save_song_metadata(data)
        elif isinstance(data, ScoreSheet):
            parent_item = item.parent()
            if parent_item:
                parent_song = parent_item.data(0, Qt.ItemDataRole.UserRole)
                self._modified_songs[parent_song.name] = parent_song
                if auto_save:
                    self._save_song_metadata(parent_song)

    def _save_song_metadata(self, song: Song):
        song_dir = self.project_dir / song.folder
        song_json = song_dir / "song.json"

        song_data = {
            "name": song.name,
            "sheets": [s.to_dict() for s in song.score_sheets],
        }

        with open(song_json, "w", encoding="utf-8-sig") as f:
            json.dump(song_data, f, ensure_ascii=False, indent=2)

    def _sync_selected_order(self):
        selected_map = {s.name: s for s in self.selected_songs}
        new_selected = []
        for name in self.project.song_order:
            if name in selected_map:
                new_selected.append(selected_map[name])
        self.project.selected_songs = new_selected
        self.selected_songs = new_selected
        self._reorder_songs()

    def _on_close(self):
        self.accept()
