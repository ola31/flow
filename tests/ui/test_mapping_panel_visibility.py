"""매핑 패널 — 매핑 없는 절 행 숨기기 (활성 절은 예외).

6개 절 행을 항상 다 보여주면 빈 슬롯이 화면을 차지한다. 매핑된 절과
현재 활성 절(더블클릭 매핑 대상)만 보여준다.
"""
from __future__ import annotations

import pytest

from flow.domain.hotspot import Hotspot
from flow.ui.editor.mapping_panel import MappingPanel


@pytest.fixture
def panel(qtbot):
    p = MappingPanel()
    qtbot.addWidget(p)
    return p


def _visible_verses(panel) -> list[int]:
    return [i for i, r in enumerate(panel._rows) if not r.isHidden()]


class TestHideUnmappedVerseRows:
    def test_only_mapped_visible(self, panel):
        h = Hotspot(x=1, y=1, slide_mappings={"0": 2, "1": 3})
        panel.show_for_hotspot(h, active_verse=3, get_image_fn=None)

        assert _visible_verses(panel) == [0, 1]  # 활성(3)이라도 미매핑은 숨김

    def test_chorus_only_shows_chorus_only(self, panel):
        h = Hotspot(x=1, y=1, slide_mappings={"5": 7})
        panel.show_for_hotspot(h, active_verse=0, get_image_fn=None)

        assert _visible_verses(panel) == [5]  # 1절(활성)이라도 빈 행은 숨김

    def test_all_mapped_all_visible(self, panel):
        h = Hotspot(
            x=1, y=1,
            slide_mappings={str(i): i for i in range(6)},
        )
        panel.show_for_hotspot(h, active_verse=2, get_image_fn=None)

        assert _visible_verses(panel) == [0, 1, 2, 3, 4, 5]

    def test_active_verse_change_keeps_mapped_only(self, panel):
        h = Hotspot(x=1, y=1, slide_mappings={"1": 3})
        panel.show_for_hotspot(h, active_verse=0, get_image_fn=None)
        assert _visible_verses(panel) == [1]

        panel.set_active_verse(3)

        assert _visible_verses(panel) == [1]  # 미매핑 활성 절은 표시 안 함

    def test_no_mapping_shows_only_active(self, panel):
        h = Hotspot(x=1, y=1)
        panel.show_for_hotspot(h, active_verse=5, get_image_fn=None)

        assert _visible_verses(panel) == [5]


class TestMappedWithoutThumbnail:
    def test_mapped_row_stays_mapped_when_thumbnail_missing(self, panel):
        """변환 전엔 썸네일이 없어도 매핑 사실은 유지 — 행이 숨지 않고
        슬라이드 번호와 해제 버튼이 보여야 한다."""
        h = Hotspot(x=1, y=1, slide_mappings={"1": 3})
        panel.show_for_hotspot(h, active_verse=0, get_image_fn=None)

        row = panel._rows[1]
        assert row._is_mapped
        assert not row.isHidden()
        assert "슬라이드 4" in row._slide_label.text()


class TestThumbnailDpiAware:
    def test_thumb_scaled_for_device_pixel_ratio(self):
        """논리 크기로만 스케일하면 HiDPI에서 흐리다 — DPR만큼 큰 픽스맵을
        만들고 devicePixelRatio를 지정해야 선명하다."""
        from PySide6.QtGui import QColor, QImage

        from flow.ui.editor.mapping_panel import _THUMB_W, _scaled_thumb

        src = QImage(480, 270, QImage.Format.Format_RGB32)
        src.fill(QColor("#334455"))

        pm = _scaled_thumb(src, dpr=2.0)

        assert pm.devicePixelRatio() == 2.0
        assert pm.width() > _THUMB_W  # 물리 픽셀은 논리 크기보다 커야 함
