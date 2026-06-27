"""Markdown 작성 규칙 설명 도움말 다이얼로그 (메뉴 + 페이지 구성)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QStackedWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from flow.ui.styles import (
    ACCENT,
    ACCENT_HOVER,
    ACCENT_INTER,
    BG_DEEP,
    BG_ELEVATED,
    BG_SURFACE,
    BORDER_SUBTLE_RGBA,
    FONT_FAMILY,
    FONT_LG,
    FONT_MD,
    FONT_SM,
    RADIUS_MD,
    SP_LG,
    SP_MD,
    SP_SM,
    SP_XL,
    SURFACE_GHOST,
    SURFACE_SUBTLE,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TEXT_TERTIARY,
)

# ─── 페이지 본문 HTML ──────────────────────────────────────────────────────────
# QTextBrowser 안의 인라인 스타일은 styles.py 토큰을 문자열 보간으로 주입한다.

_PAGE_STYLE = f"""
<style>
  body {{
    font-family: {FONT_FAMILY};
    font-size: {FONT_MD}px;
    color: {TEXT_PRIMARY};
    line-height: 1.65;
  }}
  h2 {{
    margin: 0 0 14px 0;
    font-size: 22px;
    font-weight: 600;
    color: {TEXT_PRIMARY};
  }}
  h3 {{
    margin-top: 22px;
    margin-bottom: 6px;
    font-size: {FONT_LG}px;
    font-weight: 600;
    color: {TEXT_PRIMARY};
  }}
  p {{ margin: 6px 0; color: {TEXT_SECONDARY}; }}
  ul {{ margin: 4px 0 8px 18px; color: {TEXT_SECONDARY}; }}
  li {{ margin: 3px 0; }}
  b  {{ color: {TEXT_PRIMARY}; }}
  code {{
    font-family: 'JetBrains Mono', 'Menlo', 'Consolas', monospace;
    background: {BG_ELEVATED};
    color: {ACCENT_INTER};
    padding: 2px 6px;
    border-radius: 3px;
    font-size: 12px;
  }}
  pre {{
    font-family: 'JetBrains Mono', 'Menlo', 'Consolas', monospace;
    background: {BG_ELEVATED};
    color: {TEXT_PRIMARY};
    padding: 12px 14px;
    border-radius: {RADIUS_MD}px;
    margin: 8px 0 14px 0;
    white-space: pre-wrap;
    font-size: 12px;
    line-height: 1.55;
  }}
  .tip {{
    background: rgba(94, 106, 210, 0.08);
    border-left: 3px solid {ACCENT};
    padding: 10px 14px;
    margin: 12px 0;
    border-radius: 3px;
    color: {TEXT_SECONDARY};
  }}
  .muted {{ color: {TEXT_TERTIARY}; font-size: {FONT_SM}px; }}
</style>
"""

_PAGE_INTRO = _PAGE_STYLE + """
<h2>시작하기</h2>
<p>이 편집기는 <b>가사를 적으면 자동으로 발표용 슬라이드가 만들어지는</b> 도구입니다.
오른쪽 미리보기에서 결과를 바로 확인할 수 있어요.</p>

<h3>가장 기본적인 규칙</h3>
<ul>
  <li><b>빈 줄로 구분된 가사 한 덩어리 = 슬라이드 한 장</b></li>
  <li>한 슬라이드 안에서는 줄바꿈을 그대로 유지합니다</li>
</ul>

<h3>예시</h3>
<pre>첫 번째 슬라이드의 가사

두 번째 슬라이드의 가사
두 번째 줄</pre>
<p>위처럼 적으면 슬라이드가 <b>2장</b> 만들어지고, 두 번째 슬라이드는
"두 번째 슬라이드의 가사"와 "두 번째 줄"이 한 화면에 함께 나옵니다.</p>

<div class="tip">
왼쪽 메뉴에서 항목을 골라가며 차례로 읽으면 모든 기능을 익힐 수 있습니다.
</div>
"""

_PAGE_TITLE = _PAGE_STYLE + """
<h2>곡 제목 적기</h2>
<p>파일 맨 위에 <code>#</code> 기호와 <b>한 칸 띄어쓰기</b>로 시작하는 줄을 적으면
곡 제목이 됩니다.</p>
<p>이 줄은 슬라이드로 만들어지지 <b>않고</b>, 슬라이드 아래쪽 작은 글씨(소제목)의
기본값으로만 사용됩니다.</p>

<h3>예시</h3>
<pre># 어떤 곡의 제목

첫 번째 가사

두 번째 가사</pre>

