"""Flow 디자인 토큰 및 글로벌 스타일시트

모든 색상·스페이싱·타이포그래피 값은 여기서 정의한다.
위젯 코드에서는 이 상수를 import해서 사용할 것.
"""

from __future__ import annotations

# ─── 컬러 팔레트 ────────────────────────────────────────────────────────────
# 5단계 그레이 + 1 액센트 + 시맨틱 컬러

BG_DEEP      = "#121212"   # 가장 깊은 배경 (윈도우)
BG_SURFACE   = "#1a1a1a"   # 패널·사이드바 배경
BG_ELEVATED  = "#222222"   # 카드·올린 표면
BG_HOVER     = "#2a2a2a"   # 호버 상태
BG_INPUT     = "#1e1e1e"   # 입력 필드 배경

BORDER       = "#2e2e2e"   # 기본 보더
BORDER_FOCUS = "#404040"   # 호버/포커스 보더

TEXT_PRIMARY   = "#e8e8e8"  # 본문·제목
TEXT_SECONDARY = "#a0a0a0"  # 부가 정보
TEXT_TERTIARY  = "#606060"  # 비활성·힌트
TEXT_INVERSE   = "#121212"  # 밝은 배경 위 텍스트

ACCENT         = "#5b8def"  # 주 액센트 (선택, CTA, 링크)
ACCENT_HOVER   = "#4a7de0"  # 액센트 호버
ACCENT_MUTED   = "#1e2d4a"  # 액센트 배경 (선택된 카드 등)
ACCENT_SURFACE = "#172236"  # 액센트 표면 (더 어두운)

GREEN          = "#34d399"  # 성공·매핑 완료·준비됨
GREEN_MUTED    = "#1a2e24"  # 성공 배경
AMBER          = "#f59e0b"  # 경고·미완성
AMBER_MUTED    = "#2e2410"  # 경고 배경
RED            = "#ef4444"  # 라이브·위험·삭제
RED_MUTED      = "#2e1414"  # 라이브/위험 배경
RED_HOVER      = "#dc2626"  # 위험 호버

# ─── 핫스팟 상태 색상 (RGBA 튜플) ────────────────────────────────────────────

HOTSPOT_DEFAULT_FILL   = (245, 158, 11, 150)    # 앰버 — 매핑 없음
HOTSPOT_SELECTED_FILL  = (91, 141, 239, 180)    # 액센트 블루 — 선택됨
HOTSPOT_MAPPED_FILL    = (52, 211, 153, 160)    # 민트 그린 — 매핑 완료
HOTSPOT_UNMAPPED_BORDER = (245, 158, 11, 220)   # 앰버 점선 — 미매핑 경고

# ─── 스페이싱 ────────────────────────────────────────────────────────────────

SP_XS  = 4
SP_SM  = 8
SP_MD  = 12
SP_LG  = 16
SP_XL  = 24
SP_2XL = 32

# ─── 타이포그래피 ────────────────────────────────────────────────────────────

FONT_FAMILY = "'Malgun Gothic', 'Segoe UI', 'SF Pro Display', sans-serif"
FONT_XS   = 10
FONT_SM   = 11
FONT_MD   = 12
FONT_LG   = 13
FONT_XL   = 14
FONT_2XL  = 18
FONT_TITLE = 24

# ─── 보더 라디우스 ───────────────────────────────────────────────────────────

RADIUS_SM = 4
RADIUS_MD = 6
RADIUS_LG = 8
RADIUS_XL = 10
RADIUS_PILL = 9999

# ─── 글로벌 스타일시트 ──────────────────────────────────────────────────────

