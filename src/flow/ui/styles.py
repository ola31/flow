"""Flow 디자인 토큰 및 글로벌 스타일시트

모든 색상·스페이싱·타이포그래피 값은 여기서 정의한다.
위젯 코드에서는 이 상수를 import해서 사용할 것.

디자인 언어: Linear-inspired (https://linear.app)
- 차가운 톤의 거의 검정에 가까운 배경 (#08090A)
- 보더는 거의 안 보이고, 깊이는 배경 톤 차이로 표현
- 액센트는 selection/CTA에만 절제해 사용 (인디고 #4F69E0)
- 타이포: Pretendard Variable (번들), 미설치 시 시스템 폴백
"""

from __future__ import annotations

from pathlib import Path

_PRETENDARD_PATH = (
    Path(__file__).parent.parent / "resources" / "PretendardVariable.ttf"
)
_PRETENDARD_LOADED: bool = False


def ensure_fonts_loaded() -> None:
    """Pretendard Variable 폰트를 앱에 등록.

    main.py에서 QApplication 생성 직후 1회 호출. 폰트 파일이 없거나
    로드 실패 시 조용히 폴백 (FONT_FAMILY가 시스템 폰트 폴백 체인을
    포함하므로 앱은 정상 동작).
    """
    global _PRETENDARD_LOADED
    if _PRETENDARD_LOADED:
        return
    if not _PRETENDARD_PATH.exists():
        return
    try:
        from PySide6.QtGui import QFontDatabase
        font_id = QFontDatabase.addApplicationFont(str(_PRETENDARD_PATH))
        _PRETENDARD_LOADED = font_id >= 0
    except Exception:
        pass

# ─── 컬러 팔레트 ────────────────────────────────────────────────────────────
# 차가운 다크 — 거의 검정에 미묘한 푸른 기, 단계 간 명확한 명도 차이

# 배경 5단계 (어두운 → 밝은 표면)
BG_DEEP      = "#08090A"   # 윈도우 배경 (가장 어두움)
BG_SURFACE   = "#0E0F11"   # 사이드바·패널
BG_ELEVATED  = "#16181B"   # 카드·올린 표면
BG_HOVER     = "#1C1E22"   # 호버 상태
BG_INPUT     = "#0E0F11"   # 입력 필드 (서피스와 동일 톤)

# 보더 — 거의 안 보이게, 영역 구분은 배경 톤 차이로
BORDER       = "#1F2125"   # 기본 보더 (헤어라인)
BORDER_FOCUS = "#2E3035"   # 호버/포커스 보더

# 텍스트 — 콘텐츠 가독성 우선, 명확한 3단계 위계
TEXT_PRIMARY   = "#F7F8F8"  # 본문·제목 (밝은 오프화이트)
TEXT_SECONDARY = "#9498A1"  # 부가 정보 (충분한 대비)
TEXT_TERTIARY  = "#62666D"  # 비활성·힌트
TEXT_INVERSE   = "#08090A"  # 액센트 위 텍스트

# 액센트 — Linear 인디고. 절제되어 selection/CTA에만 사용
ACCENT         = "#4F69E0"  # 주 액센트
ACCENT_HOVER   = "#6478E8"  # 액센트 호버
ACCENT_MUTED   = "#1A1F35"  # 액센트 배경 (선택된 카드 등)
ACCENT_SURFACE = "#252D52"  # 액센트 표면 (더 밝은)

# 시맨틱 — 상태 색상
GREEN          = "#3CCB7F"  # 성공·매핑 완료·준비됨
GREEN_MUTED    = "#102218"  # 성공 배경
AMBER          = "#F5A623"  # 경고·미완성
AMBER_MUTED    = "#231A0A"  # 경고 배경
RED            = "#EB5757"  # 라이브·위험·삭제
RED_MUTED      = "#2A1416"  # 라이브/위험 배경
RED_HOVER      = "#D44949"  # 위험 호버

# ─── 핫스팟 상태 색상 (RGBA 튜플) ────────────────────────────────────────────

HOTSPOT_DEFAULT_FILL    = (245, 166, 35, 150)     # 앰버 — 매핑 없음
HOTSPOT_SELECTED_FILL   = (79, 105, 224, 180)     # 액센트 인디고 — 선택됨
HOTSPOT_MAPPED_FILL     = (60, 203, 127, 160)     # 그린 — 매핑 완료
HOTSPOT_UNMAPPED_BORDER = (245, 166, 35, 220)     # 앰버 점선 — 미매핑 경고

# ─── 스페이싱 ────────────────────────────────────────────────────────────────

SP_XS  = 4
SP_SM  = 8
SP_MD  = 12
SP_LG  = 16
SP_XL  = 24
SP_2XL = 32

# ─── 타이포그래피 ────────────────────────────────────────────────────────────

# Pretendard 우선, 시스템 한글 폰트 폴백
# Pretendard가 시스템에 설치되어 있지 않으면 자동으로 다음 폰트로 폴백됨
FONT_FAMILY = (
    "'Pretendard Variable', 'Pretendard', "
    "-apple-system, 'Apple SD Gothic Neo', 'Malgun Gothic', "
    "'Segoe UI', 'Inter', sans-serif"
)

# 사이즈 — Linear는 밀도 우선 (공간보다 정보량)
FONT_XS    = 10
FONT_SM    = 11
FONT_MD    = 12
FONT_LG    = 13
FONT_XL    = 14
FONT_2XL   = 16
FONT_TITLE = 22

