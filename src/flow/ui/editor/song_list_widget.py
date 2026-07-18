"""곡 목록 위젯 (셋리스트 카드 뷰)

프로젝트의 곡을 카드 형태로 표시하고 관리하는 UI.
곡 상태(악보·PPT·매핑)를 한눈에 파악하고 빠르게 편집할 수 있다.
"""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QEvent, QPoint, QTimer
from PySide6.QtGui import QAction, QColor, QFont
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QApplication,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from flow.ui.styles import (
    BG_DEEP, BG_SURFACE, BG_ELEVATED, BG_HOVER, BG_INPUT,
    BORDER, BORDER_FOCUS, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_TERTIARY, TEXT_INVERSE,
    ACCENT, ACCENT_INTER, ACCENT_HOVER, ACCENT_MUTED, ACCENT_SURFACE,
    SURFACE_GHOST, SURFACE_SUBTLE, SURFACE_RAISED,
    BORDER_SUBTLE_RGBA, BORDER_STANDARD_RGBA,
    GREEN_MUTED, AMBER, AMBER_MUTED, RED,
    RADIUS_SM, RADIUS_MD, RADIUS_LG, FONT_SM, FONT_MD, FONT_LG, FONT_TITLE,
    FW_REGULAR, FW_MEDIUM, FW_SEMI,
    SP_XS, SP_SM, SP_MD, SP_LG,
)

from flow.domain.project import Project
from flow.domain.score_sheet import ScoreSheet
from flow.domain.song import Song, detect_slides_file


# ─── 상태 계산 헬퍼 ────────────────────────────────────────────────────────


def _song_status(song: Song) -> dict:
    """곡의 완성도 정보를 반환 (JSON 파싱 없이 파일 존재 확인)."""
    has_sheets = any(bool(s.image_path) for s in song.score_sheets)

    has_ppt = False
    has_md = False
    if song.project_dir and song.folder:
        song_dir = song.project_dir / song.folder
        has_ppt = detect_slides_file(song_dir) is not None
        has_md = (song_dir / "slides.md").exists()
    else:
        if hasattr(song, "has_slides"):
            has_ppt = song.has_slides
        if hasattr(song, "has_markdown"):
            has_md = song.has_markdown

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
        "has_md": has_md,
        "total_hotspots": total_hs,
        "mapped_hotspots": mapped_hs,
    }


def _completeness_warnings(
    sheet_count: int, has_slides: bool, mapped: int
) -> list[str]:
    """악보/슬라이드/매핑 없음 경고 목록 (정상은 빈 리스트).

    악보·슬라이드가 있어야 매핑 판정이 의미 있음 — 원인 경고만 남긴다.
    """
    warnings = []
    if sheet_count == 0:
        warnings.append("악보 없음")
    if not has_slides:
        warnings.append("슬라이드 없음")
    if sheet_count > 0 and has_slides and mapped == 0:
        warnings.append("매핑 없음")
    return warnings


def _scan_library_song(song_dir: Path) -> dict:
    """라이브러리의 곡 폴더를 스캔해 상태 정보 반환."""
    result = {"name": song_dir.name, "path": song_dir}

    # 악보 이미지 확인
    sheet_count = 0
    for sub in ("sheets", "sheet"):
        d = song_dir / sub
        if d.is_dir():
            sheet_count += sum(
                1 for f in d.iterdir()
                if f.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp"}
            )
    result["sheet_count"] = sheet_count

    # PPT / 마크다운 확인
    result["has_ppt"] = detect_slides_file(song_dir) is not None
    result["has_md"] = (song_dir / "slides.md").exists()

    # 가사 검색용 텍스트 — 선두 frontmatter(설정) 블록을 제외한 본문(원문).
    # PPT 곡 등 slides.md가 없으면 빈 문자열(제목으로만 검색). 매칭 시 lower().
    from flow.services.markdown import read_song_lyrics

    result["lyrics"] = read_song_lyrics(song_dir)

    # song.json에서 핫스팟 수 확인
    total_hs, mapped_hs = 0, 0
    song_json = song_dir / "song.json"
    if song_json.exists():
        try:
            with open(song_json, encoding="utf-8-sig") as f:
                data = json.load(f)
            for sheet_data in data.get("sheets", []):
                for h in sheet_data.get("hotspots", []):
                    total_hs += 1
                    if h.get("slide_mappings") or h.get("slide_index", -1) >= 0:
                        mapped_hs += 1
        except Exception:
            pass
    result["total_hotspots"] = total_hs
    result["mapped_hotspots"] = mapped_hs
    return result




class _ElidedLabel(QLabel):
    """폭이 모자라면 말줄임(…)으로 줄이는 라벨 — 최소 폭을 강제하지 않아
    좁은 패널에서도 우측 버튼이 잘리지 않는다. 전체 텍스트는 툴팁으로."""

    def __init__(self, text: str, parent=None) -> None:
        super().__init__(text, parent)
        self._full_text = text
        self.setToolTip(text)
        self.setMinimumWidth(40)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    def resizeEvent(self, event) -> None:  # noqa: N802
        metrics = self.fontMetrics()
        elided = metrics.elidedText(
            self._full_text, Qt.TextElideMode.ElideRight, self.width()
        )
        super().setText(elided)
        super().resizeEvent(event)


