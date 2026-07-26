"""Projects screen — full list of all projects in the workspace.

검색 + 정렬(가나다순/생성순) + 카드 클릭으로 프로젝트 진입.
"""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from flow.ui.styles import (
    BG_DEEP,
    BORDER_FOCUS,
    FONT_MD,
    SP_LG,
    SP_MD,
    SP_SM,
    TEXT_TERTIARY,
)
from flow.ui.screens._browser_widgets import (
    SORT_NAME,
    BrowserToolbar,
    ItemCard,
    sort_paths,
)


class ProjectsScreen(QWidget):
    """Workspace 의 projects/ 안 모든 프로젝트를 보여주는 페이지.

    Signals:
        project_selected(str): 프로젝트 폴더 경로 (project.json 위치의 부모)
        new_project_requested(): 새 프로젝트 생성 요청
    """

    project_selected = Signal(str)
    new_project_requested = Signal()
    # 이름 변경 요청 (프로젝트 폴더 경로) — 실제 처리는 MainWindow가 한다
    project_rename_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._workspace = None
        self._search_text = ""
        self._sort_mode = SORT_NAME

        self.setStyleSheet(f"background: {BG_DEEP};")
        root = QVBoxLayout(self)
        root.setContentsMargins(SP_LG * 2, SP_LG, SP_LG * 2, SP_LG)
        root.setSpacing(SP_MD)

        self._toolbar = BrowserToolbar(
            title="프로젝트",
            new_button_label="＋ 새 프로젝트",
        )
        self._toolbar.new_clicked.connect(self.new_project_requested.emit)
        self._toolbar.search_changed.connect(self._on_search_changed)
        self._toolbar.sort_changed.connect(self._on_sort_changed)
        self._toolbar.refresh_clicked.connect(self.force_refresh)
        root.addWidget(self._toolbar)

        # F5 — 이 화면이 떠 있을 때만 동작하도록 위젯 범위로 제한한다
        # (MainWindow의 F5는 라이브 모드 토글이라 겹치면 안 된다).
        shortcut = QShortcut(QKeySequence("F5"), self)
        shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        shortcut.activated.connect(self.force_refresh)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical { border: none; background: transparent; "
            "width: 4px; margin: 0; }"
            f"QScrollBar::handle:vertical {{ background: {BORDER_FOCUS}; "
            f"border-radius: 2px; min-height: 20px; }}"
        )
        self._cards_host = QWidget()
        self._cards_layout = QVBoxLayout(self._cards_host)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setSpacing(SP_SM)
        self._cards_layout.addStretch()
        scroll.setWidget(self._cards_host)
        root.addWidget(scroll, 1)

        self._empty_lbl = QLabel("이 워크스페이스에 프로젝트가 없습니다.")
        self._empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_lbl.setStyleSheet(
            f"color: {TEXT_TERTIARY}; font-size: {FONT_MD}px; padding: 40px;"
        )
        self._empty_lbl.hide()
        root.addWidget(self._empty_lbl)

    def set_workspace(self, workspace) -> None:
        self._workspace = workspace
        self.refresh()

    def force_refresh(self) -> None:
        """디스크에서 다시 읽는다 (새로고침 버튼 / F5).

        곡 메타데이터 캐시도 함께 버린다 — 프로젝트 카드의 곡 수는
        project.json에서 읽지만, 여기서 새로고침한 사용자는 워크스페이스
        전체가 최신이길 기대한다.
        """
        from flow.services import song_index

        song_index.invalidate()
        self.refresh()

    def refresh(self) -> None:
        while self._cards_layout.count() > 1:
            item = self._cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if self._workspace is None:
            self._empty_lbl.setText("워크스페이스가 열려있지 않습니다.")
            self._empty_lbl.show()
            return

        paths = self._workspace.list_projects()
        if self._search_text:
            q = self._search_text.lower()
            paths = [p for p in paths if q in p.name.lower()]
        paths = sort_paths(paths, self._sort_mode)

        if not paths:
            self._empty_lbl.setText(
                "이 워크스페이스에 프로젝트가 없습니다." if not self._search_text
                else f"'{self._search_text}'와(과) 일치하는 프로젝트가 없습니다."
            )
            self._empty_lbl.show()
            return
        self._empty_lbl.hide()

        for path in paths:
            subtitle = self._build_subtitle(path)
            # _open_project_by_path expects project.json, not the folder —
            # 폴더 경로는 표시용으로만 사용.
            pj_path = path / "project.json"
            card = ItemCard(
                path=str(pj_path),
                title=path.name,
                subtitle=subtitle,
                path_display=str(path),
                renamable=True,
            )
            card.clicked.connect(self.project_selected.emit)
            card.rename_requested.connect(self._on_rename_requested)
            self._cards_layout.insertWidget(self._cards_layout.count() - 1, card)

    def _build_subtitle(self, project_dir: Path) -> str:
        """Compose: 곡 N개."""
        try:
            with (project_dir / "project.json").open(encoding="utf-8-sig") as f:
                data = json.load(f)
            count = len(data.get("song_order", []))
            return f"곡 {count}개"
        except Exception:
            return ""

    def _on_rename_requested(self, project_json_path: str) -> None:
        """카드는 project.json 경로를 들고 있다 — 폴더 경로로 바꿔 올린다."""
        self.project_rename_requested.emit(
            str(Path(project_json_path).parent)
        )

    def _on_search_changed(self, text: str) -> None:
        self._search_text = text.strip()
        self.refresh()

    def _on_sort_changed(self, mode: str) -> None:
        self._sort_mode = mode
        self.refresh()
