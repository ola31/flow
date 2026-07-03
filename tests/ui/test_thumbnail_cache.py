"""슬라이드 썸네일 아이콘 캐시 테스트

refresh_slides가 변경되지 않은 슬라이드의 PNG를 다시 디코드하면 61장
덱에서 매번 3초씩 GUI가 얼어붙는다. 캐시 키가 같으면 peek(디코드)를
건너뛰어야 한다.
"""
from __future__ import annotations

from PySide6.QtGui import QImage

from flow.ui.editor.slide_preview_panel import SlidePreviewPanel


class _FakeSignal:
    def connect(self, *_a, **_k):
        pass


class _FakeManager:
    """count/peek/cache_key만 흉내내는 슬라이드 매니저."""

    def __init__(self, count=3):
        self.count = count
        self._pptx_path = None
        self.peek_calls: list[int] = []
        self.mtime = 1000.0
        self.file_changed = _FakeSignal()
        self.load_error = _FakeSignal()
        self.load_status = _FakeSignal()

    def get_slide_count(self):
        return self.count

    def peek_slide_image(self, i):
        self.peek_calls.append(i)
        img = QImage(32, 18, QImage.Format.Format_RGB32)
        img.fill(0xFF000000 + i)
        return img

    def get_slide_cache_key(self, i):
        return ("deck.pptx", self.mtime, 0.0, i)


def _make_panel(qtbot, mgr):
    panel = SlidePreviewPanel()
    qtbot.addWidget(panel)
    panel.set_slide_manager(mgr)
    return panel


class TestThumbnailIconCache:
    def test_second_refresh_skips_decoding(self, qtbot):
        mgr = _FakeManager(count=3)
        panel = _make_panel(qtbot, mgr)

        panel.refresh_slides()
        assert sorted(mgr.peek_calls) == [0, 1, 2]

        mgr.peek_calls.clear()
        panel.refresh_slides()

        assert mgr.peek_calls == [], "키가 같으면 디코드(peek) 없이 재사용해야 함"
        assert panel._list.count() == 3

    def test_file_change_invalidates_cache(self, qtbot):
        mgr = _FakeManager(count=2)
        panel = _make_panel(qtbot, mgr)
        panel.refresh_slides()
        mgr.peek_calls.clear()

        mgr.mtime = 2000.0  # 파일 변경 시뮬레이션
        panel.refresh_slides()

        assert sorted(mgr.peek_calls) == [0, 1]

    def test_none_key_falls_back_to_peek(self, qtbot):
        mgr = _FakeManager(count=2)
        mgr.get_slide_cache_key = lambda i: None
        panel = _make_panel(qtbot, mgr)

        panel.refresh_slides()
        mgr.peek_calls.clear()
        panel.refresh_slides()

        assert sorted(mgr.peek_calls) == [0, 1]  # 키 없으면 기존 방식

    def test_large_deck_decodes_incrementally(self, qtbot):
        """한 번의 refresh 호출이 예산(8장)만 디코드하고 나머지는 다음
        이벤트 루프 틱으로 미뤄 GUI 블락을 막는다."""
        mgr = _FakeManager(count=30)
        panel = _make_panel(qtbot, mgr)  # set_slide_manager가 1차 refresh 실행

        first_pass = len(mgr.peek_calls)
        assert first_pass <= panel._DECODE_BUDGET

        # 이벤트 루프가 돌면 나머지가 점진적으로 채워짐
        qtbot.waitUntil(lambda: len(set(mgr.peek_calls)) == 30, timeout=3000)
        assert panel._list.count() == 30

    def test_mapped_label_updates_without_decoding(self, qtbot):
        mgr = _FakeManager(count=2)
        panel = _make_panel(qtbot, mgr)
        panel.refresh_slides()
        mgr.peek_calls.clear()

        panel.set_mapped_slides({1})
        panel.refresh_slides()

        assert mgr.peek_calls == []
        assert "●" in panel._list.item(1).text()
        assert "●" not in panel._list.item(0).text()