GLOBAL_STYLESHEET = f"""
    QMainWindow {{ background-color: {BG_DEEP}; }}
    QWidget {{ color: {TEXT_PRIMARY}; font-family: {FONT_FAMILY}; }}

    QSplitter::handle {{ background-color: {BORDER}; }}
    QSplitter::handle:horizontal {{ width: 1px; }}
    QSplitter::handle:vertical {{ height: 1px; }}

    QWidget#CustomToolbar {{
        background-color: {BG_SURFACE};
        border-bottom: 1px solid {BORDER};
    }}
    QToolButton {{
        background-color: transparent;
        padding: {SP_SM}px {SP_MD}px;
        border-radius: {RADIUS_MD}px;
        font-weight: 500;
        font-size: {FONT_SM}px;
        color: {TEXT_SECONDARY};
    }}
    QToolButton:hover {{ background-color: {BG_HOVER}; color: {TEXT_PRIMARY}; }}
    QToolButton:pressed {{ background-color: {BG_DEEP}; }}
    QToolButton:checked {{ background-color: {ACCENT}; color: {TEXT_INVERSE}; }}

    QStatusBar {{
        background-color: {BG_SURFACE};
        color: {TEXT_TERTIARY};
        font-size: {FONT_SM}px;
        border-top: 1px solid {BORDER};
    }}

    QPushButton {{
        background-color: {BG_ELEVATED};
        border-radius: {RADIUS_MD}px;
        padding: {SP_SM}px {SP_LG}px;
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER};
    }}
    QPushButton:hover {{ background-color: {BG_HOVER}; border-color: {BORDER_FOCUS}; }}
    QPushButton:pressed {{ background-color: {BG_DEEP}; }}

    QMenu {{
        background-color: {BG_ELEVATED};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER_FOCUS};
        border-radius: {RADIUS_MD}px;
    }}
    QMenu::item {{ padding: {SP_SM}px {SP_XL}px; }}
    QMenu::item:selected {{ background-color: {ACCENT_MUTED}; color: {ACCENT}; }}

    QScrollBar:vertical {{
        border: none; background: transparent; width: 6px; margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background: {BORDER_FOCUS}; min-height: 20px; border-radius: 3px;
    }}
    QScrollBar::handle:vertical:hover {{ background: {ACCENT}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}

    QScrollBar:horizontal {{
        border: none; background: transparent; height: 6px; margin: 0;
    }}
    QScrollBar::handle:horizontal {{
        background: {BORDER_FOCUS}; min-width: 20px; border-radius: 3px;
    }}
    QScrollBar::handle:horizontal:hover {{ background: {ACCENT}; }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: none; }}

    QDialog, QMessageBox {{
        background-color: {BG_SURFACE}; color: {TEXT_PRIMARY};
        border: 1px solid {BORDER_FOCUS};
    }}
    QDialog QLabel, QMessageBox QLabel {{
        color: {TEXT_PRIMARY}; background-color: transparent;
    }}
    QDialog QPushButton, QMessageBox QPushButton {{
        background-color: {BG_ELEVATED}; color: {TEXT_PRIMARY};
        border: 1px solid {BORDER_FOCUS}; padding: {SP_SM}px {SP_LG}px;
    }}
    QDialog QPushButton:hover, QMessageBox QPushButton:hover {{
        background-color: {BG_HOVER}; border-color: {ACCENT};
    }}

    QLineEdit, QTextEdit, QPlainTextEdit, QAbstractItemView {{
        background-color: {BG_INPUT}; color: {TEXT_PRIMARY};
        border: 1px solid {BORDER}; border-radius: {RADIUS_SM}px;
        selection-background-color: {ACCENT}; selection-color: white;
    }}
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
        border-color: {ACCENT};
    }}
"""

# ─── 모드별 툴바 스타일 ─────────────────────────────────────────────────────

_TOOLBAR_BUTTON_BASE = f"""
    QToolButton {{
        background-color: transparent;
        padding: {SP_SM}px {SP_MD}px;
        border-radius: {RADIUS_MD}px;
        font-weight: 500;
        font-size: {FONT_SM}px;
        color: {TEXT_SECONDARY};
    }}
    QToolButton:hover {{ background-color: {BG_HOVER}; color: {TEXT_PRIMARY}; }}
    QToolButton:pressed {{ background-color: {BG_DEEP}; }}
"""

TOOLBAR_DEFAULT = f"""
    QWidget#CustomToolbar {{
        background-color: {BG_SURFACE};
        border-bottom: 1px solid {BORDER};
    }}
    {_TOOLBAR_BUTTON_BASE}
    QToolButton:checked {{ background-color: {ACCENT}; color: {TEXT_INVERSE}; }}
"""

TOOLBAR_LIVE = f"""
    QWidget#CustomToolbar {{
        background-color: {RED_MUTED};
        border-bottom: 2px solid {RED};
    }}
    {_TOOLBAR_BUTTON_BASE}
    QToolButton:checked {{ background-color: {RED}; color: white; }}
"""

TOOLBAR_SONG_EDIT = f"""
    QWidget#CustomToolbar {{
        background-color: {ACCENT_SURFACE};
        border-bottom: 2px solid {ACCENT};
    }}
    {_TOOLBAR_BUTTON_BASE}
    QToolButton:checked {{ background-color: {ACCENT}; color: {TEXT_INVERSE}; }}
"""
