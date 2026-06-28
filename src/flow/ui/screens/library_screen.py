"""Library screen — full list of all songs in the workspace library.

검색 + 정렬(가나다순/생성순) + 카드 클릭으로 곡 편집 진입.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from flow.ui.screens._browser_widgets import (
    SORT_NAME,
    BrowserToolbar,
    ItemCard,
    sort_paths,
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


class LibraryScreen(QWidget):
    """Workspace 의 library/ 안 모든 곡을 보여주는 페이지.

    Signals:
        song_selected(str): 곡 폴더 경로
        new_song_requested(): 새 곡 생성 요청
    """

    song_selected = Signal(str)
    new_song_requested = Signal()

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
            title="라이브러리",
            new_button_label="＋ 새 곡 만들기",
        )
        self._toolbar.new_clicked.connect(self.new_song_requested.emit)
        self._toolbar.search_changed.connect(self._on_search_changed)
        self._toolbar.sort_changed.connect(self._on_sort_changed)
        root.addWidget(self._toolbar)

        # Card scroll area
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

        # Empty state label
        self._empty_lbl = QLabel("이 워크스페이스에 곡이 없습니다.")
        self._empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_lbl.setStyleSheet(
            f"color: {TEXT_TERTIARY}; font-size: {FONT_MD}px; padding: 40px;"
        )
        self._empty_lbl.hide()
        root.addWidget(self._empty_lbl)

    def set_workspace(self, workspace) -> None:
        self._workspace = workspace
        self.refresh()

    def refresh(self) -> None:
        # Clear existing cards (everything before the trailing stretch)
        while self._cards_layout.count() > 1:
            item = self._cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if self._workspace is None:
            self._empty_lbl.setText("워크스페이스가 열려있지 않습니다.")
            self._empty_lbl.show()
            return

        paths = self._workspace.list_library_songs()
        snippets: dict[Path, str] = {}
        if self._search_text:
            from flow.services.markdown import lyric_snippet, read_song_lyrics

            q = self._search_text.lower()
            matched = []
            for p in paths:
                if q in p.name.lower():
                    matched.append(p)  # 제목 매칭 — 스니펫 없음
                    continue
                lyrics = read_song_lyrics(p)
                if q in lyrics.lower():
                    matched.append(p)
                    snippets[p] = lyric_snippet(lyrics, q)
            paths = matched

        paths = sort_paths(paths, self._sort_mode)

        if not paths:
            self._empty_lbl.setText(
                "이 워크스페이스에 곡이 없습니다." if not self._search_text
                else f"'{self._search_text}'와(과) 일치하는 곡이 없습니다."
            )
            self._empty_lbl.show()
            return
        self._empty_lbl.hide()

        for path in paths:
            subtitle = self._build_subtitle(path)
            card = ItemCard(
                path=str(path), title=path.name, subtitle=subtitle,
                match_snippet=snippets.get(path, ""),
            )
            card.clicked.connect(self.song_selected.emit)
            # Insert before the trailing stretch
            self._cards_layout.insertWidget(self._cards_layout.count() - 1, card)

    def _build_subtitle(self, song_dir: Path) -> str:
        """Compose status: 슬라이드 형식 + 악보 장수."""
        has_pptx = (song_dir / "slides.pptx").exists()
        has_md = (song_dir / "slides.md").exists()
        if has_pptx:
            slide_part = "PPT"
        elif has_md:
            slide_part = "마크다운"
        else:
            slide_part = "슬라이드 없음"

        sheet_count = 0
        for d in (song_dir / "sheets", song_dir / "sheet"):
            if d.is_dir():
                sheet_count += sum(
                    1 for f in d.iterdir()
                    if f.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp"}
                )
        sheet_part = f"악보 {sheet_count}장" if sheet_count else "악보 없음"
        return f"{slide_part} · {sheet_part}"

    def _on_search_changed(self, text: str) -> None:
        self._search_text = text.strip()
        self.refresh()

    def _on_sort_changed(self, mode: str) -> None:
        self._sort_mode = mode
        self.refresh()
