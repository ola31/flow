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
    AMBER,
    BG_INPUT,
    BG_SURFACE,
    BORDER_FOCUS,
    BORDER_STANDARD_RGBA,
    BORDER_SUBTLE_RGBA,
    FONT_2XS,
    FONT_DISPLAY,
    FONT_HEAD,
    FONT_MD,
    FONT_SM,
    FONT_TITLE,
    FW_MEDIUM,
    FW_REGULAR,
    FW_SEMI,
    RADIUS_MD,
    SP_LG,
    SP_MD,
    SP_SM,
    SP_XS,
    SURFACE_GHOST,
    SURFACE_RAISED,
    SURFACE_SUBTLE,
    TEXT_PRIMARY,
    TEXT_QUAT,
    TEXT_SECONDARY,
    TEXT_TERTIARY,
)

SORT_NAME = "name"
SORT_CREATED = "created"

# 한글 IME는 자모 하나마다 textChanged를 쏜다 — 조합 중에 매번 목록을
# 다시 그리지 않도록 입력이 멎은 뒤 한 번만 렌더한다. 필터가 디스크를
# 건드리던 시절엔 180ms로 막아야 했지만, 지금은 색인만 훑으므로(키당
# ~16ms) 대기 자체가 체감 지연이라 짧게 잡는다.
SEARCH_DEBOUNCE_MS = 120

# 라이브러리 화면의 보기 방식. 아이콘 서브셋에 그리드 글리프가 없어
# 토글은 텍스트 라벨로 만든다 (이모지는 쓰지 않는다).
VIEW_LIST = "list"
VIEW_CARDS = "cards"


