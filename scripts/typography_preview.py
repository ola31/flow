"""Typography preview — 신규 토큰 시각 확인용 1회성 도구.

실행:
    python scripts/typography_preview.py

좌측: 신규 토큰 스케일 (10/11/12/13/15/18/22/28)
우측: 실제 화면 맥락 시뮬레이션 (워크스페이스/프로젝트/다이얼로그 헤더)

본 코드는 건드리지 않음. 토큰 값을 조정하려면 SCALE 딕셔너리만 수정.
"""

from __future__ import annotations

import sys
from pathlib import Path

# flow 패키지 import 가능하게
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QVBoxLayout,
    QWidget,
)

from flow.ui.styles import (
    BG_DEEP,
    BG_ELEVATED,
    BG_SURFACE,
    BORDER_SUBTLE_RGBA,
    FONT_FAMILY,
    FW_MEDIUM,
    FW_REGULAR,
    FW_SEMI,
    GLOBAL_STYLESHEET,
    SP_LG,
    SP_MD,
    SP_SM,
    SP_XL,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TEXT_TERTIARY,
    ensure_fonts_loaded,
)

# ─── 신규 토큰 스케일 (조정해보고 싶으면 여기만 수정) ────────────────────────

SCALE = [
    ("FONT_2XS",     10, FW_REGULAR, "메타·타임스탬프"),
    ("FONT_XS",      11, FW_MEDIUM,  "라벨·캡션"),
    ("FONT_SM",      12, FW_REGULAR, "본문 기본"),
    ("FONT_MD",      13, FW_MEDIUM,  "강조 본문·리스트 제목"),
    ("FONT_LG",      15, FW_SEMI,    "카드 헤더·다이얼로그 본문 강조"),
    ("FONT_TITLE",   18, FW_SEMI,    "패널 섹션 헤더"),
    ("FONT_HEAD",    20, FW_SEMI,    "다이얼로그·EmptyState 제목"),
    ("FONT_DISPLAY", 24, FW_SEMI,    "페이지 최상위 헤드라인"),
]

SAMPLE_KO = "2026년 4월 4주차 모임 슬라이드"
SAMPLE_EN = "The quick brown fox jumps over"
SAMPLE_LONG_KO = "2026년 4월 마지막 주 청년부 정기모임"


def _font(size: int, weight: int) -> QFont:
    f = QFont("Pretendard Variable", size)
    f.setWeight(QFont.Weight(weight))
    return f


class ScalePanel(QWidget):
    """좌측: 토큰 스케일 한 줄씩."""

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SP_XL, SP_XL, SP_XL, SP_XL)
        layout.setSpacing(SP_LG)

        title = QLabel("Typography scale")
        title.setFont(_font(13, FW_SEMI))
        title.setStyleSheet(f"color: {TEXT_TERTIARY};")
        layout.addWidget(title)

        for name, size, weight, role in SCALE:
            row = self._make_row(name, size, weight, role)
            layout.addWidget(row)

        layout.addStretch()

    def _make_row(self, name: str, size: int, weight: int, role: str) -> QWidget:
        row = QWidget()
        v = QVBoxLayout(row)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(2)

        meta = QLabel(f"{name}  ·  {size}px  ·  weight {weight}  ·  {role}")
        meta.setFont(_font(10, FW_REGULAR))
        meta.setStyleSheet(f"color: {TEXT_TERTIARY};")
        v.addWidget(meta)

        sample = QLabel(f"{SAMPLE_KO}    {SAMPLE_EN}")
        sample.setFont(_font(size, weight))
        sample.setStyleSheet(f"color: {TEXT_PRIMARY};")
        v.addWidget(sample)

        return row


