"""곡 목록 위젯 (셋리스트 카드 뷰)

프로젝트의 곡을 카드 형태로 표시하고 관리하는 UI.
곡 상태(악보·PPT·매핑)를 한눈에 파악하고 빠르게 편집할 수 있다.
"""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QEvent, QPoint
from PySide6.QtGui import QAction, QColor, QFont
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from flow.domain.project import Project
from flow.domain.score_sheet import ScoreSheet
from flow.domain.song import Song


# ─── 상태 계산 헬퍼 ────────────────────────────────────────────────────────


def _song_status(song: Song) -> dict:
    """곡의 완성도 정보를 반환 (JSON 파싱 없이 파일 존재 확인)."""
    has_sheets = any(bool(s.image_path) for s in song.score_sheets)

    has_ppt = False
    if song.project_dir and song.folder:
        has_ppt = (song.project_dir / song.folder / "slides.pptx").exists()
    elif hasattr(song, "has_slides"):
        has_ppt = song.has_slides

    total_hs = sum(len(s.hotspots) for s in song.score_sheets)
    mapped_hs = sum(
        1
        for s in song.score_sheets
        for h in s.hotspots
        if h.slide_index >= 0 or h.slide_mappings
    )

    return {
        "has_sheets": has_sheets,
        "has_ppt": has_ppt,
        "total_hotspots": total_hs,
        "mapped_hotspots": mapped_hs,
    }


# ─── 시트 탭 버튼 ───────────────────────────────────────────────────────────


class _SheetTab(QPushButton):
    """선택된 곡 하단에 나타나는 페이지 탭."""

    def __init__(self, sheet: ScoreSheet, page_num: int, parent=None) -> None:
        label = f"P{page_num}"
        super().__init__(label, parent)
        self._sheet = sheet
        self.setFixedHeight(24)
        self.setMinimumWidth(36)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setToolTip(sheet.name)
        self._refresh_style(False)

    def set_current(self, active: bool) -> None:
        self.setChecked(active)
        self._refresh_style(active)

    def _refresh_style(self, active: bool) -> None:
        if active:
            self.setStyleSheet("""
                QPushButton {
                    background: #2196f3; color: #fff;
                    border: none; border-radius: 4px;
                    font-size: 10px; font-weight: bold; padding: 0 6px;
                }
            """)
        else:
            self.setStyleSheet("""
                QPushButton {
                    background: #2a2a2a; color: #888;
                    border: 1px solid #333; border-radius: 4px;
                    font-size: 10px; padding: 0 6px;
                }
                QPushButton:hover { background: #333; color: #ccc; }
            """)


# ─── 곡 카드 ────────────────────────────────────────────────────────────────


