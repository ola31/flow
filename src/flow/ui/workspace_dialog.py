"""워크스페이스 선택/생성 다이얼로그

앱 시작 시 또는 워크스페이스 변경 시 표시.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from flow.domain.workspace import Workspace


def _looks_like_song_folder(path: Path) -> bool:
    """곡 폴더들이 담긴 폴더인가 (= 워크스페이스의 library/로 보이는가)."""
    try:
        return any(
            d.is_dir() and (d / "song.json").exists() for d in path.iterdir()
        )
    except OSError:
        return False


def _looks_like_project_folder(path: Path) -> bool:
    """프로젝트 폴더들이 담긴 폴더인가 (= projects/로 보이는가)."""
    try:
        return any(
            d.is_dir() and (d / "project.json").exists() for d in path.iterdir()
        )
    except OSError:
        return False


def classify_workspace_choice(root: Path) -> tuple[str, Path | None]:
    """사용자가 고른 폴더를 어떻게 다룰지 판정한다.

    워크스페이스 루트 대신 그 안의 library/나 projects/를 고르기 쉬운데,
    그대로 초기화해 버리면 곡 폴더 안에 library/·projects/가 또 생긴다.
    한 단계 위가 워크스페이스면 그쪽을 제안하고, 곡·프로젝트 모음처럼
    보이면 초기화를 막는다.

    Returns:
        ("open", 경로)    그대로 워크스페이스
        ("parent", 상위)  상위가 워크스페이스 — 그쪽을 열어야 함
        ("inside", None)  워크스페이스 내부 폴더로 보임 — 초기화하면 안 됨
        ("init", 경로)    비어 있거나 무관한 폴더 — 초기화 후보
    """
    root = root.resolve()
    if Workspace(root=root).is_valid():
        return "open", root

    parent = root.parent
    if parent != root and Workspace(root=parent).is_valid():
        return "parent", parent

    if _looks_like_song_folder(root) or _looks_like_project_folder(root):
        return "inside", None

    return "init", root
from flow.ui.styles import (
    ACCENT,
    ACCENT_HOVER,
    BG_DEEP,
    BG_ELEVATED,
    BG_HOVER,
    BG_SURFACE,
    BORDER,
    BORDER_FOCUS,
    FONT_LG,
    FONT_MD,
    FONT_SM,
    FONT_HEAD,
    RADIUS_LG,
    RADIUS_MD,
    SP_LG,
    SP_MD,
    SP_SM,
    SP_XL,
    SP_2XL,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TEXT_TERTIARY,
)


class _RecentWorkspaceRow(QFrame):
    """최근 워크스페이스 한 줄"""

    def __init__(self, path: str, on_click, parent=None) -> None:
        super().__init__(parent)
        self._path = path
        self._on_click = on_click
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            f"""
            QFrame {{
                background: {BG_ELEVATED};
                border: none;
                border-radius: {RADIUS_MD}px;
            }}
            QFrame:hover {{ background: {BG_HOVER}; }}
            QLabel {{ background: transparent; }}
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SP_LG, SP_MD, SP_LG, SP_MD)
        layout.setSpacing(2)

        p = Path(path)
        name = QLabel(p.name)
        name.setStyleSheet(f"font-size: {FONT_LG}px; color: {TEXT_PRIMARY};")
        layout.addWidget(name)

        path_lbl = QLabel(str(p))
        path_lbl.setStyleSheet(f"font-size: {FONT_SM}px; color: {TEXT_TERTIARY};")
        layout.addWidget(path_lbl)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._on_click(self._path)
        super().mousePressEvent(event)


