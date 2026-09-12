"""마크다운 에디터 옆에 붙는 악보 보기 패널.

가사를 옮겨 적을 때는 악보를 읽으면서 타이핑한다. 예전에는 악보를 보려면
편집을 나가 프로젝트 화면으로 돌아가야 했다. 여기서는 곡의 악보 시트를
페이지 탭으로 넘기며 폭에 맞춰 보여 준다 — 편집 기능은 없고 보기만 한다.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from flow.ui.styles import (
    ACCENT_INTER,
    BG_DEEP,
    BORDER_FOCUS,
    BORDER_STANDARD_RGBA,
    BORDER_SUBTLE_RGBA,
    FONT_SM,
    FW_MEDIUM,
    FW_SEMI,
    RADIUS_SM,
    SP_SM,
    SP_XS,
    SURFACE_GHOST,
    SURFACE_RAISED,
    SURFACE_SUBTLE,
    TEXT_SECONDARY,
    TEXT_TERTIARY,
)


def resolve_sheet_images(song) -> list[tuple[str, Path]]:
    """곡의 악보 시트를 (표시 이름, 이미지 절대 경로) 목록으로.

    ScoreCanvas와 같은 규칙을 따른다 — image_path는 곡 폴더 기준이고,
    옛 프로젝트는 sheets/ 와 sheet/ 를 섞어 써서 둘 다 찾아본다. 파일이
    끝내 없는 시트는 뺀다 (빈 칸을 보여 줄 이유가 없다).
    """
    base = Path(song.abs_folder)
    out: list[tuple[str, Path]] = []
    for i, sheet in enumerate(song.score_sheets):
        raw = str(sheet.image_path or "").strip()
        if not raw:
            continue
        p = Path(raw)
        candidates = [p if p.is_absolute() else base / p]
        if "sheets/" in raw:
            candidates.append(base / raw.replace("sheets/", "sheet/"))
        elif "sheet/" in raw:
            candidates.append(base / raw.replace("sheet/", "sheets/"))
        candidates += [base / "sheets" / p.name, base / "sheet" / p.name]
        found = next((c for c in candidates if c.is_file()), None)
        if found is None:
            continue
        label = sheet.name.strip() if sheet.name else ""
        out.append((label or f"P{i + 1}", found.resolve()))
    return out


class ScoreSheetPane(QWidget):
    """페이지 탭 + 폭 맞춤 악보 이미지 (세로 스크롤)."""

    def __init__(
        self, sheets: list[tuple[str, Path]], parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._sheets: list[tuple[str, Path]] = []
        self._current = -1
        self._tabs: list[QPushButton] = []
        # 페이지별 원본 픽스맵 — 탭을 오갈 때마다 디코드하지 않는다
        self._pixmaps: dict[int, QPixmap] = {}
        self._settle_timer = QTimer(self)
        self._settle_timer.setSingleShot(True)
        self._settle_timer.setInterval(120)
        self._settle_timer.timeout.connect(self._refit)
        self._build_ui()
        self.set_sheets(sheets)

    # ── UI ────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(SP_XS)

        self._tab_row = QWidget()
        self._tab_layout = QHBoxLayout(self._tab_row)
        self._tab_layout.setContentsMargins(SP_SM, SP_XS, SP_SM, 0)
        self._tab_layout.setSpacing(SP_XS)
        self._tab_layout.addStretch()
        root.addWidget(self._tab_row)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._scroll.setStyleSheet(f"""
            QScrollArea {{ background: {BG_DEEP}; border: none; }}
            QScrollBar:vertical {{
                border: none; background: transparent; width: 6px;
            }}
            QScrollBar::handle:vertical {{
                background: {BORDER_FOCUS}; border-radius: 3px; min-height: 20px;
            }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{ height: 0; }}
        """)

        self._image = QLabel()
        self._image.setAlignment(
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop
        )
        self._image.setStyleSheet(f"background: {BG_DEEP};")
        self._image.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Minimum
        )
        self._scroll.setWidget(self._image)
        self._scroll.viewport().installEventFilter(self)
        root.addWidget(self._scroll, 1)

        self._empty = QLabel("악보가 없습니다")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setStyleSheet(
            f"color: {TEXT_TERTIARY}; font-size: {FONT_SM}px; background: {BG_DEEP};"
        )
        self._empty.hide()
        root.addWidget(self._empty, 1)

    # ── 공개 API ──────────────────────────────────────────────────────────

    def set_sheets(self, sheets: list[tuple[str, Path]]) -> None:
        self._sheets = list(sheets)
        self._pixmaps.clear()
        for tab in self._tabs:
            self._tab_layout.removeWidget(tab)
            tab.deleteLater()
        self._tabs.clear()

        for i, (label, _path) in enumerate(self._sheets):
            tab = QPushButton(label)
            tab.setCheckable(True)
            tab.setFixedHeight(24)
            tab.setCursor(Qt.CursorShape.PointingHandCursor)
            tab.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            tab.setToolTip(str(_path))
            tab.clicked.connect(lambda _c=False, k=i: self.show_page(k))
            self._tab_layout.insertWidget(i, tab)
            self._tabs.append(tab)

        has_sheets = bool(self._sheets)
        # 한 장이면 넘길 탭이 없다 — 탭 줄을 통째로 접어 악보에 자리를 준다
        self._tab_row.setVisible(len(self._sheets) > 1)
        self._scroll.setVisible(has_sheets)
        self._empty.setVisible(not has_sheets)
        self._current = -1
        if has_sheets:
            self.show_page(0)
        else:
            self._image.clear()

    def page_count(self) -> int:
        return len(self._sheets)

    def current_page(self) -> int:
        return self._current

    def show_page(self, index: int) -> None:
        if not (0 <= index < len(self._sheets)):
            return
        self._current = index
        for i, tab in enumerate(self._tabs):
            tab.setChecked(i == index)
            self._style_tab(tab, i == index)
        self._scroll.verticalScrollBar().setValue(0)
        self._refit()

    # ── 내부 ──────────────────────────────────────────────────────────────

    def _pixmap_for(self, index: int) -> QPixmap:
        pm = self._pixmaps.get(index)
        if pm is None:
            pm = QPixmap(str(self._sheets[index][1]))
            self._pixmaps[index] = pm
        return pm

    def _refit(
        self, mode: Qt.TransformationMode = Qt.TransformationMode.SmoothTransformation
    ) -> None:
        """현재 페이지를 뷰포트 폭에 맞춰 다시 그린다 (세로는 스크롤)."""
        if self._current < 0:
            return
        pm = self._pixmap_for(self._current)
        if pm.isNull():
            self._image.setText("이미지를 열 수 없습니다")
            self._image.setStyleSheet(
                f"color: {TEXT_TERTIARY}; font-size: {FONT_SM}px; "
                f"background: {BG_DEEP};"
            )
            self._image.setMinimumHeight(0)
            return
        width = max(self._scroll.viewport().width(), 1)
        scaled = pm.scaledToWidth(width, mode)
        self._image.setPixmap(scaled)
        # 라벨 높이를 이미지에 맞춰야 스크롤 범위가 생긴다
        self._image.setMinimumHeight(scaled.height())

    def eventFilter(self, obj, event) -> bool:  # noqa: N802 — Qt 오버라이드
        # 패널 자체의 resizeEvent에서 재면 스크롤 뷰포트가 아직 이전 크기라
        # 엉뚱한 폭으로 그린다 — 뷰포트가 실제로 바뀐 순간에 맞춘다.
        # 스플리터를 끄는 동안 큰 악보를 매번 부드럽게 줄이면 드래그가
        # 버벅인다 — 끌 때는 빠르게, 손을 떼면 한 번 곱게 다시 그린다.
        if obj is self._scroll.viewport() and event.type() == QEvent.Type.Resize:
            self._refit(Qt.TransformationMode.FastTransformation)
            self._settle_timer.start()
        return super().eventFilter(obj, event)

    def _style_tab(self, tab: QPushButton, active: bool) -> None:
        # 셋리스트의 시트 탭과 같은 톤 — 활성은 은은한 오버레이 + 인디고 글자
        if active:
            tab.setStyleSheet(f"""
                QPushButton {{
                    background: {SURFACE_SUBTLE}; color: {ACCENT_INTER};
                    border: 1px solid {BORDER_STANDARD_RGBA};
                    border-radius: {RADIUS_SM}px;
                    font-size: {FONT_SM}px; font-weight: {FW_SEMI}; padding: 0 10px;
                }}
            """)
        else:
            tab.setStyleSheet(f"""
                QPushButton {{
                    background: {SURFACE_GHOST}; color: {TEXT_TERTIARY};
                    border: 1px solid {BORDER_SUBTLE_RGBA};
                    border-radius: {RADIUS_SM}px;
                    font-size: {FONT_SM}px; font-weight: {FW_MEDIUM}; padding: 0 10px;
                }}
                QPushButton:hover {{
                    background: {SURFACE_RAISED}; color: {TEXT_SECONDARY};
                }}
            """)
