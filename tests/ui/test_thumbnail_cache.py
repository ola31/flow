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


class TestProgressiveRefreshDuringConversion:
    """변환 진행 신호가 올 때 썸네일을 점진적으로 채운다 (스로틀 적용)."""

    def test_progress_triggers_throttled_refresh(self, qtbot, monkeypatch):
        mgr = _FakeManager(count=3)
        panel = _make_panel(qtbot, mgr)

        calls = []
        monkeypatch.setattr(panel, "refresh_slides", lambda: calls.append(1))

        panel._on_conversion_progress(1, 61, "LibreOffice")
        panel._on_conversion_progress(2, 61, "LibreOffice")  # 스로틀로 무시
        assert len(calls) == 1

        panel._last_progress_refresh = 0.0  # 스로틀 창 경과 시뮬레이션
        panel._on_conversion_progress(30, 61, "LibreOffice")
        assert len(calls) == 2

    def test_progress_shown_in_title_not_overlay(self, qtbot):
        """변환 진행은 오버레이(썸네일 가림) 대신 제목에 비차단 표시."""
        mgr = _FakeManager(count=3)
        panel = _make_panel(qtbot, mgr)

        panel._on_conversion_progress(42, 61, "LibreOffice")

        assert "42/61" in panel._title.text()
        assert not panel._loading_overlay.isVisible()

        # 변환 완료(hide_loading) 후 제목의 진행 표시가 사라져야 함
        panel.hide_loading()
        panel.refresh_slides()
        assert "42/61" not in panel._title.text()

    def test_background_warm_scheduling_does_not_show_overlay(self, qtbot):
        """peek 미스로 예약되는 백그라운드 변환은 load_started(오버레이)를
        발신하지 않는다 — 곡 전환 때마다 화면이 가려지면 안 됨."""
        from flow.services.slide_manager import SlideManager

        mgr = SlideManager(converter=None)  # 엔진 없음 → 워커 None
        try:
            started = []
            mgr.load_started.connect(lambda: started.append(1))
            mgr._ensure_background_conversion(__import__("pathlib").Path("/x.pptx"))
            assert started == []
        finally:
            mgr.shutdown()

    def test_status_change_does_not_reenter_event_loop(self, qtbot, monkeypatch):
        """상태 라벨 갱신이 processEvents를 호출하면 스크롤 중 스터터가 생긴다."""
        from PySide6.QtWidgets import QApplication

        mgr = _FakeManager(count=1)
        panel = _make_panel(qtbot, mgr)
        calls = []
        monkeypatch.setattr(
            QApplication,
            "processEvents",
            staticmethod(lambda *a, **k: calls.append(1)),
        )
        try:
            panel._on_load_status_changed("이미지 추출 중 (3/61)...")
        finally:
            monkeypatch.undo()

        assert calls == []
        assert panel._loading_label.text() == "이미지 추출 중 (3/61)..."