class ContextPanel(QWidget):
    """우측: 실제 사용 맥락 시뮬레이션."""

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SP_XL, SP_XL, SP_XL, SP_XL)
        layout.setSpacing(SP_XL)

        section_title = QLabel("In context")
        section_title.setFont(_font(13, FW_SEMI))
        section_title.setStyleSheet(f"color: {TEXT_TERTIARY};")
        layout.addWidget(section_title)

        layout.addWidget(self._workspace_card())
        layout.addWidget(self._project_card())
        layout.addWidget(self._dialog_card())
        layout.addWidget(self._panel_card())
        layout.addStretch()

    _card_counter = 0

    def _card(self, body_widget: QWidget) -> QWidget:
        ContextPanel._card_counter += 1
        name = f"PreviewCard{ContextPanel._card_counter}"
        card = QWidget()
        card.setObjectName(name)
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        card.setStyleSheet(
            f"QWidget#{name} {{ "
            f"background-color: {BG_ELEVATED}; "
            f"border: 1px solid {BORDER_SUBTLE_RGBA}; "
            f"border-radius: 8px; "
            f"}}"
        )
        wrap = QVBoxLayout(card)
        wrap.setContentsMargins(SP_XL, SP_XL, SP_XL, SP_XL)
        wrap.setSpacing(SP_SM)
        wrap.addWidget(body_widget)
        return card

    def _workspace_card(self) -> QWidget:
        body = QWidget()
        v = QVBoxLayout(body)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(SP_SM)

        kicker = QLabel("WORKSPACE")
        kicker.setFont(_font(10, FW_MEDIUM))
        kicker.setStyleSheet(f"color: {TEXT_TERTIARY}; letter-spacing: 1px;")
        v.addWidget(kicker)

        head = QLabel("Workspaces")
        head.setFont(_font(24, FW_SEMI))
        head.setStyleSheet(f"color: {TEXT_PRIMARY};")
        v.addWidget(head)

        sub = QLabel("최근 작업한 워크스페이스를 열거나 새로 만드세요")
        sub.setFont(_font(13, FW_REGULAR))
        sub.setStyleSheet(f"color: {TEXT_SECONDARY};")
        v.addWidget(sub)

        return self._card(body)

    def _project_card(self) -> QWidget:
        body = QWidget()
        v = QVBoxLayout(body)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(SP_SM)

        head = QLabel(SAMPLE_LONG_KO)
        head.setFont(_font(24, FW_SEMI))
        head.setStyleSheet(f"color: {TEXT_PRIMARY};")
        v.addWidget(head)

        meta = QLabel("12 songs  ·  마지막 수정 2시간 전")
        meta.setFont(_font(11, FW_REGULAR))
        meta.setStyleSheet(f"color: {TEXT_TERTIARY};")
        v.addWidget(meta)

        return self._card(body)

    def _dialog_card(self) -> QWidget:
        body = QWidget()
        v = QVBoxLayout(body)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(SP_SM)

        head = QLabel("워크스페이스 선택")
        head.setFont(_font(20, FW_SEMI))
        head.setStyleSheet(f"color: {TEXT_PRIMARY};")
        v.addWidget(head)

        body_text = QLabel(
            "사용할 워크스페이스 폴더를 고르세요. 폴더 안에 projects/와 library/가 자동으로 만들어집니다."
        )
        body_text.setFont(_font(13, FW_REGULAR))
        body_text.setStyleSheet(f"color: {TEXT_SECONDARY};")
        body_text.setWordWrap(True)
        v.addWidget(body_text)

        return self._card(body)

    def _panel_card(self) -> QWidget:
        body = QWidget()
        v = QVBoxLayout(body)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(SP_MD)

        section = QLabel("Setlist")
        section.setFont(_font(18, FW_SEMI))
        section.setStyleSheet(f"color: {TEXT_PRIMARY};")
        v.addWidget(section)

        # 곡 카드 시뮬
        for i, name in enumerate(["보통 길이의 곡 제목 예시", "짧은 곡", "조금 더 긴 곡 제목 예시"], 1):
            row = QWidget()
            row_name = f"PreviewSongRow{i}"
            row.setObjectName(row_name)
            row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            r = QVBoxLayout(row)
            r.setContentsMargins(SP_MD, SP_SM, SP_MD, SP_SM)
            r.setSpacing(2)
            row.setStyleSheet(
                f"QWidget#{row_name} {{ "
                f"background-color: {BG_SURFACE}; border-radius: 6px; "
                f"}}"
            )
            song = QLabel(f"{i:02d}  {name}")
            song.setFont(_font(13, FW_MEDIUM))
            song.setStyleSheet(f"color: {TEXT_PRIMARY};")
            r.addWidget(song)
            meta = QLabel("매핑 완료  ·  4 verses")
            meta.setFont(_font(10, FW_REGULAR))
            meta.setStyleSheet(f"color: {TEXT_TERTIARY};")
            r.addWidget(meta)
            v.addWidget(row)

        return self._card(body)


class PreviewWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Flow — Typography preview")
        self.resize(1280, 900)
        self.setStyleSheet(GLOBAL_STYLESHEET + f"""
            QMainWindow {{ background-color: {BG_DEEP}; }}
            QWidget {{ background-color: transparent; }}
        """)

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        scale = ScalePanel()
        scale.setObjectName("ScalePanel")
        scale.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        scale.setStyleSheet(
            f"QWidget#ScalePanel {{ background-color: {BG_DEEP}; }}"
        )
        scale.setMinimumWidth(560)

        ctx = ContextPanel()
        ctx.setObjectName("CtxPanel")
        ctx.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        ctx.setStyleSheet(
            f"QWidget#CtxPanel {{ "
            f"background-color: {BG_SURFACE}; "
            f"border-left: 1px solid {BORDER_SUBTLE_RGBA}; "
            f"}}"
        )

        layout.addWidget(scale, 1)
        layout.addWidget(ctx, 1)

        self.setCentralWidget(central)


def main() -> None:
    app = QApplication(sys.argv)
    ensure_fonts_loaded()
    app.setStyleSheet(f"* {{ font-family: {FONT_FAMILY}; }}")

    w = PreviewWindow()
    w.show()

    # ESC로 종료
    def keyPressEvent(event):
        if event.key() == Qt.Key.Key_Escape:
            app.quit()
        QMainWindow.keyPressEvent(w, event)
    w.keyPressEvent = keyPressEvent

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
