from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from PySide6.QtGui import QAction


def _song_status(song_path: str) -> tuple[str, str]:
    """곡 폴더를 빠르게 검사해 (아이콘, 툴팁) 반환 — JSON 파싱 없이 파일 존재만 확인."""
    p = Path(song_path)
    has_sheet = any(
        f.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp"}
        for d in (p / "sheets", p / "sheet")
        if d.is_dir()
        for f in d.iterdir()
    )
    has_ppt = (p / "slides.pptx").exists()

    if has_sheet and has_ppt:
        return "준비완료", "악보 · PPT 준비완료"
    if has_sheet:
        return "미완성", "PPT 없음"
    if has_ppt:
        return "미완성", "악보 없음"
    return "○", "아직 설정 안 됨"


def _project_song_count(project_path: str) -> str:
    """project.json에서 song_order 개수만 빠르게 읽어 반환."""
    try:
        import json
        p = Path(project_path)
        with open(p, encoding="utf-8-sig") as f:
            data = json.load(f)
        count = len(data.get("song_order", []))
        return f"{count}곡" if count else ""
    except Exception:
        return ""


class _PanelList(QListWidget):
    """패널 전용 리스트 위젯 (공통 스타일)."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QListWidget {
                background: transparent;
                border: none;
                outline: none;
            }
            QListWidget::item {
                background: #2a2a2a;
                border-radius: 6px;
                margin-bottom: 4px;
                padding: 10px 12px;
                color: #ddd;
                border: 1px solid transparent;
            }
            QListWidget::item:hover {
                background: #333;
                border: 1px solid #3d3d3d;
            }
            QListWidget::item:selected {
                background: #263545;
                border: 1px solid #2196f3;
                color: #fff;
            }
            QScrollBar:vertical {
                border: none; background: transparent; width: 6px; margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #444; border-radius: 3px; min-height: 20px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)
        self.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.setWordWrap(True)


class _Panel(QFrame):
    """좌/우 패널 컨테이너."""
    def __init__(self, title: str, subtitle: str, accent: str, parent=None):
        super().__init__(parent)
        self._accent = accent
        self.setStyleSheet(f"""
            QFrame {{
                background: #1e1e1e;
                border: 1px solid #2e2e2e;
                border-top: 3px solid {accent};
                border-radius: 10px;
            }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(0)

        # 제목
        lbl_title = QLabel(title)
        lbl_title.setStyleSheet(
            f"font-size: 15px; font-weight: 900; color: {accent}; background: transparent; border: none;"
        )
        root.addWidget(lbl_title)

        # 부제
        lbl_sub = QLabel(subtitle)
        lbl_sub.setStyleSheet(
            "font-size: 11px; color: #666; background: transparent; border: none; margin-bottom: 14px;"
        )
        root.addWidget(lbl_sub)

        # 버튼 영역
        self._btn_layout = QHBoxLayout()
        self._btn_layout.setSpacing(8)
        self._btn_layout.setContentsMargins(0, 0, 0, 12)
        root.addLayout(self._btn_layout)

        # 구분선
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background: #2e2e2e; max-height: 1px; border: none;")
        root.addWidget(sep)
        root.addSpacing(10)

        # 최근 항목 레이블
        self._recent_label = QLabel("최근 항목")
        self._recent_label.setStyleSheet(
            "font-size: 11px; font-weight: bold; color: #555; background: transparent; border: none; margin-bottom: 6px;"
        )
        root.addWidget(self._recent_label)

        # 리스트
        self.list = _PanelList()
        root.addWidget(self.list, 1)

        # 빈 상태
        self._empty = QLabel("아직 없습니다")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setStyleSheet(
            "font-size: 12px; color: #444; background: transparent; border: none; padding: 20px 0;"
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
                    background: {self._accent}; color: #fff;
                    border: none; border-radius: 6px;
                    font-size: 12px; font-weight: bold; padding: 0 14px;
                }}
                QPushButton:hover {{ background: {self._accent}cc; }}
            """)
        else:
            btn.setStyleSheet("""
                QPushButton {
                    background: #2a2a2a; color: #aaa;
                    border: 1px solid #3a3a3a; border-radius: 6px;
                    font-size: 12px; padding: 0 14px;
                }
                QPushButton:hover { background: #333; color: #ddd; border-color: #555; }
            """)
        self._btn_layout.addWidget(btn)
        return btn

    def set_items(self, items: list[tuple[str, str, str, str]]) -> None:
        """items: [(path, type, display_line1, display_line2), ...]"""
        self.list.clear()
        for path, kind, line1, line2 in items:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, path)
            item.setData(Qt.ItemDataRole.UserRole + 1, kind)
            item.setText(f"{line1}\n{line2}" if line2 else line1)
            f = QFont("Malgun Gothic")
            f.setPixelSize(13)
            item.setFont(f)
            self.list.addItem(item)

        has = self.list.count() > 0
        self.list.setVisible(has)
        self._empty.setVisible(not has)
        if has:
            self.list.setCurrentRow(0)
            self.list.setFocus()


class ProjectLauncher(QWidget):
    project_selected = Signal(str)
    song_selected = Signal(str)
    new_project_requested = Signal()
    new_song_requested = Signal()
    open_project_requested = Signal()
    remove_recent_requested = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    # ── UI 구성 ──────────────────────────────────────────────────

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(48, 36, 48, 36)
        root.setSpacing(0)

        # 헤더
        hdr = QVBoxLayout()
        hdr.setSpacing(4)
        title = QLabel("FLOW")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            "font-size: 52px; font-weight: 900; color: #2196f3; letter-spacing: 3px; background: transparent;"
        )
        hdr.addWidget(title)

        sub = QLabel("예배 슬라이드 송출 시스템")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet("font-size: 13px; color: #555; background: transparent;")
        hdr.addWidget(sub)
        root.addLayout(hdr)
        root.addSpacing(32)

        # 두 패널
        body = QHBoxLayout()
        body.setSpacing(20)

        # ── 곡 라이브러리 패널 ──
        self._song_panel = _Panel(
            "곡 라이브러리",
            "악보 · PPT · 핫스팟 매핑의 기본 단위",
            "#4caf50",
        )
        self._btn_new_song = self._song_panel.add_action_btn("+ 새 곡 만들기", primary=True)
        self._btn_open_song = self._song_panel.add_action_btn("폴더에서 열기...")
        self._btn_new_song.clicked.connect(self.new_song_requested.emit)
        self._btn_open_song.clicked.connect(self._on_open_song_clicked)
        self._song_panel.list.itemActivated.connect(self._on_item_activated)
        self._song_panel.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._song_panel.list.customContextMenuRequested.connect(
            lambda pos: self._on_context_menu(self._song_panel.list, pos)
        )
        body.addWidget(self._song_panel, 1)

        # ── 프로젝트 패널 ──
        self._proj_panel = _Panel(
            "프로젝트 / 셋리스트",
            "여러 곡을 순서대로 조합해 예배에서 사용",
            "#2196f3",
        )
        self._btn_new_proj = self._proj_panel.add_action_btn("+ 새 프로젝트", primary=True)
        self._btn_open_proj = self._proj_panel.add_action_btn("폴더에서 열기...")
        self._btn_new_proj.clicked.connect(self.new_project_requested.emit)
        self._btn_open_proj.clicked.connect(self.open_project_requested.emit)
        self._proj_panel.list.itemActivated.connect(self._on_item_activated)
        self._proj_panel.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._proj_panel.list.customContextMenuRequested.connect(
            lambda pos: self._on_context_menu(self._proj_panel.list, pos)
        )
        body.addWidget(self._proj_panel, 1)

        root.addLayout(body, 1)
        root.addSpacing(16)

        # 푸터
        footer = QLabel("v1.0.0")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setStyleSheet("font-size: 10px; color: #333; background: transparent;")
        root.addWidget(footer)

    # ── 데이터 설정 ─────────────────────────────────────────────

    def set_recent_items(self, projects: list[str], songs: list[str]) -> None:
        # 곡 항목
        song_items = []
        for s_path in songs:
            p = Path(s_path)
            icon, tip = _song_status(s_path)
            line1 = f"{icon}  {p.name}"
            line2 = f"      {tip}  ·  {s_path}"
            song_items.append((s_path, "song", line1, line2))
        self._song_panel.set_items(song_items)

        # 프로젝트 항목
        proj_items = []
        for p_path in projects:
            p = Path(p_path)
            name = p.parent.name if p.name == "project.json" else p.stem
            count = _project_song_count(p_path)
            line1 = name
            line2 = f"      {count}  ·  {p_path}" if count else f"      {p_path}"
            proj_items.append((p_path, "project", line1, line2))
        self._proj_panel.set_items(proj_items)

    # ── 이벤트 핸들러 ───────────────────────────────────────────

    def _on_item_activated(self, item: QListWidgetItem) -> None:
        path = item.data(Qt.ItemDataRole.UserRole)
        kind = item.data(Qt.ItemDataRole.UserRole + 1)
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
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.warning(
            self,
            "곡 폴더를 찾을 수 없습니다",
            "선택한 폴더에 song.json 파일이 없습니다.\n올바른 곡 폴더를 선택해 주세요.",
        )

    def _on_context_menu(self, list_widget: _PanelList, pos) -> None:
        item = list_widget.itemAt(pos)
        if not item:
            return
        path = item.data(Qt.ItemDataRole.UserRole)
        kind = item.data(Qt.ItemDataRole.UserRole + 1)

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background: #252525; color: #ccc; border: 1px solid #3a3a3a; }
            QMenu::item { padding: 6px 18px; }
            QMenu::item:selected { background: #333; color: #fff; }
        """)
        remove = QAction("목록에서 제거", self)
        remove.triggered.connect(
            lambda: self.remove_recent_requested.emit(path, kind)
        )
        menu.addAction(remove)
        menu.exec(list_widget.mapToGlobal(pos))
