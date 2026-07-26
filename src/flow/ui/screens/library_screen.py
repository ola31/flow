"""Library screen — full list of all songs in the workspace library.

검색 + 정렬(가나다순/생성순) + 카드 클릭으로 곡 편집 진입.
"""
from __future__ import annotations

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

from flow.services.song_index import song_info, song_lyrics
from flow.ui.screens._browser_widgets import (
    SORT_NAME,
    BrowserToolbar,
    ItemCard,
    sort_paths,
)
from flow.ui.styles import (
    AMBER,
    BG_DEEP,
    BORDER_FOCUS,
    FONT_MD,
    SP_LG,
    SP_MD,
    SP_SM,
    TEXT_TERTIARY,
)


def _amber(text: str) -> str:
    """부제 QLabel이 rich text로 렌더 — 문제 텍스트만 앰버로 강조."""
    return f'<span style="color:{AMBER}">{text}</span>'


class LibraryScreen(QWidget):
    """Workspace 의 library/ 안 모든 곡을 보여주는 페이지.

    Signals:
        song_selected(str): 곡 폴더 경로
        new_song_requested(): 새 곡 생성 요청
    """

    song_selected = Signal(str)
    new_song_requested = Signal()
    # 삭제 요청 (곡 폴더 경로) — 실제 처리는 MainWindow가 한다
    song_delete_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._workspace = None
        self._search_text = ""
        self._sort_mode = SORT_NAME
        # 곡 폴더 경로 → 카드. 검색·정렬은 카드를 다시 만들지 않고 이
        # 풀에서 꺼내 순서만 바꾼다 (수백 개 QFrame 재생성 방지).
        self._cards: dict[str, ItemCard] = {}

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
        self._toolbar.refresh_clicked.connect(self.force_refresh)
        root.addWidget(self._toolbar)

        # F5 — 이 화면이 떠 있을 때만 동작하도록 위젯 범위로 제한한다
        # (MainWindow의 F5는 라이브 모드 토글이라 겹치면 안 된다).
        shortcut = QShortcut(QKeySequence("F5"), self)
        shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        shortcut.activated.connect(self.force_refresh)

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

    def force_refresh(self) -> None:
        """캐시를 버리고 디스크에서 다시 읽는다 (새로고침 버튼 / F5).

        refresh()는 지문이 같으면 건너뛰고 song_index는 mtime으로 캐시하는데,
        폴더째 옮기거나 이름만 바꾼 변경은 mtime이 그대로일 수 있다.
        새로고침은 "지금 디스크 상태를 그대로 보여달라"는 뜻이므로 판단을
        생략하고 전부 다시 읽는다.
        """
        from flow.services import song_index

        song_index.invalidate()
        self._last_fingerprint = None
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

        if self._workspace is None:
            self._detach_all_cards()
            for card in self._cards.values():
                card.deleteLater()
            self._cards.clear()
            self._empty_lbl.setText("워크스페이스가 열려있지 않습니다.")
            self._empty_lbl.show()
            return

        all_paths = paths_for_fp
        paths = all_paths
        snippets: dict[Path, str] = {}
        if self._search_text:
            from flow.services.markdown import lyric_snippet

            q = self._search_text.lower()
            matched = []
            for p in all_paths:
                if q in song_info(p)["name_lower"]:
                    matched.append(p)  # 제목 매칭 — 스니펫 없음
                    continue
                lyrics, lyrics_lower = song_lyrics(p)
                if q in lyrics_lower:
                    matched.append(p)
                    snippets[p] = lyric_snippet(lyrics, q)
            paths = matched

        paths = sort_paths(paths, self._sort_mode)

        # 라이브러리에서 사라진 곡의 카드는 폐기
        alive = {str(p) for p in all_paths}
        for key in [k for k in self._cards if k not in alive]:
            self._cards.pop(key).deleteLater()

        ordered: list[ItemCard] = []
        for path in paths:
            key = str(path)
            card = self._cards.get(key)
            subtitle = self._build_subtitle(path)
            if card is None:
                card = ItemCard(
                    path=key, title=path.name, subtitle=subtitle,
                    match_snippet=snippets.get(path, ""),
                    deletable=True,
                )
                card.clicked.connect(self.song_selected.emit)
                card.delete_requested.connect(self.song_delete_requested.emit)
                self._cards[key] = card
            else:
                card.set_subtitle(subtitle)
                card.set_match_snippet(snippets.get(path, ""))
            ordered.append(card)

        self._detach_all_cards()
        for i, card in enumerate(ordered):
            self._cards_layout.insertWidget(i, card)
            card.setVisible(True)

        if not ordered:
            self._empty_lbl.setText(
                "이 워크스페이스에 곡이 없습니다." if not self._search_text
                else f"'{self._search_text}'와(과) 일치하는 곡이 없습니다."
            )
            self._empty_lbl.show()
            return
        self._empty_lbl.hide()

    def _detach_all_cards(self) -> None:
        """카드를 레이아웃에서만 떼어내고 위젯은 살려둔다 (끝의 stretch 유지).

        떼어낸 위젯은 부모가 그대로라 숨기지 않으면 옛 위치에 남아 그려진다.
        """
        while self._cards_layout.count() > 1:
            self._cards_layout.takeAt(0)
        for card in self._cards.values():
            card.setVisible(False)

    def _build_subtitle(self, song_dir: Path) -> str:
        """Compose status: 슬라이드 형식 + 악보 장수 (+ 매핑 경고 꼬리)."""
        info = song_info(song_dir)
        if info["has_ppt"]:
            slide_part = "PPT"
        elif info["has_md"]:
            slide_part = "마크다운"
        else:
            slide_part = _amber("슬라이드 없음")

        sheet_count = info["sheet_count"]
        sheet_part = (
            f"악보 {sheet_count}장" if sheet_count else _amber("악보 없음")
        )

        subtitle = f"{slide_part} · {sheet_part}"
        mapping_part = self._mapping_part(
            info, info["has_ppt"] or info["has_md"], sheet_count
        )
        if mapping_part:
            subtitle += f" · {mapping_part}"
        return subtitle

    def _mapping_part(
        self, info: dict, has_slides: bool, sheet_count: int
    ) -> str:
        """매핑에 문제가 있을 때만 경고 꼬리 (정상·판단불가는 '').

        악보나 슬라이드가 없으면 매핑이 없는 건 당연하므로 생략 —
        부제의 원인 경고(악보/슬라이드 없음)가 대신한다.
        """
        if not has_slides or sheet_count == 0:
            return ""
        if not (info["path"] / "song.json").exists():
            return ""
        total = info["total_hotspots"]
        mapped = info["mapped_hotspots"]
        if mapped == 0:
            return _amber("매핑 없음")
        if mapped < total:
            return _amber(f"매핑 {mapped}/{total}")
        return ""

    def _on_search_changed(self, text: str) -> None:
        self._search_text = text.strip()
        self.refresh()

    def _on_sort_changed(self, mode: str) -> None:
        self._sort_mode = mode
        self.refresh()