<div class="tip">
<code>#</code> 다음에는 <b>꼭 한 칸 띄어야</b> 합니다. <code>#곡제목</code> 처럼
붙여 쓰면 인식되지 않아요.
</div>
"""

_PAGE_SECTION = _PAGE_STYLE + """
<h2>1절 · 후렴 등 섹션 나누기</h2>
<p><code>##</code>(샵 두 개) 와 <b>한 칸 띄어쓰기</b>로 시작하는 줄은 섹션 구분선입니다.
이 줄도 슬라이드가 되지 않고, 곡을 1절·후렴 등으로 <b>묶어주는 표시</b>일 뿐입니다.</p>

<h3>예시 — 단순 섹션</h3>
<pre># 어떤 곡

## 1절

가사 1

가사 2

## 후렴

후렴 가사</pre>

<h3>섹션마다 작은 글씨를 다르게 하고 싶다면</h3>
<p>섹션 이름 뒤에 <code>::</code> 를 적고 원하는 작은 글씨를 쓰세요.
그 섹션 안에 있는 모든 슬라이드의 작은 글씨가 자동으로 그 값이 됩니다.</p>
<pre># 어떤 곡

## 1절 :: 어떤 곡 1절

가사 1

가사 2

## 후렴 :: 어떤 곡 후렴

후렴 가사</pre>
<p>이렇게 하면 1절 슬라이드 두 장은 작은 글씨가 "어떤 곡 1절", 후렴 슬라이드는
"어떤 곡 후렴"으로 표시됩니다.</p>
"""

_PAGE_SUB = _PAGE_STYLE + """
<h2>슬라이드 작은 글씨 직접 지정</h2>
<p>슬라이드 아래쪽에 작은 글씨가 자동으로 표시되는데, 평소에는</p>
<ul>
  <li>섹션에 <code>::</code> 가 있으면 그 값이</li>
  <li>없으면 곡 제목이</li>
</ul>
<p>자동으로 들어갑니다. 그런데 <b>슬라이드 한 장만 따로</b> 작은 글씨를 적고 싶다면
슬라이드의 <b>마지막 줄</b>에 <code>&gt;</code>(꺾쇠) 와 한 칸 띄어쓰기로 적으세요.</p>

<h3>예시</h3>
<pre>이 가사는 특별해요
&gt; 직접 적은 작은 글씨</pre>
<p>이렇게 하면 그 슬라이드에서만 작은 글씨가 "직접 적은 작은 글씨" 로 바뀝니다.</p>

<div class="tip">
<code>&gt;</code> 줄은 <b>슬라이드의 마지막 줄</b>에 있을 때만 작동합니다.
중간에 있으면 그냥 가사의 일부로 취급돼요.
</div>
"""

_PAGE_PER_SLIDE = _PAGE_STYLE + """
<h2>한 슬라이드만 색·크기 바꾸기</h2>
<p>특정 슬라이드 한 장만 글자를 크게 하거나 색을 다르게 하고 싶다면,
그 슬라이드의 <b>첫 줄</b>에 <code>{ }</code> 안에 옵션을 적으세요.</p>

<h3>예시 — 글자 크게</h3>
<pre>{main_size: 72}
이 가사는 크게 보입니다</pre>

<h3>예시 — 글자 색 바꾸기 (금색)</h3>
<pre>{main_color: "#FFD700"}
강조하고 싶은 가사</pre>

<h3>예시 — 여러 옵션 한 번에</h3>
<pre>{main_size: 72, main_color: "#FFD700"}
크고 금색인 가사</pre>

<h3>예시 — 이 슬라이드만 배경 바꾸기</h3>
<pre>{background: "another_bg.jpg"}
다른 배경 위의 가사</pre>

<h3>쓸 수 있는 옵션 이름</h3>
<ul>
  <li><code>main_size</code> — 메인 가사 크기 (숫자, 예: <code>72</code>)</li>
  <li><code>main_color</code> — 메인 가사 색 (예: <code>"#FFD700"</code>)</li>
  <li><code>main_font</code> — 메인 가사 폰트
  (기본: <code>"Pretendard Variable"</code>)</li>
  <li><code>main_weight</code> — 굵기 100~900 (300=Light, 500=Medium, 700=Bold)</li>
  <li><code>sub_size</code>, <code>sub_color</code>, <code>sub_font</code>,
  <code>sub_weight</code> — 작은 글씨 쪽</li>
  <li><code>background</code> — 배경
  (이미지 파일명 또는 <code>"#000000"</code> 같은 색)</li>
</ul>