class WorkspaceDialog(QDialog):
    """워크스페이스 선택/생성 다이얼로그

    사용자가 선택한 워크스페이스는 self.selected_workspace 에 Workspace 객체로 저장됨.
    reject() 되면 None.
    """

    def __init__(self, recent_paths: list[str], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("워크스페이스 선택")
        self.setMinimumSize(560, 460)
        self.setStyleSheet(f"QDialog {{ background: {BG_DEEP}; }}")
        self.selected_workspace: Workspace | None = None
        self._recent_paths = recent_paths
        self._setup_ui()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(SP_2XL, SP_2XL, SP_2XL, SP_2XL)
        root.setSpacing(SP_LG)

        title = QLabel("워크스페이스 선택")
        title.setStyleSheet(
            f"font-size: {FONT_HEAD}px; font-weight: 600; color: {TEXT_PRIMARY};"
        )
        root.addWidget(title)

        desc = QLabel(
            "워크스페이스는 곡 라이브러리와 프로젝트들을 담는 폴더입니다.\n"
            "기존 워크스페이스를 열거나 새로 만드세요."
        )
        desc.setStyleSheet(f"font-size: {FONT_MD}px; color: {TEXT_TERTIARY};")
        desc.setWordWrap(True)
        root.addWidget(desc)

        # 버튼 행
        btn_row = QHBoxLayout()
        btn_row.setSpacing(SP_SM)

        btn_new = QPushButton("새로 만들기")
        btn_new.setFixedHeight(40)
        btn_new.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_new.setStyleSheet(
            f"""
            QPushButton {{
                background: {ACCENT}; color: #fff; border: none;
                border-radius: {RADIUS_MD}px; font-size: {FONT_MD}px;
                font-weight: 500; padding: 0 {SP_XL}px;
            }}
            QPushButton:hover {{ background: {ACCENT_HOVER}; }}
            """
        )
        btn_new.clicked.connect(self._on_new)
        btn_row.addWidget(btn_new)

        btn_open = QPushButton("폴더에서 열기")
        btn_open.setFixedHeight(40)
        btn_open.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_open.setStyleSheet(
            f"""
            QPushButton {{
                background: transparent; color: {TEXT_SECONDARY};
                border: 1px solid {BORDER}; border-radius: {RADIUS_MD}px;
                font-size: {FONT_MD}px; padding: 0 {SP_XL}px;
            }}
            QPushButton:hover {{ background: {BG_HOVER}; color: {TEXT_PRIMARY}; border-color: {BORDER_FOCUS}; }}
            """
        )
        btn_open.clicked.connect(self._on_open)
        btn_row.addWidget(btn_open)
        btn_row.addStretch()

        root.addLayout(btn_row)

        # 최근 목록
        recent_label = QLabel("최근 워크스페이스")
        recent_label.setStyleSheet(
            f"font-size: {FONT_SM}px; color: {TEXT_TERTIARY};"
        )
        from PySide6.QtGui import QFont
        _rf = recent_label.font()
        _rf.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.0)
        recent_label.setFont(_rf)
        root.addWidget(recent_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(SP_SM)

        if not self._recent_paths:
            empty = QLabel("최근 목록이 비어있습니다")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(
                f"font-size: {FONT_MD}px; color: {TEXT_TERTIARY}; padding: {SP_2XL}px 0;"
            )
            vbox.addWidget(empty)
        else:
            for path in self._recent_paths:
                row = _RecentWorkspaceRow(path, self._on_recent_clicked)
                vbox.addWidget(row)

        vbox.addStretch()
        scroll.setWidget(container)
        root.addWidget(scroll, 1)

    # === actions ===

    def _on_new(self) -> None:
        """워크스페이스로 사용할 폴더 1회 선택.

        파일 다이얼로그에서 기존 폴더를 선택하거나 '새 폴더 만들기'로 빈
        폴더를 만들어 선택. 그 폴더 자체가 워크스페이스가 됨.
        """
        folder = QFileDialog.getExistingDirectory(
            self,
            "워크스페이스로 사용할 빈 폴더를 선택하세요 (새 폴더 만들기 가능)",
            str(Path.home()),
            QFileDialog.Option.ShowDirsOnly,
        )
        if not folder:
            return

        root = Path(folder).resolve()

        # 이미 워크스페이스면 그대로 사용 (실수 방지)
        maybe = Workspace(root=root)
        if maybe.is_valid():
            reply = QMessageBox.question(
                self,
                "기존 워크스페이스",
                f"이미 워크스페이스로 초기화된 폴더입니다:\n{root}\n\n열까요?",
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            self.selected_workspace = maybe
            self.accept()
            return

        # 비어있지 않은 임의의 폴더는 거부 (의도치 않은 초기화 방지)
        if root.exists() and any(root.iterdir()):
            QMessageBox.warning(
                self,
                "빈 폴더가 아닙니다",
                f"선택한 폴더에 이미 다른 파일이 있습니다:\n{root}\n\n"
                "빈 폴더를 만들어 선택하거나, 다른 위치를 사용해 주세요.\n"
                "(파일 다이얼로그 안에서 새 폴더를 만들 수 있습니다)",
            )
            return

        # 빈 폴더 → 워크스페이스로 초기화
        try:
            ws = Workspace.create(root)
        except Exception as e:
            QMessageBox.critical(self, "생성 실패", str(e))
            return

        if not (ws.library_dir.exists() and ws.projects_dir.exists()):
            QMessageBox.critical(
                self,
                "초기화 실패",
                f"워크스페이스 하위 폴더 생성에 실패했습니다:\n{root}\n"
                f"library/: {ws.library_dir.exists()}, "
                f"projects/: {ws.projects_dir.exists()}",
            )
            return

        self.selected_workspace = ws
        self.accept()

    def _on_open(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self,
            "워크스페이스 폴더 선택",
            "",
            QFileDialog.Option.ShowDirsOnly,
        )
        if not folder:
            return

        kind, target = classify_workspace_choice(Path(folder))

        if kind == "open":
            ws = Workspace(root=target)

        elif kind == "parent":
            # library/ 나 projects/ 를 고른 흔한 실수 — 상위를 제안한다
            reply = QMessageBox.question(
                self,
                "상위 폴더가 워크스페이스입니다",
                f"'{Path(folder).name}' 은(는) 워크스페이스 안의 폴더입니다.\n"
                f"워크스페이스는 그 상위인 아래 폴더입니다. 이걸 열까요?\n\n{target}",
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            ws = Workspace(root=target)

        elif kind == "inside":
            # 곡/프로젝트 모음으로 보이는데 상위도 워크스페이스가 아님.
            # 여기서 초기화하면 곡 폴더 안에 library/·projects/가 생긴다.
            QMessageBox.warning(
                self,
                "워크스페이스가 아닙니다",
                "이 폴더는 곡(또는 프로젝트) 폴더들이 담긴 폴더로 보입니다.\n"
                "워크스페이스는 library/ 와 projects/ 를 함께 담는 상위 "
                "폴더입니다.\n\n한 단계 위 폴더를 선택해 주세요.",
            )
            return

        else:  # init
            reply = QMessageBox.question(
                self,
                "워크스페이스 아님",
                f"선택한 폴더는 워크스페이스가 아닙니다.\n"
                f"library/ 와 projects/ 폴더를 새로 만들어 초기화할까요?\n\n{target}",
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            ws = Workspace.create(target)

        self.selected_workspace = ws
        self.accept()

    def _on_recent_clicked(self, path: str) -> None:
        ws = Workspace(root=Path(path))
        if not ws.is_valid():
            QMessageBox.warning(
                self,
                "워크스페이스를 찾을 수 없음",
                f"폴더가 없거나 유효하지 않습니다:\n{path}",
            )
            return
        self.selected_workspace = ws
        self.accept()

