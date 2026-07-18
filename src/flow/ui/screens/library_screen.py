"""Library screen — full list of all songs in the workspace library.

검색 + 정렬(가나다순/생성순) + 카드 클릭으로 곡 편집 진입.
"""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from flow.domain.song import detect_slides_file
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
    RED,
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

    def _fingerprint(self, paths) -> tuple:
        """카드 재구성 필요 여부 판정용 지문.

        곡 추가/삭제(폴더 목록), 저장(song.json mtime), 파일 추가/제거
        (폴더 mtime)를 감지한다. 검색어·정렬 변경도 재구성 대상.
        """
        entries = []
        for p in paths:
            try:
                sj = p / "song.json"
                entries.append((
                    p.name,
                    p.stat().st_mtime,
                    sj.stat().st_mtime if sj.exists() else 0.0,
                ))
            except OSError:
                entries.append((p.name, 0.0, 0.0))
        return (self._search_text, self._sort_mode, tuple(entries))

    def refresh(self) -> None:
        # 페이지 전환마다 카드 수백 개를 재생성하면 전환이 느려진다 —
        # 내용이 안 바뀌었으면 기존 카드를 그대로 둔다.
        if self._workspace is not None:
            paths_for_fp = self._workspace.list_library_songs()
            fp = self._fingerprint(paths_for_fp)
            if fp == getattr(self, "_last_fingerprint", None):
                return
            self._last_fingerprint = fp
        else:
            self._last_fingerprint = None

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
        """Compose status: 슬라이드 형식 + 악보 장수 (+ 매핑 경고 꼬리)."""
        has_pptx = detect_slides_file(song_dir) is not None
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

        subtitle = f"{slide_part} · {sheet_part}"
        mapping_part = self._mapping_part(
            song_dir, has_pptx or has_md, sheet_count
        )
        if mapping_part:
            subtitle += f" · {mapping_part}"
        return subtitle

    def _mapping_part(
        self, song_dir: Path, has_slides: bool, sheet_count: int
    ) -> str:
        """매핑에 문제가 있을 때만 경고 꼬리 (정상·판단불가는 '').

        악보나 슬라이드가 없으면 매핑이 없는 건 당연하므로 생략 —
        부제의 원인 경고(악보/슬라이드 없음)가 대신한다.
        """
        if not has_slides or sheet_count == 0:
            return ""
        song_json = song_dir / "song.json"
        if not song_json.exists():
            return ""
        try:
            with open(song_json, encoding="utf-8-sig") as f:
                data = json.load(f)
        except (OSError, ValueError):
            return ""
        total, mapped = 0, 0
        for sheet_data in data.get("sheets", []):
            for h in sheet_data.get("hotspots", []):
                total += 1
                if h.get("slide_mappings") or h.get("slide_index", -1) >= 0:
                    mapped += 1
        if mapped == 0:
            # QLabel이 rich text로 렌더 — 매핑 없음만 빨강으로 강조
            return f'<span style="color:{RED}">매핑 없음</span>'
        if mapped < total:
            return f"매핑 {mapped}/{total}"
        return ""

    def _on_search_changed(self, text: str) -> None:
        self._search_text = text.strip()
        self.refresh()

    def _on_sort_changed(self, mode: str) -> None:
        self._sort_mode = mode
        self.refresh()