<div class="tip">
색은 <b>큰따옴표</b>로 감싸야 합니다 — <code>"#FFD700"</code> 이라고 쓰세요.
</div>
"""

_PAGE_FRONTMATTER = _PAGE_STYLE + """
<h2>곡 전체 기본값 (Frontmatter)</h2>
<p>곡 전체에 폰트, 색, 배경 등 기본값을 정하고 싶다면 파일 <b>맨 위에</b>
<code>---</code> 두 줄로 감싼 블록을 두세요. 이 블록을
<b>Frontmatter</b>라고 부릅니다.</p>
<p>툴바의 <b>"Frontmatter 편집"</b> 버튼을 누르면 폼으로 편하게 편집할 수도
있습니다.</p>

<h3>예시 1 — 폰트 굵기 바꾸기</h3>
<p>기본 폰트는 <b>Pretendard Variable</b> 이고, 굵기는 <code>main_weight</code>·
<code>sub_weight</code> 로 100~900 사이 숫자를 지정합니다.</p>
<pre>---
main_weight: 700   # 메인을 Bold 굵기로
sub_weight: 300    # 작은 글씨는 Light
---

# 곡 제목

가사 …</pre>
<p class="muted">자주 쓰이는 값: 300 = Light, 500 = Medium,
600 = SemiBold, 700 = Bold</p>

<p>아래처럼 <b>익숙한 이름</b>으로 적어도 동일하게 동작합니다 — 자동으로
같은 굵기의 Pretendard 로 변환되니 시스템에 별도 폰트가 설치되어 있지 않아도 됩니다.</p>
<pre>---
main_font: Pretendard Bold
sub_font: Pretendard Light
---</pre>

<h3>예시 2 — 배경 사진 바꾸기</h3>
<p>곡 폴더에 <code>bg.jpg</code> 파일을 넣어둔 경우:</p>
<pre>---
background: bg.jpg
---</pre>

<h3>예시 3 — 검정 단색 배경</h3>
<pre>---
background: "#000000"
---</pre>

<h3>예시 4 — 글자 크기와 색 동시에 바꾸기</h3>
<pre>---
main_size: 56
main_color: "#FFFFFF"
sub_size: 24
sub_color: "#CCCCCC"
---</pre>

<h3>예시 5 — 긴 가사일 때만 다른 배경</h3>
<p>가사가 3줄이면 <code>background_3plus</code>, 4줄이면
<code>background_4plus</code> 배경을 씁니다. 줄 수에 맞춰 배경을 따로 정할 수
있어요.</p>
<pre>---
background: bg_short.jpg
background_3plus: bg_3lines.jpg
background_4plus: bg_4lines.jpg
---</pre>

<h3>예시 6 — 모든 옵션 한꺼번에</h3>
<pre>---
main_font: Pretendard Variable
main_size: 38
main_weight: 500
main_color: "#F0F0F0"
sub_font: Pretendard Variable
sub_size: 20
sub_weight: 300
sub_color: "#F0F0F0"
background: bg.jpg
---

# 곡 제목

가사 …</pre>

<div class="tip">
적지 않은 항목은 자동으로 시스템 기본값이 적용되니, <b>바꾸고 싶은 것만</b>
적으면 됩니다.
</div>
"""

_PAGE_PRIORITY = _PAGE_STYLE + """
<h2>우선순위 — 무엇이 무엇을 이기는가</h2>
<p>같은 옵션을 여러 곳에 적었을 때 어떤 게 적용되는지 정리한 표입니다.</p>

<h3>글자 옵션 (폰트 · 크기 · 색)</h3>
<ul>
  <li>1순위: 슬라이드 첫 줄 <code>{ }</code> 옵션</li>
  <li>2순위: Frontmatter</li>
  <li>3순위: 시스템 기본값</li>
</ul>

<h3>작은 글씨 (Sub)</h3>
<ul>
  <li>1순위: 슬라이드 마지막 줄 <code>&gt;</code> 로 직접 지정한 값</li>
  <li>2순위: 섹션 <code>## ... :: 부제목</code></li>
  <li>3순위: 곡 제목 <code>#</code></li>
</ul>

<h3>배경</h3>
<ul>
  <li>1순위: 슬라이드 <code>{background: ...}</code></li>
  <li>2순위: 가사가 4줄이면 Frontmatter <code>background_4plus</code></li>
  <li>3순위: 가사가 3줄이면 Frontmatter <code>background_3plus</code></li>
  <li>4순위: Frontmatter <code>background</code></li>
  <li>5순위: 시스템 기본값</li>
</ul>