# 가중치 (Pretendard Variable 기준; 폴백 폰트에서도 호환)
FW_REGULAR = 440
FW_MEDIUM  = 520
FW_SEMI    = 600

# ─── 보더 라디우스 ───────────────────────────────────────────────────────────

RADIUS_SM   = 4
RADIUS_MD   = 6
RADIUS_LG   = 8
RADIUS_XL   = 10
RADIUS_PILL = 9999

# ─── 글로벌 스타일시트 ──────────────────────────────────────────────────────

GLOBAL_STYLESHEET = f"""
    QMainWindow {{ background-color: {BG_DEEP}; }}
    QWidget {{
        color: {TEXT_PRIMARY};
        font-family: {FONT_FAMILY};
        font-weight: {FW_REGULAR};
    }}

    QSplitter::handle {{ background-color: {BG_SURFACE}; }}
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
        font-weight: {FW_MEDIUM};
        font-size: {FONT_SM}px;
        color: {TEXT_SECONDARY};
    }}
    QToolButton:hover {{ background-color: {BG_HOVER}; color: {TEXT_PRIMARY}; }}
    QToolButton:pressed {{ background-color: {BG_DEEP}; }}
    QToolButton:checked {{ background-color: {ACCENT}; color: #ffffff; }}
    QToolButton:disabled {{ color: {TEXT_TERTIARY}; }}

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
        font-weight: {FW_MEDIUM};
    }}
    QPushButton:hover {{
        background-color: {BG_HOVER};
        border-color: {BORDER_FOCUS};
    }}
    QPushButton:pressed {{ background-color: {BG_DEEP}; }}
    QPushButton:disabled {{
        color: {TEXT_TERTIARY};
        background-color: {BG_SURFACE};
        border-color: {BORDER};
    }}

    QMenu {{
        background-color: {BG_ELEVATED};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER_FOCUS};
        border-radius: {RADIUS_MD}px;
        padding: 4px;
    }}
    QMenu::item {{
        padding: {SP_SM}px {SP_XL}px;
        border-radius: {RADIUS_SM}px;
    }}
    QMenu::item:selected {{ background-color: {BG_HOVER}; color: {TEXT_PRIMARY}; }}

    /* 스크롤바 — 평소 얇게, 호버 시 살짝 두껍게 */
    QScrollBar:vertical {{
        border: none; background: transparent; width: 8px; margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background: {BORDER_FOCUS};
        min-height: 24px;
        border-radius: 4px;
    }}
    QScrollBar::handle:vertical:hover {{ background: {TEXT_TERTIARY}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}

    QScrollBar:horizontal {{
        border: none; background: transparent; height: 8px; margin: 0;
    }}
    QScrollBar::handle:horizontal {{
        background: {BORDER_FOCUS};
        min-width: 24px;
        border-radius: 4px;
    }}
    QScrollBar::handle:horizontal:hover {{ background: {TEXT_TERTIARY}; }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: none; }}

    QDialog, QMessageBox {{
        background-color: {BG_SURFACE};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER};
    }}
    QDialog QLabel, QMessageBox QLabel {{
        color: {TEXT_PRIMARY}; background-color: transparent;
    }}
    QDialog QPushButton, QMessageBox QPushButton {{
        background-color: {BG_ELEVATED};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER};
        padding: {SP_SM}px {SP_LG}px;
        font-weight: {FW_MEDIUM};
    }}
    QDialog QPushButton:hover, QMessageBox QPushButton:hover {{
        background-color: {BG_HOVER};
        border-color: {BORDER_FOCUS};
    }}

    QLineEdit, QTextEdit, QPlainTextEdit, QAbstractItemView {{
        background-color: {BG_INPUT};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER};
        border-radius: {RADIUS_SM}px;
        selection-background-color: {ACCENT};
        selection-color: #ffffff;
        font-weight: {FW_REGULAR};
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
        font-weight: {FW_MEDIUM};
        font-size: {FONT_SM}px;
        color: {TEXT_SECONDARY};
    }}
    QToolButton:hover {{ background-color: {BG_HOVER}; color: {TEXT_PRIMARY}; }}
    QToolButton:pressed {{ background-color: {BG_DEEP}; }}
    QToolButton:disabled {{ color: {TEXT_TERTIARY}; }}
"""

TOOLBAR_DEFAULT = f"""
    QWidget#CustomToolbar {{
        background-color: {BG_SURFACE};
        border-bottom: 1px solid {BORDER};
    }}
    {_TOOLBAR_BUTTON_BASE}
    QToolButton:checked {{ background-color: {ACCENT}; color: #ffffff; }}
"""

TOOLBAR_LIVE = f"""
    QWidget#CustomToolbar {{
        background-color: {RED_MUTED};
        border-bottom: 2px solid {RED};
    }}
    {_TOOLBAR_BUTTON_BASE}
    QToolButton:checked {{ background-color: {RED}; color: #ffffff; }}
"""

TOOLBAR_SONG_EDIT = f"""
    QWidget#CustomToolbar {{
        background-color: {ACCENT_SURFACE};
        border-bottom: 2px solid {ACCENT};
    }}
    {_TOOLBAR_BUTTON_BASE}
    QToolButton:checked {{ background-color: {ACCENT}; color: #ffffff; }}
"""
