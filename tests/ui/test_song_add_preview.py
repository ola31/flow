"""곡 추가 카드 클릭 펼침 미리보기 테스트

추가(참조/복사) 전에 어떤 곡인지 확인할 방법이 없었다 — 카드 본체를
클릭하면 첫 악보 썸네일 + 가사 앞 6줄이 펼쳐진다. 라이브 중 추가 패널과
일반 곡 추가 팝업이 같은 위젯을 쓰므로 양쪽에 적용된다.
"""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QLabel

from flow.ui.editor.song_list_widget import SongLibraryBrowser, _LibrarySongCard


def _png(path: Path) -> Path:
    img = QImage(8, 8, QImage.Format.Format_RGB32)
    img.fill(QColor("#123456"))
    img.save(str(path))
    return path


def _info(**over) -> dict:
    base = {
        "name": "song_x",
        "sheet_count": 1,
        "has_ppt": True,
        "has_md": False,
        "total_hotspots": 1,
        "mapped_hotspots": 1,
        "lyrics": "",
        "first_sheet": None,
    }
    base.update(over)
    return base


def _texts(card) -> list[str]:
    return [lbl.text() for lbl in card.findChildren(QLabel)]


class TestCardPreview:
    def test_click_emits_toggle_request(self, qtbot):
        card = _LibrarySongCard(_info())
        qtbot.addWidget(card)
        card.show()

        with qtbot.waitSignal(card.toggle_preview_requested, timeout=1000):
            qtbot.mouseClick(card, Qt.MouseButton.LeftButton)

    def test_expand_shows_lyrics_lines(self, qtbot):
        lyrics = "\n".join(f"라인{i}" for i in range(1, 5))
        card = _LibrarySongCard(_info(lyrics=lyrics))
        qtbot.addWidget(card)

        card.set_preview_expanded(True)

        texts = _texts(card)
        assert any("라인1" in t and "라인4" in t for t in texts)

    def test_lyrics_capped_at_six_lines(self, qtbot):
        lyrics = "\n".join(f"라인{i}" for i in range(1, 11))
        card = _LibrarySongCard(_info(lyrics=lyrics))
        qtbot.addWidget(card)

        card.set_preview_expanded(True)

        preview = next(t for t in _texts(card) if "라인1" in t)
        assert "라인6" in preview
        assert "라인7" not in preview

    def test_thumbnail_from_first_sheet(self, qtbot, tmp_path):
        sheet = _png(tmp_path / "page1.png")
        card = _LibrarySongCard(_info(first_sheet=sheet))
        qtbot.addWidget(card)

        card.set_preview_expanded(True)

        thumbs = [
            lbl for lbl in card.findChildren(QLabel)
            if lbl.pixmap() is not None and not lbl.pixmap().isNull()
        ]
        assert thumbs, "악보 썸네일이 없음"

    def test_no_content_placeholder(self, qtbot):
        card = _LibrarySongCard(_info(lyrics="", first_sheet=None))
        qtbot.addWidget(card)

        card.set_preview_expanded(True)

        assert "미리볼 내용 없음" in _texts(card)

    def test_collapse_hides_preview(self, qtbot):
        card = _LibrarySongCard(_info(lyrics="라인1"))
        qtbot.addWidget(card)
        card.set_preview_expanded(True)

        card.set_preview_expanded(False)

        preview = next(
            lbl for lbl in card.findChildren(QLabel) if "라인1" in lbl.text()
        )
        assert not preview.isVisibleTo(card)

    def test_add_button_does_not_toggle(self, qtbot):
        card = _LibrarySongCard(_info(), workspace_mode=True)
        qtbot.addWidget(card)
        card.show()
        emitted = []
        card.toggle_preview_requested.connect(emitted.append)

        qtbot.mouseClick(card._add_buttons[0], Qt.MouseButton.LeftButton)

        assert emitted == []


class TestBrowserSingleExpand:
    def _browser(self, qtbot, tmp_path):
        for name in ("song_one", "song_two"):
            d = tmp_path / name
            d.mkdir()
            with open(d / "song.json", "w", encoding="utf-8-sig") as f:
                json.dump({"name": name, "sheets": []}, f)
            (d / "slides.md").write_text(f"# p\n{name} 가사", encoding="utf-8")
        browser = SongLibraryBrowser(tmp_path, set())
        qtbot.addWidget(browser)
        return browser

    def test_only_one_card_expanded(self, qtbot, tmp_path):
        browser = self._browser(qtbot, tmp_path)
        c1, c2 = browser._cards[0], browser._cards[1]

        c1.toggle_preview_requested.emit(c1._name)
        assert c1._preview_expanded and not c2._preview_expanded

        c2.toggle_preview_requested.emit(c2._name)
        assert c2._preview_expanded and not c1._preview_expanded

    def test_second_click_collapses(self, qtbot, tmp_path):
        browser = self._browser(qtbot, tmp_path)
        c1 = browser._cards[0]

        c1.toggle_preview_requested.emit(c1._name)
        c1.toggle_preview_requested.emit(c1._name)

        assert not c1._preview_expanded


class TestPreviewSheetReadable:
    """악보 썸네일이 손톱만 하면 의미가 없다 — 카드 폭에 맞춰 크게."""

    def test_sheet_scales_to_card_width(self, qtbot, tmp_path):
        sheet = _png(tmp_path / "page1.png")
        card = _LibrarySongCard(_info(first_sheet=sheet))
        qtbot.addWidget(card)
        card.resize(320, 80)
        card.show()

        card.set_preview_expanded(True)

        thumb = next(
            lbl for lbl in card.findChildren(QLabel)
            if lbl.pixmap() is not None and not lbl.pixmap().isNull()
        )
        assert thumb.pixmap().width() >= 240, (
            f"썸네일 폭 {thumb.pixmap().width()}px — 카드 폭에 맞춰야 함"
        )