class _FakeManager:
    """count/peek/cache_key만 흉내내는 슬라이드 매니저."""

    def __init__(self, count=3):
        self.count = count
        self._pptx_path = None
        self.peek_calls: list[int] = []
        self.thumb_calls: list[int] = []
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

    def peek_thumbnail(self, i, max_w=480, max_h=270):
        # 실제 매니저처럼 내부적으로 peek을 사용 (공유 캐시 워밍 시뮬레이션)
        self.thumb_calls.append(i)
        return self.peek_slide_image(i)

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
        # 아이콘은 나중에 채워져도 아이템 자체는 즉시 전부 존재해야
        # (행 번호 == 슬라이드 인덱스 유지, select_slide가 어긋나지 않게)
        assert panel._list.count() == 30

        # 이벤트 루프가 돌면 나머지가 점진적으로 채워짐
        qtbot.waitUntil(lambda: len(set(mgr.peek_calls)) == 30, timeout=3000)
        assert panel._list.count() == 30

    def test_unconverted_slides_keep_rows_aligned(self, qtbot):
        """아직 변환 안 된 슬라이드(peek=None)도 자리 표시 아이템을 만들어
        목록 행과 슬라이드 인덱스가 어긋나지 않아야 한다.

        큰 PPT가 백그라운드 변환 중일 때 그 슬라이드들을 건너뛰면, 뒤쪽
        곡(마크다운)의 썸네일이 앞 행을 차지해 핫스팟 선택(select_slide)이
        엉뚱한 행을 잡거나 실패한다.
        """
        from PySide6.QtCore import Qt

        mgr = _FakeManager(count=6)
        real_peek = mgr.peek_slide_image

        def partial_peek(i):
            mgr.peek_calls.append(i)
            if i < 3:
                return None  # 앞쪽 3장은 아직 변환 안 됨 (큰 PPT)
            return real_peek(i)

        mgr.peek_slide_image = partial_peek
        panel = _make_panel(qtbot, mgr)

        assert panel._list.count() == 6
        for i in range(6):
            item = panel._list.item(i)
            assert item.data(Qt.ItemDataRole.UserRole) == i

        panel.select_slide(4)
        assert panel._list.currentRow() == 4

    def test_strip_refresh_warms_shared_thumbnail_cache(self, qtbot):
        """스트립 채우기가 peek_thumbnail을 쓰면 클릭용 축소본 캐시가
        함께 데워져, 이후 핫스팟 클릭이 디코드 없이 즉시 뜬다."""
        mgr = _FakeManager(count=3)
        panel = _make_panel(qtbot, mgr)  # 참조 유지 필수 (지연 채움 타이머)
        qtbot.waitUntil(lambda: len(set(mgr.thumb_calls)) == 3, timeout=3000)

        assert sorted(set(mgr.thumb_calls)) == [0, 1, 2], (
            "스트립이 peek_thumbnail 경로로 디코드해 공유 캐시를 데워야 함"
        )
        assert panel._list.count() == 3

    def test_placeholder_items_keep_thumbnail_geometry(self, qtbot):
        """자리 표시 아이템도 실제 썸네일과 같은 크기의 아이콘을 가져야 한다.

        IconMode는 나중에 setIcon해도 셀 크기를 재계산하지 않으므로,
        아이콘 없이 만들면 변환 완료 후에도 썸네일이 조그맣게 남는다.
        """
        from PySide6.QtGui import QImage

        state = {"ready": False}

        def big(i):
            img = QImage(1920, 1080, QImage.Format.Format_RGB32)
            img.fill(0xFF202020)
            return img

        mgr = _FakeManager(count=3)
        mgr.peek_slide_image = lambda i: big(i) if state["ready"] else None
        mgr.get_slide_cache_key = lambda i: (
            "deck", 2.0 if state["ready"] else 1.0, 0.0, i,
        )
        panel = _make_panel(qtbot, mgr)
        panel.resize(1200, 160)
        panel.show()
        qtbot.waitExposed(panel)

        placeholder_rect = panel._list.visualItemRect(panel._list.item(1))

        state["ready"] = True
        panel.refresh_slides()
        filled_rect = panel._list.visualItemRect(panel._list.item(1))

        # 채워진 뒤에도 셀 크기가 placeholder 때와 같아야 하고(재배치 없음),
        # 그 크기는 아이콘 크기(144x81) 이상이어야 한다
        assert placeholder_rect.size() == filled_rect.size()
        assert filled_rect.width() >= 144
        assert filled_rect.height() >= 81

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


class TestRefreshDoesNotEmitSelection:
    """프로그램이 목록을 다시 채울 때 slide_selected가 나가면 안 된다.

    takeItem/clear가 현재 항목을 지우면 Qt가 current를 다른 행으로 옮기며
    currentItemChanged를 쏜다. MainWindow는 그 신호를 "사용자가 슬라이드를
    골랐다"로 보고 선택된 핫스팟에 매핑을 걸어 undo를 push한다 — 곡 편집에
    들어갔다 나오기만 해도 프로젝트가 변경됨으로 표시되던 원인.
    """

    def test_truncating_list_emits_nothing(self, qtbot):
        mgr = _FakeManager(count=5)
        panel = _make_panel(qtbot, mgr)
        panel.refresh_slides()
        panel.select_slide(4)  # 마지막 항목이 현재 선택

        emitted: list[int] = []
        panel.slide_selected.connect(emitted.append)

        mgr.count = 2  # 곡 편집 진입 — 슬라이드 수가 줄어듦
        panel.refresh_slides()

        assert emitted == []

    def test_growing_list_emits_nothing(self, qtbot):
        mgr = _FakeManager(count=1)
        panel = _make_panel(qtbot, mgr)
        panel.refresh_slides()
        panel.select_slide(0)

        emitted: list[int] = []
        panel.slide_selected.connect(emitted.append)

        mgr.count = 4  # 프로젝트로 복귀 — 슬라이드 수가 늘어남
        panel.refresh_slides()

        assert emitted == []

    def test_user_click_still_emits(self, qtbot):
        mgr = _FakeManager(count=3)
        panel = _make_panel(qtbot, mgr)
        panel.refresh_slides()

        emitted: list[int] = []
        panel.slide_selected.connect(emitted.append)

        # 실제 사용자 선택은 신호가 그대로 나가야 한다
        panel._list.setCurrentRow(1)

        assert emitted == [1]
