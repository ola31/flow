from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt, QPoint, Signal
from PySide6.QtGui import QAction, QColor, QFont
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from flow.ui.styles import (
    BG_DEEP, BG_SURFACE, BG_ELEVATED, BG_HOVER, BG_INPUT,
    BORDER, BORDER_FOCUS, BORDER_SUBTLE_RGBA, BORDER_STANDARD_RGBA,
    SURFACE_GHOST, SURFACE_SUBTLE, SURFACE_RAISED,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_TERTIARY, TEXT_INVERSE,
    ACCENT, ACCENT_HOVER, ACCENT_MUTED, ACCENT_SURFACE,
    GREEN, GREEN_MUTED, AMBER, RED,
    RADIUS_SM, RADIUS_MD, RADIUS_LG, RADIUS_XL,
    FONT_XS, FONT_SM, FONT_MD, FONT_LG, FONT_XL, FONT_2XL, FONT_TITLE,
    FW_REGULAR, FW_MEDIUM, FW_SEMI,
    SP_XS, SP_SM, SP_MD, SP_LG, SP_XL, SP_2XL,
)


def _song_status(song_path: str) -> tuple[str, str, str]:
    """곡 폴더 검사 → (상태 텍스트, 툴팁, 색상)."""
    p = Path(song_path)
    has_sheet = any(
        f.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp"}
        for d in (p / "sheets", p / "sheet")
        if d.is_dir()
        for f in d.iterdir()
    )
    has_ppt = (p / "slides.pptx").exists()

    if has_sheet and has_ppt:
        return "준비완료", "악보 · PPT 준비완료", GREEN
    if has_sheet:
        return "PPT 없음", "PPT 없음", AMBER
    if has_ppt:
        return "악보 없음", "악보 없음", AMBER
    return "미설정", "아직 설정 안 됨", TEXT_TERTIARY


def _project_song_count(project_path: str) -> str:
    try:
        with open(Path(project_path), encoding="utf-8-sig") as f:
            data = json.load(f)
        count = len(data.get("song_order", []))
        return f"{count}곡" if count else ""
    except Exception:
        return ""


def _shadow(parent, blur: int = 24, offset: int = 4, opacity: int = 80) -> None:
    """드롭 섀도우를 위젯에 적용."""
    effect = QGraphicsDropShadowEffect(parent)
    effect.setBlurRadius(blur)
    effect.setOffset(0, offset)
    effect.setColor(QColor(0, 0, 0, opacity))
    parent.setGraphicsEffect(effect)


# ─── 최근 항목 카드 ──────────────────────────────────────────────────────────


