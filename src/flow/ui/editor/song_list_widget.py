"""곡 목록 위젯

곡과 악보 페이지를 계층적으로 표시하고 관리하는 UI
"""

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
)
from PySide6.QtCore import Signal, Qt, QPoint, QTimer, QEvent
from PySide6.QtGui import QAction, QColor

from flow.domain.project import Project
from flow.domain.score_sheet import ScoreSheet


class CustomTreeWidget(QTreeWidget):
    """드래그 앤 드롭 제어가 가능한 커스텀 트리 위젯"""

    def __init__(self, parent_widget, parent=None):
        super().__init__(parent)
        self.parent_widget = parent_widget  # SongListWidget 참조

    def dragEnterEvent(self, event):
        """드래그 시작 - 편집 모드 체크"""
        if not self.parent_widget._editable:
            event.ignore()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        """드래그 이동 중 - 시트가 곡 밖으로 나가는 것을 철저히 차단"""
        if not self.parent_widget._editable:
            event.ignore()
            return

        source_item = self.currentItem()
        if not source_item:
            event.ignore()
            return

        target_item = self.itemAt(event.position().toPoint())
        source_data = source_item.data(0, Qt.ItemDataRole.UserRole)

        # 시트를 드래그하는 경우
        if isinstance(source_data, ScoreSheet):
            # 1. 타겟이 없는 경우 (리스트 끝 빈 공간 등) -> 거부
            if not target_item:
                event.ignore()
                return

            target_data = target_item.data(0, Qt.ItemDataRole.UserRole)

            # 2. 타겟이 시트인 경우 -> 같은 곡(부모)에 속한 경우에만 허용
            if isinstance(target_data, ScoreSheet):
                if source_item.parent() != target_item.parent():
                    event.ignore()
                    return

            # 3. 타겟이 곡인 경우 -> 자신이 원래 속해있던 곡인 경우에만 허용
            elif hasattr(target_data, "score_sheets"):
                if source_item.parent() != target_item:
                    event.ignore()
                    return

            # 4. 그 외 (루트 레벨의 엉뚱한 위치 등) -> 거부
            else:
                event.ignore()
                return

        super().dragMoveEvent(event)

    def dropEvent(self, event):
        """드롭 이벤트 - 안전한 이동 보장 및 Segfault 방지"""
        if not self.parent_widget._editable:
            event.ignore()
            return

        source_item = self.currentItem()
        if not source_item:
            event.ignore()
            return

        target_item = self.itemAt(event.position().toPoint())
        source_data = source_item.data(0, Qt.ItemDataRole.UserRole)

        # 시트(ScoreSheet) 이동 제한 재검증
        if isinstance(source_data, ScoreSheet):
            if not target_item:
                event.ignore()
                return

            target_data = target_item.data(0, Qt.ItemDataRole.UserRole)
            is_valid_drop = False

            if isinstance(target_data, ScoreSheet):
                # 다른 시트 위에/사이에 드롭하는 경우 -> 같은 부모면 허용
                if source_item.parent() == target_item.parent():
                    is_valid_drop = True
            elif hasattr(target_data, "score_sheets"):
                # 곡 제목(부모)에 드롭하는 경우
                if source_item.parent() == target_item:
                    # [수정] 이미 내 부모라면 이동(맨 뒤로 가기)할 필요가 없으므로 이벤트 무시
                    # 이렇게 하면 자리바꿈 현상이 발생하지 않음
                    event.ignore()
                    return
                # 다른 곡 제목에 드롭하는 경우 -> 현재 시스템은 다른 곡 이동을 금지하므로 ignore (위에서 이미 처리됨)

            if not is_valid_drop:
                event.ignore()
                return

        # 기본 드롭 처리 실행
        super().dropEvent(event)

        # [중요] Segfault 방지: 드롭 트랜잭션이 완전히 끝난 후(10ms 뒤) 구조 검증 실행
        from PySide6.QtCore import QTimer

        QTimer.singleShot(10, self.parent_widget._finalize_drop_operation)


