"""곡 목록 위젯

곡과 악보 페이지를 계층적으로 표시하고 관리하는 UI
"""

import json

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QMenu,
    QMessageBox,
    QFileDialog,
    QInputDialog,
    QTreeWidgetItemIterator,
    QSizePolicy,
    QLineEdit,
)
from PySide6.QtCore import Signal, Qt, QPoint, QTimer, QEvent
from PySide6.QtGui import QAction, QColor
from pathlib import Path

from flow.domain.project import Project
from flow.domain.score_sheet import ScoreSheet
from flow.domain.song import Song


class SongListWidget(QWidget):
    """곡 목록 사이드바 (탐색 및 선택 최적화)

    Signals:
        song_selected: 곡이 선택되었을 때 (ScoreSheet)
        song_added: 새 곡이 추가되었을 때 (ScoreSheet)
        song_removed: 곡이 삭제되었을 때 (str: sheet_id)
        song_reload_requested: 슬라이드 새로고침 요청 (Song)
    """

    song_selected = Signal(object)  # ScoreSheet
    song_added = Signal(object)  # ScoreSheet
    song_removed = Signal(str)
    song_reload_requested = Signal(object)
    song_edit_requested = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._project: Project | None = None
        self._main_window = None
        self._editable = True
        self._is_flat_view = False
        self._show_song_names = True
        self._is_standalone = False
        self._search_text = ""
        self._setup_ui()

    def _setup_ui(self) -> None:
        """UI 초기화 (Tree View 기반 탐색기)"""
        self.setStyleSheet("background-color: #1a1a1a; ")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        # 1. 트리 위젯 (표준 QTreeWidget 사용, 드래그 비활성화, 외부 드롭 활성화)
        self._tree = QTreeWidget(self)
        self._tree.setHeaderHidden(True)
        self._tree.setIndentation(15)
        self._tree.setDragEnabled(False)
        self._tree.setAcceptDrops(True)
        self._tree.setRootIsDecorated(False)
        self._tree.setAnimated(True)

        self._tree.setStyleSheet("""
            QTreeWidget {
                background-color: #1e1e1e;
                border: 1px solid #333;
                border-radius: 6px;
                outline: none;
                padding: 4px;
                color: #ccc;
            }
            QTreeWidget::item {
                height: 32px;
                border-bottom: 1px solid #252525;
            }
            QTreeWidget::item:hover {
                background-color: #2a2a2a;
            }
            QTreeWidget::item:selected {
                background-color: #26384a;
                color: #2196f3;
                font-weight: bold;
            }
            QTreeWidget::item:selected:!active {
                background-color: #2a2a2a;
                color: #ccc;
            }
        """)

        self._tree.currentItemChanged.connect(self._on_selection_changed)
        self._tree.itemClicked.connect(self._on_item_clicked)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._on_context_menu)

        self._tree.dragEnterEvent = self._on_tree_drag_enter
        self._tree.dropEvent = self._on_tree_drop

        # 키보드 단축키 설정
        self._tree.installEventFilter(self)

        # 2. 헤더 및 제어 버튼 레이아웃
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(4, 4, 4, 4)
        header_layout.setSpacing(4)

        header = QLabel("📋 곡 목록")
        header.setStyleSheet("""
            font-weight: 800; 
            font-size: 14px; 
            color: #2196f3; 
            letter-spacing: 0.5px;
        """)
        header_layout.addWidget(header)
        header_layout.addStretch()

        btn_style = """
            QPushButton {
                background-color: #2a2a2a;
                color: #aaa;
                border: 1px solid #333;
                border-radius: 4px;
                font-size: 10px;
                font-weight: bold;
                padding: 4px 6px;
            }
            QPushButton:hover {
                background-color: #383838;
                color: white;
                border: 1px solid #2196f3;
            }
            QPushButton:checked {
                background-color: #203040;
                color: #2196f3;
                border: 1px solid #2196f3;
            }
        """

        # 단일 목록 토글 버튼
        self._flat_view_btn = QPushButton("목록형")
        self._flat_view_btn.setCheckable(True)
        self._flat_view_btn.setToolTip("곡 제목을 숨기고 시트만 나열하는 모드입니다.")
        self._flat_view_btn.setStyleSheet(btn_style)
        self._flat_view_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._flat_view_btn.clicked.connect(self._on_flat_view_toggled)
        header_layout.addWidget(self._flat_view_btn)

        # 설정/추가 옵션 메뉴 버튼
        self._options_btn = QPushButton("⚙️")
        self._options_btn.setToolTip("보기 옵션 및 제어")
        self._options_btn.setStyleSheet(
            btn_style + "QPushButton { font-size: 12px; padding: 3px 6px; }"
        )
        self._options_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        # 옵션 메뉴 구성
        self._options_menu = QMenu(self)
        self._options_menu.setStyleSheet("""
            QMenu { background-color: #2a2a2a; color: #ccc; border: 1px solid #444; }
            QMenu::item { padding: 6px 20px; }
            QMenu::item:selected { background-color: #3d3d3d; color: white; }
            QMenu::separator { height: 1px; background: #444; margin: 4px 0px; }
        """)

        self._act_expand = QAction("📂 전체 펼치기", self)
        self._act_expand.triggered.connect(self._tree.expandAll)
        self._options_menu.addAction(self._act_expand)

        self._act_collapse = QAction("📁 전체 접기", self)
        self._act_collapse.triggered.connect(self._tree.collapseAll)
        self._options_menu.addAction(self._act_collapse)

        self._options_menu.addSeparator()

        self._act_show_song = QAction("🎵 곡 제목 표시 (목록형 전용)", self)
        self._act_show_song.setCheckable(True)
        self._act_show_song.setChecked(True)
        self._act_show_song.triggered.connect(self._on_show_song_names_toggled)
        self._options_menu.addAction(self._act_show_song)

        self._options_menu.addSeparator()

        self._act_settings = QAction("⚙️ 환경설정...", self)
        self._act_settings.triggered.connect(self._on_settings_clicked)
        self._options_menu.addAction(self._act_settings)

        self._options_btn.clicked.connect(self._show_options_menu)
        header_layout.addWidget(self._options_btn)

        layout.addLayout(header_layout)

        # 검색창 추가
        self._search_bar = QLineEdit()
        self._search_bar.setPlaceholderText("🔍 곡 또는 시트 검색...")
        self._search_bar.setStyleSheet("""
            QLineEdit {
                background-color: #252525;
                color: #ccc;
                border: 1px solid #333;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
            }
            QLineEdit:focus {
                border: 1px solid #2196f3;
                background-color: #2a2a2a;
            }
        """)
        self._search_bar.textChanged.connect(self._on_search_text_changed)
        self._search_bar.installEventFilter(self)
        layout.addWidget(self._search_bar)

        layout.addWidget(self._tree)

        # 3. 하단 버튼들
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(6)

        self._import_ppt_btn = QPushButton("📥 PPT 가져오기")
        self._import_ppt_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._import_ppt_btn.setFixedHeight(34)
        self._import_ppt_btn.setStyleSheet("""
            QPushButton {
                background-color: #333;
                color: #ccc;
                border: 1px solid #444;
                border-radius: 6px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #444; border: 1px solid #2196f3; color: white; }
        """)
        self._import_ppt_btn.clicked.connect(self._on_import_ppt_clicked)
        self._import_ppt_btn.hide()
        btn_layout.addWidget(self._import_ppt_btn)

        main_btn_layout = QHBoxLayout()
        main_btn_layout.setSpacing(6)

        self._add_btn = QPushButton("+ 곡 추가")
        self._add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._add_btn.setFixedHeight(34)
        self._add_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196f3;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #1e88e5; }
            QPushButton:disabled { background-color: #333; color: #666; }
        """)
        self._add_btn.clicked.connect(self._on_add_clicked)
        main_btn_layout.addWidget(self._add_btn, 1)

        self._remove_btn = QPushButton("🗑️")
        self._remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._remove_btn.setFixedSize(34, 34)
        self._remove_btn.setStyleSheet("""
            QPushButton {
                background-color: #333;
                color: #888;
                border: 1px solid #444;
                border-radius: 6px;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #444; color: #ff4444; border: 1px solid #ff4444; }
            QPushButton:disabled { background-color: #252525; color: #444; border: 1px solid #333; }
        """)
        self._remove_btn.clicked.connect(self._on_remove_clicked)
        main_btn_layout.addWidget(self._remove_btn)

        btn_layout.addLayout(main_btn_layout)
        layout.addLayout(btn_layout)

    def _on_tree_drag_enter(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def _on_tree_drop(self, event):
        urls = event.mimeData().urls()
        if not urls or not self._project:
            return

        project_dir = (
            self._main_window._project_path.parent if self._main_window else None
        )
        if not project_dir:
            return

        imported_count = 0
        for url in urls:
            src_path = Path(url.toLocalFile())
            if src_path.is_dir() and (src_path / "song.json").exists():
                try:
                    song_name = self._main_window._repo.import_song_folder(
                        project_dir, src_path
                    )
                    song_obj = self._main_window._repo.load_standalone_song(
                        project_dir / "songs" / song_name
                    ).selected_songs[0]
                    song_obj.project_dir = project_dir

                    if song_name not in [s.name for s in self._project.selected_songs]:
                        self._project.selected_songs.append(song_obj)
                        if song_name not in self._project.song_order:
                            self._project.song_order.append(song_name)
                        imported_count += 1
                except Exception as e:
                    QMessageBox.warning(
                        self, "가져오기 실패", f"'{src_path.name}' 가져오기 실패: {e}"
                    )

        if imported_count > 0:
            self.refresh_list()
            if self._main_window:
                self._main_window._mark_dirty()
            QMessageBox.information(
                self,
                "가져오기 완료",
                f"{imported_count}개의 곡을 성공적으로 가져왔습니다.",
            )

    def set_standalone(self, standalone: bool) -> None:
        self._is_standalone = standalone
        if standalone:
            self._add_btn.setText("+ 시트(이미지) 추가")
            self._import_ppt_btn.show()
            self._flat_view_btn.hide()
        else:
            self._add_btn.setText("+ 곡 추가")
            self._import_ppt_btn.hide()
            self._flat_view_btn.show()

    def _get_project_dir(self) -> Path | None:
        if not self._main_window or not self._main_window._project_path:
            return None
        if self._is_standalone:
            return self._main_window._project_path
        return self._main_window._project_path.parent

    def set_project(self, project: Project) -> None:
        """프로젝트 설정 및 곡 목록 갱신"""
        self._project = project

        if project and len(project.selected_songs) <= 1:
            self._search_bar.hide()
        else:
            self._search_bar.show()

        self.refresh_list()

    def _clear_tree_safely(self) -> None:
        """QTreeWidgetItem을 하나씩 제거하여 안전하게 트리를 비움.

        PySide6에서 _tree.clear() 호출 시 C++ 측이 QTreeWidgetItem을
        일괄 삭제하면서 Python wrapper와 GC가 충돌하여 segfault가 발생함.
        takeTopLevelItem()으로 하나씩 꺼내 Python 참조를 해제한 뒤
        del로 명시 삭제하면 C++ 일괄 삭제가 발생하지 않아 안전함.
        """
        import gc

        while self._tree.topLevelItemCount() > 0:
            top = self._tree.takeTopLevelItem(0)
            if top is None:
                break
            for j in range(top.childCount()):
                child = top.child(j)
                if child is not None:
                    child.setData(0, Qt.ItemDataRole.UserRole, None)
                    child.setData(0, Qt.ItemDataRole.UserRole + 1, None)
            top.setData(0, Qt.ItemDataRole.UserRole, None)
            top.setData(0, Qt.ItemDataRole.UserRole + 1, None)
            del top

        gc.collect()

    def set_main_window(self, win) -> None:
        """메인 윈도우 참조 설정"""
        self._main_window = win

    def set_editable(self, editable: bool) -> None:
        """편집 모드 활성/비활성 제어"""
        self._editable = editable
        self._add_btn.setEnabled(editable)
        self._remove_btn.setEnabled(editable)

    def install_event_filter(self, filter_obj) -> None:
        """외부 필터 설치"""
        self._tree.installEventFilter(filter_obj)

    def eventFilter(self, watched, event) -> bool:
        """키보드 단축키 처리 (Ctrl+F: 검색, Esc: 검색취소)"""
        if event.type() == QEvent.Type.KeyPress:
            key = event.key()
            modifiers = event.modifiers()

            if modifiers & Qt.KeyboardModifier.ControlModifier and key == Qt.Key.Key_F:
                self._search_bar.setFocus()
                self._search_bar.selectAll()
                return True

            if watched == self._search_bar and key == Qt.Key.Key_Escape:
                self._search_bar.clear()
                self._tree.setFocus()
                return True

        return super().eventFilter(watched, event)

    def set_current_index(self, index: int) -> None:
        """프로젝트의 전체 시트 인덱스 기준으로 트리 아이템 선택"""
        if not self._project:
            return
        sheets = self._project.all_score_sheets
        if 0 <= index < len(sheets):
            self.select_sheet_by_id(sheets[index].id)

    def clear_selection(self) -> None:
        """트리 선택 해제"""
        self._tree.clearSelection()

    def select_next_song(self) -> bool:
        """다음 곡/페이지 선택"""
        if not self._project:
            return False

        all_sheets = self._project.all_score_sheets
        if not all_sheets:
            return False

        current_idx = self._project.current_sheet_index
        if current_idx + 1 < len(all_sheets):
            self._project.current_sheet_index += 1
            self._update_selection_from_project()

            new_sheet = all_sheets[self._project.current_sheet_index]
            self.song_selected.emit(new_sheet)

            if self._main_window:
                self._main_window.statusBar().showMessage(
                    f"시트 이동: {self._project.current_sheet_index + 1} / {len(all_sheets)} ({new_sheet.name})",
                    1000,
                )
            return True
        return False

    def select_previous_song(self) -> bool:
        """이전 곡/페이지 선택"""
        if not self._project:
            return False

        all_sheets = self._project.all_score_sheets
        if not all_sheets:
            return False

        current_idx = self._project.current_sheet_index
        if current_idx > 0:
            self._project.current_sheet_index -= 1
            self._update_selection_from_project()

            new_sheet = all_sheets[self._project.current_sheet_index]
            self.song_selected.emit(new_sheet)

            if self._main_window:
                self._main_window.statusBar().showMessage(
                    f"시트 이동: {self._project.current_sheet_index + 1} / {len(all_sheets)} ({new_sheet.name})",
                    1000,
                )
            return True
        return False

    def _update_selection_from_project(self) -> None:
        """프로젝트의 현재 인덱스에 맞춰 트리 아이템을 시각적으로 선택 (순서 기반)"""
        target_idx = self._project.current_sheet_index if self._project else -1
        if target_idx < 0:
            return

        self._tree.blockSignals(True)
        self._tree.clearSelection()

        current_count = 0
        it = QTreeWidgetItemIterator(self._tree)
        while it.value():
            item = it.value()
            data = item.data(0, Qt.ItemDataRole.UserRole)

            if isinstance(data, ScoreSheet):
                if current_count == target_idx:
                    self._tree.setCurrentItem(item)
                    item.setSelected(True)
                    self._tree.scrollToItem(item)
                    if item.parent():
                        item.parent().setExpanded(True)
                    break
                current_count += 1
            it += 1

        self._tree.blockSignals(False)
        self._update_indicators()

    def refresh_list(self) -> None:
        """곡 목록 갱신 (탐색용 계층 구조 또는 단일 목록, 검색 필터 포함)"""
        self._tree.blockSignals(True)
        self._clear_tree_safely()

        if not self._project:
            self._tree.blockSignals(False)
            return

        # 모드 상태에 따른 옵션 메뉴 활성화
        self._act_expand.setEnabled(not self._is_flat_view)
        self._act_collapse.setEnabled(not self._is_flat_view)
        self._act_show_song.setEnabled(self._is_flat_view)

        query = self._search_text.lower().strip()
        current_sheet = self._project.get_current_score_sheet()

        for song in self._project.selected_songs:
            song_matches = query in song.name.lower()
            valid_sheets = [
                s
                for s in song.score_sheets
                if s.image_path and str(s.image_path).strip()
            ]

            filtered_sheets = []
            for s in valid_sheets:
                if not query or song_matches or query in s.name.lower():
                    filtered_sheets.append(s)

            if query and not song_matches and not filtered_sheets:
                continue

            if not self._is_flat_view:
                song_item = QTreeWidgetItem([song.name])
                font = song_item.font(0)
                font.setBold(True)
                song_item.setFont(0, font)
                song_item.setData(0, Qt.ItemDataRole.UserRole, song)
                self._tree.addTopLevelItem(song_item)
                if query:
                    song_item.setExpanded(True)

            all_sheets_before = []
            for s in self._project.selected_songs:
                if s == song:
                    break
                all_sheets_before.extend(
                    [
                        sh
                        for sh in s.score_sheets
                        if sh.image_path and str(sh.image_path).strip()
                    ]
                )
            global_start_idx = len(all_sheets_before)

            sheet_to_idx = {
                s.id: global_start_idx + i for i, s in enumerate(valid_sheets)
            }

            for sheet in (
                filtered_sheets if self._is_flat_view or query else valid_sheets
            ):
                display_name = sheet.name
                if not self._is_flat_view:
                    prefix = f"{song.name} -"
                    if display_name.startswith(prefix):
                        display_name = display_name[len(prefix) :].strip()
                    orig_idx = valid_sheets.index(sheet) + 1
                    item_text = f"  P{orig_idx}: {display_name}"
                else:
                    if self._show_song_names:
                        if len(valid_sheets) == 1 and (
                            display_name == song.name
                            or display_name.startswith(f"{song.name} -")
                        ):
                            item_text = song.name
                        else:
                            item_text = f"{song.name} - {display_name}"
                    else:
                        item_text = display_name

                sheet_item = QTreeWidgetItem([item_text])
                sheet_item.setData(0, Qt.ItemDataRole.UserRole, sheet)
                sheet_item.setData(
                    0, Qt.ItemDataRole.UserRole + 1, sheet_to_idx.get(sheet.id)
                )

                if not self._is_flat_view:
                    song_item.addChild(sheet_item)
                    if (
                        not query
                        and current_sheet
                        and any(s.id == current_sheet.id for s in valid_sheets)
                    ):
                        song_item.setExpanded(True)
                else:
                    self._tree.addTopLevelItem(sheet_item)

            if not valid_sheets and not self._is_flat_view:
                empty_item = QTreeWidgetItem(["  (등록된 시트 없음)"])
                empty_item.setForeground(0, QColor("#666"))
                song_item.addChild(empty_item)
                song_item.setExpanded(True)

        self._update_selection_from_project()
        self._tree.blockSignals(False)

    def _on_search_text_changed(self, text: str):
        """검색어 변경 핸들러"""
        self._search_text = text
        self.refresh_list()

    def _on_flat_view_toggled(self, checked: bool):
        """단일 목록 모드 토글"""
        self._is_flat_view = checked
        self.refresh_list()

    def _on_show_song_names_toggled(self, checked: bool):
        """단일 목록에서 곡 이름 표시 토글"""
        self._show_song_names = checked
        if self._is_flat_view:
            self.refresh_list()

    def _on_settings_clicked(self):
        """환경설정 클릭"""
        if self._main_window:
            self._main_window._show_settings()

    def _show_options_menu(self):
        """설정 메뉴 표시"""
        self._options_menu.exec(
            self._options_btn.mapToGlobal(QPoint(0, self._options_btn.height()))
        )

    def _on_selection_changed(
        self, current: QTreeWidgetItem | None, previous: QTreeWidgetItem | None
    ) -> None:
        """곡 선택 변경 (트리 노드 선택 시 호출)"""
        if not current or not self._project or self._tree.signalsBlocked():
            return

        data = current.data(0, Qt.ItemDataRole.UserRole)

        target_sheet = None
        if isinstance(data, ScoreSheet):
            target_sheet = data
        elif hasattr(data, "score_sheets") and data.score_sheets:
            if current.childCount() > 0:
                self._tree.setCurrentItem(current.child(0))
                return
            target_sheet = data.score_sheets[0]

        if target_sheet:
            new_idx = current.data(0, Qt.ItemDataRole.UserRole + 1)

            if new_idx is None:
                all_sheets = self._project.all_score_sheets
                for i, s in enumerate(all_sheets):
                    if s.id == target_sheet.id:
                        new_idx = i
                        break

            if new_idx is not None and new_idx != self._project.current_sheet_index:
                self._project.current_sheet_index = new_idx
                self._update_indicators()
                self.song_selected.emit(target_sheet)
            elif new_idx is not None:
                self._update_indicators()

    def _update_indicators(self) -> None:
        """현재 선택된 항목 인디케이터(▶) 업데이트"""
        current_sheet = (
            self._project.get_current_score_sheet() if self._project else None
        )

        it = QTreeWidgetItemIterator(self._tree)
        while it.value():
            item = it.value()
            data = item.data(0, Qt.ItemDataRole.UserRole)

            base_text = item.text(0).replace("▶ ", "").strip()

            if (
                isinstance(data, ScoreSheet)
                and current_sheet
                and data.id == current_sheet.id
            ):
                item.setText(0, f"▶ {base_text}")
                item.setForeground(0, QColor("#2196f3"))
                self._tree.blockSignals(True)
                self._tree.setCurrentItem(item)
                self._tree.blockSignals(False)
            else:
                item.setText(0, base_text)
                item.setForeground(0, QColor("#ccc"))
            it += 1

    def _on_item_clicked(self, item: QTreeWidgetItem) -> None:
        """아이템 클릭 시 (접기/펼치기 토글)"""
        data = item.data(0, Qt.ItemDataRole.UserRole)

        if hasattr(data, "score_sheets") and not isinstance(data, ScoreSheet):
            item.setExpanded(not item.isExpanded())
            if item.childCount() > 0:
                self._tree.setCurrentItem(item.child(0))

        elif isinstance(data, ScoreSheet):
            self.song_selected.emit(data)

        if self._main_window:
            self._main_window._canvas.setFocus()

    def _on_add_clicked(self) -> None:
        if self._is_standalone and self._project and self._project.selected_songs:
            self._set_song_image(self._project.selected_songs[0])
            return

        if not self._project or not self._main_window:
            return

        project_dir = self._main_window._project_path.parent
        songs_dir = project_dir / "songs"

        if not songs_dir.exists():
            songs_dir.mkdir(parents=True, exist_ok=True)

        included_names = {s.name for s in self._project.selected_songs}
        available = []
        for folder in sorted(songs_dir.iterdir()):
            if folder.is_dir() and (folder / "song.json").exists():
                if folder.name not in included_names:
                    available.append(folder.name)

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #2a2a2a; color: #ccc;
                border: 1px solid #444; border-radius: 6px;
                padding: 4px 0;
            }
            QMenu::item {
                padding: 8px 20px; font-size: 12px;
            }
            QMenu::item:selected {
                background-color: #3d3d3d; color: white;
            }
            QMenu::item:disabled {
                color: #555;
            }
            QMenu::separator {
                height: 1px; background: #444; margin: 4px 8px;
            }
        """)

        if available:
            for name in available:
                act = menu.addAction(f"📂  {name}")
                act.triggered.connect(
                    lambda checked, n=name: self._add_existing_song(n)
                )
        else:
            empty = menu.addAction("(추가 가능한 곡 없음)")
            empty.setEnabled(False)

        menu.addSeparator()
        new_act = menu.addAction("✚  새 곡 만들기")
        new_act.triggered.connect(self._add_new_song_inline)

        menu.exec(self._add_btn.mapToGlobal(QPoint(0, -menu.sizeHint().height())))

    def _add_existing_song(self, name: str) -> None:
        if not self._project or not self._main_window:
            return

        project_dir = self._main_window._project_path.parent
        song = self._load_song_from_folder(name, project_dir)
        if not song:
            QMessageBox.warning(self, "오류", f"'{name}' 곡을 로드할 수 없습니다.")
            return

        self._project.selected_songs.append(song)
        if name not in self._project.song_order:
            self._project.song_order.append(name)

        self.refresh_list()
        self._main_window._mark_dirty()

    def _load_song_from_folder(self, name: str, project_dir: Path) -> Song | None:
        song_dir = project_dir / "songs" / name
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

            return Song(
                name=name,
                folder=Path("songs") / name,
                score_sheets=score_sheets,
                project_dir=project_dir,
            )
        except Exception:
            return None

    def _on_import_ppt_clicked(self) -> None:
        if self._project and self._project.selected_songs:
            self._import_song_ppt(self._project.selected_songs[0])

    def _add_new_song_inline(self) -> None:
        if not self._project or not self._main_window:
            return

        name, ok = QInputDialog.getText(self, "새 곡", "곡 이름:")
        if not ok or not name.strip():
            return

        name = name.strip()
        project_dir = self._main_window._project_path.parent
        song_dir = project_dir / "songs" / name

        if song_dir.exists():
            QMessageBox.warning(self, "오류", f"'{name}' 곡이 이미 존재합니다.")
            return

        try:
            main_repo = getattr(self._main_window, "_repo", None)
            if main_repo:
                main_repo.init_song_folder(song_dir, name)
            else:
                song_dir.mkdir(parents=True)
                (song_dir / "sheets").mkdir(exist_ok=True)
                song_data = {"name": name, "sheets": []}
                with open(song_dir / "song.json", "w", encoding="utf-8-sig") as f:
                    json.dump(song_data, f, ensure_ascii=False, indent=2)

            song = Song(
                name=name,
                folder=Path("songs") / name,
                score_sheets=[],
                project_dir=project_dir,
            )
            self._project.selected_songs.append(song)
            if name not in self._project.song_order:
                self._project.song_order.append(name)

            self.refresh_list()
            self._main_window._mark_dirty()
        except Exception as e:
            QMessageBox.warning(self, "오류", f"곡 생성 실패: {e}")

    def _set_song_image(self, song):
        """악보 이미지 추가"""
        import shutil

        project_dir = self._get_project_dir() or Path.cwd()
        song_dir = project_dir / song.folder
        initial_dir = str(song_dir) if song_dir.exists() else str(project_dir)

        image_path, _ = QFileDialog.getOpenFileName(
            self,
            f"'{song.name}'에 추가할 악보 이미지 선택",
            initial_dir,
            "이미지 (*.jpg *.jpeg *.png *.bmp)",
        )

        if not image_path:
            return

        p_path = Path(image_path).resolve()
        default_name = f"{song.name} - {p_path.stem}"
        sheet_name, ok = QInputDialog.getText(
            self,
            "시트 이름 지정",
            f"추가할 시트('{p_path.name}')의 이름을 입력하세요:",
            text=default_name,
        )
        if not ok or not sheet_name.strip():
            return

        sheets_dir = song.sheets_dir if song.sheets_dir else (song.folder / "sheets")
        abs_sheets_dir = project_dir / sheets_dir
        abs_sheets_dir.mkdir(parents=True, exist_ok=True)

        dest_path = abs_sheets_dir / p_path.name

        if p_path.parent != abs_sheets_dir:
            try:
                shutil.copy2(image_path, dest_path)
            except shutil.SameFileError:
                pass

        new_sheet_path = f"{sheets_dir.relative_to(song.folder) if song.folder and sheets_dir.is_relative_to(song.folder) else 'sheets'}/{p_path.name}"
        new_sheet = ScoreSheet(name=sheet_name.strip(), image_path=new_sheet_path)
        song.score_sheets.append(new_sheet)

        self.refresh_list()
        self.select_sheet_by_id(new_sheet.id)

        if self._main_window:
            self._main_window._mark_dirty()

    def select_sheet_by_id(self, sheet_id: str) -> None:
        """ID 기반 선택"""
        it = QTreeWidgetItemIterator(self._tree)
        while it.value():
            item = it.value()
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if isinstance(data, ScoreSheet) and data.id == sheet_id:
                self._tree.setCurrentItem(item)
                if item.parent():
                    item.parent().setExpanded(True)
                break
            it += 1

    def _on_remove_clicked(self) -> None:
        if not self._project:
            return

        current = self._tree.currentItem()
        if not current:
            return

        data = current.data(0, Qt.ItemDataRole.UserRole)

        if isinstance(data, ScoreSheet):
            if self._is_standalone:
                reply = QMessageBox.question(
                    self,
                    "페이지 삭제",
                    f"'{data.name}' 페이지를 삭제하시겠습니까?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if reply == QMessageBox.StandardButton.Yes:
                    self._project.remove_score_sheet(data.id)
                    self.refresh_list()
                    self.song_removed.emit(data.id)
                    if self._main_window:
                        self._main_window._mark_dirty()
        elif hasattr(data, "name"):
            self._remove_song(data)

    def _on_context_menu(self, pos: QPoint) -> None:
        if not self._editable:
            return
        item = self._tree.itemAt(pos)
        if not item:
            return

        menu = QMenu(self)
        data = item.data(0, Qt.ItemDataRole.UserRole)

        if self._is_standalone:
            self._build_standalone_context_menu(menu, item, data)
        elif isinstance(data, ScoreSheet):
            return
        else:
            self._build_project_context_menu(menu, data)

        menu.exec(self._tree.mapToGlobal(pos))

    def _build_project_context_menu(self, menu: QMenu, song) -> None:
        open_act = QAction("📂 곡 열기", self)
        open_act.triggered.connect(lambda: self.song_edit_requested.emit(song))
        menu.addAction(open_act)

        folder_act = QAction("📁 폴더 열기", self)
        folder_act.triggered.connect(lambda: self._open_song_folder(song))
        menu.addAction(folder_act)

        reload_act = QAction("🔄 새로고침", self)
        reload_act.triggered.connect(lambda: self.song_reload_requested.emit(song))
        menu.addAction(reload_act)

        menu.addSeparator()

        remove_act = QAction("✕ 프로젝트에서 제거", self)
        remove_act.triggered.connect(lambda: self._remove_song(song))
        menu.addAction(remove_act)

    def _build_standalone_context_menu(self, menu: QMenu, item, data) -> None:
        if isinstance(data, ScoreSheet):
            rename_action = QAction("📝 시트 이름 변경", self)
            rename_action.triggered.connect(lambda: self._on_rename_clicked(item))
            menu.addAction(rename_action)
        else:
            song = data

            open_folder_act = QAction("📂 폴더 열기", self)
            open_folder_act.triggered.connect(lambda: self._open_song_folder(song))
            menu.addAction(open_folder_act)

            edit_ppt_act = QAction("📽 PPT 편집", self)
            edit_ppt_act.triggered.connect(lambda: self._open_song_ppt(song))
            menu.addAction(edit_ppt_act)

            import_ppt_act = QAction("📥 PPT 파일 가져오기", self)
            import_ppt_act.triggered.connect(lambda: self._import_song_ppt(song))
            menu.addAction(import_ppt_act)

            reload_ppt_act = QAction("🔄 슬라이드 새로고침", self)
            reload_ppt_act.triggered.connect(
                lambda: self.song_reload_requested.emit(song)
            )
            menu.addAction(reload_ppt_act)

            menu.addSeparator()

            rename_action = QAction("📝 곡 이름 변경", self)
            rename_action.triggered.connect(lambda: self._on_rename_clicked(item))
            menu.addAction(rename_action)

    def _remove_song(self, song) -> None:
        if not self._project:
            return

        reply = QMessageBox.question(
            self,
            "곡 제거",
            f"'{song.name}' 곡을 프로젝트에서 제거하시겠습니까?\n(곡 파일은 삭제되지 않습니다)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        if song in self._project.selected_songs:
            self._project.selected_songs.remove(song)
        if song.name in self._project.song_order:
            self._project.song_order.remove(song.name)

        self.refresh_list()
        self.song_removed.emit("ALL_OF_SONG")
        if self._main_window:
            self._main_window._mark_dirty()

    def _open_song_folder(self, song):
        """폴더 열기"""
        import os, subprocess, sys

        project_dir = self._get_project_dir()
        if not project_dir:
            return
        path = project_dir / song.folder
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])

    def _open_song_ppt(self, song):
        """PPT 열기"""
        import os, subprocess, sys

        project_dir = self._get_project_dir()
        if not project_dir:
            return
        path = project_dir / song.folder / "slides.pptx"
        if not path.exists():
            QMessageBox.warning(self, "오류", "PPT 파일이 존재하지 않습니다.")
            return
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])

    def _import_song_ppt(self, song):
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
            self.song_reload_requested.emit(song)
            QMessageBox.information(self, "완료", "PPT 파일을 성공적으로 가져왔습니다.")
        except Exception as e:
            QMessageBox.critical(self, "오류", f"파일을 가져오는데 실패했습니다: {e}")

    def _on_rename_clicked(self, item: QTreeWidgetItem) -> None:
        """이름 변경"""
        if not self._project:
            return
        data = item.data(0, Qt.ItemDataRole.UserRole)
        new_name, ok = QInputDialog.getText(
            self, "이름 변경", "새 이름을 입력하세요:", text=data.name
        )
        if ok and new_name.strip():
            data.name = new_name.strip()
            self.refresh_list()
            if isinstance(data, ScoreSheet):
                self.song_selected.emit(data)
            else:
                valid = [s for s in data.score_sheets if s.image_path]
                if valid:
                    self.song_selected.emit(valid[0])
            if self._main_window:
                self._main_window._mark_dirty()
