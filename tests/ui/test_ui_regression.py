"""UI 회귀 테스트

최근 수정된 3개 버그에 대한 어설션 기반 회귀 테스트:

1. 아이콘 매핑 (commit 365fd97): library/queue_music 코드포인트가 이 폰트에서
   예상과 다른 글리프로 렌더링됨. UI에서는 music_note/view_list로 교체됨.
   → 회귀 방지: UI 코드에서 library/queue_music 이름 사용 금지, 이모지 금지,
     서브셋 폰트가 모든 매핑된 코드포인트에 글리프를 포함하는지 확인.

2. 매핑된 슬라이드 배경색 안 바뀜 (commit 81c4cb4 → 6506e08):
   QListWidget::item의 stylesheet background-color가 item.setBackground()를
   덮어써서, 최종적으로 setForeground()로 전환함.
   → 회귀 방지: set_mapped_slides() 호출 시 매핑된 아이템의 foreground()가
     실제로 바뀌는지 확인.

3. 매핑 표시 이모지 제거 (commit 365fd97):
   "(🔗)" 같은 이모지가 아마추어 느낌이라 "●"로 교체함.
   → 회귀 방지: 매핑 레이블에 "●"가 포함되고, 🔗 같은 이모지는 없는지 확인.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QListWidgetItem

from flow.ui.editor.slide_preview_panel import SlidePreviewPanel
from flow.ui.icons import _CODEPOINTS, _FONT_PATH


SRC_UI = Path(__file__).resolve().parents[2] / "src" / "flow" / "ui"


# =============================================================================
# Bug 1: Icon rendering / codepoint mapping
# =============================================================================


class TestIconRegression:
    """아이콘 매핑 회귀 방지 (commit 365fd97, 8973b72)"""

    def test_subset_font_contains_all_mapped_codepoints(self):
        """_CODEPOINTS의 모든 코드포인트가 서브셋 폰트에 실제 글리프로 존재해야 함.

        과거 버그: 서브셋 빌드 시 특정 코드포인트가 누락되면 런타임에 공백이나
        ? 아이콘으로 렌더링됨. fonttools로 cmap 직접 검사.
        """
        from fontTools.ttLib import TTFont

        assert _FONT_PATH.exists(), f"서브셋 폰트 파일 누락: {_FONT_PATH}"

        font = TTFont(str(_FONT_PATH))
        cmap = font.getBestCmap()

        missing = [
            (name, cp)
            for name, cp in _CODEPOINTS.items()
            if cp not in cmap
        ]
        assert not missing, (
            f"서브셋 폰트에 다음 아이콘 코드포인트가 누락됨: {missing}\n"
            f"scripts로 폰트를 재빌드하거나 _CODEPOINTS 맵을 정리해야 함."
        )

    @pytest.mark.parametrize(
        "banned_name",
        ["library", "queue_music"],
    )
    def test_deprecated_icon_names_not_used_in_ui(self, banned_name: str):
        """library/queue_music 코드포인트는 이 폰트에서 잘못된 글리프로 렌더됨.

        회귀 방지: 어떤 UI 파일도 icon("library") / icon_label("library") /
        icon_qicon("library") / icon_pixmap("library") / icon_text_label 등의
        아이콘 조회 함수에 이 이름을 넘기지 않도록 한다.

        검사 범위는 "icon 관련 호출의 첫 인자 위치에 banned_name이 쓰였는지"로
        제한 — 'library'가 단순 문자열 상수(예: source 식별자)로 쓰이는 건 허용.
        (codepoint map에서는 여전히 보존해도 됨 — 사용처만 금지.)
        """
        # icon_xxx(..., "library" ... ) 또는 icon(..., 'library' ...) 형태를 검출
        pattern = re.compile(
            rf"""\bicon(?:_\w+)?\s*\(\s*["']{banned_name}["']"""
        )
        offenders: list[str] = []
        for py_file in SRC_UI.rglob("*.py"):
            text = py_file.read_text(encoding="utf-8")
            if py_file.name == "icons.py":
                continue
            if pattern.search(text):
                offenders.append(str(py_file.relative_to(SRC_UI.parent)))

        assert not offenders, (
            f"아이콘 이름 '{banned_name}' 사용이 감지됨 (잘못된 글리프로 렌더됨):\n"
            + "\n".join(f"  - {p}" for p in offenders)
            + "\n대체: 'library' → 'music_note', 'queue_music' → 'view_list'"
        )

    def test_no_emoji_in_user_facing_ui_text(self):
        """UI 코드에 '🔗' 및 기타 대표적 이모지 금지.

        과거: 슬라이드 매핑 표시를 "(🔗)"로 하다가 아마추어 느낌이라 제거함.
        이 테스트는 특정 이모지 세트만 감시 (광범위한 이모지 정규식은 노이즈가 큼).
        """
        banned_chars = ["🔗", "🎵", "⚙️", "📁", "📂", "✅", "❌"]
        offenders: list[tuple[str, str]] = []
        for py_file in SRC_UI.rglob("*.py"):
            # 회귀 테스트 자체는 이 문자를 참조하므로 제외
            if py_file.resolve() == Path(__file__).resolve():
                continue
            text = py_file.read_text(encoding="utf-8")
            for ch in banned_chars:
                if ch in text:
                    offenders.append((str(py_file.relative_to(SRC_UI.parent)), ch))

        assert not offenders, (
            "UI 코드에 금지된 이모지가 포함됨. Material Symbols 아이콘으로 교체하세요:\n"
            + "\n".join(f"  - {p}: {ch}" for p, ch in offenders)
        )


# =============================================================================
# Bug 2 & 3: Slide preview mapping indicator
# =============================================================================


@pytest.fixture
def preview_panel(qapp) -> SlidePreviewPanel:
    """SlidePreviewPanel 인스턴스 + 3개 더미 아이템을 list에 직접 추가.

    SlideManager를 거치지 않고 테스트하기 위해 내부 _list에 직접 삽입.
    실제 코드에서도 refresh_slides()가 이렇게 item을 만듦.
    """
    panel = SlidePreviewPanel()
    for i in range(3):
        item = QListWidgetItem(f"Slide {i + 1}")
        item.setData(Qt.ItemDataRole.UserRole, i)
        panel._list.addItem(item)
    return panel


class TestSlideMappingIndicator:
    """매핑된 슬라이드 표시 회귀 방지 (commit 81c4cb4 → 6506e08)"""

    def test_mapped_slide_foreground_color_changes(self, preview_panel: SlidePreviewPanel):
        """매핑된 슬라이드는 foreground 색상이 액센트 컬러로 변경됨.

        과거 버그: stylesheet의 item background-color가 setBackground()를
        덮어써서 배경색이 안 바뀌었음. 해결: setForeground() 사용.

        회귀 방지: set_mapped_slides([0, 2]) 호출 후 item(0)과 item(2)는
        기본색(회색)과 다른 색이어야 함.
        """
        preview_panel.set_mapped_slides({0, 2})

        mapped_0 = preview_panel._list.item(0).foreground().color()
        normal_1 = preview_panel._list.item(1).foreground().color()
        mapped_2 = preview_panel._list.item(2).foreground().color()

        # 매핑된 아이템은 같은 색, 매핑 안 된 건 다른 색
        assert mapped_0 == mapped_2, "매핑된 아이템들은 같은 색상이어야 함"
        assert mapped_0 != normal_1, (
            "매핑된 아이템과 매핑 안 된 아이템의 색이 달라야 함. "
            f"둘 다 {mapped_0.name()} = 색 변화 없음 (회귀!)"
        )

    def test_mapped_slide_uses_accent_color_not_default(
        self, preview_panel: SlidePreviewPanel
    ):
        """매핑된 슬라이드 foreground는 명시적으로 액센트 컬러 계열이어야 함.

        단순히 '달라야 함'이 아니라 의도된 파란색인지 확인해서, 향후 누군가
        매핑 색상 대신 disabled(회색)로 바꾸는 실수를 잡는다.
        """
        preview_panel.set_mapped_slides({1})
        mapped_color = preview_panel._list.item(1).foreground().color()

        # 파란색 계열 (blue > red and blue > green)
        assert mapped_color.blue() > mapped_color.red(), (
            f"매핑 색상은 파란색 계열이어야 함. 현재: {mapped_color.name()}"
        )
        assert mapped_color.blue() > 128, (
            f"파란 채널이 충분히 강해야 함. 현재: blue={mapped_color.blue()}"
        )

    def test_unmapped_slide_has_normal_color(self, preview_panel: SlidePreviewPanel):
        """매핑 안 된 슬라이드는 회색(또는 기본) 계열"""
        preview_panel.set_mapped_slides({0})
        normal_color = preview_panel._list.item(1).foreground().color()

        # 무채색에 가까움 (r ≈ g ≈ b)
        channels = [normal_color.red(), normal_color.green(), normal_color.blue()]
        spread = max(channels) - min(channels)
        assert spread < 30, (
            f"매핑 안 된 색은 무채색(회색)에 가까워야 함. "
            f"현재: {normal_color.name()}, spread={spread}"
        )

    def test_unmapping_resets_color(self, preview_panel: SlidePreviewPanel):
        """매핑 해제 시 색상도 원래대로 돌아가야 함."""
        preview_panel.set_mapped_slides({0})
        mapped_color = preview_panel._list.item(0).foreground().color()

        preview_panel.set_mapped_slides(set())  # 전체 해제
        after_unmap = preview_panel._list.item(0).foreground().color()

        assert mapped_color != after_unmap, (
            "매핑 해제 후에도 같은 색이 유지됨 (회귀!)"
        )


class TestSlideMappingLabel:
    """매핑 표시 텍스트 회귀 방지 (commit 365fd97, c006da7)"""

    def test_mapped_slide_label_contains_dot(self, preview_panel: SlidePreviewPanel):
        """매핑된 슬라이드 레이블에 '●' 포함"""
        preview_panel.set_mapped_slides({1})
        assert "●" in preview_panel._list.item(1).text()

    def test_mapped_slide_label_has_no_emoji(self, preview_panel: SlidePreviewPanel):
        """매핑 레이블에 '🔗' 또는 유사 이모지가 있으면 안 됨 (과거 복구 방지)"""
        preview_panel.set_mapped_slides({0, 1, 2})
        for i in range(3):
            text = preview_panel._list.item(i).text()
            assert "🔗" not in text, f"Slide {i+1}에 🔗 이모지 발견: {text!r}"

    def test_unmapped_slide_label_has_no_dot(self, preview_panel: SlidePreviewPanel):
        """매핑 안 된 슬라이드 레이블에는 '●' 없음"""
        preview_panel.set_mapped_slides({1})
        assert "●" not in preview_panel._list.item(0).text()
        assert "●" not in preview_panel._list.item(2).text()

    def test_mapped_label_format_stable(self, preview_panel: SlidePreviewPanel):
        """매핑 레이블 형식: 'Slide N ●' (숫자 포함)"""
        preview_panel.set_mapped_slides({0})
        text = preview_panel._list.item(0).text()
        assert text.startswith("Slide 1"), (
            f"매핑 레이블이 'Slide N'으로 시작해야 함. 현재: {text!r}"
        )
        assert "●" in text


# =============================================================================
# Cross-cutting: Stylesheet vs programmatic color precedence
# =============================================================================


class TestStylesheetPrecedenceRegression:
    """QListWidget::item stylesheet이 setBackground를 덮는다는 사실을
    주석/문서에만 기록하는 게 아니라 테스트로 잠그기.

    과거 버그: 매핑된 아이템의 setBackground()가 동작 안 함을 한참 디버깅함.
    이 테스트는 우리가 '배경' 대신 '텍스트' 색상을 쓰는 결정을 강제한다.
    """

    def test_list_item_css_does_not_hardcode_background_color(
        self, preview_panel: SlidePreviewPanel
    ):
        """슬라이드 리스트 stylesheet에 명시적 'background-color: #XXX'가 있으면
        setBackground가 덮여서 매핑 표시가 안 될 수 있음.

        현재는 ::item background를 transparent로 둬서 setBackground()를 다시
        쓸 수 있게 되어 있음. 명시적 불투명 색상이 들어오면 경고.
        """
        sheet = preview_panel._list.styleSheet()
        # ::item 섹션에 transparent 또는 기본값만 허용
        item_section_match = re.search(
            r"QListWidget::item\s*\{([^}]*)\}", sheet
        )
        assert item_section_match, "QListWidget::item 셀렉터가 있어야 함"

        item_css = item_section_match.group(1)
        # 불투명 배경이면 경고 (transparent는 허용)
        bg_match = re.search(r"background(?:-color)?\s*:\s*([^;]+);", item_css)
        if bg_match:
            value = bg_match.group(1).strip().lower()
            assert value == "transparent", (
                f"QListWidget::item에 불투명 background가 설정됨: {value!r}. "
                "이 경우 setBackground()가 덮여서 매핑 표시가 안 됨. "
                "transparent로 바꾸거나 setForeground()를 사용하세요."
            )
