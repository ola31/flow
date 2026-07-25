"""Shared widgets for LibraryScreen / ProjectsScreen — search bar, sort dropdown, item card."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from flow.ui.icons import icon_qicon
from flow.ui.styles import (
    BG_INPUT,
    BG_SURFACE,
    BORDER_STANDARD_RGBA,
    BORDER_SUBTLE_RGBA,
    FONT_HEAD,
    FONT_MD,
    FONT_SM,
    FW_MEDIUM,
    FW_SEMI,
    RADIUS_MD,
    SP_MD,
    SP_SM,
    SP_XS,
    SURFACE_SUBTLE,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TEXT_TERTIARY,
)

SORT_NAME = "name"
SORT_CREATED = "created"

# 한글 IME는 자모 하나마다 textChanged를 쏜다 — 매 입력마다 목록을 다시
# 필터링하면 큰 라이브러리에서 타이핑이 밀린다. 입력이 멎은 뒤 한 번만 렌더.
SEARCH_DEBOUNCE_MS = 180


class BrowserToolbar(QWidget):
    """Title + new-button + search + sort dropdown row."""

    new_clicked = Signal()
    search_changed = Signal(str)
    sort_changed = Signal(str)  # SORT_NAME | SORT_CREATED

    def __init__(
        self,
        title: str,
        new_button_label: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SP_SM)

        # Title row
        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(SP_MD)
        lbl = QLabel(title)
        lbl.setStyleSheet(
            f"color: {TEXT_PRIMARY}; font-size: {FONT_HEAD}px; font-weight: {FW_SEMI};"
        )
        title_row.addWidget(lbl)
        title_row.addStretch()
        self._btn_new = QPushButton(new_button_label)
        self._btn_new.setProperty("variant", "primary")
        self._btn_new.setFixedHeight(32)
        self._btn_new.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_new.clicked.connect(self.new_clicked.emit)
        title_row.addWidget(self._btn_new)
        layout.addLayout(title_row)

        # Search + sort row
        ctrls = QHBoxLayout()
        ctrls.setContentsMargins(0, 0, 0, 0)
        ctrls.setSpacing(SP_MD)

        self._search = QLineEdit()
        self._search.setPlaceholderText("검색…")
        self._search.setClearButtonEnabled(True)
        self._search.setFixedHeight(32)
        self._search.setStyleSheet(
            f"QLineEdit {{ background: {BG_INPUT}; color: {TEXT_PRIMARY}; "
            f"border: 1px solid {BORDER_STANDARD_RGBA}; border-radius: {RADIUS_MD}px; "
            f"padding: 4px 10px; font-size: {FONT_MD}px; }}"
        )
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(SEARCH_DEBOUNCE_MS)
        self._search_timer.timeout.connect(
            lambda: self.search_changed.emit(self._search.text())
        )
        self._search.textChanged.connect(lambda _t: self._search_timer.start())
        ctrls.addWidget(self._search, 1)

        sort_lbl = QLabel("정렬")
        sort_lbl.setStyleSheet(f"color: {TEXT_TERTIARY}; font-size: {FONT_SM}px;")
        ctrls.addWidget(sort_lbl)

        self._sort = QComboBox()
        self._sort.addItem("가나다순", SORT_NAME)
        self._sort.addItem("생성순 (최신)", SORT_CREATED)
        self._sort.setFixedHeight(32)
        self._sort.setCursor(Qt.CursorShape.PointingHandCursor)
        self._sort.setStyleSheet(
            f"QComboBox {{ background: {BG_INPUT}; color: {TEXT_PRIMARY}; "
            f"border: 1px solid {BORDER_STANDARD_RGBA}; border-radius: {RADIUS_MD}px; "
            f"padding: 4px 10px; font-size: {FONT_MD}px; }} "
            # Drop-down 화살표 영역도 어두운 배경 — 기본은 흰색 박스가 보임.
            f"QComboBox::drop-down {{ border: none; background: transparent; width: 20px; }} "
            f"QComboBox::down-arrow {{ width: 10px; height: 10px; }} "
            # 펼친 popup 리스트 스타일 — 기본 흰색 박스 제거.
            f"QComboBox QAbstractItemView {{ "
            f"background: {BG_SURFACE}; color: {TEXT_PRIMARY}; "
            f"border: 1px solid {BORDER_STANDARD_RGBA}; border-radius: {RADIUS_MD}px; "
            f"padding: 4px; outline: 0; "
            f"selection-background-color: {SURFACE_SUBTLE}; "
            f"selection-color: {TEXT_PRIMARY}; }}"
        )
        self._sort.currentIndexChanged.connect(
            lambda _: self.sort_changed.emit(self._sort.currentData())
        )
        ctrls.addWidget(self._sort)

        layout.addLayout(ctrls)

    def search_text(self) -> str:
        return self._search.text()

    def sort_mode(self) -> str:
        return self._sort.currentData()

    def clear_search(self) -> None:
        """검색어 비우기 — 프로그램이 부르는 경로라 디바운스 없이 즉시 반영."""
        self._search.clear()
        self._search_timer.stop()
        self.search_changed.emit("")


class ItemCard(QFrame):
    """Click-to-open card showing name + sub line + path hint."""

    clicked = Signal(str)  # path
    rename_requested = Signal(str)  # path

    def __init__(
        self,
        path: str,
        title: str,
        subtitle: str = "",
        path_display: str | None = None,
        match_snippet: str = "",
        renamable: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._path = path
        self._match_snippet = match_snippet
        self._renamable = renamable
        if renamable:
            self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            self.customContextMenuRequested.connect(self._show_context_menu)
        self.setObjectName("ItemCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            f"QFrame#ItemCard {{ background: {BG_SURFACE}; "
            f"border: 1px solid {BORDER_SUBTLE_RGBA}; border-radius: {RADIUS_MD}px; }} "
            f"QFrame#ItemCard:hover {{ background: {SURFACE_SUBTLE}; "
            f"border-color: {BORDER_STANDARD_RGBA}; }}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SP_MD + 2, SP_SM + 2, SP_MD + 2, SP_SM + 2)
        layout.setSpacing(SP_XS)

        self._title_lbl = QLabel(title)
        self._title_lbl.setStyleSheet(
            f"background: transparent; color: {TEXT_PRIMARY}; "
            f"font-size: {FONT_MD + 1}px; font-weight: {FW_MEDIUM};"
        )
        layout.addWidget(self._title_lbl)

        # 부제·스니펫 라벨은 항상 만들어 두고 내용이 없으면 숨긴다 — 검색
        # 필터마다 카드를 새로 만들지 않고 텍스트만 바꿔 끼우기 위해서다.
        self._sub_lbl = QLabel(subtitle)
        self._sub_lbl.setStyleSheet(
            f"background: transparent; color: {TEXT_SECONDARY}; "
            f"font-size: {FONT_SM}px;"
        )
        self._sub_lbl.setVisible(bool(subtitle))
        layout.addWidget(self._sub_lbl)

        # 가사 검색 매칭 줄 — 가사로 검색되어 매칭 줄이 있을 때만 표시
        self._snippet_lbl = QLabel(f"“{match_snippet}”" if match_snippet else "")
        self._snippet_lbl.setStyleSheet(
            f"background: transparent; color: {TEXT_SECONDARY}; "
            f"font-size: {FONT_SM}px;"
        )
        self._snippet_lbl.setVisible(bool(match_snippet))
        layout.addWidget(self._snippet_lbl)

        # path hint (사용자에게 보여줄 경로는 path_display로 별도 지정 가능)
        self._path_lbl = QLabel(path_display if path_display is not None else path)
        self._path_lbl.setStyleSheet(
            f"background: transparent; color: {TEXT_TERTIARY}; font-size: 10px;"
        )
        self._path_lbl.setWordWrap(True)
        layout.addWidget(self._path_lbl)

    def set_title(self, title: str) -> None:
        self._title_lbl.setText(title)

    def set_subtitle(self, subtitle: str) -> None:
        self._sub_lbl.setText(subtitle)
        self._sub_lbl.setVisible(bool(subtitle))

    def set_match_snippet(self, snippet: str) -> None:
        self._match_snippet = snippet
        self._snippet_lbl.setText(f"“{snippet}”" if snippet else "")
        self._snippet_lbl.setVisible(bool(snippet))

    def _show_context_menu(self, pos) -> None:
        menu = QMenu(self)
        act = menu.addAction("이름 변경")
        act.triggered.connect(lambda: self.rename_requested.emit(self._path))
        menu.exec(self.mapToGlobal(pos))

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit(self._path)
        super().mouseReleaseEvent(event)


def sort_paths(
    paths: list[Path],
    mode: str,
    name_key=None,
) -> list[Path]:
    """Sort paths by name (alphabetical) or by folder mtime (newest first).

    `name_key` lets callers pass a custom display name for sorting (e.g.,
    project.json's display name vs folder name).
    """
    if mode == SORT_CREATED:
        return sorted(paths, key=lambda p: p.stat().st_mtime, reverse=True)
    key = name_key or (lambda p: p.name)
    return sorted(paths, key=lambda p: key(p).lower())