<div class="tip">
요약: <b>좁은 범위(슬라이드)에서 정한 게 넓은 범위(곡 전체)보다 항상 이깁니다.</b>
</div>
"""

_PAGES: tuple[tuple[str, str], ...] = (
    ("시작하기", _PAGE_INTRO),
    ("곡 제목 적기", _PAGE_TITLE),
    ("1절 · 후렴 나누기", _PAGE_SECTION),
    ("작은 글씨 지정", _PAGE_SUB),
    ("한 슬라이드만 꾸미기", _PAGE_PER_SLIDE),
    ("곡 전체 기본값 (Frontmatter)", _PAGE_FRONTMATTER),
    ("우선순위 정리", _PAGE_PRIORITY),
)

# ─── 위젯 스타일시트 ──────────────────────────────────────────────────────────

_DIALOG_QSS = f"""
QDialog {{
    background: {BG_DEEP};
}}
"""

_MENU_QSS = f"""
QListWidget#HelpMenu {{
    background: {BG_SURFACE};
    border: none;
    border-right: 1px solid {BORDER_SUBTLE_RGBA};
    outline: 0;
    padding: {SP_SM}px 0;
    font-family: {FONT_FAMILY};
    font-size: {FONT_MD}px;
    color: {TEXT_SECONDARY};
}}
QListWidget#HelpMenu::item {{
    padding: 10px 18px;
    border-left: 3px solid transparent;
    background: transparent;
    color: {TEXT_SECONDARY};
}}
QListWidget#HelpMenu::item:hover {{
    background: {SURFACE_GHOST};
    color: {TEXT_PRIMARY};
}}
QListWidget#HelpMenu::item:selected {{
    background: {SURFACE_SUBTLE};
    color: {ACCENT_INTER};
    border-left: 3px solid {ACCENT_INTER};
}}
"""

_BROWSER_QSS = f"""
QTextBrowser {{
    background: {BG_DEEP};
    border: none;
    padding: {SP_XL}px {SP_XL}px;
    color: {TEXT_PRIMARY};
    selection-background-color: {ACCENT};
    selection-color: #FFFFFF;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: rgba(255, 255, 255, 0.18);
    min-height: 24px;
    border-radius: 5px;
}}
QScrollBar::handle:vertical:hover {{
    background: rgba(255, 255, 255, 0.30);
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
"""

_FOOTER_QSS = f"""
QFrame#HelpFooter {{
    background: {BG_SURFACE};
    border-top: 1px solid {BORDER_SUBTLE_RGBA};
}}
QPushButton#HelpClose {{
    background: {ACCENT};
    color: #FFFFFF;
    border: none;
    border-radius: {RADIUS_MD}px;
    padding: 8px 22px;
    font-family: {FONT_FAMILY};
    font-size: {FONT_MD}px;
    font-weight: 500;
}}
QPushButton#HelpClose:hover {{ background: {ACCENT_HOVER}; }}
"""


class MarkdownHelpDialog(QDialog):
    """좌측 메뉴 + 우측 본문 구성의 마크다운 도움말."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("마크다운 작성 도움말")
        self.resize(900, 680)
        self.setStyleSheet(_DIALOG_QSS)

        # Left menu
        self._menu = QListWidget()
        self._menu.setObjectName("HelpMenu")
        self._menu.setFixedWidth(240)
        self._menu.setStyleSheet(_MENU_QSS)
        self._menu.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        for title, _ in _PAGES:
            item = QListWidgetItem(title)
            self._menu.addItem(item)

        # Right content stack
        self._stack = QStackedWidget()
        for _, html in _PAGES:
            page = QTextBrowser()
            page.setOpenExternalLinks(True)
            page.setStyleSheet(_BROWSER_QSS)
            page.document().setDocumentMargin(0)
            page.setHtml(html)
            self._stack.addWidget(page)

        self._menu.currentRowChanged.connect(self._stack.setCurrentIndex)
        self._menu.setCurrentRow(0)

        # Body row (menu | content)
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self._menu)
        body.addWidget(self._stack, 1)

        body_wrap = QWidget()
        body_wrap.setLayout(body)

        # Footer
        close_btn = QPushButton("닫기")
        close_btn.setObjectName("HelpClose")
        close_btn.clicked.connect(self.accept)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        footer = QFrame()
        footer.setObjectName("HelpFooter")
        footer.setStyleSheet(_FOOTER_QSS)
        footer_row = QHBoxLayout(footer)
        footer_row.setContentsMargins(SP_LG, SP_MD, SP_LG, SP_MD)
        footer_row.addStretch(1)
        footer_row.addWidget(close_btn)

        # Root
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(body_wrap, 1)
        root.addWidget(footer)

        close_btn.setDefault(True)
        close_btn.setFocus(Qt.FocusReason.OtherFocusReason)