class BrowserToolbar(QWidget):
    """Title + new-button + search + sort dropdown row."""

    new_clicked = Signal()
    search_changed = Signal(str)
    sort_changed = Signal(str)  # SORT_NAME | SORT_CREATED
    refresh_clicked = Signal()
    view_changed = Signal(str)  # VIEW_LIST | VIEW_CARDS
    back_clicked = Signal()

    def __init__(
        self,
        title: str,
        new_button_label: str,
        parent: QWidget | None = None,
        *,
        view_toggle: bool = False,
    ) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SP_SM)

        # Title row
        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(SP_MD)

        # 뒤로가기 — 분류 안으로 들어갔을 때만 보인다
        self._btn_back = QPushButton("←")
        self._btn_back.setFixedSize(32, 32)
        self._btn_back.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_back.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_back.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {TEXT_SECONDARY}; "
            f"border: 1px solid {BORDER_SUBTLE_RGBA}; "
            f"border-radius: {RADIUS_MD}px; font-size: {FONT_MD}px; }} "
            f"QPushButton:hover {{ background: {SURFACE_SUBTLE}; }}"
        )
        self._btn_back.clicked.connect(self.back_clicked.emit)
        self._btn_back.setVisible(False)
        title_row.addWidget(self._btn_back)

        # 제목 — 위에 작은 메타 줄, 아래 큰 제목
        title_box = QVBoxLayout()
        title_box.setContentsMargins(0, 0, 0, 0)
        title_box.setSpacing(0)
        self._meta_lbl = QLabel("")
        self._meta_lbl.setStyleSheet(
            f"color: {TEXT_QUAT}; font-size: {FONT_2XS}px; letter-spacing: 1px;"
        )
        self._meta_lbl.setVisible(False)
        title_box.addWidget(self._meta_lbl)
        self._default_title = title
        lbl = QLabel(title)
        lbl.setStyleSheet(
            f"color: {TEXT_PRIMARY}; font-size: {FONT_HEAD}px; font-weight: {FW_SEMI};"
        )
        self._title_lbl = lbl
        title_box.addWidget(lbl)
        title_row.addLayout(title_box)
        title_row.addStretch()

        # 보기 전환 — 목록 / 분류별 카드
        self._view = VIEW_LIST
        self._view_buttons: dict[str, QPushButton] = {}
        if view_toggle:
            for mode, label in ((VIEW_LIST, "목록"), (VIEW_CARDS, "카드")):
                btn = QPushButton(label)
                btn.setCheckable(True)
                btn.setFixedHeight(32)
                btn.setMinimumWidth(52)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                btn.clicked.connect(
                    lambda _c=False, m=mode: self.set_view(m)
                )
                self._view_buttons[mode] = btn
                title_row.addWidget(btn)
            self._refresh_view_buttons()

        # 새로고침 — 파일 관리자에서 폴더를 직접 고쳤을 때처럼 앱 밖에서
        # 일어난 변경을 즉시 반영하기 위한 수단 (F5도 같은 동작).
        self._btn_refresh = QPushButton()
        self._btn_refresh.setIcon(icon_qicon("refresh", size=16, color=TEXT_SECONDARY))
        self._btn_refresh.setFixedSize(32, 32)
        self._btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_refresh.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_refresh.setToolTip("새로고침 (F5)")
        self._btn_refresh.setStyleSheet(
            f"QPushButton {{ background: transparent; border: 1px solid "
            f"{BORDER_SUBTLE_RGBA}; border-radius: {RADIUS_MD}px; }} "
            f"QPushButton:hover {{ background: {SURFACE_SUBTLE}; "
            f"border-color: {BORDER_STANDARD_RGBA}; }}"
        )
        self._btn_refresh.clicked.connect(self.refresh_clicked.emit)
        title_row.addWidget(self._btn_refresh)

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


    # ── 제목 / 뒤로가기 ─────────────────────────────────────────────────

    def title(self) -> str:
        return self._title_lbl.text()

    def back_visible(self) -> bool:
        return not self._btn_back.isHidden()

    def set_context(self, title: str | None = None, meta: str = "") -> None:
        """제목 줄을 바꾼다.

        Args:
            title: None이면 생성 시의 기본 제목으로 되돌린다.
            meta: 제목 위 작은 줄. 빈 문자열이면 숨긴다.
        """
        self._title_lbl.setText(title if title is not None else self._default_title)
        self._meta_lbl.setText(meta)
        self._meta_lbl.setVisible(bool(meta))
        self._btn_back.setVisible(title is not None)

    def set_new_button_label(self, label: str) -> None:
        self._btn_new.setText(label)

    # ── 보기 전환 ───────────────────────────────────────────────────────

    def view(self) -> str:
        return self._view

    def set_view(self, mode: str) -> None:
        """보기 방식을 바꾼다. 값이 실제로 달라질 때만 신호를 낸다."""
        if mode not in (VIEW_LIST, VIEW_CARDS) or mode == self._view:
            self._refresh_view_buttons()
            return
        self._view = mode
        self._refresh_view_buttons()
        self.view_changed.emit(mode)

    def _refresh_view_buttons(self) -> None:
        for mode, btn in self._view_buttons.items():
            active = mode == self._view
            btn.setChecked(active)
            btn.setStyleSheet(
                f"QPushButton {{ background: "
                f"{SURFACE_RAISED if active else 'transparent'}; "
                f"color: {TEXT_PRIMARY if active else TEXT_TERTIARY}; "
                f"border: 1px solid "
                f"{BORDER_STANDARD_RGBA if active else BORDER_SUBTLE_RGBA}; "
                f"border-radius: {RADIUS_MD}px; font-size: {FONT_SM}px; "
                f"font-weight: {FW_MEDIUM}; padding: 0 10px; }} "
                f"QPushButton:hover {{ background: {SURFACE_SUBTLE}; }}"
            )