class _RecentCard(QFrame):
    """최근 항목 하나를 나타내는 카드."""

    clicked = Signal(str, str)       # (path, kind)
    remove_requested = Signal(str, str)
    clone_requested = Signal(str)    # (project path) — kind="project"에서만 발생

    def __init__(self, path: str, kind: str, title: str, detail: str,
                 badge: str = "", badge_color: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("RecentCard")
        self._path = path
        self._kind = kind
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._setup_ui(title, detail, badge, badge_color)

    def _setup_ui(self, title: str, detail: str, badge: str, badge_color: str) -> None:
        self.setStyleSheet(f"""
            QFrame#RecentCard {{
                background: {BG_ELEVATED};
                border: none;
                border-radius: {RADIUS_LG}px;
            }}
            QFrame#RecentCard:hover {{
                background: {BG_HOVER};
            }}
            QFrame#RecentCard QLabel {{
                background: transparent;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SP_LG, SP_MD, SP_LG, SP_MD)
        layout.setSpacing(4)

        # 제목 행
        top = QHBoxLayout()
        top.setSpacing(SP_SM)
        name_lbl = QLabel(title)
        name_lbl.setStyleSheet(
            f"font-size: {FONT_LG}px; color: {TEXT_PRIMARY};"
        )
        top.addWidget(name_lbl, 1)

        if badge:
            b = QLabel(badge)
            b.setStyleSheet(
                f"font-size: 10px; color: {badge_color}; "
                f"padding: 0 2px;"
            )
            top.addWidget(b)

        layout.addLayout(top)

        # 경로
        path_lbl = QLabel(detail)
        path_lbl.setStyleSheet(f"font-size: {FONT_SM}px; color: {TEXT_TERTIARY};")
        path_lbl.setWordWrap(True)
        layout.addWidget(path_lbl)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._path, self._kind)
        super().mousePressEvent(event)

    def contextMenuEvent(self, event) -> None:
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{ background: {BG_ELEVATED}; color: {TEXT_PRIMARY};
                     border: 1px solid {BORDER_FOCUS}; border-radius: {RADIUS_MD}px; }}
            QMenu::item {{ padding: {SP_SM}px {SP_LG}px; font-size: {FONT_MD}px; }}
            QMenu::item:selected {{ background: {ACCENT_MUTED}; color: {ACCENT}; }}
        """)

        if self._kind == "project":
            clone_act = QAction("복제해서 새로 만들기", self)
            clone_act.triggered.connect(lambda: self.clone_requested.emit(self._path))
            menu.addAction(clone_act)
            menu.addSeparator()

        act = QAction("목록에서 제거", self)
        act.triggered.connect(lambda: self.remove_requested.emit(self._path, self._kind))
        menu.addAction(act)
        menu.exec(event.globalPos())


# ─── 패널 ────────────────────────────────────────────────────────────────────


class _Panel(QFrame):
    """홈 화면의 좌/우 패널."""

    def __init__(
        self,
        title: str,
        subtitle: str,
        icon_name: str = "",
        empty_icon: str = "search",
        empty_title: str = "아직 없습니다",
        empty_description: str = "",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("HomePanel")
        self._cards: list[_RecentCard] = []
        self._icon_name = icon_name
        self._empty_config = (empty_icon, empty_title, empty_description)

        self.setStyleSheet(f"""
            QFrame#HomePanel {{
                background: {BG_SURFACE};
                border: none;
                border-radius: {RADIUS_XL}px;
            }}
            QFrame#HomePanel QLabel {{
                background: transparent;
            }}
            QFrame#HomePanel QPushButton {{
                background: transparent;
            }}
        """)
        _shadow(self, blur=32, offset=6, opacity=60)

        root = QVBoxLayout(self)
        root.setContentsMargins(SP_LG + 4, SP_LG + 4, SP_LG + 4, SP_LG + 4)
        root.setSpacing(0)

        # 제목
        lbl_title = QLabel(title)
        lbl_title.setStyleSheet(
            f"font-size: {FONT_2XL}px; font-weight: {FW_SEMI}; color: {TEXT_PRIMARY};"
        )
        root.addWidget(lbl_title)
        root.addSpacing(SP_XS)

        # 부제
        lbl_sub = QLabel(subtitle)
        lbl_sub.setStyleSheet(
            f"font-size: {FONT_MD}px; color: {TEXT_TERTIARY}; font-weight: {FW_REGULAR};"
        )
        root.addWidget(lbl_sub)
        root.addSpacing(SP_LG)

        # 버튼 영역
        self._btn_layout = QHBoxLayout()
        self._btn_layout.setSpacing(SP_SM)
        self._btn_layout.setContentsMargins(0, 0, 0, 0)
        root.addLayout(self._btn_layout)
        root.addSpacing(SP_XL)

        # "최근" 레이블 — 작은 capslike 라벨 (Linear 패턴)
        # letter-spacing은 stylesheet 미지원 → QFont로 적용
        self._recent_label = QLabel("최근 항목")
        self._recent_label.setStyleSheet(
            f"font-size: {FONT_XS}px; color: {TEXT_TERTIARY}; "
            f"font-weight: {FW_MEDIUM};"
        )
        _f = self._recent_label.font()
        _f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.0)
        self._recent_label.setFont(_f)
        root.addWidget(self._recent_label)
        root.addSpacing(SP_SM)

        # 카드 스크롤 영역
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"""
            QScrollArea {{ background: transparent; border: none; }}
            QScrollBar:vertical {{
                border: none; background: transparent; width: 4px; margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background: {BORDER_FOCUS}; border-radius: 2px; min-height: 20px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)

        self._cards_widget = QWidget()
        self._cards_widget.setStyleSheet("background: transparent;")
        self._cards_layout = QVBoxLayout(self._cards_widget)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setSpacing(SP_SM)
        self._cards_layout.addStretch()

        scroll.setWidget(self._cards_widget)
        root.addWidget(scroll, 1)

        # 빈 상태 — Linear-style 디자인
        from flow.ui.empty_state import EmptyState
        empty_icon, empty_title, empty_desc = self._empty_config
        self._empty = EmptyState(
            icon=empty_icon,
            title=empty_title,
            description=empty_desc,
            compact=True,
        )
        root.addWidget(self._empty)

    def add_action_btn(self, text: str, primary: bool = False) -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedHeight(36)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        if primary:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {ACCENT}; color: #fff;
                    border: none; border-radius: {RADIUS_MD}px;
                    font-size: {FONT_MD}px; font-weight: 500; padding: 0 {SP_LG}px;
                }}
                QPushButton:hover {{ background: {ACCENT_HOVER}; }}
            """)
        else:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; color: {TEXT_SECONDARY};
                    border: 1px solid {BORDER}; border-radius: {RADIUS_MD}px;
                    font-size: {FONT_MD}px; padding: 0 {SP_LG}px;
                }}
                QPushButton:hover {{ background: {BG_HOVER}; color: {TEXT_PRIMARY}; border-color: {BORDER_FOCUS}; }}
            """)
        self._btn_layout.addWidget(btn)
        return btn

    def set_cards(self, cards: list[_RecentCard]) -> None:
        for c in self._cards:
            self._cards_layout.removeWidget(c)
            c.deleteLater()
        self._cards = cards

        for c in cards:
            self._cards_layout.insertWidget(self._cards_layout.count() - 1, c)

        has = bool(cards)
        self._recent_label.setVisible(has)
        self._empty.setVisible(not has)

        if has:
            cards[0].setFocus()


# ─── 메인 런처 ───────────────────────────────────────────────────────────────


class ProjectLauncher(QWidget):
    project_selected = Signal(str)
    song_selected = Signal(str)
    new_project_requested = Signal()
    new_song_requested = Signal()
    open_project_requested = Signal()
    remove_recent_requested = Signal(str, str)
    switch_workspace_requested = Signal()
    clone_project_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background: {BG_DEEP};")
        self._workspace = None
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(48, SP_MD, 48, SP_XL)
        root.setSpacing(0)

        # ── 워크스페이스 헤더 — 단일 메뉴 트리거 버튼
        # 좌측 상단에 작게 배치 (Linear 패턴: 팀/워크스페이스 selector)
        ws_bar = QHBoxLayout()
        ws_bar.setSpacing(0)

        self._ws_button = QPushButton("워크스페이스 없음")
        self._ws_button.setFixedHeight(30)
        self._ws_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._ws_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._ws_button.setStyleSheet(
            f"""
            QPushButton {{
                background: {SURFACE_GHOST};
                color: {TEXT_SECONDARY};
                border: 1px solid {BORDER_SUBTLE_RGBA};
                border-radius: {RADIUS_MD}px;
                font-size: {FONT_SM}px;
                font-weight: {FW_MEDIUM};
                padding: 0 {SP_MD}px;
                text-align: left;
            }}
            QPushButton:hover {{
                background: {SURFACE_SUBTLE};
                border-color: {BORDER_STANDARD_RGBA};
                color: {TEXT_PRIMARY};
            }}
            """
        )
        self._ws_button.clicked.connect(self._show_workspace_menu)
        ws_bar.addWidget(self._ws_button)
        ws_bar.addStretch()
        root.addLayout(ws_bar)
        root.addSpacing(SP_2XL + SP_SM)

        # ── 메인 헤더 (FLOW 타이틀 + 부제)
        hdr = QVBoxLayout()
        hdr.setSpacing(SP_SM)

        title = QLabel("FLOW")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            f"font-size: 36px; font-weight: {FW_REGULAR}; color: {TEXT_PRIMARY};"
        )
        _t_font = title.font()
        _t_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 8.0)
        title.setFont(_t_font)
        hdr.addWidget(title)

        sub = QLabel("악보 기반 슬라이드 송출 시스템")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet(
            f"font-size: {FONT_MD}px; color: {TEXT_TERTIARY}; font-weight: {FW_REGULAR};"
        )
        hdr.addWidget(sub)

        root.addLayout(hdr)
        root.addSpacing(SP_2XL + SP_SM)

        # ── 두 패널
        body = QHBoxLayout()
        body.setSpacing(SP_LG)

        self._song_panel = _Panel(
            "곡 라이브러리",
            "악보 · PPT · 핫스팟 매핑의 기본 단위",
            icon_name="music_note",
            empty_icon="image",
            empty_title="곡이 없습니다",
            empty_description="새 곡을 만들거나 외부 폴더에서 가져오세요",
        )
        self._btn_new_song = self._song_panel.add_action_btn("새 곡 만들기", primary=True)
        self._btn_open_song = self._song_panel.add_action_btn("폴더에서 열기")
        self._btn_new_song.clicked.connect(self.new_song_requested.emit)
        self._btn_open_song.clicked.connect(self._on_open_song_clicked)
        body.addWidget(self._song_panel, 1)

        self._proj_panel = _Panel(
            "프로젝트",
            "곡을 조합해 셋리스트로 사용",
            icon_name="view_list",
            empty_icon="view_list",
            empty_title="프로젝트가 없습니다",
            empty_description="새 프로젝트를 만들어 곡들을 셋리스트로 구성하세요",
        )
        self._btn_new_proj = self._proj_panel.add_action_btn("새 프로젝트", primary=True)
        self._btn_open_proj = self._proj_panel.add_action_btn("폴더에서 열기")
        self._btn_new_proj.clicked.connect(self.new_project_requested.emit)
        self._btn_open_proj.clicked.connect(self.open_project_requested.emit)
        body.addWidget(self._proj_panel, 1)

        root.addLayout(body, 1)
        root.addSpacing(SP_LG)

        # 푸터
        footer = QLabel("v1.0.0")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setStyleSheet(f"font-size: 10px; color: {TEXT_TERTIARY};")
        root.addWidget(footer)

    # ── 데이터 설정 ─────────────────────────────────────────────

    def set_workspace(self, workspace) -> None:
        """워크스페이스를 설정하고 프로젝트/라이브러리 목록을 자동 갱신."""
        self._workspace = workspace
        if workspace is None:
            self._ws_button.setText("워크스페이스 없음 ▾")
            self._ws_button.setToolTip("")
            self._song_panel.set_cards([])
            self._proj_panel.set_cards([])
            return

        self._ws_button.setText(f"{workspace.name}  ▾")
        self._ws_button.setToolTip(str(workspace.root))
        self.refresh_workspace_items()

    def _show_workspace_menu(self) -> None:
        """워크스페이스 헤더 클릭 시 액션 메뉴 표시."""
        from flow.ui.icons import icon_qicon

        menu = QMenu(self)
        menu.setStyleSheet(self._menu_stylesheet())

        if self._workspace is not None:
            act_open = QAction(
                icon_qicon("folder_open", 16, TEXT_SECONDARY),
                "워크스페이스 폴더 열기",
                self,
            )
            act_open.triggered.connect(self._open_workspace_folder)
            menu.addAction(act_open)
            menu.addSeparator()

        act_switch = QAction(
            icon_qicon("refresh", 16, TEXT_SECONDARY),
            "워크스페이스 변경 / 새로 만들기",
            self,
        )
        act_switch.triggered.connect(self.switch_workspace_requested.emit)
        menu.addAction(act_switch)

        # 버튼 바로 아래에 표시
        below = self._ws_button.mapToGlobal(QPoint(0, self._ws_button.height() + 4))
        menu.exec(below)

    def _menu_stylesheet(self) -> str:
        return f"""
            QMenu {{ background: {BG_ELEVATED}; color: {TEXT_PRIMARY};
                     border: 1px solid {BORDER_FOCUS}; border-radius: {RADIUS_MD}px;
                     padding: 4px; }}
            QMenu::item {{ padding: {SP_SM}px {SP_LG}px; font-size: {FONT_MD}px;
                            border-radius: {RADIUS_SM}px; }}
            QMenu::item:selected {{ background: {BG_HOVER}; color: {TEXT_PRIMARY}; }}
            QMenu::separator {{ height: 1px; background: {BORDER}; margin: 4px 6px; }}
        """

    def _open_workspace_folder(self) -> None:
        if self._workspace is None:
            return
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._workspace.root)))

    def refresh_workspace_items(self) -> None:
        """워크스페이스의 projects/ 및 library/ 내용을 읽어 카드 갱신."""
        if self._workspace is None:
            return

        # 프로젝트 카드 (projects/ 하위)
        proj_cards = []
        for proj_dir in self._workspace.list_projects():
            pj_path = proj_dir / "project.json"
            count_txt = _project_song_count(str(pj_path))
            card = _RecentCard(
                str(pj_path),
                "project",
                proj_dir.name,
                str(proj_dir),
                count_txt,
                ACCENT,
            )
            card.clicked.connect(self._on_card_clicked)
            card.remove_requested.connect(self.remove_recent_requested.emit)
            card.clone_requested.connect(self.clone_project_requested.emit)
            proj_cards.append(card)
        self._proj_panel.set_cards(proj_cards)

        # 라이브러리 곡 카드 (library/ 하위)
        song_cards = []
        for song_dir in self._workspace.list_library_songs():
            status, tip, color = _song_status(str(song_dir))
            card = _RecentCard(
                str(song_dir),
                "song",
                song_dir.name,
                str(song_dir),
                status,
                color,
            )
            card.clicked.connect(self._on_card_clicked)
            card.remove_requested.connect(self.remove_recent_requested.emit)
            song_cards.append(card)
        self._song_panel.set_cards(song_cards)

    def set_recent_items(self, projects: list[str], songs: list[str]) -> None:
        # 곡 카드
        song_cards = []
        for s_path in songs:
            p = Path(s_path)
            status, tip, color = _song_status(s_path)
            card = _RecentCard(s_path, "song", p.name, str(s_path), status, color)
            card.clicked.connect(self._on_card_clicked)
            card.remove_requested.connect(self.remove_recent_requested.emit)
            song_cards.append(card)
        self._song_panel.set_cards(song_cards)

        # 프로젝트 카드
        proj_cards = []
        for p_path in projects:
            p = Path(p_path)
            name = p.parent.name if p.name == "project.json" else p.stem
            count = _project_song_count(p_path)
            badge = count if count else ""
            card = _RecentCard(p_path, "project", name, str(p_path), badge, ACCENT)
            card.clicked.connect(self._on_card_clicked)
            card.remove_requested.connect(self.remove_recent_requested.emit)
            card.clone_requested.connect(self.clone_project_requested.emit)
            proj_cards.append(card)
        self._proj_panel.set_cards(proj_cards)

    # ── 이벤트 핸들러 ───────────────────────────────────────────

    def _on_card_clicked(self, path: str, kind: str) -> None:
        if kind == "project":
            self.project_selected.emit(path)
        else:
            self.song_selected.emit(path)

    def _on_open_song_clicked(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "곡 폴더 선택", "", QFileDialog.Option.ShowDirsOnly
        )
        if not folder:
            return
        p = Path(folder)
        if (p / "song.json").exists():
            self.song_selected.emit(str(p))
            return
        if (p.parent / "song.json").exists():
            self.song_selected.emit(str(p.parent))
            return
        QMessageBox.warning(
            self,
            "곡 폴더를 찾을 수 없습니다",
            "선택한 폴더에 song.json 파일이 없습니다.\n올바른 곡 폴더를 선택해 주세요.",
        )
