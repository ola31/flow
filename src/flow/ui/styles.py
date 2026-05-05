"""Flow 디자인 토큰 및 글로벌 스타일시트

모든 색상·스페이싱·타이포그래피 값은 여기서 정의한다.
위젯 코드에서는 이 상수를 import해서 사용할 것.

디자인 언어: Linear-inspired (https://linear.app)
- 차가운 톤의 거의 검정 배경 (#08090A)
- 보더는 솔리드 다크가 아닌 반투명 흰색 (rgba(255,255,255,0.05~0.08))
- 표면은 흰색 opacity 스태킹으로 깊이 표현 (페이지→패널→카드→호버)
- 액센트(인디고 #5E6AD2)는 화면당 1개의 진짜 Primary CTA에만 풀 채움 사용
  나머지 버튼/배지/카드는 Ghost(rgba 0.02) ~ Subtle(rgba 0.04~0.05)
- 타이포: Pretendard Variable (한글+영문 통합 가변 폰트)
- 가중치 510(Linear 시그니처)을 기본 UI 가중치로

참고: rgba 토큰은 Qt stylesheet에서만 사용. QColor() 등 Python 코드에선
솔리드 hex 폴백(BORDER, BORDER_FOCUS)을 사용할 것.
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
# Linear 실측값 그대로 (https://linear.app DESIGN.md)

# 배경 — 흰색 opacity 스태킹 모델 (페이지→패널→카드→호버)
BG_DEEP      = "#08090A"   # 윈도우 배경 (marketing black)
BG_SURFACE   = "#0F1011"   # 패널·사이드바
BG_ELEVATED  = "#191A1B"   # 카드·올린 표면
BG_HOVER     = "#28282C"   # 호버 상태

# 입력 — 패널과 동일 톤(평평하게)
BG_INPUT     = "#0F1011"

# 보더 — 솔리드 hex (QColor용 폴백)
BORDER       = "#23252A"   # 솔리드 보더 (분명한 분리 필요 시)
BORDER_FOCUS = "#3E3E44"

# 보더 — 반투명 흰색 (Qt stylesheet에서 권장: 어두운 배경에서 더 자연스러움)
BORDER_SUBTLE_RGBA   = "rgba(255, 255, 255, 0.05)"  # 기본 헤어라인
BORDER_STANDARD_RGBA = "rgba(255, 255, 255, 0.08)"  # 카드/입력 보더

# 표면 — 버튼 배경의 흰색 오버레이 단계
SURFACE_GHOST   = "rgba(255, 255, 255, 0.02)"  # 기본 버튼 (거의 안 보임)
SURFACE_SUBTLE  = "rgba(255, 255, 255, 0.04)"  # 강조 버튼
SURFACE_RAISED  = "rgba(255, 255, 255, 0.05)"  # 툴바 버튼·호버
SURFACE_HOVER   = "rgba(255, 255, 255, 0.07)"  # 강조 호버

# 텍스트 — Linear 4-tier 정확 매칭
TEXT_PRIMARY   = "#F7F8F8"  # 본문·제목 (거의 흰색, 눈 피로 방지)
TEXT_SECONDARY = "#D0D6E0"  # 부가 정보·설명 (실버 그레이, 충분한 가독성)
TEXT_TERTIARY  = "#8A8F98"  # 메타데이터·플레이스홀더
TEXT_QUAT      = "#62666D"  # 비활성·타임스탬프
TEXT_INVERSE   = "#08090A"  # 액센트 위 텍스트

# 액센트 — Linear 인디고 (브랜드 + 인터랙티브 두 변형)
ACCENT         = "#5E6AD2"   # 브랜드: Primary CTA 배경
ACCENT_INTER   = "#7170FF"   # 인터랙티브: 링크·활성 상태 (조금 더 밝음)
ACCENT_HOVER   = "#828FFF"   # 액센트 위 호버 (가장 밝음)
ACCENT_MUTED   = "#1A1F35"   # 액센트 배경 (선택된 카드 등)
ACCENT_SURFACE = "#252D52"   # 액센트 표면 (한 단계 위)

# 시맨틱 — 상태 색상 (Linear의 status indicator)
GREEN          = "#10B981"   # 성공·매핑 완료 (Linear emerald)
GREEN_MUTED    = "#0D2A1F"
AMBER          = "#F5A623"   # 경고·미완성
AMBER_MUTED    = "#231A0A"
RED            = "#EB5757"   # 라이브·위험
RED_MUTED      = "#2A1416"
RED_HOVER      = "#D44949"

# ─── 핫스팟 상태 색상 (RGBA 튜플) ────────────────────────────────────────────

HOTSPOT_DEFAULT_FILL    = (245, 166, 35, 90)      # 앰버 — 매핑 없음
HOTSPOT_SELECTED_FILL   = (94, 106, 210, 110)     # 액센트 인디고 — 선택됨
HOTSPOT_MAPPED_FILL     = (16, 185, 129, 100)     # 그린 — 매핑 완료
HOTSPOT_UNMAPPED_BORDER = (245, 166, 35, 180)     # 앰버 점선 — 미매핑 경고

# ─── 스페이싱 ────────────────────────────────────────────────────────────────

SP_XS  = 4
SP_SM  = 8
SP_MD  = 12
SP_LG  = 16
SP_XL  = 24
SP_2XL = 32

# ─── 타이포그래피 ────────────────────────────────────────────────────────────

# Pretendard 우선, 시스템 한글 폰트 폴백
FONT_FAMILY = (
    "'Pretendard Variable', 'Pretendard', "
    "-apple-system, 'Apple SD Gothic Neo', 'Malgun Gothic', "
    "'Segoe UI', 'Inter', sans-serif"
)

# 사이즈 — 8단계 hierarchy (2XS → DISPLAY)
FONT_2XS     = 10   # 메타·타임스탬프
FONT_XS      = 11   # 라벨·캡션
FONT_SM      = 12   # 본문 기본
FONT_MD      = 13   # 강조 본문·리스트 제목
FONT_LG      = 15   # 카드 헤더·다이얼로그 본문 강조
FONT_TITLE   = 18   # 패널 섹션 헤더
FONT_HEAD    = 20   # 다이얼로그·EmptyState 제목
FONT_DISPLAY = 24   # 페이지 최상위 헤드라인

# 가중치 — Linear의 시그니처는 510 (regular와 medium 사이)
# Pretendard Variable은 모든 weight 지원
FW_REGULAR = 400   # 본문
FW_MEDIUM  = 510   # UI 기본 (Linear 시그니처)
FW_SEMI    = 590   # 강조·헤딩 (최대값, 700/bold는 사용 안 함)

# ─── 보더 라디우스 ───────────────────────────────────────────────────────────

RADIUS_SM   = 4
RADIUS_MD   = 6
RADIUS_LG   = 8
RADIUS_XL   = 12
RADIUS_PILL = 9999

# ─── 글로벌 스타일시트 ──────────────────────────────────────────────────────
# Linear의 핵심: 버튼 기본은 ghost (rgba 0.02), 솔리드 채움 안 씀
# 보더는 반투명 흰색, 호버는 흰색 opacity 한 단계 올리기

GLOBAL_STYLESHEET = f"""
    QMainWindow {{ background-color: {BG_DEEP}; }}
    QWidget {{
        color: {TEXT_PRIMARY};
        font-family: {FONT_FAMILY};
        font-weight: {FW_REGULAR};
    }}

    /* 툴팁 — 어두운 테마 매칭. 기본은 검정 박스라 디자인을 깨뜨림. */
    QToolTip {{
        background-color: {BG_ELEVATED};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER_STANDARD_RGBA};
        border-radius: {RADIUS_SM}px;
        padding: 4px 8px;
        font-size: {FONT_SM}px;
    }}

    QSplitter::handle {{ background-color: {BG_SURFACE}; }}
    QSplitter::handle:horizontal {{ width: 1px; }}
    QSplitter::handle:vertical {{ height: 1px; }}

    /* 툴바 — Subtle 톤 (rgba white 0.05) */
    QWidget#CustomToolbar {{
        background-color: {BG_SURFACE};
        border-bottom: 1px solid {BORDER_SUBTLE_RGBA};
    }}
    QToolButton {{
        background-color: transparent;
        padding: {SP_SM}px {SP_MD}px;
        border-radius: {RADIUS_MD}px;
        font-weight: {FW_MEDIUM};
        font-size: {FONT_SM}px;
        color: {TEXT_SECONDARY};
        border: 1px solid transparent;
    }}
    QToolButton:hover {{
        background-color: {SURFACE_RAISED};
        color: {TEXT_PRIMARY};
    }}
    QToolButton:pressed {{ background-color: {SURFACE_GHOST}; }}
    QToolButton:checked {{
        background-color: {SURFACE_SUBTLE};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER_STANDARD_RGBA};
    }}
    QToolButton:disabled {{ color: {TEXT_QUAT}; }}

    QStatusBar {{
        background-color: {BG_SURFACE};
        color: {TEXT_QUAT};
        font-size: {FONT_SM}px;
        border-top: 1px solid {BORDER_SUBTLE_RGBA};
    }}

    /* 기본 버튼 — Ghost (Linear의 기본). 솔리드 채움은 Primary 클래스에만. */
    QPushButton {{
        background-color: {SURFACE_GHOST};
        border-radius: {RADIUS_MD}px;
        padding: {SP_SM}px {SP_LG}px;
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER_STANDARD_RGBA};
        font-weight: {FW_MEDIUM};
        font-size: {FONT_SM}px;
    }}
    QPushButton:hover {{
        background-color: {SURFACE_SUBTLE};
        border-color: {BORDER_STANDARD_RGBA};
    }}
    QPushButton:pressed {{ background-color: {SURFACE_GHOST}; }}
    QPushButton:disabled {{
        color: {TEXT_QUAT};
        background-color: transparent;
        border-color: {BORDER_SUBTLE_RGBA};
    }}

    /* Primary CTA — 화면당 1개. 위젯에서 setProperty("variant", "primary")로 활성 */
    QPushButton[variant="primary"] {{
        background-color: {ACCENT};
        color: white;
        border: 1px solid {ACCENT};
    }}
    QPushButton[variant="primary"]:hover {{
        background-color: {ACCENT_HOVER};
        border-color: {ACCENT_HOVER};
    }}
    QPushButton[variant="primary"]:pressed {{
        background-color: {ACCENT};
    }}
    QPushButton[variant="primary"]:disabled {{
        background-color: {ACCENT_MUTED};
        color: {TEXT_TERTIARY};
        border-color: {ACCENT_MUTED};
    }}

    /* Danger 변형 (삭제 등) */
    QPushButton[variant="danger"] {{
        background-color: {SURFACE_GHOST};
        color: {RED};
        border: 1px solid {BORDER_STANDARD_RGBA};
    }}
    QPushButton[variant="danger"]:hover {{
        background-color: {RED_MUTED};
        border-color: {RED};
        color: {RED};
    }}

    QMenu {{
        background-color: {BG_ELEVATED};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER_STANDARD_RGBA};
        border-radius: {RADIUS_MD}px;
        padding: 4px;
    }}
    QMenu::item {{
        padding: {SP_SM}px {SP_XL}px;
        border-radius: {RADIUS_SM}px;
        font-weight: {FW_MEDIUM};
        font-size: {FONT_SM}px;
    }}
    QMenu::item:selected {{
        background-color: {SURFACE_RAISED};
        color: {TEXT_PRIMARY};
    }}

    /* 스크롤바 — 평소 얇게, 호버 시 살짝 두드러지게 */
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
        border: 1px solid {BORDER_STANDARD_RGBA};
    }}
    QDialog QLabel, QMessageBox QLabel {{
        color: {TEXT_PRIMARY}; background-color: transparent;
    }}

    QLineEdit, QTextEdit, QPlainTextEdit, QAbstractItemView {{
        background-color: {SURFACE_GHOST};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER_STANDARD_RGBA};
        border-radius: {RADIUS_SM}px;
        selection-background-color: {ACCENT};
        selection-color: white;
        font-weight: {FW_REGULAR};
    }}
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
        border-color: {ACCENT_INTER};
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
        border: 1px solid transparent;
    }}
    QToolButton:hover {{
        background-color: {SURFACE_RAISED};
        color: {TEXT_PRIMARY};
    }}
    QToolButton:pressed {{ background-color: {SURFACE_GHOST}; }}
    QToolButton:disabled {{ color: {TEXT_QUAT}; }}