class CategoryTile(QFrame):
    """분류 하나를 나타내는 타일 — 이름, 곡 수, 미리보기 곡 몇 줄.

    카드 뷰의 첫 화면은 곡이 아니라 이 타일들이다. 사진이 없으므로 곡 수를
    큰 고스트 숫자로 세워 타일마다 다른 무게추를 준다.
    """

    clicked = Signal(str)  # 분류명

    PREVIEW_LIMIT = 3

    def __init__(self, name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._name = name
        self._count = 0
        self._preview: list[str] = []
        self.setObjectName("CategoryTile")
        self.setMinimumHeight(186)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            f"QFrame#CategoryTile {{ background: {BG_SURFACE}; "
            f"border: 1px solid {BORDER_SUBTLE_RGBA}; "
            f"border-radius: {RADIUS_MD + 2}px; }} "
            f"QFrame#CategoryTile:hover {{ background: {SURFACE_SUBTLE}; "
            f"border-color: {BORDER_STANDARD_RGBA}; }}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SP_LG, SP_MD + 4, SP_LG, SP_MD + 4)
        layout.setSpacing(0)

        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(SP_SM)
        self._name_lbl = QLabel(name)
        self._name_lbl.setStyleSheet(
            f"background: transparent; color: {TEXT_PRIMARY}; "
            f"font-size: {FONT_TITLE}px; font-weight: {FW_SEMI};"
        )
        head.addWidget(self._name_lbl, 1)
        self._count_lbl = QLabel("0")
        self._count_lbl.setStyleSheet(
            f"background: transparent; color: {TEXT_QUAT}; "
            f"font-size: {FONT_DISPLAY}px; font-weight: {FW_REGULAR};"
        )
        head.addWidget(self._count_lbl, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(head)
        layout.addSpacing(SP_MD)

        rule = QFrame()
        rule.setFixedHeight(1)
        rule.setStyleSheet(f"background: {BORDER_SUBTLE_RGBA}; border: none;")
        layout.addWidget(rule)
        layout.addSpacing(SP_MD)

        # 미리보기 줄은 최대 개수만큼 미리 만들어 두고 내용만 갈아끼운다
        self._preview_lbls: list[QLabel] = []
        for _ in range(self.PREVIEW_LIMIT):
            lbl = QLabel("")
            lbl.setStyleSheet(
                f"background: transparent; color: {TEXT_TERTIARY}; "
                f"font-size: {FONT_SM}px; padding: 1px 0;"
            )
            layout.addWidget(lbl)
            self._preview_lbls.append(lbl)
        layout.addStretch()

        self._more_lbl = QLabel("")
        self._more_lbl.setStyleSheet(
            f"background: transparent; color: {TEXT_QUAT}; font-size: {FONT_2XS}px;"
        )
        layout.addWidget(self._more_lbl)

    def name(self) -> str:
        return self._name

    def count(self) -> int:
        return self._count

    def preview_names(self) -> list[str]:
        return list(self._preview)

    def set_contents(self, count: int, preview: list[str]) -> None:
        self._count = count
        self._preview = preview[: self.PREVIEW_LIMIT]
        self._count_lbl.setText(str(count))
        for i, lbl in enumerate(self._preview_lbls):
            text = self._preview[i] if i < len(self._preview) else ""
            lbl.setText(text)
            lbl.setVisible(bool(text))
        hidden = count - len(self._preview)
        self._more_lbl.setText(f"외 {hidden}곡" if hidden > 0 else "")
        self._more_lbl.setVisible(hidden > 0)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 (Qt 오버라이드)
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self.rect().contains(event.position().toPoint())
        ):
            self.clicked.emit(self._name)
        super().mouseReleaseEvent(event)


class NewCategoryTile(QPushButton):
    """분류 타일 그리드 끝에 붙는 '＋ 새 분류' 점선 타일."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("＋  새 분류", parent)
        self.setMinimumHeight(186)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {TEXT_QUAT}; "
            f"border: 1px dashed {BORDER_FOCUS}; "
            f"border-radius: {RADIUS_MD + 2}px; font-size: {FONT_MD}px; }} "
            f"QPushButton:hover {{ color: {TEXT_SECONDARY}; }}"
        )


class ItemCard(QFrame):
    """Click-to-open card showing name + sub line + path hint."""

    clicked = Signal(str)  # path
    rename_requested = Signal(str)  # path
    delete_requested = Signal(str)  # path
    categorize_requested = Signal(str)  # path

    # 상태 칩 최대 개수 (악보 / 슬라이드 형식 / 매핑)
    MAX_CHIPS = 3

    def __init__(
        self,
        path: str,
        title: str,
        subtitle: str = "",
        path_display: str | None = None,
        match_snippet: str = "",
        renamable: bool = False,
        deletable: bool = False,
        categorizable: bool = False,
        show_path: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._path = path
        self._match_snippet = match_snippet
        self._renamable = renamable
        self._deletable = deletable
        self._categorizable = categorizable
        if renamable or deletable or categorizable:
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
        # [주의] setVisible은 반드시 addWidget 뒤에. 부모 없는 위젯을 보이게
        # 하면 Qt는 그것을 최상위 창으로 띄운다 — 카드 수백 개면 작은 창이
        # 우르르 떴다 사라지며 페이지 전환이 번쩍인다.
        self._sub_lbl = QLabel(subtitle)
        self._sub_lbl.setStyleSheet(
            f"background: transparent; color: {TEXT_SECONDARY}; "
            f"font-size: {FONT_SM}px;"
        )
        layout.addWidget(self._sub_lbl)
        self._sub_lbl.setVisible(bool(subtitle))

        # 상태 칩 줄 — set_chips로 채우면 부제 문장을 대신한다. 칩 위젯은
        # 최대 개수만큼 미리 만들어 두고 내용만 갈아끼운다 (카드 재사용과
        # 같은 이유 — 검색 한 글자마다 위젯을 새로 만들지 않는다).
        self._chip_row = QWidget(self)
        self._chip_row.setStyleSheet("background: transparent;")
        chip_lay = QHBoxLayout(self._chip_row)
        chip_lay.setContentsMargins(0, 0, 0, 0)
        chip_lay.setSpacing(SP_XS + 2)
        self._chips: list[QLabel] = []
        for _ in range(self.MAX_CHIPS):
            chip = QLabel("")
            chip.setVisible(False)
            chip_lay.addWidget(chip)
            self._chips.append(chip)
        chip_lay.addStretch()
        self._chip_row.setVisible(False)
        layout.addWidget(self._chip_row)

        # 가사 검색 매칭 줄 — 가사로 검색되어 매칭 줄이 있을 때만 표시
        self._snippet_lbl = QLabel(f"“{match_snippet}”" if match_snippet else "")
        self._snippet_lbl.setStyleSheet(
            f"background: transparent; color: {TEXT_SECONDARY}; "
            f"font-size: {FONT_SM}px;"
        )
        layout.addWidget(self._snippet_lbl)
        self._snippet_lbl.setVisible(bool(match_snippet))

        # path hint (사용자에게 보여줄 경로는 path_display로 별도 지정 가능)
        self._path_lbl = QLabel(path_display if path_display is not None else path)
        self._path_lbl.setStyleSheet(
            f"background: transparent; color: {TEXT_TERTIARY}; font-size: 10px;"
        )
        self._path_lbl.setWordWrap(True)
        layout.addWidget(self._path_lbl)
        # [주의] setVisible은 반드시 addWidget 뒤에 — 부모 없는 위젯을 보이게
        # 하면 Qt가 독립 창으로 띄워 페이지 전환이 번쩍인다
        self._path_lbl.setVisible(show_path)

    def set_title(self, title: str) -> None:
        self._title_lbl.setText(title)

    def set_subtitle(self, subtitle: str) -> None:
        self._sub_lbl.setText(subtitle)
        self._sub_lbl.setVisible(bool(subtitle))

    def set_chips(self, chips: list[tuple[str, bool]]) -> None:
        """상태를 칩으로 표시한다. 빈 목록이면 부제 문장으로 되돌린다.

        Args:
            chips: (문구, 문제 여부) 목록. 문제인 칩만 앰버로 칠한다.
        """
        chips = chips[: self.MAX_CHIPS]
        for i, chip in enumerate(self._chips):
            if i < len(chips):
                text, warn = chips[i]
                chip.setText(text)
                chip.setStyleSheet(
                    f"background: {SURFACE_GHOST}; border-radius: 4px; "
                    f"padding: 2px 7px; font-size: {FONT_2XS}px; "
                    f"color: {AMBER if warn else TEXT_QUAT};"
                )
                chip.setProperty("warn", warn)
                chip.setVisible(True)
            else:
                chip.setVisible(False)
        self._chip_row.setVisible(bool(chips))
        self._sub_lbl.setVisible(not chips and bool(self._sub_lbl.text()))

    def chip_texts(self) -> list[str]:
        return [c.text() for c in self._chips if not c.isHidden()]

    def warned_chips(self) -> list[str]:
        return [
            c.text() for c in self._chips
            if not c.isHidden() and c.property("warn")
        ]

    def set_match_snippet(self, snippet: str) -> None:
        self._match_snippet = snippet
        self._snippet_lbl.setText(f"“{snippet}”" if snippet else "")
        self._snippet_lbl.setVisible(bool(snippet))

    def build_context_menu(self) -> QMenu | None:
        """허용된 동작만 담은 메뉴 (없으면 None). exec 없이 검사 가능."""
        menu = QMenu(self)
        if self._renamable:
            act = menu.addAction("이름 변경")
            act.triggered.connect(lambda: self.rename_requested.emit(self._path))
        if self._categorizable:
            act = menu.addAction("분류 지정…")
            act.triggered.connect(
                lambda: self.categorize_requested.emit(self._path)
            )
        if self._deletable:
            if not menu.isEmpty():
                menu.addSeparator()
            act = menu.addAction("삭제")
            act.triggered.connect(lambda: self.delete_requested.emit(self._path))
        if menu.isEmpty():
            menu.deleteLater()
            return None
        return menu

    def _show_context_menu(self, pos) -> None:
        menu = self.build_context_menu()
        if menu is not None:
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