class _SongCard(QFrame):
    """셋리스트의 곡 하나를 나타내는 카드 위젯."""

    sheet_selected = Signal(object)     # ScoreSheet
    edit_requested = Signal(object)     # Song
    remove_requested = Signal(object)   # Song
    reload_requested = Signal(object)   # Song

    def __init__(self, song: Song, position: int, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("SongCard")
        self._song = song
        self._position = position
        self._is_selected = False
        self._current_sheet_id: str | None = None
        self._sheet_tabs: list[_SheetTab] = []
        self._setup_ui()
        self.refresh_status()

    # ── UI 구성 ──────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(6)

        # ── 상단 행: 번호 배지 + 곡 이름 + 액션 버튼
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(8)

        self._badge = QLabel(str(self._position))
        self._badge.setFixedSize(22, 22)
        self._badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._badge.setStyleSheet(
            "background: #333; color: #888; border-radius: 11px; "
            "font-size: 10px; font-weight: bold;"
        )
        top_row.addWidget(self._badge)

        self._name_label = QLabel(self._song.name)
        self._name_label.setStyleSheet(
            "font-size: 13px; font-weight: bold; color: #ddd; background: transparent;"
        )
        self._name_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        top_row.addWidget(self._name_label, 1)

        # 편집 버튼 (hover 시 표시)
        self._btn_edit = QPushButton("편집")
        self._btn_edit.setFixedHeight(22)
        self._btn_edit.setMinimumWidth(46)
        self._btn_edit.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_edit.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_edit.setStyleSheet("""
            QPushButton {
                background: #2a3a4a; color: #64b5f6; border: 1px solid #2a5a8a;
                border-radius: 4px; font-size: 10px; font-weight: bold;
            }
            QPushButton:hover { background: #1e3a5a; }
        """)
        self._btn_edit.clicked.connect(lambda: self.edit_requested.emit(self._song))
        self._btn_edit.hide()
        top_row.addWidget(self._btn_edit)

        self._btn_remove = QPushButton("✕")
        self._btn_remove.setFixedSize(22, 22)
        self._btn_remove.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_remove.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_remove.setStyleSheet("""
            QPushButton {
                background: transparent; color: #555; border: none;
                font-size: 11px; font-weight: bold;
            }
            QPushButton:hover { color: #ff4444; }
        """)
        self._btn_remove.clicked.connect(lambda: self.remove_requested.emit(self._song))
        self._btn_remove.hide()
        top_row.addWidget(self._btn_remove)

        root.addLayout(top_row)

        # ── 상태 행: 악보·PPT·매핑 배지
        self._status_row = QHBoxLayout()
        self._status_row.setContentsMargins(30, 0, 0, 0)
        self._status_row.setSpacing(6)
        self._lbl_sheets = QLabel()
        self._lbl_ppt = QLabel()
        self._lbl_mapping = QLabel()
        for lbl in (self._lbl_sheets, self._lbl_ppt, self._lbl_mapping):
            lbl.setStyleSheet("font-size: 10px; background: transparent;")
        self._status_row.addWidget(self._lbl_sheets)
        self._status_row.addWidget(self._lbl_ppt)
        self._status_row.addWidget(self._lbl_mapping)
        self._status_row.addStretch()
        root.addLayout(self._status_row)

        # ── 시트 탭 행 (선택 시만 표시)
        self._tabs_container = QWidget()
        tabs_layout = QHBoxLayout(self._tabs_container)
        tabs_layout.setContentsMargins(30, 0, 0, 0)
        tabs_layout.setSpacing(4)
        self._tabs_layout = tabs_layout
        self._tabs_layout.addStretch()
        self._tabs_container.hide()
        root.addWidget(self._tabs_container)

        self._refresh_frame_style()

    # ── 상태 갱신 ─────────────────────────────────────────────────────────

    def refresh_status(self) -> None:
        st = _song_status(self._song)

        # 악보
        if st["has_sheets"]:
            self._lbl_sheets.setText("🖼 악보")
            self._lbl_sheets.setStyleSheet("font-size: 10px; color: #4caf50; background: transparent;")
        else:
            self._lbl_sheets.setText("🖼 악보 없음")
            self._lbl_sheets.setStyleSheet("font-size: 10px; color: #ff9800; background: transparent;")

        # PPT
        if st["has_ppt"]:
            self._lbl_ppt.setText("📊 PPT")
            self._lbl_ppt.setStyleSheet("font-size: 10px; color: #4caf50; background: transparent;")
        else:
            self._lbl_ppt.setText("📊 PPT 없음")
            self._lbl_ppt.setStyleSheet("font-size: 10px; color: #ff9800; background: transparent;")

        # 매핑
        total = st["total_hotspots"]
        mapped = st["mapped_hotspots"]
        if total == 0:
            self._lbl_mapping.setText("핫스팟 없음")
            self._lbl_mapping.setStyleSheet("font-size: 10px; color: #666; background: transparent;")
        elif mapped == total:
            self._lbl_mapping.setText(f"🔵 {total}개 매핑 완료")
            self._lbl_mapping.setStyleSheet("font-size: 10px; color: #4caf50; background: transparent;")
        else:
            self._lbl_mapping.setText(f"🔵 {mapped}/{total} 매핑")
            self._lbl_mapping.setStyleSheet("font-size: 10px; color: #ff9800; background: transparent;")

    def set_selected(self, selected: bool, current_sheet_id: str | None = None) -> None:
        self._is_selected = selected
        self._current_sheet_id = current_sheet_id
        self._badge.setStyleSheet(
            "background: #2196f3; color: #fff; border-radius: 11px; "
            "font-size: 10px; font-weight: bold;"
            if selected else
            "background: #333; color: #888; border-radius: 11px; "
            "font-size: 10px; font-weight: bold;"
        )
        self._name_label.setStyleSheet(
            "font-size: 13px; font-weight: bold; color: #fff; background: transparent;"
            if selected else
            "font-size: 13px; font-weight: bold; color: #ddd; background: transparent;"
        )
        self._refresh_tabs(current_sheet_id)
        self._tabs_container.setVisible(selected and bool(self._sheet_tabs))
        self._refresh_frame_style()

    def _refresh_tabs(self, current_sheet_id: str | None) -> None:
        # 기존 탭 제거
        for tab in self._sheet_tabs:
            self._tabs_layout.removeWidget(tab)
            tab.deleteLater()
        self._sheet_tabs.clear()

        valid_sheets = [s for s in self._song.score_sheets if s.image_path]
        for i, sheet in enumerate(valid_sheets):
            tab = _SheetTab(sheet, i + 1, self._tabs_container)
            tab.set_current(sheet.id == current_sheet_id)
            tab.clicked.connect(lambda checked, s=sheet: self.sheet_selected.emit(s))
            self._sheet_tabs.append(tab)
            self._tabs_layout.insertWidget(self._tabs_layout.count() - 1, tab)

    def _refresh_frame_style(self) -> None:
        if self._is_selected:
            self.setStyleSheet("""
                QFrame#SongCard {
                    background: #1a2535;
                    border: 1px solid #2196f3;
                    border-radius: 8px;
                }
            """)
        else:
            self.setStyleSheet("""
                QFrame#SongCard {
                    background: #222;
                    border: 1px solid #2e2e2e;
                    border-radius: 8px;
                }
                QFrame#SongCard:hover {
                    background: #252525;
                    border: 1px solid #3a3a3a;
                }
            """)

    # ── 호버 시 액션 버튼 표시 ────────────────────────────────────────────

    def enterEvent(self, event) -> None:
        self._btn_edit.show()
        self._btn_remove.show()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._btn_edit.hide()
        self._btn_remove.hide()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            # 탭 클릭이 아닌 카드 영역 클릭 → 첫 번째 시트 선택
            valid = [s for s in self._song.score_sheets if s.image_path]
            if valid:
                self.sheet_selected.emit(valid[0])
        super().mousePressEvent(event)

    def contextMenuEvent(self, event) -> None:
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background: #252525; color: #ccc; border: 1px solid #3a3a3a; }
            QMenu::item { padding: 6px 18px; font-size: 12px; }
            QMenu::item:selected { background: #333; color: #fff; }
            QMenu::separator { height: 1px; background: #3a3a3a; margin: 4px 0; }
        """)
        edit_act = QAction("✏  곡 편집", self)
        edit_act.triggered.connect(lambda: self.edit_requested.emit(self._song))
        menu.addAction(edit_act)

        reload_act = QAction("🔄  슬라이드 새로고침", self)
        reload_act.triggered.connect(lambda: self.reload_requested.emit(self._song))
        menu.addAction(reload_act)

        menu.addSeparator()
        remove_act = QAction("✕  셋리스트에서 제거", self)
        remove_act.triggered.connect(lambda: self.remove_requested.emit(self._song))
        menu.addAction(remove_act)

        menu.exec(event.globalPos())


# ─── 단독 곡 편집 패널 (standalone 모드) ────────────────────────────────────


class _StandalonePanel(QWidget):
    """단독 곡 편집 모드 전용 — 시트 페이지 탭 목록."""

    sheet_selected = Signal(object)     # ScoreSheet
    add_sheet_requested = Signal()
    import_ppt_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._song: Song | None = None
        self._current_sheet_id: str | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # 곡 이름 헤더
        self._song_name = QLabel("—")
        self._song_name.setStyleSheet(
            "font-size: 14px; font-weight: 900; color: #fbc02d;"
        )
        layout.addWidget(self._song_name)

        # 페이지 카드 컨테이너
        self._pages_layout = QVBoxLayout()
        self._pages_layout.setSpacing(4)
        layout.addLayout(self._pages_layout)

        layout.addStretch()

        # PPT 가져오기 버튼
        self._btn_ppt = QPushButton("📥  PPT 가져오기")
        self._btn_ppt.setFixedHeight(34)
        self._btn_ppt.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_ppt.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_ppt.setStyleSheet("""
            QPushButton {
                background: #2a2a2a; color: #ccc;
                border: 1px solid #3a3a3a; border-radius: 6px;
                font-size: 11px; font-weight: bold;
            }
            QPushButton:hover { background: #333; border-color: #fbc02d; color: #fff; }
        """)
        self._btn_ppt.clicked.connect(self.import_ppt_requested.emit)
        layout.addWidget(self._btn_ppt)

        # 악보 이미지 추가 버튼
        self._btn_add = QPushButton("＋  악보 이미지 추가")
        self._btn_add.setFixedHeight(34)
        self._btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_add.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_add.setStyleSheet("""
            QPushButton {
                background: #fbc02d; color: #1a1a1a;
                border: none; border-radius: 6px;
                font-size: 11px; font-weight: bold;
            }
            QPushButton:hover { background: #f9a825; }
        """)
        self._btn_add.clicked.connect(self.add_sheet_requested.emit)
        layout.addWidget(self._btn_add)

    def set_song(self, song: Song | None, current_sheet_id: str | None = None) -> None:
        self._song = song
        self._current_sheet_id = current_sheet_id
        self._refresh()

    def set_current_sheet(self, sheet_id: str) -> None:
        self._current_sheet_id = sheet_id
        self._refresh()

    def _refresh(self) -> None:
        # 기존 페이지 카드 제거
        while self._pages_layout.count():
            item = self._pages_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self._song:
            self._song_name.setText("—")
            return

        self._song_name.setText(self._song.name)
        valid_sheets = [s for s in self._song.score_sheets if s.image_path]

        for i, sheet in enumerate(valid_sheets):
            card = _PageCard(sheet, i + 1, sheet.id == self._current_sheet_id)
            card.selected.connect(self.sheet_selected.emit)
            self._pages_layout.addWidget(card)

        if not valid_sheets:
            empty = QLabel("악보 이미지를 추가해 주세요")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet("font-size: 11px; color: #555; padding: 12px 0;")
            self._pages_layout.addWidget(empty)


class _PageCard(QFrame):
    """단독 모드에서 시트 페이지를 나타내는 작은 카드."""

    selected = Signal(object)  # ScoreSheet

    def __init__(self, sheet: ScoreSheet, page_num: int, active: bool, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("PageCard")
        self._sheet = sheet
        self._setup_ui(page_num, active)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _setup_ui(self, page_num: int, active: bool) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)

        badge = QLabel(f"P{page_num}")
        badge.setFixedSize(26, 26)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(
            "background: #fbc02d; color: #1a1a1a; border-radius: 13px; "
            "font-size: 10px; font-weight: bold;"
            if active else
            "background: #333; color: #888; border-radius: 13px; "
            "font-size: 10px; font-weight: bold;"
        )
        layout.addWidget(badge)

        name_lbl = QLabel(self._sheet.name)
        name_lbl.setStyleSheet(
            "font-size: 12px; color: #fff; font-weight: bold;"
            if active else
            "font-size: 12px; color: #aaa;"
        )
        layout.addWidget(name_lbl, 1)

        self.setStyleSheet(
            "QFrame#PageCard { background: #2a2200; border: 1px solid #fbc02d; border-radius: 6px; }"
            if active else
            "QFrame#PageCard { background: #1e1e1e; border: 1px solid #2e2e2e; border-radius: 6px; }"
            "QFrame#PageCard:hover { background: #242424; border-color: #444; }"
        )

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.selected.emit(self._sheet)
        super().mousePressEvent(event)


# ─── 메인 위젯 ──────────────────────────────────────────────────────────────


class SongListWidget(QWidget):
    """곡 목록 사이드바 — 셋리스트 카드 뷰 (프로젝트 모드) + 시트 탭 (단독 모드)

    Signals:
        song_selected: 곡/시트가 선택됨 (ScoreSheet)
        song_added:    새 곡이 추가됨 (ScoreSheet)
        song_removed:  곡/시트가 삭제됨 (str: sheet_id)
        song_reload_requested: 슬라이드 새로고침 요청 (Song)
        song_edit_requested:   곡 편집 모드 진입 요청 (Song)
    """

    song_selected = Signal(object)       # ScoreSheet
    song_added = Signal(object)          # ScoreSheet
    song_removed = Signal(str)
    song_reload_requested = Signal(object)
    song_edit_requested = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._project: Project | None = None
        self._main_window = None
        self._editable = True
        self._is_standalone = False
        self._cards: list[_SongCard] = []
        self._standalone_panel: _StandalonePanel | None = None
        self._setup_ui()

    # ── UI 구성 ──────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        self.setStyleSheet("background: #1a1a1a;")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── 헤더
        header_frame = QFrame()
        header_frame.setFixedHeight(44)
        header_frame.setStyleSheet(
            "background: #1e1e1e; border-bottom: 1px solid #2a2a2a;"
        )
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(12, 0, 12, 0)
        header_layout.setSpacing(6)

        self._title_label = QLabel("셋리스트")
        self._title_label.setStyleSheet(
            "font-size: 13px; font-weight: 900; color: #2196f3; letter-spacing: 0.5px;"
        )
        header_layout.addWidget(self._title_label)

        self._count_label = QLabel()
        self._count_label.setStyleSheet("font-size: 11px; color: #555;")
        header_layout.addWidget(self._count_label)
        header_layout.addStretch()

        root.addWidget(header_frame)

        # ── 스크롤 영역 (카드 목록)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical {
                border: none; background: transparent; width: 4px; margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #333; border-radius: 2px; min-height: 20px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        self._cards_widget = QWidget()
        self._cards_widget.setStyleSheet("background: transparent;")
        self._cards_layout = QVBoxLayout(self._cards_widget)
        self._cards_layout.setContentsMargins(8, 8, 8, 8)
        self._cards_layout.setSpacing(6)
        self._cards_layout.addStretch()

        self._scroll.setWidget(self._cards_widget)
        root.addWidget(self._scroll, 1)

        # ── 하단 액션 버튼
        self._footer = QFrame()
        self._footer.setStyleSheet(
            "background: #1e1e1e; border-top: 1px solid #2a2a2a;"
        )
        footer_layout = QVBoxLayout(self._footer)
        footer_layout.setContentsMargins(8, 8, 8, 8)
        footer_layout.setSpacing(6)

        self._btn_add_lib = QPushButton("＋  라이브러리에서 추가")
        self._btn_add_lib.setFixedHeight(34)
        self._btn_add_lib.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_add_lib.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_add_lib.setStyleSheet("""
            QPushButton {
                background: #2196f3; color: #fff;
                border: none; border-radius: 6px;
                font-size: 11px; font-weight: bold;
            }
            QPushButton:hover { background: #1e88e5; }
            QPushButton:disabled { background: #2a2a2a; color: #555; }
        """)
        self._btn_add_lib.clicked.connect(self._on_add_clicked)
        footer_layout.addWidget(self._btn_add_lib)

        self._btn_new_song = QPushButton("✚  새 곡 만들기")
        self._btn_new_song.setFixedHeight(30)
        self._btn_new_song.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_new_song.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_new_song.setStyleSheet("""
            QPushButton {
                background: transparent; color: #666;
                border: 1px solid #333; border-radius: 6px;
                font-size: 11px;
            }
            QPushButton:hover { background: #252525; color: #aaa; border-color: #444; }
            QPushButton:disabled { color: #444; border-color: #2a2a2a; }
        """)
        self._btn_new_song.clicked.connect(self._add_new_song_inline)
        footer_layout.addWidget(self._btn_new_song)

        root.addWidget(self._footer)

    # ── 퍼블릭 인터페이스 (MainWindow 호환) ──────────────────────────────

    def set_main_window(self, win) -> None:
        self._main_window = win

    def install_event_filter(self, filter_obj) -> None:
        self._scroll.installEventFilter(filter_obj)

    def set_standalone(self, standalone: bool) -> None:
        self._is_standalone = standalone
        if standalone:
            self._title_label.setText("곡 편집")
            self._title_label.setStyleSheet(
                "font-size: 13px; font-weight: 900; color: #fbc02d; letter-spacing: 0.5px;"
            )
            self._footer.setVisible(False)
        else:
            self._title_label.setText("셋리스트")
            self._title_label.setStyleSheet(
                "font-size: 13px; font-weight: 900; color: #2196f3; letter-spacing: 0.5px;"
            )
            self._footer.setVisible(True)

    def set_project(self, project: Project | None) -> None:
        self._project = project
        self.refresh_list()

    def set_editable(self, editable: bool) -> None:
        self._editable = editable
        self._btn_add_lib.setEnabled(editable)
        self._btn_new_song.setEnabled(editable)

    def refresh_list(self) -> None:
        """카드 목록 전체 갱신."""
        # 기존 카드 제거
        for card in self._cards:
            self._cards_layout.removeWidget(card)
            card.deleteLater()
        self._cards.clear()

        if self._standalone_panel:
            self._cards_layout.removeWidget(self._standalone_panel)
            self._standalone_panel.deleteLater()
            self._standalone_panel = None

        if not self._project:
            self._count_label.setText("")
            return

        if self._is_standalone:
            self._refresh_standalone()
        else:
            self._refresh_project()

    def _refresh_standalone(self) -> None:
        """단독 곡 편집 모드: 시트 페이지 패널."""
        song = (
            self._project.selected_songs[0]
            if self._project.selected_songs
            else None
        )
        current_sheet = self._project.get_current_score_sheet()
        current_id = current_sheet.id if current_sheet else None

        panel = _StandalonePanel()
        panel.set_song(song, current_id)
        panel.sheet_selected.connect(self._on_sheet_selected_direct)
        panel.add_sheet_requested.connect(self._on_add_sheet_clicked)
        panel.import_ppt_requested.connect(self._on_import_ppt_clicked)

        self._standalone_panel = panel
        self._cards_layout.insertWidget(self._cards_layout.count() - 1, panel)
        self._count_label.setText("")

    def _refresh_project(self) -> None:
        """프로젝트 모드: 셋리스트 카드 목록."""
        songs = self._project.selected_songs
        current_sheet = self._project.get_current_score_sheet()
        current_id = current_sheet.id if current_sheet else None

        for i, song in enumerate(songs):
            card = _SongCard(song, i + 1)

            # 현재 선택된 시트가 이 곡에 속하면 선택 상태
            song_sheet_ids = {s.id for s in song.score_sheets}
            is_selected = current_id in song_sheet_ids

            card.set_selected(is_selected, current_id if is_selected else None)
            card.sheet_selected.connect(self._on_sheet_selected_direct)
            card.edit_requested.connect(self.song_edit_requested.emit)
            card.remove_requested.connect(self._remove_song)
            card.reload_requested.connect(self.song_reload_requested.emit)

            self._cards.append(card)
            self._cards_layout.insertWidget(self._cards_layout.count() - 1, card)

        count = len(songs)
        self._count_label.setText(f"{count}곡" if count else "")

    def _on_sheet_selected_direct(self, sheet: ScoreSheet) -> None:
        if not self._project:
            return
        all_sheets = self._project.all_score_sheets
        for i, s in enumerate(all_sheets):
            if s.id == sheet.id:
                self._project.current_sheet_index = i
                break
        self._update_card_selection(sheet.id)
        self.song_selected.emit(sheet)
        if self._main_window:
            self._main_window._canvas.setFocus()

    def _update_card_selection(self, sheet_id: str) -> None:
        if self._is_standalone:
            if self._standalone_panel:
                self._standalone_panel.set_current_sheet(sheet_id)
            return

        for card in self._cards:
            song_sheet_ids = {s.id for s in card._song.score_sheets}
            is_selected = sheet_id in song_sheet_ids
            card.set_selected(is_selected, sheet_id if is_selected else None)

    # ── 탐색 (MainWindow에서 호출) ────────────────────────────────────────

    def select_sheet_by_id(self, sheet_id: str) -> None:
        if not self._project:
            return
        all_sheets = self._project.all_score_sheets
        for i, s in enumerate(all_sheets):
            if s.id == sheet_id:
                self._project.current_sheet_index = i
                break
        self._update_card_selection(sheet_id)

    def set_current_index(self, index: int) -> None:
        if not self._project:
            return
        sheets = self._project.all_score_sheets
        if 0 <= index < len(sheets):
            self._project.current_sheet_index = index
            self._update_card_selection(sheets[index].id)

    def clear_selection(self) -> None:
        for card in self._cards:
            card.set_selected(False)

    def select_next_song(self) -> bool:
        if not self._project:
            return False
        all_sheets = self._project.all_score_sheets
        if not all_sheets:
            return False
        idx = self._project.current_sheet_index
        if idx + 1 < len(all_sheets):
            self._project.current_sheet_index += 1
            new_sheet = all_sheets[self._project.current_sheet_index]
            self._update_card_selection(new_sheet.id)
            self.song_selected.emit(new_sheet)
            if self._main_window:
                self._main_window.statusBar().showMessage(
                    f"시트 {self._project.current_sheet_index + 1}/{len(all_sheets)}", 1000
                )
            return True
        return False

    def select_previous_song(self) -> bool:
        if not self._project:
            return False
        all_sheets = self._project.all_score_sheets
        if not all_sheets:
            return False
        idx = self._project.current_sheet_index
        if idx > 0:
            self._project.current_sheet_index -= 1
            new_sheet = all_sheets[self._project.current_sheet_index]
            self._update_card_selection(new_sheet.id)
            self.song_selected.emit(new_sheet)
            if self._main_window:
                self._main_window.statusBar().showMessage(
                    f"시트 {self._project.current_sheet_index + 1}/{len(all_sheets)}", 1000
                )
            return True
        return False

    # ── 곡 추가 / 관리 ───────────────────────────────────────────────────

    def _get_project_dir(self) -> Path | None:
        if not self._main_window or not self._main_window._project_path:
            return None
        if self._is_standalone:
            return self._main_window._project_path
        return self._main_window._project_path.parent

    def _on_add_clicked(self) -> None:
        """라이브러리에서 곡 추가 — 사용 가능한 곡 목록 메뉴."""
        if not self._project or not self._main_window:
            return

        project_dir = self._main_window._project_path.parent
        songs_dir = project_dir / "songs"
        if not songs_dir.exists():
            songs_dir.mkdir(parents=True, exist_ok=True)

        included = {s.name for s in self._project.selected_songs}
        available = [
            f.name
            for f in sorted(songs_dir.iterdir())
            if f.is_dir() and (f / "song.json").exists() and f.name not in included
        ]

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background: #252525; color: #ccc;
                border: 1px solid #3a3a3a; border-radius: 6px;
                padding: 4px 0;
            }
            QMenu::item { padding: 8px 20px; font-size: 12px; }
            QMenu::item:selected { background: #333; color: #fff; }
            QMenu::item:disabled { color: #555; }
            QMenu::separator { height: 1px; background: #3a3a3a; margin: 4px 8px; }
        """)

        if available:
            title = menu.addAction("라이브러리")
            title.setEnabled(False)
            for name in available:
                act = menu.addAction(f"  {name}")
                act.triggered.connect(
                    lambda checked, n=name: self._add_existing_song(n)
                )
        else:
            empty = menu.addAction("추가 가능한 곡이 없습니다")
            empty.setEnabled(False)

        menu.exec(self._btn_add_lib.mapToGlobal(QPoint(0, -menu.sizeHint().height())))

    def _add_existing_song(self, name: str) -> None:
        if not self._project or not self._main_window:
            return
        project_dir = self._main_window._project_path.parent
        song = self._load_song_from_folder(name, project_dir)
        if not song:
            QMessageBox.warning(self, "오류", f"'{name}' 곡을 불러올 수 없습니다.")
            return
        self._project.selected_songs.append(song)
        if name not in self._project.song_order:
            self._project.song_order.append(name)
        self.refresh_list()
        if self._main_window:
            self._main_window._mark_dirty()

    def _load_song_from_folder(self, name: str, project_dir: Path) -> Song | None:
        song_dir = project_dir / "songs" / name
        song_json = song_dir / "song.json"
        if not song_json.exists():
            return None
        try:
            with open(song_json, encoding="utf-8-sig") as f:
                data = json.load(f)
            sheets_data = data.get("sheets", [])
            if not sheets_data and data.get("sheet"):
                sheets_data = [data["sheet"]]
            score_sheets = [ScoreSheet.from_dict(sd) for sd in sheets_data if sd]
            if not score_sheets:
                score_sheets = [ScoreSheet(name=name)]
            return Song(
                name=name,
                folder=Path("songs") / name,
                score_sheets=score_sheets,
                project_dir=project_dir,
            )
        except Exception:
            return None

    def _add_new_song_inline(self) -> None:
        if not self._project or not self._main_window:
            return
        name, ok = QInputDialog.getText(self, "새 곡 만들기", "곡 이름:")
        if not ok or not name.strip():
            return
        name = name.strip()
        project_dir = self._main_window._project_path.parent
        song_dir = project_dir / "songs" / name
        if song_dir.exists():
            QMessageBox.warning(self, "오류", f"'{name}' 곡이 이미 존재합니다.")
            return
        try:
            repo = getattr(self._main_window, "_repo", None)
            if repo:
                repo.init_song_folder(song_dir, name)
            else:
                song_dir.mkdir(parents=True)
                (song_dir / "sheets").mkdir(exist_ok=True)
                with open(song_dir / "song.json", "w", encoding="utf-8-sig") as f:
                    json.dump({"name": name, "sheets": []}, f, ensure_ascii=False, indent=2)

            song = Song(name=name, folder=Path("songs") / name, score_sheets=[], project_dir=project_dir)
            self._project.selected_songs.append(song)
            if name not in self._project.song_order:
                self._project.song_order.append(name)
            self.refresh_list()
            if self._main_window:
                self._main_window._mark_dirty()
        except Exception as e:
            QMessageBox.warning(self, "오류", f"곡 생성 실패: {e}")

    def _remove_song(self, song: Song) -> None:
        if not self._project:
            return
        reply = QMessageBox.question(
            self,
            "곡 제거",
            f"'{song.name}'을(를) 셋리스트에서 제거하시겠습니까?\n(파일은 삭제되지 않습니다)",
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

    # ── 단독 모드 전용 액션 ───────────────────────────────────────────────

    def _on_add_sheet_clicked(self) -> None:
        if self._project and self._project.selected_songs:
            self._set_song_image(self._project.selected_songs[0])

    def _on_import_ppt_clicked(self) -> None:
        if self._project and self._project.selected_songs:
            self._import_song_ppt(self._project.selected_songs[0])

    def _set_song_image(self, song: Song) -> None:
        import shutil

        project_dir = self._get_project_dir() or Path.cwd()
        song_dir = project_dir / song.folder
        image_path, _ = QFileDialog.getOpenFileName(
            self,
            f"'{song.name}'에 추가할 악보 이미지 선택",
            str(song_dir) if song_dir.exists() else str(project_dir),
            "이미지 (*.jpg *.jpeg *.png *.bmp)",
        )
        if not image_path:
            return

        p_path = Path(image_path).resolve()
        default_name = f"{song.name} - {p_path.stem}"
        sheet_name, ok = QInputDialog.getText(
            self, "시트 이름 지정",
            f"'{p_path.name}'의 이름을 입력하세요:",
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

        rel_sheets = (
            sheets_dir.relative_to(song.folder)
            if song.folder and sheets_dir.is_relative_to(song.folder)
            else Path("sheets")
        )
        new_sheet = ScoreSheet(
            name=sheet_name.strip(),
            image_path=str(rel_sheets / p_path.name),
        )
        song.score_sheets.append(new_sheet)
        self.refresh_list()
        self.select_sheet_by_id(new_sheet.id)
        if self._main_window:
            self._main_window._mark_dirty()

    def _import_song_ppt(self, song: Song) -> None:
        import shutil

        file_path, _ = QFileDialog.getOpenFileName(
            self, "PPT 파일 선택", "", "PowerPoint 파일 (*.pptx)"
        )
        if not file_path:
            return

        dest = song.abs_slides_path
        if dest.exists():
            reply = QMessageBox.question(
                self, "덮어쓰기",
                "이미 PPT 파일이 있습니다. 덮어쓰시겠습니까?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        try:
            shutil.copy2(file_path, dest)
            self.song_reload_requested.emit(song)
            self.refresh_list()
            QMessageBox.information(self, "완료", "PPT 파일을 성공적으로 가져왔습니다.")
        except Exception as e:
            QMessageBox.critical(self, "오류", f"파일 가져오기 실패: {e}")

    # ── 드롭 (외부 파일/폴더) ────────────────────────────────────────────

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        if not self._project or not self._main_window:
            return
        project_dir = self._main_window._project_path.parent
        imported = 0
        for url in event.mimeData().urls():
            src = Path(url.toLocalFile())
            if src.is_dir() and (src / "song.json").exists():
                try:
                    name = self._main_window._repo.import_song_folder(project_dir, src)
                    song_obj = self._main_window._repo.load_standalone_song(
                        project_dir / "songs" / name
                    ).selected_songs[0]
                    song_obj.project_dir = project_dir
                    if name not in [s.name for s in self._project.selected_songs]:
                        self._project.selected_songs.append(song_obj)
                        if name not in self._project.song_order:
                            self._project.song_order.append(name)
                        imported += 1
                except Exception as e:
                    QMessageBox.warning(self, "가져오기 실패", f"'{src.name}': {e}")

        if imported:
            self.refresh_list()
            self._main_window._mark_dirty()