class SongListWidget(QWidget):
    """곡 목록 사이드바 (계층 구조)

    Signals:
        song_selected: 곡이 선택되었을 때 (ScoreSheet)
        song_added: 새 곡이 추가되었을 때 (ScoreSheet)
        song_removed: 곡이 삭제되었을 때 (str: sheet_id)
    """

    song_selected = Signal(object)  # ScoreSheet
    song_added = Signal(object)  # ScoreSheet
    song_removed = Signal(str)  # sheet_id
    song_reload_requested = Signal(object)  # Song

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._project: Project | None = None
        self._main_window = None  # 메인 윈도우 참조 보관
        self._editable = True
        self._is_flat_view = False  # 단일 목록 모드 상태
        self._show_song_names = True  # 단일 목록에서 곡 제목 표시 여부
        self._setup_ui()

    def _setup_ui(self) -> None:
        """UI 초기화 (Tree View 기반)"""
        self.setStyleSheet("background-color: #1a1a1a; ")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        # 1. 트리 위젯 우선 생성 (버튼 연결을 위함)
        self._tree = CustomTreeWidget(self)
        self._tree.setHeaderHidden(True)
        self._tree.setIndentation(15)
        self._tree.setDragEnabled(True)
        self._tree.setAcceptDrops(True)
        self._tree.setDragDropMode(QTreeWidget.DragDropMode.InternalMove)
        self._tree.setDefaultDropAction(Qt.DropAction.MoveAction)
        self._tree.setDropIndicatorShown(True)  # [추가] 드롭 위치 지시선 표시
        self._tree.setRootIsDecorated(False)
        self._tree.setAnimated(True)  # [추가] 폴더 열릴 때 애니메이션 효과

        self._tree.setStyleSheet("""
            QTreeWidget {
                background-color: #222;
                border: 1px solid #333;
                border-radius: 6px;
                outline: none;
                padding: 4px;
            }
            QTreeWidget::item {
                height: 38px;
                color: #ccc;
                border-bottom: 1px solid #2a2a2a;
            }
            QTreeWidget::item:hover {
                background-color: #2a2a2a;
                color: white;
            }
            QTreeWidget::item:selected {
                background-color: #203040;
                color: #2196f3;
                font-weight: bold;
            }
        """)

        self._tree.currentItemChanged.connect(self._on_selection_changed)
        self._tree.itemClicked.connect(self._on_item_clicked)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._on_context_menu)

        # 키보드 단축키 설정 (Ctrl + Up/Down)
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

        # 단일 목록 토글 버튼 (텍스트 단축)
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
        layout.addWidget(self._tree)

        # 3. 하단 버튼들
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(6)

        self._add_btn = QPushButton("+ 곡 추가 / 관리")
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
        btn_layout.addWidget(self._add_btn, 1)

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
        btn_layout.addWidget(self._remove_btn)

        layout.addLayout(btn_layout)

    def _finalize_drop_operation(self):
        """드롭 작업 완료 후 최종 검증 및 데이터 동기화"""
        self._validate_tree_structure()
        self._update_order_after_drop()

    def _update_order_after_drop(self):
        """드롭 후 계층 구조를 도메인 모델에 동기화"""
        if not self._project:
            return

        new_song_order = []
        for i in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(i)
            data = item.data(0, Qt.ItemDataRole.UserRole)

            if hasattr(data, "score_sheets") and not isinstance(data, ScoreSheet):
                data.order = i
                new_song_order.append(data)

                valid_sheets = []
                for j in range(item.childCount()):
                    child = item.child(j)
                    sheet_data = child.data(0, Qt.ItemDataRole.UserRole)
                    if isinstance(sheet_data, ScoreSheet):
                        valid_sheets.append(sheet_data)

                data.score_sheets = valid_sheets

        self._project.selected_songs = new_song_order

        if self._main_window:
            self._main_window._mark_dirty()
            self._main_window._save_project()

    def _validate_tree_structure(self):
        """트리 계층 구조 무결성 검증 및 보정 (시트 소실 방지 강화)"""
        if not self._project:
            return

        has_changes = False

        # 1. 루트 레벨 시트 검사 및 보정
        for i in range(self._tree.topLevelItemCount() - 1, -1, -1):
            item = self._tree.topLevelItem(i)
            data = item.data(0, Qt.ItemDataRole.UserRole)

            if isinstance(data, ScoreSheet):
                target_song_item = None

                # 먼저 위쪽으로 가장 가까운 곡 검색
                for j in range(i - 1, -1, -1):
                    p_item = self._tree.topLevelItem(j)
                    p_data = p_item.data(0, Qt.ItemDataRole.UserRole)
                    if hasattr(p_data, "score_sheets") and not isinstance(
                        p_data, ScoreSheet
                    ):
                        target_song_item = p_item
                        break

                # 위쪽에 곡이 없으면 아래쪽으로 검색
                if not target_song_item:
                    for j in range(i + 1, self._tree.topLevelItemCount()):
                        n_item = self._tree.topLevelItem(j)
                        n_data = n_item.data(0, Qt.ItemDataRole.UserRole)
                        if hasattr(n_data, "score_sheets") and not isinstance(
                            n_data, ScoreSheet
                        ):
                            target_song_item = n_item
                            break

                self._tree.takeTopLevelItem(i)
                if target_song_item:
                    # 위쪽 곡을 찾았다면 맨 뒤에 추가, 아래쪽 곡을 찾았다면 맨 앞에 삽입
                    if self._tree.indexOfTopLevelItem(target_song_item) < i:
                        target_song_item.addChild(item)
                    else:
                        target_song_item.insertChild(0, item)
                    target_song_item.setExpanded(True)

                has_changes = True

        orphans = []
        it = QTreeWidgetItemIterator(self._tree)
        while it.value():
            item = it.value()
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if isinstance(data, ScoreSheet) and item.childCount() > 0:
                parent_song = item.parent()
                if parent_song:
                    for k in range(item.childCount() - 1, -1, -1):
                        child = item.takeChild(k)
                        orphans.append((parent_song, child))
            it += 1

        for parent, child in orphans:
            parent.addChild(child)
            has_changes = True

        if has_changes:
            self._update_order_after_drop()

    def set_project(self, project: Project) -> None:
        """프로젝트 설정 및 곡 목록 갱신"""
        self._project = project
        self.refresh_list()

    def set_main_window(self, win) -> None:
        """메인 윈도우 참조 설정 (프로젝트 경로 획득용)"""
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
        """내부 키보드 단축키 처리 (Ctrl + Up/Down)"""
        if watched == self._tree and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            modifiers = event.modifiers()

            if modifiers & Qt.KeyboardModifier.ControlModifier:
                item = self._tree.currentItem()
                if not item:
                    return False

                if key == Qt.Key.Key_Up:
                    self._on_move_item(item, -1)
                    return True
                elif key == Qt.Key.Key_Down:
                    self._on_move_item(item, 1)
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

            # [디버그] 상태바에 현재 위치 표시
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

            # [디버그] 상태바에 현재 위치 표시
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

        # [수정] ID 충돌 방지를 위해 전체 트리에서 N번째 시트 아이템을 직접 찾음
        current_count = 0
        found = False
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
                    found = True
                    break
                current_count += 1
            it += 1

        self._tree.blockSignals(False)
        self._update_indicators()

    def refresh_list(self) -> None:
        """곡 목록 갱신 (계층 구조 또는 단일 목록 대응)"""
        self._tree.blockSignals(True)
        self._tree.clear()

        if not self._project:
            self._tree.blockSignals(False)
            return

        # 단일 목록 모드 상태에 따른 옵션 메뉴 활성화/비활성화
        self._act_expand.setEnabled(not self._is_flat_view)
        self._act_collapse.setEnabled(not self._is_flat_view)
        self._act_show_song.setEnabled(self._is_flat_view)

        current_sheet = self._project.get_current_score_sheet()

        for song in self._project.selected_songs:
            # 1. 유효한 시트만 필터링 (이미지가 있는 것만)
            valid_sheets = [
                s
                for s in song.score_sheets
                if s.image_path and str(s.image_path).strip()
            ]

            if not self._is_flat_view:
                # [기본 모드] 곡 제목 아이템 생성
                song_item = QTreeWidgetItem([song.name])
                font = song_item.font(0)
                font.setBold(True)
                song_item.setFont(0, font)
                song_item.setData(0, Qt.ItemDataRole.UserRole, song)
                flags = song_item.flags()
                flags &= ~Qt.ItemFlag.ItemIsSelectable  # 선택 불가
                flags |= Qt.ItemFlag.ItemIsDragEnabled  # 드래그 가능
                song_item.setFlags(flags)
                self._tree.addTopLevelItem(song_item)

                if not valid_sheets:
                    continue

            # 2. 시트 목록 구성 (전체 프로젝트 기준 인덱스 계산)
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

            for i, sheet in enumerate(valid_sheets):
                # 표시 이름 최적화
                display_name = sheet.name
                if not self._is_flat_view:
                    # 곡 제목 중복 제거 (계층 구조일 때만)
                    prefix = f"{song.name} -"
                    if display_name.startswith(prefix):
                        display_name = display_name[len(prefix) :].strip()
                    item_text = f"  P{i + 1}: {display_name}"
                else:
                    # 단일 목록 모드: 설정에 따라 곡 제목 표시 여부 결정
                    if self._show_song_names:
                        # 시트가 1개뿐이고 이름이 곡 이름과 같다면 곡 이름만 표시
                        if len(valid_sheets) == 1 and (
                            display_name == song.name
                            or display_name.startswith(f"{song.name} -")
                        ):
                            item_text = song.name
                        else:
                            item_text = f"{song.name} - {display_name}"
                    else:
                        # 곡 제목 없이 시트 이름만 표시
                        item_text = display_name

                sheet_item = QTreeWidgetItem([item_text])
                sheet_item.setData(0, Qt.ItemDataRole.UserRole, sheet)
                sheet_item.setData(
                    0, Qt.ItemDataRole.UserRole + 1, global_start_idx + i
                )

                if not self._is_flat_view:
                    song_item.addChild(sheet_item)
                    # 현재 선택된 시트가 이 곡에 있으면 트리 확장
                    if current_sheet and any(
                        s.id == current_sheet.id for s in valid_sheets
                    ):
                        song_item.setExpanded(True)
                else:
                    # 단일 목록 모드: 직접 최상위에 추가
                    self._tree.addTopLevelItem(sheet_item)

        self._update_selection_from_project()
        self._tree.blockSignals(False)

    def _on_flat_view_toggled(self, checked: bool):
        """단일 목록 모드 토글 핸들러"""
        self._is_flat_view = checked
        self._tree.setDragEnabled(not checked)
        self.refresh_list()

    def _on_show_song_names_toggled(self, checked: bool):
        """단일 목록에서 곡 이름 표시 토글 핸들러"""
        self._show_song_names = checked
        if self._is_flat_view:
            self.refresh_list()

    def _on_settings_clicked(self):
        """설정 메뉴 클릭 핸들러"""
        if self._main_window:
            self._main_window._show_settings()

    def _show_options_menu(self):
        """설정 메뉴 표시"""
        # 버튼 바로 아래에 메뉴 표시
        self._options_menu.exec(
            self._options_btn.mapToGlobal(QPoint(0, self._options_btn.height()))
        )

    def _on_selection_changed(
        self, current: QTreeWidgetItem | None, previous: QTreeWidgetItem | None
    ) -> None:
        """곡 선택 변경 (트리 노드 선택 시 호출)"""
        # [추가] 시그널이 차단된 상태거나 인덱스 업데이트 중이면 무시
        if not current or not self._project or self._tree.signalsBlocked():
            return

        data = current.data(0, Qt.ItemDataRole.UserRole)

        target_sheet = None
        if isinstance(data, ScoreSheet):
            target_sheet = data
        elif hasattr(data, "score_sheets") and data.score_sheets:
            # 방향키 등으로 '곡' 노드에 진입한 경우 -> 첫 번째 페이지로 자동 점프
            if current.childCount() > 0:
                self._tree.setCurrentItem(current.child(0))
                return
            target_sheet = data.score_sheets[0]

        if target_sheet:
            # [수정] ID 충돌 방지를 위해 저장된 절대 인덱스 우선 사용
            new_idx = current.data(0, Qt.ItemDataRole.UserRole + 1)

            # 인덱스 데이터가 없으면 검색으로 대체 (하위 호환)
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
                # 인덱스는 같지만 시각적 갱신이 필요할 수 있음
                self._update_indicators()

    def _update_indicators(self) -> None:
        """삼각형 기호(▶) 위치 업데이트 (트리 구조 대응)"""
        current_sheet = (
            self._project.get_current_score_sheet() if self._project else None
        )

        it = QTreeWidgetItemIterator(self._tree)
        while it.value():
            item = it.value()
            data = item.data(0, Qt.ItemDataRole.UserRole)

            # 원본 텍스트 가져오기 (이미 삼각형이 있으면 제거)
            base_text = item.text(0).replace("▶ ", "").strip()

            if (
                isinstance(data, ScoreSheet)
                and current_sheet
                and data.id == current_sheet.id
            ):
                item.setText(0, f"▶ {base_text}")
                item.setForeground(0, QColor("#2196f3"))
                # [추가] 인디케이터가 있는 아이템을 트리에서 선택 상태로 동기화
                self._tree.blockSignals(True)
                self._tree.setCurrentItem(item)
                self._tree.blockSignals(False)
            else:
                item.setText(0, base_text)
                item.setForeground(0, QColor("#ccc"))
            it += 1

    def _on_item_clicked(self, item: QTreeWidgetItem) -> None:
        """아이템 클릭 시 (곡 제목 클릭 토글 및 포커스 반환)"""
        data = item.data(0, Qt.ItemDataRole.UserRole)

        # 곡 제목 노드인 경우 (Song 객체인 경우)
        if hasattr(data, "score_sheets") and not isinstance(data, ScoreSheet):
            # 1. 접기/펼치기 상태 토글
            item.setExpanded(not item.isExpanded())

            # 2. 첫 페이지 자동 선택 (기존 편의 기능)
            if item.childCount() > 0:
                self._tree.setCurrentItem(item.child(0))

        elif isinstance(data, ScoreSheet):
            self.song_selected.emit(data)

        if self._main_window:
            self._main_window._canvas.setFocus()

    def _on_add_clicked(self) -> None:
        """[수정] 버튼 클릭 시 무조건 곡 관리 다이얼로그 호출"""
        if self._main_window:
            self._main_window._manage_songs()

    def _set_song_image(self, song):
        """특정 곡에 새로운 악보 페이지(이미지) 추가"""
        import shutil
        from pathlib import Path

        # 프로젝트 폴더 또는 곡 폴더를 기본 경로로 설정
        project_dir = (
            self._main_window._project_path.parent if self._main_window else Path.cwd()
        )
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

        # [추가] 시트 이름 입력 받기
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

        # [수정] 해당 곡의 sheet 폴더에 있지 않다면 복사
        if p_path.parent != abs_sheets_dir:
            try:
                shutil.copy2(image_path, dest_path)
            except shutil.SameFileError:
                pass

        # 도메인 모델 업데이트
        from flow.domain.score_sheet import ScoreSheet

        rel_sheets_dir = (
            sheets_dir.relative_to(song.folder)
            if song.folder and sheets_dir.is_relative_to(song.folder)
            else Path("sheets")
        )
        new_sheet_path = f"{rel_sheets_dir}/{p_path.name}"

        new_sheet = ScoreSheet(name=sheet_name.strip(), image_path=new_sheet_path)
        song.score_sheets.append(new_sheet)

        self.refresh_list()

        # 시트 선택 및 트리 확장
        self.select_sheet_by_id(new_sheet.id)

        if self._main_window:
            self._main_window._mark_dirty()
            self._main_window._save_project()

    def select_sheet_by_id(self, sheet_id: str) -> None:
        """ID를 기반으로 트리의 시트 아이템 선택"""
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
        """곡(또는 페이지) 삭제 버튼 클릭"""
        if not self._project:
            return

        current = self._tree.currentItem()
        if not current:
            return

        data = current.data(0, Qt.ItemDataRole.UserRole)

        if isinstance(data, ScoreSheet):
            # 페이지 삭제
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
        else:
            # 곡 삭제
            reply = QMessageBox.question(
                self,
                "곡 삭제",
                f"'{data.name}' 곡을 프로젝트에서 제외하시겠습니까?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                if data in self._project.selected_songs:
                    self._project.selected_songs.remove(data)
                    self.refresh_list()
                    # 곡이 삭제되면 관련 시트들도 모두 제거됨 (UI상)
                    self.song_removed.emit("ALL_OF_SONG")

    def _on_move_item(self, item: QTreeWidgetItem, delta: int):
        """항목의 순서를 위/아래로 이동 (데이터 동기화 포함)"""
        parent = item.parent()
        if parent:
            # 자식 노드(시트) 이동
            index = parent.indexOfChild(item)
            new_index = index + delta
            if 0 <= new_index < parent.childCount():
                parent.takeChild(index)
                parent.insertChild(new_index, item)
                self._tree.setCurrentItem(item)
        else:
            # 최상위 노드(곡) 이동
            index = self._tree.indexOfTopLevelItem(item)
            new_index = index + delta
            if 0 <= new_index < self._tree.topLevelItemCount():
                self._tree.takeTopLevelItem(index)
                self._tree.insertTopLevelItem(new_index, item)
                self._tree.setCurrentItem(item)

        # 데이터 모델 업데이트
        self._update_order_after_drop()

    def _on_context_menu(self, pos: QPoint) -> None:
        """우클릭 컨텍스트 메뉴 (요구사항에 따른 메뉴 분기)"""
        if not self._editable:
            return
        item = self._tree.itemAt(pos)
        if not item:
            return

        menu = QMenu(self)
        data = item.data(0, Qt.ItemDataRole.UserRole)

        if isinstance(data, ScoreSheet):
            # [시트 노드] 이동, 삭제, 이름 변경
            move_up_action = QAction("🔼 위로 이동", self)
            move_up_action.triggered.connect(lambda: self._on_move_item(item, -1))
            menu.addAction(move_up_action)

            move_down_action = QAction("🔽 아래로 이동", self)
            move_down_action.triggered.connect(lambda: self._on_move_item(item, 1))
            menu.addAction(move_down_action)

            menu.addSeparator()

            rename_action = QAction("📝 시트 이름 변경", self)
            rename_action.triggered.connect(lambda: self._on_rename_clicked(item))
            menu.addAction(rename_action)

            menu.addSeparator()
            remove_action = QAction("🗑️ 시트 삭제", self)
            remove_action.triggered.connect(self._on_remove_clicked)
            menu.addAction(remove_action)
        else:
            # [곡 노드] 전체 기능 제공
            song = data
            open_folder_act = QAction("📂 폴더 열기", self)
            open_folder_act.triggered.connect(lambda: self._open_song_folder(song))
            menu.addAction(open_folder_act)

            edit_ppt_act = QAction("📽 PPT 편집", self)
            edit_ppt_act.triggered.connect(lambda: self._open_song_ppt(song))
            menu.addAction(edit_ppt_act)

            reload_ppt_act = QAction("🔄 슬라이드 새로고침", self)
            reload_ppt_act.triggered.connect(
                lambda: self.song_reload_requested.emit(song)
            )
            menu.addAction(reload_ppt_act)

            menu.addSeparator()

            set_image_act = QAction("➕ 시트 추가...", self)
            set_image_act.triggered.connect(lambda: self._set_song_image(song))
            menu.addAction(set_image_act)

            menu.addSeparator()

            rename_action = QAction("📝 곡 이름 변경", self)
            rename_action.triggered.connect(lambda: self._on_rename_clicked(item))
            menu.addAction(rename_action)

            menu.addSeparator()

            # [곡 노드] 순서 변경 추가
            move_up_action = QAction("🔼 곡 위로 이동", self)
            move_up_action.triggered.connect(lambda: self._on_move_item(item, -1))
            menu.addAction(move_up_action)

            move_down_action = QAction("🔽 곡 아래로 이동", self)
            move_down_action.triggered.connect(lambda: self._on_move_item(item, 1))
            menu.addAction(move_down_action)

            menu.addSeparator()
            remove_action = QAction("🗑️ 곡 프로젝트에서 제거", self)
            remove_action.triggered.connect(self._on_remove_clicked)
            menu.addAction(remove_action)

        menu.exec(self._tree.mapToGlobal(pos))

    def _open_song_folder(self, song):
        """곡 폴더 열기"""
        import os
        import subprocess
        import sys

        path = self._main_window._project_path.parent / song.folder
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])

    def _open_song_ppt(self, song):
        """곡 PPT 열기"""
        import os
        import subprocess
        import sys

        path = self._main_window._project_path.parent / song.folder / "slides.pptx"
        if not path.exists():
            QMessageBox.warning(self, "오류", "PPT 파일이 존재하지 않습니다.")
            return

        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])

    def _on_rename_clicked(self, item: QTreeWidgetItem) -> None:
        """[수정] 곡 또는 페이지 이름 변경"""
        if not self._project:
            return
        data = item.data(0, Qt.ItemDataRole.UserRole)

        current_name = data.name

        new_name, ok = QInputDialog.getText(
            self, "이름 변경", "새 이름을 입력하세요:", text=current_name
        )
        if ok and new_name.strip():
            # 실제 데이터 변경
            data.name = new_name.strip()
            self.refresh_list()

            # 시트인 경우 메인 윈도우에 알림
            if isinstance(data, ScoreSheet):
                self.song_selected.emit(data)
            else:
                # 곡인 경우 첫 번째 시트가 있다면 선택 유도
                valid_sheets = [s for s in data.score_sheets if s.image_path]
                if valid_sheets:
                    self.song_selected.emit(valid_sheets[0])