class _LibrarySongCard(QFrame):
    """라이브러리 다이얼로그 안의 곡 카드."""

    add_clicked = Signal(str, str)  # (song name, source: "library" | "local")

    def __init__(
        self,
        info: dict,
        workspace_mode: bool = False,
        added: bool = False,
        match_snippet: str = "",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("LibSongCard")
        self._name = info["name"]
        self._workspace_mode = workspace_mode
        self._match_snippet = match_snippet
        self._add_buttons: list[QPushButton] = []
        self._added: bool = False
        self._setup_ui(info)
        self.set_added(added)

    def _setup_ui(self, info: dict) -> None:
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(f"""
            QFrame#LibSongCard {{
                background: {BG_ELEVATED};
                border: 1px solid {BORDER};
                border-radius: {RADIUS_LG}px;
            }}
            QFrame#LibSongCard:hover {{
                background: {BG_HOVER};
                border: 1px solid {BORDER_FOCUS};
            }}
        """)

        root = QHBoxLayout(self)
        root.setContentsMargins(SP_MD, SP_SM, SP_MD, SP_SM)
        root.setSpacing(SP_MD)

        # 왼쪽: 이름 + 상태
        left = QVBoxLayout()
        left.setSpacing(4)

        name_lbl = _ElidedLabel(info["name"])
        name_lbl.setStyleSheet(
            f"font-size: {FONT_TITLE}px; font-weight: 500; color: {TEXT_PRIMARY}; background: transparent;"
        )
        left.addWidget(name_lbl)

        status_row = QHBoxLayout()
        status_row.setSpacing(10)

        # 문제가 있을 때만 앰버 경고 (정상은 조용히, 완료 카운트 없음)
        warnings = _completeness_warnings(
            info["sheet_count"],
            info["has_ppt"] or info.get("has_md"),
            info["mapped_hotspots"],
        )
        for text in warnings:
            lbl = QLabel(text)
            lbl.setStyleSheet(
                f"font-size: {FONT_SM}px; color: {AMBER}; background: transparent;"
            )
            status_row.addWidget(lbl)

        status_row.addStretch()
        left.addLayout(status_row)

        # "이미 추가됨" 배지 — 기본 숨김, set_added(True) 시 표시
        self._added_badge = QLabel("이미 추가됨")
        self._added_badge.setStyleSheet(
            f"font-size: {FONT_SM}px; font-weight: {FW_REGULAR}; color: {TEXT_TERTIARY};"
            f" background: {SURFACE_SUBTLE}; border-radius: {RADIUS_SM}px;"
            f" padding: 1px 6px;"
        )
        self._added_badge.setVisible(False)
        left.addWidget(self._added_badge)

        # 가사 검색 매칭 줄 — 가사로 검색되어 매칭 줄이 있을 때만 표시.
        if self._match_snippet:
            snippet_lbl = _ElidedLabel(f"“{self._match_snippet}”")
            snippet_lbl.setStyleSheet(
                f"font-size: {FONT_SM}px; color: {TEXT_SECONDARY};"
                f" background: transparent;"
            )
            left.addWidget(snippet_lbl)

        root.addLayout(left, 1)

        # 오른쪽: 추가 버튼(들)
        primary_css = f"""
            QPushButton {{
                background: {ACCENT}; color: #fff;
                border: none; border-radius: {RADIUS_MD}px;
                font-size: {FONT_MD}px; font-weight: 500; padding: 0 14px;
            }}
            QPushButton:hover {{ background: {ACCENT_HOVER}; }}
        """
        secondary_css = f"""
            QPushButton {{
                background: transparent; color: {TEXT_SECONDARY};
                border: 1px solid {BORDER}; border-radius: {RADIUS_MD}px;
                font-size: {FONT_MD}px; padding: 0 12px;
            }}
            QPushButton:hover {{ background: {BG_HOVER}; color: {TEXT_PRIMARY}; border-color: {BORDER_FOCUS}; }}
        """

        if self._workspace_mode:
            # 워크스페이스 모드: "참조" + "복사" 두 버튼
            btn_ref = QPushButton("참조")
            btn_ref.setFixedHeight(30)
            btn_ref.setMinimumWidth(56)
            btn_ref.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_ref.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn_ref.setToolTip("라이브러리 곡을 이 프로젝트에 참조로 추가 (공용)")
            btn_ref.setStyleSheet(primary_css)
            btn_ref.clicked.connect(lambda: self.add_clicked.emit(self._name, "library"))
            root.addWidget(btn_ref)
            self._add_buttons.append(btn_ref)

            btn_copy = QPushButton("복사")
            btn_copy.setFixedHeight(30)
            btn_copy.setMinimumWidth(56)
            btn_copy.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_copy.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn_copy.setToolTip("이 프로젝트만의 로컬 복사본으로 추가 (커스터마이즈용)")
            btn_copy.setStyleSheet(secondary_css)
            btn_copy.clicked.connect(lambda: self.add_clicked.emit(self._name, "local"))
            root.addWidget(btn_copy)
            self._add_buttons.append(btn_copy)
        else:
            # 레거시 모드: 단일 "추가" 버튼
            btn = QPushButton("추가")
            btn.setFixedHeight(30)
            btn.setMinimumWidth(56)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setStyleSheet(primary_css)
            btn.clicked.connect(lambda: self.add_clicked.emit(self._name, "local"))
            root.addWidget(btn)
            self._add_buttons.append(btn)

    def set_added(self, added: bool) -> None:
        """이미 추가됨 상태를 토글한다."""
        self._added = added
        for btn in self._add_buttons:
            btn.setEnabled(not added)
        self._added_badge.setVisible(added)
        cursor = Qt.CursorShape.ArrowCursor if added else Qt.CursorShape.PointingHandCursor
        self.setCursor(cursor)


class SongLibraryBrowser(QWidget):
    """재사용 가능한 곡 라이브러리 브라우저 위젯.

    검색 박스 + 카드 스크롤 + 빈 상태를 담는 독립 위젯.
    모달 다이얼로그(SongLibraryDialog)와 향후 라이브 패널 양쪽에 임베드 가능.
    """

    song_chosen = Signal(str, str)  # (이름, source: "library" | "local")

    def __init__(
        self,
        songs_dir: Path,
        included_names: set[str],
        parent=None,
        workspace=None,
    ) -> None:
        super().__init__(parent)
        self._songs_dir = songs_dir
        self._included: set[str] = set(included_names)
        self._workspace = workspace
        self._all_infos: list[dict] = []
        self._cards: list[_LibrarySongCard] = []
        self._setup_ui()
        self._scan()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(SP_MD)

        # 검색
        self._search = QLineEdit()
        self._search.setPlaceholderText("곡 이름 검색...")
        self._search.setFixedHeight(34)
        self._search.setStyleSheet(f"""
            QLineEdit {{
                background: {BG_INPUT}; color: {TEXT_PRIMARY};
                border: 1px solid {BORDER}; border-radius: {RADIUS_MD}px;
                padding: 0 10px; font-size: {FONT_MD}px;
            }}
            QLineEdit:focus {{ border-color: {ACCENT}; }}
        """)
        # 키 입력마다 카드 전체 재생성은 큰 라이브러리에서 버벅임 —
        # 150ms 디바운스 후 한 번만 렌더
        from PySide6.QtCore import QTimer

        self._filter_timer = QTimer(self)
        self._filter_timer.setSingleShot(True)
        self._filter_timer.setInterval(150)
        self._filter_timer.timeout.connect(
            lambda: self._filter(self._search.text())
        )
        self._search.textChanged.connect(
            lambda _t: self._filter_timer.start()
        )
        root.addWidget(self._search)

        # 카드 스크롤 영역
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setStyleSheet(f"""
            QScrollArea {{ background: transparent; border: none; }}
            QScrollBar:vertical {{
                border: none; background: transparent; width: 6px;
            }}
            QScrollBar::handle:vertical {{
                background: {BORDER_FOCUS}; border-radius: 3px; min-height: 20px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)

        self._list_widget = QWidget()
        self._list_widget.setStyleSheet("background: transparent;")
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(SP_SM)
        self._list_layout.addStretch()

        self._scroll.setWidget(self._list_widget)
        root.addWidget(self._scroll, 1)

        # 빈 상태 — 컴팩트 EmptyState
        from flow.ui.empty_state import EmptyState
        self._empty_widget = EmptyState(
            icon="search",
            title="추가할 수 있는 곡이 없습니다",
            description="새 곡을 먼저 만들어 주세요",
            compact=True,
        )
        self._empty_widget.hide()
        root.addWidget(self._empty_widget)

    def _scan(self) -> None:
        """곡 폴더를 스캔해 전체 곡 정보 로드 (포함 여부와 무관하게 모두 수집)."""
        self._all_infos.clear()
        scan_dir = (
            self._workspace.library_dir if self._workspace is not None
            else self._songs_dir
        )
        if not scan_dir.exists():
            self._show_empty(
                icon="image",
                title="라이브러리가 비어있습니다",
                description="새 곡을 먼저 만들어 주세요",
            )
            return

        for folder in sorted(scan_dir.iterdir()):
            if folder.is_dir() and (folder / "song.json").exists():
                self._all_infos.append(_scan_library_song(folder))

        self._render(self._all_infos)

    def _filter(self, query: str) -> None:
        q = query.strip().lower()
        if not q:
            self._render(self._all_infos)
            return
        filtered = [
            info for info in self._all_infos
            if q in info["name"].lower() or q in info.get("lyrics", "").lower()
        ]
        self._render(filtered, q)

    def _render(self, infos: list[dict], query: str = "") -> None:
        for card in self._cards:
            self._list_layout.removeWidget(card)
            card.deleteLater()
        self._cards.clear()

        if not infos:
            if self._all_infos:
                self._show_empty(
                    icon="search",
                    title="검색 결과가 없습니다",
                    description="다른 검색어로 시도해 보세요",
                )
            else:
                self._show_empty(
                    icon="image",
                    title="추가할 수 있는 곡이 없습니다",
                    description="새 곡을 먼저 만들어 주세요",
                )
            return

        self._empty_widget.hide()
        self._scroll.show()

        workspace_mode = self._workspace is not None
        for info in infos:
            added = info["name"] in self._included
            # 제목이 아니라 가사로 매칭된 경우에만 매칭 줄을 카드에 표시
            snippet = ""
            if query and query not in info["name"].lower():
                from flow.services.markdown import lyric_snippet

                snippet = lyric_snippet(info.get("lyrics", ""), query)
            card = _LibrarySongCard(
                info, workspace_mode=workspace_mode, added=added,
                match_snippet=snippet,
            )
            card.add_clicked.connect(self._on_song_added)
            self._cards.append(card)
            self._list_layout.insertWidget(self._list_layout.count() - 1, card)

    def _show_empty(
        self, icon: str = "search", title: str = "", description: str = ""
    ) -> None:
        """빈 상태 위젯을 새로 만들어 교체."""
        from flow.ui.empty_state import EmptyState

        parent_layout = self._empty_widget.parentWidget().layout()
        idx = parent_layout.indexOf(self._empty_widget)
        self._empty_widget.deleteLater()

        self._empty_widget = EmptyState(
            icon=icon, title=title, description=description, compact=True
        )
        parent_layout.insertWidget(idx, self._empty_widget)
        self._empty_widget.show()
        self._scroll.hide()

    def _on_song_added(self, name: str, source: str) -> None:
        self.song_chosen.emit(name, source)
        self.mark_added(name)

    def mark_added(self, name: str) -> None:
        """이름에 해당하는 카드를 '이미 추가됨' 상태로 표시한다."""
        self._included.add(name)
        for card in self._cards:
            if card._name == name:
                card.set_added(True)

    def focus_search(self) -> None:
        """검색 박스에 포커스를 준다."""
        self._search.setFocus()


class SongLibraryDialog(QDialog):
    """곡 라이브러리 브라우저 다이얼로그.

    두 가지 모드:
      - 레거시: songs_dir 경로를 직접 스캔 (workspace=None)
      - 워크스페이스: workspace.library_dir를 스캔, 카드에 "참조"/"복사" 버튼 표시
    """

    song_chosen = Signal(str, str)  # (이름, source: "library" | "local")

    def __init__(
        self,
        songs_dir: Path,
        included_names: set[str],
        parent=None,
        workspace=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("곡 라이브러리")
        self.setMinimumSize(480, 400)
        self.resize(520, 500)
        self._setup_ui(songs_dir, included_names, workspace)

    def _setup_ui(
        self,
        songs_dir: Path,
        included_names: set[str],
        workspace,
    ) -> None:
        self.setStyleSheet(f"""
            QDialog {{
                background: {BG_SURFACE}; color: {TEXT_PRIMARY};
                border: 1px solid {BORDER};
            }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(SP_LG, SP_LG, SP_LG, SP_LG)
        root.setSpacing(SP_MD)

        # 헤더
        header = QLabel("곡 라이브러리")
        header.setStyleSheet(
            f"font-size: 18px; font-weight: {FW_SEMI}; color: {TEXT_PRIMARY};"
        )
        root.addWidget(header)

        sub = QLabel("셋리스트에 추가할 곡을 선택하세요")
        sub.setStyleSheet(f"font-size: {FONT_MD}px; color: {TEXT_TERTIARY};")
        root.addWidget(sub)

        # 브라우저 위젯 (검색 + 스크롤 + 빈 상태)
        self._browser = SongLibraryBrowser(
            songs_dir=songs_dir,
            included_names=included_names,
            parent=self,
            workspace=workspace,
        )
        self._browser.song_chosen.connect(self.song_chosen)
        root.addWidget(self._browser, 1)

        # 하단 닫기
        btn_close = QPushButton("닫기")
        btn_close.setFixedHeight(34)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet(f"""
            QPushButton {{
                background: {BG_HOVER}; color: {TEXT_SECONDARY};
                border: 1px solid {BORDER}; border-radius: {RADIUS_MD}px;
                font-size: {FONT_MD}px; padding: 0 20px;
            }}
            QPushButton:hover {{ background: {BG_ELEVATED}; color: {TEXT_PRIMARY}; }}
        """)
        btn_close.clicked.connect(self.close)
        root.addWidget(btn_close)

    # ── 하위 호환 위임 프로퍼티 ─────────────────────────────────────────────

    @property
    def _cards(self) -> list[_LibrarySongCard]:
        """브라우저 카드 목록 위임 (외부 접근 호환성)."""
        return self._browser._cards

    @property
    def _all_infos(self) -> list[dict]:
        """브라우저 전체 곡 정보 위임 (외부 접근 호환성)."""
        return self._browser._all_infos


# ─── 시트 탭 버튼 ───────────────────────────────────────────────────────────


class _SheetTab(QPushButton):
    """선택된 곡 하단에 나타나는 페이지 탭."""

    def __init__(
        self, sheet: ScoreSheet, page_num: int, parent=None, show_name: bool = False
    ) -> None:
        label = sheet.name if show_name and sheet.name else f"P{page_num}"
        super().__init__(label, parent)
        self._sheet = sheet
        self._show_name = show_name
        if show_name:
            # 이름 표시 모드: 한 줄에 하나씩 크게 (좌측 정렬, 전체 폭)
            self.setFixedHeight(32)
            self.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
            )
        else:
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
        # Linear 패턴: active = 미묘한 white-overlay + ACCENT_INTER 텍스트
        # 솔리드 인디고 채움 안 함
        # 이름 표시 모드: 한 줄 전체 폭이므로 좌측 정렬 + 조금 큰 글씨
        metrics = (
            f"font-size: {FONT_SM}px; padding: 0 10px; text-align: left;"
            if self._show_name
            else "font-size: 10px; padding: 0 6px;"
        )
        if active:
            self.setStyleSheet(f"""
                QPushButton {{
                    background: {SURFACE_SUBTLE}; color: {ACCENT_INTER};
                    border: 1px solid {BORDER_STANDARD_RGBA};
                    border-radius: {RADIUS_SM}px;
                    {metrics}
                    font-weight: {FW_SEMI};
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QPushButton {{
                    background: {SURFACE_GHOST}; color: {TEXT_TERTIARY};
                    border: 1px solid {BORDER_SUBTLE_RGBA};
                    border-radius: {RADIUS_SM}px;
                    {metrics}
                    font-weight: {FW_MEDIUM};
                }}
                QPushButton:hover {{
                    background: {SURFACE_RAISED};
                    color: {TEXT_SECONDARY};
                }}
            """)


# ─── 곡 카드 ────────────────────────────────────────────────────────────────


class _SongCard(QFrame):
    """셋리스트의 곡 하나를 나타내는 카드 위젯."""

    sheet_selected = Signal(object)     # ScoreSheet
    edit_requested = Signal(object)     # Song
    remove_requested = Signal(object)   # Song
    reload_requested = Signal(object)   # Song
    import_ppt_requested = Signal(object)  # Song
    move_requested = Signal(object, int)   # (Song, -1=위/+1=아래)
    move_mode_requested = Signal(object)   # Song (방향키 이동 모드)
    toggle_sheet_names_requested = Signal(object)  # Song

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
        root.setContentsMargins(SP_SM, SP_XS + 2, SP_SM, SP_XS + 2)
        root.setSpacing(4)

        # ── 상단 행: 번호 배지 + 곡 이름 + 액션 버튼
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(SP_XS + 2)

        self._badge = QLabel(str(self._position))
        self._badge.setFixedSize(22, 22)
        self._badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._badge.setStyleSheet(
            f"background: {BG_ELEVATED}; color: {TEXT_TERTIARY}; border-radius: 11px; "
            f"font-size: 10px;"
        )
        top_row.addWidget(self._badge)

        self._name_label = QLabel(self._song.name)
        self._name_label.setStyleSheet(
            f"font-size: {FONT_LG}px; font-weight: {FW_MEDIUM}; color: {TEXT_PRIMARY}; background: transparent;"
        )
        self._name_label.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed
        )
        self._name_label.setMinimumWidth(0)
        self._name_label.setToolTip(self._song.name)
        top_row.addWidget(self._name_label, 1)

        # 형식 태그 — 선택된 카드에서만 표시 (중립 정보, 경고 아님)
        self._fmt_tag = QLabel()
        self._fmt_tag.setStyleSheet(
            f"font-size: 10px; color: {TEXT_TERTIARY}; background: transparent;"
        )
        self._fmt_tag.hide()
        top_row.addWidget(self._fmt_tag)

        # 편집 버튼 (hover 시 표시)
        self._btn_edit = QPushButton("편집")
        self._btn_edit.setFixedHeight(24)
        self._btn_edit.setMinimumWidth(52)
        self._btn_edit.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_edit.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_edit.setStyleSheet(f"""
            QPushButton {{
                background: {ACCENT_MUTED}; color: {ACCENT}; border: 1px solid {ACCENT_SURFACE};
                border-radius: {RADIUS_MD}px; font-size: 10px; padding: 0 8px;
            }}
            QPushButton:hover {{ background: {ACCENT_SURFACE}; }}
            QPushButton:disabled {{
                background: {BG_ELEVATED}; color: {TEXT_TERTIARY};
                border: 1px solid {BORDER};
            }}
        """)
        self._btn_edit.clicked.connect(lambda: self.edit_requested.emit(self._song))
        self._btn_edit.hide()
        top_row.addWidget(self._btn_edit)

        self._btn_remove = QPushButton("✕")
        self._btn_remove.setFixedSize(22, 22)
        self._btn_remove.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_remove.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_remove.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {TEXT_TERTIARY}; border: none;
                font-size: {FONT_SM}px;
            }}
            QPushButton:hover {{ color: {RED}; }}
        """)
        self._btn_remove.clicked.connect(lambda: self.remove_requested.emit(self._song))
        self._btn_remove.hide()
        top_row.addWidget(self._btn_remove)

        root.addLayout(top_row)

        # ── 상태 행: 문제가 있을 때만 앰버 경고 (정상은 조용히)
        self._status_widget = QWidget()
        status_row = QHBoxLayout(self._status_widget)
        status_row.setContentsMargins(30, 0, 0, 0)
        status_row.setSpacing(SP_MD)
        self._lbl_warnings = QLabel()
        self._lbl_warnings.setStyleSheet(
            f"font-size: 10px; color: {AMBER}; background: transparent;"
        )
        status_row.addWidget(self._lbl_warnings)
        status_row.addStretch()
        self._status_widget.hide()
        root.addWidget(self._status_widget)

        # ── 시트 탭 영역 (선택 시만 표시) — 줄바꿈 그리드로 N개 이상도 안전
        from PySide6.QtWidgets import QGridLayout
        self._tabs_container = QWidget()
        tabs_layout = QGridLayout(self._tabs_container)
        tabs_layout.setContentsMargins(30, 0, 0, 0)
        tabs_layout.setHorizontalSpacing(4)
        tabs_layout.setVerticalSpacing(4)
        self._tabs_layout = tabs_layout
        self._tabs_container.hide()
        root.addWidget(self._tabs_container)

        self._refresh_frame_style()

    # ── 상태 갱신 ─────────────────────────────────────────────────────────

    def refresh_status(self) -> None:
        st = _song_status(self._song)
        has_slides = st["has_ppt"] or st["has_md"]

        warnings = []
        if not st["has_sheets"]:
            warnings.append("악보 없음")
        if not has_slides:
            warnings.append("슬라이드 없음")
        if st["has_sheets"] and has_slides:
            # 악보·슬라이드가 있어야 매핑이 의미 있음 — 원인 경고만 표시
            total, mapped = st["total_hotspots"], st["mapped_hotspots"]
            if mapped == 0:
                warnings.append("매핑 없음")
            elif mapped < total:
                warnings.append(f"매핑 {mapped}/{total}")

        self._lbl_warnings.setText(" · ".join(warnings))
        self._status_widget.setVisible(bool(warnings))

        if st["has_ppt"]:
            self._fmt_tag.setText("PPT")
        elif st["has_md"]:
            self._fmt_tag.setText("마크다운")
        else:
            self._fmt_tag.setText("")
        self._fmt_tag.setVisible(self._is_selected and bool(self._fmt_tag.text()))

    def set_selected(self, selected: bool, current_sheet_id: str | None = None) -> None:
        self._is_selected = selected
        self._current_sheet_id = current_sheet_id
        # Selected: 미묘한 white-overlay + ACCENT_INTER 텍스트 (Linear 패턴)
        # Idle: 더 어두운 배경 + 흐린 텍스트
        self._badge.setStyleSheet(
            f"background: {SURFACE_SUBTLE}; color: {ACCENT_INTER}; "
            f"border-radius: 11px; font-size: 10px; font-weight: {FW_SEMI};"
            if selected else
            f"background: {SURFACE_GHOST}; color: {TEXT_TERTIARY}; "
            f"border-radius: 11px; font-size: 10px; font-weight: {FW_MEDIUM};"
        )
        self._name_label.setStyleSheet(
            f"font-size: {FONT_LG}px; font-weight: 500; color: #fff; background: transparent;"
            if selected else
            f"font-size: {FONT_LG}px; font-weight: 500; color: {TEXT_PRIMARY}; background: transparent;"
        )
        self._refresh_tabs(current_sheet_id)
        self._tabs_container.setVisible(selected and bool(self._sheet_tabs))
        self._fmt_tag.setVisible(selected and bool(self._fmt_tag.text()))
        self._refresh_frame_style()

    # 시트 탭 한 행에 들어갈 최대 개수
    _TABS_PER_ROW = 4

    def _refresh_tabs(self, current_sheet_id: str | None) -> None:
        # 기존 탭 제거
        for tab in self._sheet_tabs:
            self._tabs_layout.removeWidget(tab)
            tab.deleteLater()
        self._sheet_tabs.clear()

        valid_sheets = [s for s in self._song.score_sheets if s.image_path]
        for i, sheet in enumerate(valid_sheets):
            tab = _SheetTab(
                sheet,
                i + 1,
                self._tabs_container,
                show_name=self._song.show_sheet_names,
            )
            tab.set_current(sheet.id == current_sheet_id)
            tab.clicked.connect(lambda checked, s=sheet: self.sheet_selected.emit(s))
            self._sheet_tabs.append(tab)
            if self._song.show_sheet_names:
                # 이름 표시 모드: 한 줄에 한 시트 (stretch 열까지 스팬)
                self._tabs_layout.addWidget(tab, i, 0, 1, self._TABS_PER_ROW + 1)
            else:
                row, col = divmod(i, self._TABS_PER_ROW)
                self._tabs_layout.addWidget(tab, row, col)
        # 마지막 컬럼 이후 stretch로 좌측 정렬 (격자 모드 전용)
        if not self._song.show_sheet_names:
            last_row_count = (
                len(valid_sheets) % self._TABS_PER_ROW or self._TABS_PER_ROW
            )
            if last_row_count < self._TABS_PER_ROW:
                self._tabs_layout.setColumnStretch(self._TABS_PER_ROW, 1)

    def _refresh_frame_style(self) -> None:
        # Linear 패턴: selected = 미묘한 white-overlay + 좌측 액센트 바
        # idle = ghost(거의 투명), hover = subtle white-overlay
        if self._is_selected:
            self.setStyleSheet(f"""
                QFrame#SongCard {{
                    background: {SURFACE_SUBTLE};
                    border: 1px solid {BORDER_STANDARD_RGBA};
                    border-left: 3px solid {ACCENT_INTER};
                    border-radius: {RADIUS_LG}px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QFrame#SongCard {{
                    background: {SURFACE_GHOST};
                    border: 1px solid {BORDER_SUBTLE_RGBA};
                    border-radius: {RADIUS_LG}px;
                }}
                QFrame#SongCard:hover {{
                    background: {SURFACE_SUBTLE};
                    border-color: {BORDER_STANDARD_RGBA};
                }}
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
        self._build_context_menu().exec(event.globalPos())

    def _build_context_menu(self) -> QMenu:
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{ background: {BG_ELEVATED}; color: {TEXT_PRIMARY}; border: 1px solid {BORDER_FOCUS}; border-radius: {RADIUS_MD}px; }}
            QMenu::item {{ padding: {SP_SM}px {SP_LG}px; font-size: {FONT_MD}px; }}
            QMenu::item:selected {{ background: {ACCENT_MUTED}; color: {ACCENT}; }}
            QMenu::separator {{ height: 1px; background: {BORDER}; margin: 4px 0; }}
        """)
        edit_act = QAction("곡 편집", self)
        edit_act.triggered.connect(lambda: self.edit_requested.emit(self._song))
        menu.addAction(edit_act)

        reload_act = QAction("슬라이드 새로고침", self)
        reload_act.triggered.connect(lambda: self.reload_requested.emit(self._song))
        menu.addAction(reload_act)

        import_ppt_act = QAction("PPT 가져오기", self)
        import_ppt_act.triggered.connect(
            lambda: self.import_ppt_requested.emit(self._song)
        )
        menu.addAction(import_ppt_act)

        toggle_names_act = QAction(
            "시트 이름 숨기기" if self._song.show_sheet_names else "시트 이름 표시",
            self,
        )
        toggle_names_act.triggered.connect(
            lambda: self.toggle_sheet_names_requested.emit(self._song)
        )
        menu.addAction(toggle_names_act)

        menu.addSeparator()
        move_mode_act = QAction("위치 이동", self)
        move_mode_act.triggered.connect(
            lambda: self.move_mode_requested.emit(self._song)
        )
        menu.addAction(move_mode_act)

        up_act = QAction("위로 이동", self)
        up_act.triggered.connect(lambda: self.move_requested.emit(self._song, -1))
        menu.addAction(up_act)

        down_act = QAction("아래로 이동", self)
        down_act.triggered.connect(lambda: self.move_requested.emit(self._song, 1))
        menu.addAction(down_act)

        menu.addSeparator()
        remove_act = QAction("셋리스트에서 제거", self)
        remove_act.triggered.connect(lambda: self.remove_requested.emit(self._song))
        menu.addAction(remove_act)

        return menu


# ─── 단독 곡 편집 패널 (standalone 모드) ────────────────────────────────────


class _SwitcherRow(QPushButton):
    """곡 전환 목록의 한 줄 — 곡 이름 + (문제 시) 둘째 줄 앰버 경고.

    경고를 이름 옆에 붙이면 좁은 패널에서 잘리므로 별도 줄로 내린다.
    텍스트는 내부 라벨로 그린다 (버튼 텍스트는 세로 중앙 고정이라 2줄 불가).
    """

    def __init__(
        self, name: str, is_current: bool, warning: str = "", parent=None
    ) -> None:
        super().__init__("", parent)
        self._name = name
        self._is_current = is_current
        self._warning = warning
        self.setFixedHeight(44 if warning else 28)
        self.setCursor(
            Qt.CursorShape.ArrowCursor if is_current
            else Qt.CursorShape.PointingHandCursor
        )
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setToolTip(name)

        name_lbl = QLabel(name)
        name_lbl.setStyleSheet(
            f"color: {ACCENT_INTER}; font-size: {FONT_MD}px; "
            f"font-weight: {FW_SEMI}; background: transparent;"
            if is_current else
            f"color: {TEXT_SECONDARY}; font-size: {FONT_MD}px; "
            f"background: transparent;"
        )
        name_lbl.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed
        )
        name_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        body = QVBoxLayout(self)
        body.setContentsMargins(10 if is_current else 13, 3, 10, 3)
        body.setSpacing(0)
        body.addStretch()
        body.addWidget(name_lbl)
        if warning:
            warn_lbl = QLabel(warning)
            warn_lbl.setStyleSheet(
                f"color: {AMBER}; font-size: 10px; background: transparent;"
            )
            warn_lbl.setSizePolicy(
                QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed
            )
            warn_lbl.setAttribute(
                Qt.WidgetAttribute.WA_TransparentForMouseEvents
            )
            body.addWidget(warn_lbl)
        body.addStretch()

        if is_current:
            self.setStyleSheet(
                f"QPushButton {{ background: {SURFACE_SUBTLE}; border: none; "
                f"border-left: 3px solid {ACCENT_INTER}; "
                f"border-radius: {RADIUS_SM}px; }}"
            )
        else:
            self.setStyleSheet(
                f"QPushButton {{ background: transparent; border: none; "
                f"border-radius: {RADIUS_SM}px; }}"
                f"QPushButton:hover {{ background: {SURFACE_SUBTLE}; }}"
            )


class _LibrarySongSwitcher(QWidget):
    """단독 곡 편집 좌측의 곡 전환 목록.

    라이브러리 페이지로 돌아가지 않고 다른 곡을 바로 연다. 클릭 시
    song_open_requested(폴더 경로)를 발신 — 저장 확인은 기존
    _open_song_by_path 경로가 처리한다.
    """

    song_open_requested = Signal(str)
    collapse_toggled = Signal(bool)

    def __init__(
        self, library_dir: Path, current_name: str,
        collapsed: bool = False, search_text: str = "", parent=None,
    ) -> None:
        super().__init__(parent)
        self._library_dir = library_dir
        self._current_name = current_name
        self._rows: list[_SwitcherRow] = []
        self._collapsed = collapsed
        self._setup_ui()
        self._populate()
        if search_text:
            self._search.setText(search_text)  # textChanged → _filter
        self._apply_collapsed()
        # 곡 전환으로 재생성되면 스크롤이 맨 위로 리셋됨 — 레이아웃 반영 후
        # 현재 곡 행이 보이게 스크롤. receiver=self로 위젯 파괴 시 콜백도
        # 함께 사라진다 (재생성 직후 죽은 행 접근 방지).
        QTimer.singleShot(0, self, self._scroll_to_current)

    def _scroll_to_current(self, attempt: int = 0) -> None:
        row = next(
            (r for r in self._rows if r._is_current and not r.isHidden()),
            None,
        )
        if row is None:
            return
        # 첫 페인트 전에 스크롤을 끝내야 '맨 위였다가 점프'하는 깜빡임이
        # 없다. 표시 전엔 행들이 아직 (0,0)이므로 레이아웃을 강제 확정한
        # 뒤, 현재 곡이 가운데 오도록 스크롤바 값을 직접 계산한다
        # (ensureWidgetVisible의 최소 스크롤은 행을 하단 끝에 붙인다).
        self._list_layout.activate()
        viewport_h = self._list_scroll.viewport().height() or 220
        target = max(0, row.pos().y() - (viewport_h - row.height()) // 2)
        bar = self._list_scroll.verticalScrollBar()
        if bar.maximum() == 0 and target > 0 and attempt < 10:
            # 스크롤 범위가 아직 안 잡힘 — 잡힌 뒤 재시도
            QTimer.singleShot(
                30, self, lambda: self._scroll_to_current(attempt + 1)
            )
            return
        bar.setValue(target)  # 범위를 넘으면 Qt가 클램프

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(4)

        self._header_btn = QPushButton("곡 전환")
        self._header_btn.setFixedHeight(26)
        self._header_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._header_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._header_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; text-align: left; "
            f"padding: 0 2px; border: none; color: {TEXT_TERTIARY}; "
            f"font-size: {FONT_SM}px; font-weight: {FW_SEMI}; }}"
            f"QPushButton:hover {{ color: {TEXT_SECONDARY}; }}"
        )
        self._header_btn.clicked.connect(self._toggle_collapsed)
        root.addWidget(self._header_btn)

        self._body = QWidget()
        body = QVBoxLayout(self._body)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(4)

        self._search = QLineEdit()
        self._search.setPlaceholderText("곡 검색...")
        self._search.setFixedHeight(30)
        self._search.setStyleSheet(
            f"QLineEdit {{ background: {BG_INPUT}; color: {TEXT_PRIMARY}; "
            f"border: 1px solid {BORDER}; border-radius: {RADIUS_MD}px; "
            f"padding: 0 8px; font-size: {FONT_SM}px; }}"
            f"QLineEdit:focus {{ border-color: {ACCENT}; }}"
        )
        self._search.textChanged.connect(self._filter)
        body.addWidget(self._search)

        self._list_scroll = QScrollArea()
        self._list_scroll.setWidgetResizable(True)
        self._list_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._list_scroll.setMaximumHeight(220)
        self._list_scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
        )
        self._list_container = QWidget()
        self._list_container.setStyleSheet("background: transparent;")
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(2)
        self._list_layout.addStretch()
        self._list_scroll.setWidget(self._list_container)
        body.addWidget(self._list_scroll)

        root.addWidget(self._body)

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background: {BORDER_SUBTLE_RGBA}; border: none;")
        root.addWidget(divider)

    def _populate(self) -> None:
        try:
            folders = sorted(
                d for d in self._library_dir.iterdir()
                if d.is_dir() and (d / "song.json").exists()
            )
        except OSError:
            folders = []
        for d in folders:
            st = _scan_library_song(d)
            warning = " · ".join(
                _completeness_warnings(
                    st["sheet_count"],
                    st["has_ppt"] or st["has_md"],
                    st["mapped_hotspots"],
                )
            )
            row = _SwitcherRow(d.name, d.name == self._current_name, warning)
            if not row._is_current:
                row.clicked.connect(
                    lambda _c=False, path=str(d): self.song_open_requested.emit(
                        path
                    )
                )
            self._rows.append(row)
            self._list_layout.insertWidget(self._list_layout.count() - 1, row)

    def _filter(self, query: str) -> None:
        q = query.strip().lower()
        for row in self._rows:
            row.setVisible(not q or q in row._name.lower())

    def _toggle_collapsed(self) -> None:
        self._collapsed = not self._collapsed
        self._apply_collapsed()
        self.collapse_toggled.emit(self._collapsed)

    def _apply_collapsed(self) -> None:
        self._body.setVisible(not self._collapsed)
        arrow = "▸" if self._collapsed else "▾"
        self._header_btn.setText(f"{arrow}  곡 전환")


class _StandalonePanel(QWidget):
    """단독 곡 편집 모드 전용 — 시트 페이지 탭 목록."""

    sheet_selected = Signal(object)     # ScoreSheet
    sheet_rename_requested = Signal(object)     # ScoreSheet
    sheet_move_requested = Signal(object, int)  # (ScoreSheet, delta)
    sheet_delete_requested = Signal(object)     # ScoreSheet
    sheet_clear_mappings_requested = Signal(object)  # ScoreSheet
    sheet_move_mode_requested = Signal(object)  # ScoreSheet
    add_sheet_requested = Signal()
    edit_markdown_requested = Signal()
    open_ppt_requested = Signal()
    import_ppt_requested = Signal()
    open_folder_requested = Signal()

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
            f"font-size: {FONT_TITLE}px; font-weight: {FW_SEMI}; color: {TEXT_PRIMARY};"
        )
        layout.addWidget(self._song_name)

        # 페이지 카드 컨테이너
        self._pages_layout = QVBoxLayout()
        self._pages_layout.setSpacing(4)
        layout.addLayout(self._pages_layout)

        layout.addStretch()

        # 페이지 카드(P1, P2…)와 동작 버튼 그룹 시각적 분리
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setFixedHeight(1)
        divider.setStyleSheet(
            f"background: {BORDER_SUBTLE_RGBA}; border: none;"
        )
        layout.addWidget(divider)
        layout.addSpacing(SP_SM)

        from flow.ui.icons import icon_qicon
        from PySide6.QtCore import QSize
        _icon_size = QSize(16, 16)
        # 텍스트 길이가 달라도 아이콘 위치를 통일하기 위한 좌측 정렬 + 일정 padding.
        _icon_btn_qss = "QPushButton { text-align: left; padding-left: 14px; }"

        # PPT 편집 — 글로벌 ghost 스타일 사용
        self._btn_open_ppt = QPushButton("PPT 편집")
        self._btn_open_ppt.setIcon(icon_qicon("slideshow", size=16, color=TEXT_PRIMARY))
        self._btn_open_ppt.setIconSize(_icon_size)
        self._btn_open_ppt.setFixedHeight(34)
        self._btn_open_ppt.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_open_ppt.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_open_ppt.setStyleSheet(_icon_btn_qss)
        self._btn_open_ppt.setToolTip(
            "이 곡의 slides.pptx를 기본 프로그램(PowerPoint 등)으로 엽니다"
        )
        self._btn_open_ppt.clicked.connect(self.open_ppt_requested.emit)
        layout.addWidget(self._btn_open_ppt)

        # PPT 가져오기 — 외부 .pptx를 곡 폴더의 slides.pptx로 복사
        self._btn_import_ppt = QPushButton("PPT 가져오기")
        self._btn_import_ppt.setIcon(
            icon_qicon("slideshow", size=16, color=TEXT_PRIMARY)
        )
        self._btn_import_ppt.setIconSize(_icon_size)
        self._btn_import_ppt.setFixedHeight(34)
        self._btn_import_ppt.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_import_ppt.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_import_ppt.setStyleSheet(_icon_btn_qss)
        self._btn_import_ppt.setToolTip(
            "외부에서 만든 .pptx 파일을 이 곡의 슬라이드(slides.pptx)로 가져옵니다"
        )
        self._btn_import_ppt.clicked.connect(self.import_ppt_requested.emit)
        layout.addWidget(self._btn_import_ppt)

        # 마크다운 편집 — 인앱 에디터로 slides.md 편집
        self._btn_edit_md = QPushButton("마크다운 편집")
        self._btn_edit_md.setIcon(icon_qicon("edit_note", size=16, color=TEXT_PRIMARY))
        self._btn_edit_md.setIconSize(_icon_size)
        self._btn_edit_md.setFixedHeight(34)
        self._btn_edit_md.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_edit_md.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_edit_md.setStyleSheet(_icon_btn_qss)
        self._btn_edit_md.setToolTip(
            "이 곡의 slides.md를 인앱 에디터로 편집합니다 (없으면 생성)"
        )
        self._btn_edit_md.clicked.connect(self.edit_markdown_requested.emit)
        layout.addWidget(self._btn_edit_md)

        # 곡 폴더 열기 — OS 파일 관리자
        self._btn_open_folder = QPushButton("곡 폴더 열기")
        self._btn_open_folder.setIcon(
            icon_qicon("folder_open", size=16, color=TEXT_PRIMARY)
        )
        self._btn_open_folder.setIconSize(_icon_size)
        self._btn_open_folder.setFixedHeight(34)
        self._btn_open_folder.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_open_folder.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_open_folder.setStyleSheet(_icon_btn_qss)
        self._btn_open_folder.setToolTip(
            "이 곡의 폴더를 OS 파일 관리자에서 엽니다"
        )
        self._btn_open_folder.clicked.connect(self.open_folder_requested.emit)
        layout.addWidget(self._btn_open_folder)

        # 악보 이미지 추가 버튼 — 패널 내 Primary CTA
        self._btn_add = QPushButton("＋  악보 이미지 추가")
        self._btn_add.setFixedHeight(34)
        self._btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_add.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_add.setProperty("variant", "primary")
        self._btn_add.clicked.connect(self.add_sheet_requested.emit)
        layout.addWidget(self._btn_add)

        # 곡 폴더 경로 표시 (가장 하단, tertiary 텍스트)
        self._path_label = QLabel("")
        self._path_label.setStyleSheet(
            f"color: {TEXT_TERTIARY}; font-size: 10px; padding-top: 6px;"
        )
        self._path_label.setWordWrap(True)
        self._path_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(self._path_label)

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
            self._path_label.setText("")
            return

        self._song_name.setText(self._song.name)
        try:
            self._path_label.setText(str(self._song.abs_folder))
        except Exception:
            self._path_label.setText("")
        valid_sheets = [s for s in self._song.score_sheets if s.image_path]

        for i, sheet in enumerate(valid_sheets):
            card = _PageCard(sheet, i + 1, sheet.id == self._current_sheet_id)
            card.selected.connect(self.sheet_selected.emit)
            card.rename_requested.connect(self.sheet_rename_requested.emit)
            card.move_requested.connect(self.sheet_move_requested.emit)
            card.delete_requested.connect(self.sheet_delete_requested.emit)
            card.clear_mappings_requested.connect(
                self.sheet_clear_mappings_requested.emit
            )
            card.move_mode_requested.connect(self.sheet_move_mode_requested.emit)
            self._pages_layout.addWidget(card)

        if not valid_sheets:
            empty = QLabel("악보 이미지를 추가해 주세요")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet("font-size: 11px; color: #555; padding: 12px 0;")
            self._pages_layout.addWidget(empty)


class _PageCard(QFrame):
    """단독 모드에서 시트 페이지를 나타내는 작은 카드."""

    selected = Signal(object)          # ScoreSheet
    rename_requested = Signal(object)  # ScoreSheet
    move_requested = Signal(object, int)  # (ScoreSheet, -1=위/+1=아래)
    delete_requested = Signal(object)  # ScoreSheet
    clear_mappings_requested = Signal(object)  # ScoreSheet
    move_mode_requested = Signal(object)  # ScoreSheet (방향키 이동 모드)

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
        # 페이지 번호 배지 — active일 때 ACCENT_INTER 텍스트 + 미묘한 white-overlay
        badge.setStyleSheet(
            f"background: {SURFACE_SUBTLE}; color: {ACCENT_INTER}; "
            f"border-radius: 13px; font-size: 10px; font-weight: {FW_SEMI};"
            if active else
            f"background: {SURFACE_GHOST}; color: {TEXT_TERTIARY}; "
            f"border-radius: 13px; font-size: 10px; font-weight: {FW_MEDIUM};"
        )
        layout.addWidget(badge)

        name_lbl = QLabel(self._sheet.name)
        name_lbl.setStyleSheet(
            f"font-size: {FONT_MD}px; color: {TEXT_PRIMARY}; font-weight: {FW_MEDIUM};"
            if active else
            f"font-size: {FONT_MD}px; color: {TEXT_SECONDARY};"
        )
        layout.addWidget(name_lbl, 1)

        # active 상태: 좌측 액센트 바 + 미묘한 white-overlay (Linear 패턴)
        if active:
            self.setStyleSheet(
                f"QFrame#PageCard {{ "
                f"background: {SURFACE_SUBTLE}; "
                f"border: 1px solid {BORDER_STANDARD_RGBA}; "
                f"border-left: 3px solid {ACCENT_INTER}; "
                f"border-radius: {RADIUS_MD}px; }}"
            )
        else:
            self.setStyleSheet(
                f"QFrame#PageCard {{ "
                f"background: {SURFACE_GHOST}; "
                f"border: 1px solid {BORDER_SUBTLE_RGBA}; "
                f"border-radius: {RADIUS_MD}px; }}"
                f"QFrame#PageCard:hover {{ "
                f"background: {SURFACE_SUBTLE}; "
                f"border-color: {BORDER_STANDARD_RGBA}; }}"
            )

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.selected.emit(self._sheet)
        super().mousePressEvent(event)

    def contextMenuEvent(self, event) -> None:
        self._build_context_menu().exec(event.globalPos())

    def _build_context_menu(self) -> QMenu:
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{ background: {BG_ELEVATED}; color: {TEXT_PRIMARY}; border: 1px solid {BORDER_FOCUS}; border-radius: {RADIUS_MD}px; }}
            QMenu::item {{ padding: {SP_SM}px {SP_LG}px; font-size: {FONT_MD}px; }}
            QMenu::item:selected {{ background: {ACCENT_MUTED}; color: {ACCENT}; }}
            QMenu::separator {{ height: 1px; background: {BORDER}; margin: 4px 0; }}
        """)

        rename_act = QAction("이름 변경", self)
        rename_act.triggered.connect(lambda: self.rename_requested.emit(self._sheet))
        menu.addAction(rename_act)

        move_mode_act = QAction("위치 이동", self)
        move_mode_act.triggered.connect(
            lambda: self.move_mode_requested.emit(self._sheet)
        )
        menu.addAction(move_mode_act)

        up_act = QAction("위로 이동", self)
        up_act.triggered.connect(lambda: self.move_requested.emit(self._sheet, -1))
        menu.addAction(up_act)

        down_act = QAction("아래로 이동", self)
        down_act.triggered.connect(lambda: self.move_requested.emit(self._sheet, 1))
        menu.addAction(down_act)

        menu.addSeparator()
        clear_map_act = QAction("모든 매핑 해제", self)
        clear_map_act.triggered.connect(
            lambda: self.clear_mappings_requested.emit(self._sheet)
        )
        menu.addAction(clear_map_act)

        menu.addSeparator()
        delete_act = QAction("삭제", self)
        delete_act.triggered.connect(lambda: self.delete_requested.emit(self._sheet))
        menu.addAction(delete_act)

        return menu


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
    song_open_requested = Signal(str)    # 단독 편집: 다른 라이브러리 곡 열기

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._project: Project | None = None
        self._main_window = None
        self._editable = True
        self._is_standalone = False
        self._cards: list[_SongCard] = []
        self._standalone_panel: _StandalonePanel | None = None
        # 위치 이동 모드: {"kind": "sheet"|"song", "obj": ..., "start": int}
        self._move_mode: dict | None = None
        self._song_switcher: _LibrarySongSwitcher | None = None
        self._switcher_collapsed = False  # 세션 내 접힘 상태 유지
        self._switcher_search = ""  # 곡 전환 시 검색어 유지
        self._setup_ui()

    # ── UI 구성 ──────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        self.setStyleSheet(f"background: {BG_SURFACE};")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── 헤더 — Linear-style 슬림 (40px) + 헤어라인 separator
        header_frame = QFrame()
        header_frame.setFixedHeight(40)
        header_frame.setStyleSheet(
            f"background: {BG_SURFACE}; "
            f"border-bottom: 1px solid {BORDER_SUBTLE_RGBA};"
        )
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(SP_MD, 0, SP_SM, 0)
        header_layout.setSpacing(SP_XS + 2)

        from flow.ui.icons import icon_label
        self._title_icon = icon_label("view_list", 16, TEXT_SECONDARY, header_frame)
        header_layout.addWidget(self._title_icon)

        self._title_label = QLabel("셋리스트")
        self._title_label.setStyleSheet(
            f"font-size: {FONT_LG}px; font-weight: {FW_SEMI}; color: {TEXT_PRIMARY};"
        )
        header_layout.addWidget(self._title_label)

        self._count_label = QLabel()
        self._count_label.setStyleSheet(f"font-size: {FONT_SM}px; color: {TEXT_TERTIARY};")
        header_layout.addWidget(self._count_label)
        header_layout.addStretch()

        root.addWidget(header_frame)

        # ── 스크롤 영역 (카드 목록)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet(f"""
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
        self._cards_layout.setContentsMargins(SP_XS, SP_XS, SP_XS, SP_XS)
        self._cards_layout.setSpacing(4)
        self._cards_layout.addStretch()

        self._scroll.setWidget(self._cards_widget)
        root.addWidget(self._scroll, 1)

        # ── 하단 액션 버튼
        self._footer = QFrame()
        self._footer.setStyleSheet(
            f"background: {BG_SURFACE}; border-top: 1px solid {BORDER};"
        )
        footer_layout = QVBoxLayout(self._footer)
        footer_layout.setContentsMargins(8, 8, 8, 8)
        footer_layout.setSpacing(6)

        self._btn_add_lib = QPushButton("＋  라이브러리에서 추가")
        self._btn_add_lib.setFixedHeight(34)
        self._btn_add_lib.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_add_lib.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_add_lib.setStyleSheet(f"""
            QPushButton {{
                background: {ACCENT}; color: #fff;
                border: none; border-radius: {RADIUS_MD}px;
                font-size: {FONT_SM}px;
            }}
            QPushButton:hover {{ background: {ACCENT_HOVER}; }}
            QPushButton:disabled {{ background: {BG_HOVER}; color: {TEXT_TERTIARY}; }}
        """)
        self._btn_add_lib.clicked.connect(self._on_add_clicked)
        footer_layout.addWidget(self._btn_add_lib)

        self._btn_new_song = QPushButton("새 곡 만들기")
        self._btn_new_song.setFixedHeight(30)
        self._btn_new_song.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_new_song.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_new_song.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {TEXT_TERTIARY};
                border: 1px solid {BORDER}; border-radius: {RADIUS_MD}px;
                font-size: {FONT_SM}px;
            }}
            QPushButton:hover {{ background: {BG_HOVER}; color: {TEXT_SECONDARY}; border-color: {BORDER_FOCUS}; }}
            QPushButton:disabled {{ color: {TEXT_TERTIARY}; border-color: {BORDER}; }}
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
        from flow.ui.icons import icon, icon_font
        self._is_standalone = standalone
        if standalone:
            self._title_label.setText("곡 편집")
            self._title_icon.setFont(icon_font(16))
            self._title_icon.setText(icon("edit"))
            self._footer.setVisible(False)
        else:
            self._title_label.setText("셋리스트")
            self._title_icon.setFont(icon_font(16))
            self._title_icon.setText(icon("view_list"))
            self._title_label.setStyleSheet(
                f"font-size: {FONT_LG}px; font-weight: {FW_SEMI}; color: {TEXT_PRIMARY};"
            )
            self._footer.setVisible(True)

    def set_project(self, project: Project | None) -> None:
        self._project = project
        self.refresh_list()

    def set_editable(self, editable: bool) -> None:
        self._editable = editable
        # 라이브 중에도 "라이브러리에서 추가"는 허용 (좌측 패널로 열림)
        self._btn_add_lib.setEnabled(True)
        self._btn_new_song.setEnabled(editable)
        # 카드별 편집 버튼도 상태 반영 (라이브 중 편집 진입 차단)
        for card in self._cards:
            btn_edit = getattr(card, "_btn_edit", None)
            if btn_edit is not None:
                btn_edit.setEnabled(editable)
                btn_edit.setToolTip(
                    "" if editable else "라이브 모드 중에는 편집할 수 없습니다"
                )

    def _on_switcher_collapse(self, collapsed: bool) -> None:
        self._switcher_collapsed = collapsed

    # ── 위치 이동 모드 (방향키) ──────────────────────────────────────────

    def _move_mode_items(self) -> list | None:
        if not self._move_mode or not self._project:
            return None
        if self._move_mode["kind"] == "song":
            return self._project.selected_songs
        song = self._find_song_of_sheet(self._move_mode["obj"])
        return song.score_sheets if song else None

    def _enter_move_mode(self, kind: str, obj) -> None:
        """우클릭 '위치 이동' 진입: ↑↓ 이동, Enter 확정, Esc 취소."""
        if getattr(self._main_window, "_is_live", False):
            return
        if self._move_mode:
            self._exit_move_mode(confirm=True)
        self._move_mode = {"kind": kind, "obj": obj, "start": -1}
        items = self._move_mode_items()
        idx = (
            next((i for i, x in enumerate(items) if x is obj), None)
            if items is not None
            else None
        )
        if idx is None:
            self._move_mode = None
            return
        self._move_mode["start"] = idx

        self.grabKeyboard()
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)  # 바깥 클릭 = 확정
        self.refresh_list()
        self._show_move_hint("위치 이동: ↑↓ 이동 · Enter 확정 · Esc 취소")

    def _show_move_hint(self, msg: str) -> None:
        status_fn = getattr(self._main_window, "statusBar", None)
        if callable(status_fn):
            try:
                status_fn().showMessage(msg, 0 if msg else 1)
            except Exception:
                pass

    def _shift_moving(self, delta: int) -> None:
        items = self._move_mode_items()
        if items is None:
            return
        obj = self._move_mode["obj"]
        i = next((k for k, x in enumerate(items) if x is obj), None)
        if i is None:
            return
        j = i + delta
        if not (0 <= j < len(items)):
            return
        items[i], items[j] = items[j], items[i]
        self.refresh_list()

    def _exit_move_mode(self, confirm: bool) -> None:
        mm = self._move_mode
        if not mm:
            return
        self._move_mode = None
        self.releaseKeyboard()
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
        self._show_move_hint("")

        items = (
            self._project.selected_songs
            if mm["kind"] == "song"
            else (
                self._find_song_of_sheet(mm["obj"]).score_sheets
                if self._find_song_of_sheet(mm["obj"])
                else None
            )
        )
        if items is None:
            self.refresh_list()
            return
        obj = mm["obj"]
        cur = next((k for k, x in enumerate(items) if x is obj), None)

        if cur is None or cur == mm["start"]:
            self.refresh_list()
            return

        if not confirm:
            # 취소: 원위치 복귀
            items.pop(cur)
            items.insert(mm["start"], obj)
            self.refresh_list()
            return

        # 확정: 영속화
        if mm["kind"] == "song":
            self._project.song_order = [s.name for s in items]
            if self._main_window:
                self._main_window._on_songs_changed()
        else:
            self.refresh_list()
            if self._main_window:
                self._main_window._mark_dirty()

    def keyPressEvent(self, event) -> None:
        if self._move_mode:
            key = event.key()
            if key == Qt.Key.Key_Up:
                self._shift_moving(-1)
            elif key == Qt.Key.Key_Down:
                self._shift_moving(1)
            elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._exit_move_mode(confirm=True)
            elif key == Qt.Key.Key_Escape:
                self._exit_move_mode(confirm=False)
            event.accept()
            return
        super().keyPressEvent(event)

    def eventFilter(self, watched, event) -> bool:
        # 이동 모드 중 아무 곳이나 마우스 클릭 = 확정 종료
        if self._move_mode and event.type() == QEvent.Type.MouseButtonPress:
            self._exit_move_mode(confirm=True)
        return super().eventFilter(watched, event)

    def _apply_move_mode_visuals(self) -> None:
        """이동 중인 카드는 강조, 나머지는 비활성+흐림."""
        if not self._move_mode:
            return
        from PySide6.QtWidgets import QGraphicsOpacityEffect

        def mark(card, is_moving: bool) -> None:
            if is_moving:
                card.setStyleSheet(
                    card.styleSheet()
                    + f"QFrame#SongCard, QFrame#PageCard {{"
                    f" border: 2px solid {ACCENT}; }}"
                )
            else:
                card.setEnabled(False)
                eff = QGraphicsOpacityEffect(card)
                eff.setOpacity(0.35)
                card.setGraphicsEffect(eff)

        obj = self._move_mode["obj"]
        if self._move_mode["kind"] == "song":
            for card in self._cards:
                mark(card, card._song is obj)
        elif self._standalone_panel is not None:
            layout = self._standalone_panel._pages_layout
            for i in range(layout.count()):
                w = layout.itemAt(i).widget()
                if isinstance(w, _PageCard):
                    mark(w, w._sheet is obj)

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
        if self._song_switcher:
            self._switcher_search = self._song_switcher._search.text()
            self._cards_layout.removeWidget(self._song_switcher)
            self._song_switcher.deleteLater()
            self._song_switcher = None

        if not self._project:
            self._count_label.setText("")
            return

        if self._is_standalone:
            self._refresh_standalone()
        else:
            self._refresh_project()

        self._apply_move_mode_visuals()

    def _refresh_standalone(self) -> None:
        """단독 곡 편집 모드: 시트 페이지 패널."""
        song = (
            self._project.selected_songs[0]
            if self._project.selected_songs
            else None
        )
        current_sheet = self._project.get_current_score_sheet()
        current_id = current_sheet.id if current_sheet else None

        # 곡 전환 목록 — 라이브러리로 돌아가지 않고 다른 곡을 바로 연다
        workspace = getattr(self._main_window, "_workspace", None)
        if workspace is not None and song is not None:
            # 현재 곡 매칭은 폴더명 기준 — song.name(표시 이름)은 폴더명과
            # 다를 수 있다 (워크스페이스 곡 정체성 = 폴더명)
            project_path = getattr(self._main_window, "_project_path", None)
            current_folder = Path(project_path).name if project_path else song.name
            self._song_switcher = _LibrarySongSwitcher(
                workspace.library_dir,
                current_folder,
                collapsed=self._switcher_collapsed,
                search_text=self._switcher_search,
            )
            self._song_switcher.song_open_requested.connect(
                self.song_open_requested.emit
            )
            self._song_switcher.collapse_toggled.connect(
                self._on_switcher_collapse
            )
            self._cards_layout.insertWidget(
                self._cards_layout.count() - 1, self._song_switcher
            )

        panel = _StandalonePanel()
        panel.set_song(song, current_id)
        panel.sheet_selected.connect(self._on_sheet_selected_direct)
        panel.sheet_rename_requested.connect(self._rename_sheet)
        panel.sheet_move_requested.connect(self._move_sheet)
        panel.sheet_delete_requested.connect(self._delete_sheet)
        panel.sheet_clear_mappings_requested.connect(self._clear_sheet_mappings)
        panel.sheet_move_mode_requested.connect(
            lambda sheet: self._enter_move_mode("sheet", sheet)
        )
        panel.add_sheet_requested.connect(self._on_add_sheet_clicked)
        panel.open_ppt_requested.connect(self._on_open_ppt_clicked)
        panel.import_ppt_requested.connect(self._on_import_ppt_clicked)
        panel.edit_markdown_requested.connect(self._on_edit_markdown_clicked)
        panel.open_folder_requested.connect(self._on_open_folder_clicked)

        # PPT/마크다운 상호 배타: 곡 폴더에 실제로 있는 형식만 활성화.
        # 한쪽이 있는 곡에 다른 형식 버튼을 누르면 새 파일이 생성되며 기존
        # 형식을 덮어쓰는 사고가 일어날 수 있어 둘 다 disabled로 명시한다.
        if song is not None:
            panel._btn_open_ppt.setEnabled(song.has_slides)
            if not song.has_slides:
                panel._btn_open_ppt.setToolTip(
                    "이 곡은 PPT가 없습니다 (마크다운 곡)."
                )
            panel._btn_edit_md.setEnabled(not (song.has_slides and not song.has_markdown))
            if song.has_slides and not song.has_markdown:
                panel._btn_edit_md.setToolTip(
                    "이 곡은 PPT 슬라이드를 사용합니다. 마크다운으로 전환하려면 PPT를 먼저 제거하세요."
                )
            panel._btn_import_ppt.setEnabled(not song.has_markdown)
            if song.has_markdown:
                panel._btn_import_ppt.setToolTip(
                    "이 곡은 마크다운 슬라이드를 사용합니다. "
                    "PPT로 전환하려면 slides.md를 먼저 제거하세요."
                )
        else:
            panel._btn_open_ppt.setEnabled(False)
            panel._btn_import_ppt.setEnabled(False)
            panel._btn_edit_md.setEnabled(False)

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
            card.import_ppt_requested.connect(self._import_ppt_to_song)
            card.move_requested.connect(self._move_song)
            card.move_mode_requested.connect(
                lambda song: self._enter_move_mode("song", song)
            )
            card.toggle_sheet_names_requested.connect(self._toggle_sheet_names)

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

        selected_card = None
        for card in self._cards:
            song_sheet_ids = {s.id for s in card._song.score_sheets}
            is_selected = sheet_id in song_sheet_ids
            card.set_selected(is_selected, sheet_id if is_selected else None)
            if is_selected:
                selected_card = card

        # 방향키 곡 전환 시 선택 카드가 스크롤 밖에 숨지 않게. 선택하면
        # 시트 탭이 펼쳐져 카드 높이가 바뀌므로 레이아웃 반영 후 스크롤.
        if selected_card is not None:
            QTimer.singleShot(
                0,
                lambda c=selected_card: self._scroll.ensureWidgetVisible(c, 0, 8),
            )

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
        """라이브러리 브라우저 다이얼로그를 열어 곡 추가."""
        if not self._project or not self._main_window:
            return
        if getattr(self._main_window, "_is_live", False):
            self._main_window._open_live_song_add_panel()
            return

        project_dir = self._main_window._project_path.parent
        songs_dir = project_dir / "songs"
        if not songs_dir.exists():
            songs_dir.mkdir(parents=True, exist_ok=True)

        included = {s.name for s in self._project.selected_songs}
        workspace = getattr(self._main_window, "_workspace", None)

        dlg = SongLibraryDialog(songs_dir, included, self, workspace=workspace)
        dlg.song_chosen.connect(self._add_existing_song)
        dlg.exec()

    def _add_existing_song(
        self, name: str, source: str = "local", reload_slides: bool = True
    ) -> None:
        """라이브러리 다이얼로그에서 선택한 곡을 프로젝트에 추가.

        source = "library": workspace/library/{name}에서 참조로 로드
        source = "local": 필요하면 workspace/library → project/songs 복사 후 로드
        reload_slides: True면 _on_songs_changed로 슬라이드 미리보기를 즉시 갱신.
            라이브 중 추가는 송출 무중단을 위해 False로 호출(호출 측이 저장 처리).
        """
        if not self._project or not self._main_window:
            return

        project_dir = self._main_window._project_path.parent
        workspace = getattr(self._main_window, "_workspace", None)

        song = None
        if workspace is not None:
            if source == "local":
                # library/{name}이 있으면 project/songs/{name}으로 복사
                lib_src = workspace.library_song_dir(name)
                local_dst = project_dir / "songs" / name
                if lib_src.exists() and not local_dst.exists():
                    import shutil
                    shutil.copytree(lib_src, local_dst)

            # Song.load_from_workspace가 우선순위(local→library) 적용
            song = Song.load_from_workspace(workspace, project_dir.name, name)

        if song is None:
            # 폴백: 레거시 방식 (project/songs에서 직접 로드)
            song = self._load_song_from_folder(name, project_dir)

        if not song:
            QMessageBox.warning(self, "오류", f"'{name}' 곡을 불러올 수 없습니다.")
            return

        # 중복 가드 — 같은 곡이 두 번 들어가면 오프셋/매핑이 전부 꼬인다
        if any(s.name == song.name for s in self._project.selected_songs):
            self.refresh_list()
            return

        self._project.selected_songs.append(song)
        # song_order는 실제 Song.name과 일치해야 한다 (요청 폴더명이 아니라)
        if song.name not in self._project.song_order:
            self._project.song_order.append(song.name)
        self.refresh_list()
        if not self._main_window:
            return
        if reload_slides:
            # 저장 + 인덱스 로컬화 + load_songs로 슬라이드 미리보기를 즉시 갱신
            # (재열기 없이도 새 곡 슬라이드가 보이도록).
            self._main_window._on_songs_changed()
        else:
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

            # 슬라이드 형식 선택 (마크다운 / PPT)
            from flow.ui.dialogs import flow_question

            use_markdown = flow_question(
                self,
                "슬라이드 형식 선택",
                "새 곡 슬라이드를 어떤 형식으로 시작할까요?\n\n"
                "• 마크다운: 텍스트로 가사를 적으면 Flow가 슬라이드로 자동 변환\n"
                "• PowerPoint: 외부 도구로 만든 .pptx 가져오기",
                yes_text="마크다운",
                no_text="PowerPoint",
            )

            if use_markdown:
                template = (
                    "---\n"
                    "main_size: 56\n"
                    "sub_size: 18\n"
                    "background: \"#000000\"\n"
                    "---\n"
                    "\n"
                    f"# {song.name}\n"
                    "\n"
                    "## 1절\n"
                    "\n"
                    "첫 슬라이드 가사\n"
                )
                song.markdown_path.write_text(template, encoding="utf-8")
                self._open_markdown_editor(song)
            # else: PPT — 사용자가 외부 도구로 .pptx 생성 또는 'PPT 가져오기' 사용
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

    def _on_edit_markdown_clicked(self) -> None:
        """단독 곡 편집 모드: 이 곡의 slides.md를 인앱 에디터로 편집.

        파일이 없으면 starter 템플릿을 생성한 뒤 띄움.
        """
        if not self._project or not self._project.selected_songs:
            return
        song = self._project.selected_songs[0]

        if not song.markdown_path.exists():
            template = (
                "---\n"
                "main_size: 56\n"
                "sub_size: 18\n"
                "background: \"#000000\"\n"
                "---\n"
                "\n"
                f"# {song.name}\n"
                "\n"
                "## 1절\n"
                "\n"
                "첫 슬라이드 가사\n"
            )
            try:
                song.markdown_path.write_text(template, encoding="utf-8")
            except Exception as e:
                from flow.ui.dialogs import flow_warning
                flow_warning(
                    self, "오류", f"마크다운 파일 생성 실패:\n{e}"
                )
                return

        self._open_markdown_editor(song)

    def _on_open_folder_clicked(self) -> None:
        """단독 곡 편집 모드: 이 곡의 폴더를 OS 파일 관리자에서 열기."""
        if not self._project or not self._project.selected_songs:
            return
        song = self._project.selected_songs[0]
        folder = song.abs_folder
        if not folder.exists():
            from flow.ui.dialogs import flow_warning
            flow_warning(self, "폴더 없음", f"곡 폴더가 존재하지 않습니다:\n{folder}")
            return
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder))):
            from flow.ui.dialogs import flow_warning
            flow_warning(
                self,
                "열기 실패",
                f"폴더를 여는 데 실패했습니다:\n{folder}",
            )

    def _on_open_ppt_clicked(self) -> None:
        """단독 곡 편집 모드: 이 곡의 slides.pptx를 OS 기본 프로그램으로 열기.

        Windows에서 Flow는 백그라운드 PowerPoint COM으로 슬라이드를 변환하는데,
        사용자가 같은 PPT를 PowerPoint에서 직접 열면 파일 점유/COM 경합으로
        파워포인트가 튕기거나 저장에 실패할 수 있음. 대응:
          1) 진행 중인 슬라이드 변환 작업 중단 (stop_workers)
          2) 편집 워크플로우 안내 다이얼로그 (Cancel 가능)
        """
        if not self._project or not self._project.selected_songs:
            return
        song = self._project.selected_songs[0]

        pptx_path = song.abs_slides_path
        from flow.ui.dialogs import flow_warning, flow_question
        if not pptx_path.exists():
            flow_warning(
                self,
                "PPT 없음",
                f"이 곡에 연결된 PPT 파일이 없습니다.\n"
                f"'곡 폴더 열기'로 폴더를 연 뒤 slides.pptx를 추가하세요.\n\n{pptx_path}",
            )
            return

        ok = flow_question(
            self,
            "PPT 편집 열기",
            "이 곡의 PPT를 기본 프로그램(PowerPoint 등)으로 엽니다.\n\n"
            "Flow는 편집 중 자동 슬라이드 변환을 일시 중지합니다.\n\n"
            "권장 작업 순서:\n"
            "  1. PowerPoint에서 편집 후 저장\n"
            "  2. PowerPoint를 완전히 닫기\n"
            "  3. Flow로 돌아와서 슬라이드 패널의 '새로고침' 클릭",
            yes_text="PPT 열기", no_text="취소",
        )
        if not ok:
            return

        # 진행 중이거나 대기 중인 슬라이드 변환 작업 중단 + 파일 watcher 일시 중지
        # → PowerPoint가 저장하는 동안 자동 리로드로 인한 파일 락 충돌 방지.
        # 사용자가 PowerPoint를 닫고 슬라이드 패널의 '새로고침'을 누르면 재개됨.
        if self._main_window is not None:
            slide_manager = getattr(self._main_window, "_slide_manager", None)
            if slide_manager is not None:
                try:
                    slide_manager.pause_file_watching()
                except Exception:
                    pass

        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        url = QUrl.fromLocalFile(str(pptx_path))
        if not QDesktopServices.openUrl(url):
            QMessageBox.warning(
                self,
                "열기 실패",
                f"PPT 파일을 여는 데 실패했습니다:\n{pptx_path}",
            )

    def _move_song(self, song: Song, delta: int) -> None:
        """셋리스트 곡 순서 변경. 오프셋 재계산·저장은 _on_songs_changed가 담당."""
        if not self._project or not self._main_window:
            return
        if getattr(self._main_window, "_is_live", False):
            return
        songs = self._project.selected_songs
        i = next((idx for idx, s in enumerate(songs) if s is song), None)
        if i is None:
            return
        j = i + delta
        if not (0 <= j < len(songs)):
            return
        songs[i], songs[j] = songs[j], songs[i]
        self._project.song_order = [s.name for s in songs]
        self._main_window._on_songs_changed()

    def _toggle_sheet_names(self, song: Song) -> None:
        """셋리스트 탭의 P1, P2… ↔ 시트 이름 표시 토글 (곡별, song.json 저장)."""
        song.show_sheet_names = not song.show_sheet_names
        self.refresh_list()
        if self._main_window:
            self._main_window._mark_dirty()

    # ── 시트(페이지) 관리 ────────────────────────────────────────────────

    def _find_song_of_sheet(self, sheet: ScoreSheet) -> Song | None:
        if not self._project:
            return None
        for song in self._project.selected_songs:
            if any(s is sheet for s in song.score_sheets):
                return song
        return None

    def _rename_sheet(self, sheet: ScoreSheet) -> None:
        from flow.ui import dialogs

        new_name, ok = dialogs.flow_input_text(
            self,
            "시트 이름 변경",
            "새 이름을 입력하세요:",
            default=sheet.name,
        )
        new_name = new_name.strip()
        if not ok or not new_name or new_name == sheet.name:
            return
        sheet.name = new_name
        self.refresh_list()
        if self._main_window:
            self._main_window._mark_dirty()

    def _move_sheet(self, sheet: ScoreSheet, delta: int) -> None:
        song = self._find_song_of_sheet(sheet)
        if song is None:
            return
        sheets = song.score_sheets
        i = next(idx for idx, s in enumerate(sheets) if s is sheet)
        j = i + delta
        if not (0 <= j < len(sheets)):
            return
        sheets[i], sheets[j] = sheets[j], sheets[i]
        self.refresh_list()
        if self._main_window:
            self._main_window._mark_dirty()

    def _delete_sheet(self, sheet: ScoreSheet) -> None:
        from flow.ui import dialogs

        song = self._find_song_of_sheet(sheet)
        if song is None:
            return
        ok = dialogs.flow_question(
            self,
            "시트 삭제",
            f"'{sheet.name}' 시트를 삭제하시겠습니까?\n"
            "(이미지 파일은 삭제되지 않습니다)",
            yes_text="삭제",
            no_text="취소",
        )
        if not ok:
            return
        song.score_sheets = [s for s in song.score_sheets if s is not sheet]
        self.refresh_list()
        self.song_removed.emit(sheet.id)
        if self._main_window:
            self._main_window._mark_dirty()

    def _clear_sheet_mappings(self, sheet: ScoreSheet) -> None:
        """시트의 모든 핫스팟 매핑 일괄 해제 (Ctrl+Z 복구 가능)."""
        from flow.ui import dialogs

        if getattr(self._main_window, "_is_live", False):
            return
        mapped = sum(
            1
            for h in sheet.hotspots
            if h.slide_index >= 0
            or any(v >= 0 for v in h.slide_mappings.values())
        )
        if mapped == 0:
            dialogs.flow_warning(
                self, "매핑 없음", "이 시트에는 해제할 매핑이 없습니다."
            )
            return
        ok = dialogs.flow_question(
            self,
            "매핑 일괄 해제",
            f"'{sheet.name}' 시트의 핫스팟 {mapped}개에 걸린 매핑을 모두 "
            "해제하시겠습니까?\n(핫스팟 자체는 남고, Ctrl+Z로 되돌릴 수 있습니다)",
            yes_text="모두 해제",
            no_text="취소",
        )
        if not ok:
            return

        from flow.ui.undo_commands import ClearSheetMappingsCommand

        mw = self._main_window
        command = ClearSheetMappingsCommand(
            sheet,
            update_cb=lambda: (
                mw._canvas.update(),
                mw._update_mapped_slides_ui()
                if hasattr(mw, "_update_mapped_slides_ui")
                else None,
            ),
        )
        mw._undo_stack.push(command)
        mw._mark_dirty()

    def _on_import_ppt_clicked(self) -> None:
        """단독 곡 편집 모드: 이 곡에 외부 PPT 가져오기."""
        if not self._project or not self._project.selected_songs:
            return
        self._import_ppt_to_song(self._project.selected_songs[0])

    def _import_ppt_to_song(self, song: Song) -> None:
        """외부 .pptx를 곡 폴더의 slides.pptx로 복사하고 슬라이드 리로드."""
        import shutil

        from flow.ui import dialogs

        if getattr(self._main_window, "_is_live", False):
            dialogs.flow_warning(
                self,
                "라이브 모드",
                "라이브 송출 중에는 PPT를 가져올 수 없습니다.\n"
                "먼저 라이브 모드를 종료해 주세요(Esc).",
            )
            return

        # 마크다운이 있으면 PPT가 무시되므로(마크다운 우선) 조용한 실패 방지
        if song.has_markdown:
            dialogs.flow_warning(
                self,
                "마크다운 곡",
                "이 곡은 마크다운 슬라이드(slides.md)를 사용하고 있어\n"
                "PPT를 가져와도 표시되지 않습니다.\n\n"
                "PPT로 전환하려면 곡 폴더에서 slides.md를 먼저 제거하세요.",
            )
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            f"'{song.name}'에 가져올 PPT 파일 선택",
            "",
            "PowerPoint 파일 (*.pptx)",
        )
        if not file_path:
            return

        dest = song.abs_slides_path
        if dest.exists():
            ok = dialogs.flow_question(
                self,
                "파일 덮어쓰기",
                "이 곡에 이미 슬라이드 파일(slides.pptx)이 있습니다.\n"
                "선택한 파일로 덮어쓰시겠습니까?",
                yes_text="덮어쓰기",
                no_text="취소",
            )
            if not ok:
                return

        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file_path, dest)
        except shutil.SameFileError:
            pass
        except Exception as e:
            QMessageBox.warning(
                self, "가져오기 실패", f"PPT 파일을 가져오지 못했습니다: {e}"
            )
            return

        self.song_reload_requested.emit(song)
        self.refresh_list()

    def _open_markdown_editor(self, song) -> None:
        """markdown 곡 전용 인앱 에디터를 메인 윈도우 내부 화면으로 전환."""
        if self._main_window is not None and hasattr(
            self._main_window, "show_markdown_editor"
        ):
            self._main_window.show_markdown_editor(song)

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
            image_path=(rel_sheets / p_path.name).as_posix(),
        )
        song.score_sheets.append(new_sheet)
        self.refresh_list()
        self.select_sheet_by_id(new_sheet.id)
        if self._main_window:
            self._main_window._mark_dirty()

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