"""

TOOLBAR_DEFAULT = f"""
    QWidget#CustomToolbar {{
        background-color: {BG_SURFACE};
        border-bottom: 1px solid {BORDER_SUBTLE_RGBA};
    }}
    {_TOOLBAR_BUTTON_BASE}
    QToolButton:checked {{
        background-color: {SURFACE_SUBTLE};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER_STANDARD_RGBA};
    }}
"""

TOOLBAR_LIVE = f"""
    QWidget#CustomToolbar {{
        background-color: {BG_SURFACE};
        border-top: 3px solid {RED};
        border-bottom: 1px solid {BORDER_SUBTLE_RGBA};
    }}
    {_TOOLBAR_BUTTON_BASE}
    QToolButton:checked {{
        background-color: {SURFACE_SUBTLE};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER_STANDARD_RGBA};
    }}
"""

TOOLBAR_SONG_EDIT = f"""
    QWidget#CustomToolbar {{
        background-color: {BG_SURFACE};
        border-top: 3px solid {ACCENT};
        border-bottom: 1px solid {BORDER_SUBTLE_RGBA};
    }}
    {_TOOLBAR_BUTTON_BASE}
    QToolButton:checked {{
        background-color: {SURFACE_SUBTLE};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER_STANDARD_RGBA};
    }}
"""
