from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt, Signal
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
    BORDER, BORDER_FOCUS, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_TERTIARY, TEXT_INVERSE,
    ACCENT, ACCENT_HOVER, ACCENT_MUTED, ACCENT_SURFACE,
    GREEN, GREEN_MUTED, AMBER, RED,
    RADIUS_MD, RADIUS_LG, RADIUS_XL,
    FONT_SM, FONT_MD, FONT_LG, FONT_XL, FONT_2XL, FONT_TITLE,
    SP_SM, SP_MD, SP_LG, SP_XL, SP_2XL,
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
        act = QAction("목록에서 제거", self)
        act.triggered.connect(lambda: self.remove_requested.emit(self._path, self._kind))
        menu.addAction(act)
        menu.exec(event.globalPos())


# ─── 패널 ────────────────────────────────────────────────────────────────────


class _Panel(QFrame):
    """홈 화면의 좌/우 패널."""

    def __init__(self, title: str, subtitle: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("HomePanel")
        self._cards: list[_RecentCard] = []

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
        root.setContentsMargins(SP_XL, SP_XL, SP_XL, SP_XL)
        root.setSpacing(0)

        # 제목
        lbl_title = QLabel(title)
        lbl_title.setStyleSheet(
            f"font-size: {FONT_2XL}px; font-weight: 600; color: {TEXT_PRIMARY};"
        )
        root.addWidget(lbl_title)
        root.addSpacing(4)

        # 부제
        lbl_sub = QLabel(subtitle)
        lbl_sub.setStyleSheet(f"font-size: {FONT_MD}px; color: {TEXT_TERTIARY};")
        root.addWidget(lbl_sub)
        root.addSpacing(SP_XL)

        # 버튼 영역
        self._btn_layout = QHBoxLayout()
        self._btn_layout.setSpacing(SP_SM)
        self._btn_layout.setContentsMargins(0, 0, 0, 0)
        root.addLayout(self._btn_layout)
        root.addSpacing(SP_2XL)

        # "최근" 레이블
        self._recent_label = QLabel("최근 항목")
        self._recent_label.setStyleSheet(
            f"font-size: {FONT_SM}px; color: {TEXT_TERTIARY}; "
            "letter-spacing: 1px;"
        )
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

        # 빈 상태
        self._empty = QLabel("아직 없습니다")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setStyleSheet(
            f"font-size: {FONT_MD}px; color: {TEXT_TERTIARY}; padding: {SP_2XL}px 0;"
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

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background: {BG_DEEP};")
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(60, 48, 60, 32)
        root.setSpacing(0)

        # ── 헤더
        hdr = QVBoxLayout()
        hdr.setSpacing(6)

        title = QLabel("FLOW")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            f"font-size: 36px; font-weight: 300; color: {ACCENT}; "
            "letter-spacing: 8px;"
        )
        hdr.addWidget(title)

        sub = QLabel("예배 슬라이드 송출 시스템")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet(f"font-size: {FONT_LG}px; color: {TEXT_TERTIARY};")
        hdr.addWidget(sub)

        root.addLayout(hdr)
        root.addSpacing(48)

        # ── 두 패널
        body = QHBoxLayout()
        body.setSpacing(SP_XL)

        self._song_panel = _Panel(
            "곡 라이브러리",
            "악보 · PPT · 핫스팟 매핑의 기본 단위",
        )
        self._btn_new_song = self._song_panel.add_action_btn("새 곡 만들기", primary=True)
        self._btn_open_song = self._song_panel.add_action_btn("폴더에서 열기")
        self._btn_new_song.clicked.connect(self.new_song_requested.emit)
        self._btn_open_song.clicked.connect(self._on_open_song_clicked)
        body.addWidget(self._song_panel, 1)

        self._proj_panel = _Panel(
            "프로젝트",
            "곡을 조합해 예배 셋리스트로 사용",
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
