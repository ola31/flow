"""커스텀 다이얼로그 헬퍼 — QMessageBox/QInputDialog의 raw Qt 느낌 대체.

OS 기본 다이얼로그(QMessageBox, QInputDialog)는 타이틀바 글자 잘림, 시스템
폰트 강제, 다크 테마와 톤 안 맞는 버튼 등 prototype 느낌의 주요 원인이 됨.

이 모듈은 동일 API를 노출하는 커스텀 QDialog 헬퍼를 제공한다:
  - flow_info(parent, title, message)        → bool (OK 클릭 여부)
  - flow_warning(parent, title, message)     → bool
  - flow_question(parent, title, message)    → bool (Yes 클릭 시 True)
  - flow_error(parent, title, message)       → bool
  - flow_input_text(parent, title, prompt,   → (text, ok)
                    default="", placeholder="")

특징:
  - FramelessWindowHint + 커스텀 타이틀바 → OS chrome 제거, 다크 톤 통일
  - 우측 X 버튼으로 닫기, 드래그로 이동 가능
  - 설계 토큰 100% 사용
  - Primary CTA(확인/Yes)는 인디고 채움, 나머지는 Ghost
"""

from __future__ import annotations

import os

from PySide6.QtCore import Qt, QPoint, QSize
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QFrame,
    QSizePolicy,
)

from flow.ui.styles import (
    BG_DEEP, BG_SURFACE, BG_ELEVATED,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_TERTIARY, TEXT_QUAT,
    ACCENT, ACCENT_INTER, AMBER, RED, GREEN,
    SURFACE_GHOST, SURFACE_SUBTLE, SURFACE_RAISED,
    BORDER_SUBTLE_RGBA, BORDER_STANDARD_RGBA,
    FONT_XS, FONT_SM, FONT_MD, FONT_LG, FONT_HEAD, FW_REGULAR, FW_MEDIUM, FW_SEMI,
    RADIUS_MD, RADIUS_LG, SP_SM, SP_MD, SP_LG, SP_XL, SP_2XL,
)


_INFO_GLYPH    = ("정보", TEXT_SECONDARY)
_WARNING_GLYPH = ("경고", AMBER)
_ERROR_GLYPH   = ("오류", RED)
_QUESTION_GLYPH = ("확인", ACCENT_INTER)


class _FlowDialog(QDialog):
    """프레임리스 + 커스텀 타이틀바를 가진 베이스 다이얼로그.

    드래그로 이동 가능. ESC로 닫기. 라운드 코너 + 헤어라인 보더.
    """

    def __init__(self, parent: QWidget | None = None, title: str = "") -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._title_text = title
        self._drag_offset: QPoint | None = None

        # 외곽 컨테이너 (라운드 + 보더)
        self._frame = QFrame(self)
        self._frame.setObjectName("FlowDialogFrame")
        self._frame.setStyleSheet(f"""
            QFrame#FlowDialogFrame {{
                background-color: {BG_SURFACE};
                border: 1px solid {BORDER_STANDARD_RGBA};
                border-radius: {RADIUS_LG}px;
            }}
        """)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._frame)

        self._main = QVBoxLayout(self._frame)
        self._main.setContentsMargins(0, 0, 0, 0)
        self._main.setSpacing(0)

        self._build_title_bar()

    def _build_title_bar(self) -> None:
        bar = QFrame()
        bar.setFixedHeight(40)
        bar.setStyleSheet(
            f"background: transparent; border-bottom: 1px solid {BORDER_SUBTLE_RGBA};"
        )
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(SP_LG, 0, SP_SM, 0)
        layout.setSpacing(SP_SM)

        self._title_label = QLabel(self._title_text)
        self._title_label.setStyleSheet(
            f"color: {TEXT_PRIMARY}; font-size: {FONT_HEAD}px; "
            f"font-weight: {FW_SEMI}; background: transparent; border: none;"
        )
        layout.addWidget(self._title_label, 1)

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(28, 28)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_close.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {TEXT_TERTIARY};
                border: none; border-radius: {RADIUS_MD}px;
                font-size: {FONT_LG}px;
            }}
            QPushButton:hover {{
                background: {SURFACE_SUBTLE}; color: {TEXT_PRIMARY};
            }}
        """)
        btn_close.clicked.connect(self.reject)
        layout.addWidget(btn_close)

        self._main.addWidget(bar)
        self._title_bar = bar

    # ── 본문 컨테이너 (subclass에서 채움) ───────────────────────────────────
    def body_layout(self) -> QVBoxLayout:
        if not hasattr(self, "_body_layout"):
            body = QFrame()
            body.setStyleSheet("background: transparent;")
            self._body_layout = QVBoxLayout(body)
            self._body_layout.setContentsMargins(SP_XL, SP_LG, SP_XL, SP_LG)
            self._body_layout.setSpacing(SP_MD)
            self._main.addWidget(body, 1)
        return self._body_layout

    def add_button_row(self, buttons: list[QPushButton]) -> None:
        bar = QFrame()
        bar.setStyleSheet(
            f"background: transparent; border-top: 1px solid {BORDER_SUBTLE_RGBA};"
        )
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(SP_LG, SP_MD, SP_LG, SP_MD)
        layout.setSpacing(SP_SM)
        layout.addStretch()
        for btn in buttons:
            layout.addWidget(btn)
        self._main.addWidget(bar)

    # ── 드래그로 이동 ───────────────────────────────────────────────────────
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            tb_geo = self._title_bar.geometry()
            local = event.position().toPoint()
            if tb_geo.contains(local):
                self._drag_offset = (
                    event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                )
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_offset is not None and (event.buttons() & Qt.MouseButton.LeftButton):
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_offset = None
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
            return
        super().keyPressEvent(event)

    def exec(self) -> int:
        """pytest 실행 중에는 다이얼로그를 띄우지 않고 즉시 Accept 반환.

        모달 다이얼로그가 자동 테스트 흐름을 막지 않도록 함. 특정 동작
        검증이 필요한 테스트는 flow_warning/flow_question 등을
        monkeypatch.setattr로 직접 패치하면 됨.
        """
        if os.environ.get("PYTEST_CURRENT_TEST"):
            return QDialog.DialogCode.Accepted
        return super().exec()


def _make_button(text: str, *, primary: bool = False) -> QPushButton:
    btn = QPushButton(text)
    btn.setFixedHeight(32)
    btn.setMinimumWidth(80)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    if primary:
        btn.setProperty("variant", "primary")
    return btn


def _make_message_dialog(
    parent: QWidget | None,
    title: str,
    message: str,
    *,
    glyph_color: str,
    glyph_label: str,
    primary_text: str,
    cancel_text: str | None = None,
) -> bool:
    """공통 메시지 다이얼로그 빌더. Yes(=primary 클릭) → True."""
    dlg = _FlowDialog(parent, title=title)
    dlg.setMinimumWidth(420)

    body = dlg.body_layout()

    # 라벨 + 메시지
    header = QHBoxLayout()
    header.setSpacing(SP_MD)
    glyph = QLabel(glyph_label)
    glyph.setFixedSize(40, 24)
    glyph.setAlignment(Qt.AlignmentFlag.AlignCenter)
    glyph.setStyleSheet(
        f"background: {SURFACE_SUBTLE}; color: {glyph_color}; "
        f"border-radius: {RADIUS_MD}px; "
        f"font-size: {FONT_MD}px; font-weight: {FW_SEMI};"
    )
    header.addWidget(glyph, 0, Qt.AlignmentFlag.AlignTop)

    msg_label = QLabel(message)
    msg_label.setWordWrap(True)
    msg_label.setStyleSheet(
        f"color: {TEXT_PRIMARY}; font-size: {FONT_MD}px; "
        f"font-weight: {FW_REGULAR}; background: transparent; border: none;"
    )
    msg_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    header.addWidget(msg_label, 1)
    body.addLayout(header)

    # 버튼 행
    buttons = []
    if cancel_text:
        btn_cancel = _make_button(cancel_text)
        btn_cancel.clicked.connect(dlg.reject)
        buttons.append(btn_cancel)

    btn_primary = _make_button(primary_text, primary=True)
    btn_primary.clicked.connect(dlg.accept)
    btn_primary.setDefault(True)
    btn_primary.setAutoDefault(True)
    buttons.append(btn_primary)
    dlg.add_button_row(buttons)

    return dlg.exec() == QDialog.DialogCode.Accepted


# ─── 공개 API (QMessageBox 대체) ────────────────────────────────────────────


def flow_info(parent, title: str, message: str) -> bool:
    """정보 알림. 단일 확인 버튼."""
    return _make_message_dialog(
        parent, title, message,
        glyph_color=_INFO_GLYPH[1], glyph_label=_INFO_GLYPH[0],
        primary_text="확인",
    )


def flow_warning(parent, title: str, message: str) -> bool:
    """경고. 단일 확인 버튼."""
    return _make_message_dialog(
        parent, title, message,
        glyph_color=_WARNING_GLYPH[1], glyph_label=_WARNING_GLYPH[0],
        primary_text="확인",
    )


def flow_error(parent, title: str, message: str) -> bool:
    """오류. 단일 확인 버튼."""
    return _make_message_dialog(
        parent, title, message,
        glyph_color=_ERROR_GLYPH[1], glyph_label=_ERROR_GLYPH[0],
        primary_text="확인",
    )


def flow_question(parent, title: str, message: str,
                  *, yes_text: str = "예", no_text: str = "아니오") -> bool:
    """예/아니오 질문. Yes 클릭 시 True."""
    return _make_message_dialog(
        parent, title, message,
        glyph_color=_QUESTION_GLYPH[1], glyph_label=_QUESTION_GLYPH[0],
        primary_text=yes_text, cancel_text=no_text,
    )


# ─── 3-way 다이얼로그 (저장/버리기/취소 패턴) ────────────────────────────────

# 반환값 상수
SAVE = "save"
DISCARD = "discard"
CANCEL = "cancel"


def flow_save_changes(
    parent,
    title: str = "저장 확인",
    message: str = "저장되지 않은 변경사항이 있습니다.\n진행하기 전에 저장하시겠습니까?",
    *,
    save_text: str = "저장",
    discard_text: str = "저장 안 함",
    cancel_text: str = "취소",
) -> str:
    """3-way 저장/버리기/취소 다이얼로그.

    Returns:
        SAVE | DISCARD | CANCEL 문자열 상수
    """
    dlg = _FlowDialog(parent, title=title)
    dlg.setMinimumWidth(440)
    body = dlg.body_layout()

    header = QHBoxLayout()
    header.setSpacing(SP_MD)
    glyph = QLabel(_QUESTION_GLYPH[0])
    glyph.setFixedSize(40, 24)
    glyph.setAlignment(Qt.AlignmentFlag.AlignCenter)
    glyph.setStyleSheet(
        f"background: {SURFACE_SUBTLE}; color: {_QUESTION_GLYPH[1]}; "
        f"border-radius: {RADIUS_MD}px; "
        f"font-size: {FONT_MD}px; font-weight: {FW_SEMI};"
    )
    header.addWidget(glyph, 0, Qt.AlignmentFlag.AlignTop)

    msg_label = QLabel(message)
    msg_label.setWordWrap(True)
    msg_label.setStyleSheet(
        f"color: {TEXT_PRIMARY}; font-size: {FONT_MD}px; "
        f"font-weight: {FW_REGULAR}; background: transparent; border: none;"
    )
    msg_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    header.addWidget(msg_label, 1)
    body.addLayout(header)

    # 결과 추적용
    result = {"value": CANCEL}

    btn_cancel = _make_button(cancel_text)
    btn_cancel.clicked.connect(lambda: (result.update(value=CANCEL), dlg.reject()))

    btn_discard = _make_button(discard_text)
    btn_discard.setStyleSheet(
        f"QPushButton {{ background: {SURFACE_GHOST}; color: {RED}; "
        f"border: 1px solid {BORDER_STANDARD_RGBA}; "
        f"border-radius: {RADIUS_MD}px; padding: {SP_SM}px {SP_LG}px; "
        f"font-weight: {FW_MEDIUM}; }}"
        f"QPushButton:hover {{ background: {SURFACE_SUBTLE}; border-color: {RED}; }}"
    )
    btn_discard.clicked.connect(lambda: (result.update(value=DISCARD), dlg.accept()))

    btn_save = _make_button(save_text, primary=True)
    btn_save.clicked.connect(lambda: (result.update(value=SAVE), dlg.accept()))
    btn_save.setDefault(True)
    btn_save.setAutoDefault(True)

    dlg.add_button_row([btn_cancel, btn_discard, btn_save])

    dlg.exec()
    return result["value"]


# ─── 모니터 선택 다이얼로그 ────────────────────────────────────────────────


def flow_select_screen(
    parent,
    screens: list,
    *,
    current_name: str = "",
    default_windowed: bool | None = None,
    title: str = "송출 모니터 선택",
) -> tuple[object | None, bool] | None:
    """송출에 사용할 QScreen + 윈도우 모드 여부 선택.

    Returns:
        (screen, windowed) 튜플 — screen은 선택된 QScreen, windowed는
        True면 fullscreen 대신 윈도우 모드로 송출. 사용자 취소 시 None 반환.
    """
    from PySide6.QtWidgets import QButtonGroup, QRadioButton, QCheckBox

    dlg = _FlowDialog(parent, title=title)
    dlg.setMinimumWidth(480)
    body = dlg.body_layout()

    n = len(screens)
    if n > 1:
        intro_text = f"{n}개의 모니터가 감지되었습니다. 송출할 모니터를 선택하세요."
    else:
        intro_text = (
            "모니터가 1개만 감지되었습니다. 이 모니터로 송출하면 화면 전체를 "
            "덮습니다 (Flow 창이 가려짐). 윈도우 모드를 선택하면 작은 창으로 띄울 수 있습니다."
        )
    intro = QLabel(intro_text)
    intro.setWordWrap(True)
    intro.setStyleSheet(
        f"color: {TEXT_SECONDARY}; font-size: {FONT_MD}px; "
        "background: transparent; border: none;"
    )
    body.addWidget(intro)

    group = QButtonGroup(dlg)
    radios: list[tuple[QRadioButton, object]] = []
    for i, screen in enumerate(screens):
        geo = screen.geometry()
        try:
            from PySide6.QtGui import QGuiApplication
            is_primary = screen == QGuiApplication.primaryScreen()
        except Exception:
            is_primary = (i == 0)

        label_text = (
            f"모니터 {i + 1}  ·  {geo.width()} × {geo.height()}"
            f"  ·  {screen.name() or '(이름 없음)'}"
        )
        if is_primary:
            label_text += "   [주 모니터]"

        radio = QRadioButton(label_text)
        radio.setStyleSheet(
            f"QRadioButton {{ color: {TEXT_PRIMARY}; font-size: {FONT_MD}px; "
            f"background: transparent; padding: {SP_SM}px 0; "
            f"font-weight: {FW_MEDIUM}; spacing: 8px; }}"
            f"QRadioButton::indicator {{ width: 14px; height: 14px; "
            f"border-radius: 8px; border: 1.5px solid {BORDER_STANDARD_RGBA}; "
            f"background: {BG_ELEVATED}; }}"
            f"QRadioButton::indicator:checked {{ border: 4px solid {ACCENT}; "
            f"background: {BG_DEEP}; }}"
        )
        if current_name and screen.name() == current_name:
            radio.setChecked(True)
        elif not current_name and not is_primary and i > 0:
            radio.setChecked(True)
        group.addButton(radio, i)
        radios.append((radio, screen))
        body.addWidget(radio)

    if not any(r.isChecked() for r, _ in radios):
        radios[0][0].setChecked(True)

    # 윈도우 모드 체크박스 — 단일 모니터 환경의 기본 옵션, 다중 모니터에서도 선택 가능
    chk_windowed = QCheckBox("윈도우 모드로 표시 (전체화면 대신 작은 창)")
    chk_windowed.setStyleSheet(
        f"color: {TEXT_SECONDARY}; font-size: {FONT_SM}px; "
        f"background: transparent; padding: {SP_SM}px 0;"
    )
    # 기본값: 명시적으로 전달된 값이 우선, 없으면 단일 모니터에서 윈도우 모드
    chk_windowed.setChecked(
        default_windowed if default_windowed is not None else (n == 1)
    )
    body.addWidget(chk_windowed)

    btn_cancel = _make_button("취소")
    btn_cancel.clicked.connect(dlg.reject)

    btn_ok = _make_button("송출 시작", primary=True)
    btn_ok.clicked.connect(dlg.accept)
    btn_ok.setDefault(True)
    btn_ok.setAutoDefault(True)

    dlg.add_button_row([btn_cancel, btn_ok])

    if dlg.exec() != QDialog.DialogCode.Accepted:
        return None

    chosen_screen = None
    for radio, screen in radios:
        if radio.isChecked():
            chosen_screen = screen
            break
    return (chosen_screen, chk_windowed.isChecked())


# ─── 텍스트 입력 다이얼로그 (QInputDialog.getText 대체) ────────────────────


def flow_input_text(
    parent,
    title: str,
    prompt: str,
    *,
    default: str = "",
    placeholder: str = "",
    ok_text: str = "확인",
    cancel_text: str = "취소",
) -> tuple[str, bool]:
    """텍스트 입력 다이얼로그.

    Returns:
        (입력된 텍스트, 확인 여부). 취소 시 ("", False).
    """
    dlg = _FlowDialog(parent, title=title)
    dlg.setMinimumWidth(440)

    body = dlg.body_layout()

    if prompt:
        prompt_label = QLabel(prompt)
        prompt_label.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: {FONT_MD}px; "
            "background: transparent; border: none;"
        )
        prompt_label.setWordWrap(True)
        body.addWidget(prompt_label)

    line = QLineEdit()
    line.setText(default)
    if placeholder:
        line.setPlaceholderText(placeholder)
    line.setFixedHeight(36)
    line.setStyleSheet(
        f"QLineEdit {{ background: {SURFACE_GHOST}; color: {TEXT_PRIMARY}; "
        f"border: 1px solid {BORDER_STANDARD_RGBA}; border-radius: {RADIUS_MD}px; "
        f"padding: 0 {SP_MD}px; font-size: {FONT_MD}px; "
        f"font-weight: {FW_MEDIUM}; }} "
        f"QLineEdit:focus {{ border-color: {ACCENT_INTER}; }}"
    )
    line.selectAll()
    body.addWidget(line)

    buttons = []
    btn_cancel = _make_button(cancel_text)
    btn_cancel.clicked.connect(dlg.reject)
    buttons.append(btn_cancel)

    btn_ok = _make_button(ok_text, primary=True)
    btn_ok.clicked.connect(dlg.accept)
    btn_ok.setDefault(True)
    btn_ok.setAutoDefault(True)
    buttons.append(btn_ok)
    dlg.add_button_row(buttons)

    line.returnPressed.connect(dlg.accept)

    if dlg.exec() == QDialog.DialogCode.Accepted:
        return line.text().strip(), True
    return "", False


# ─── 설치 안내 다이얼로그 ───────────────────────────────────────────────────

_LIBREOFFICE_URL = "https://www.libreoffice.org/download/"

_INSTALL_GUIDE_BY_OS: dict[str, dict[str, str]] = {
    "win32": {
        "title": "PPT 변환 엔진 필요",
        "message": (
            "PPT 슬라이드를 미리보기로 변환하려면 Microsoft PowerPoint "
            "또는 LibreOffice가 설치되어 있어야 합니다.\n\n"
            "둘 다 없는 경우 LibreOffice 설치를 권장합니다 (무료, 가벼움).\n"
            "다운로드 페이지에서 Windows 버전을 선택하세요."
        ),
    },
    "darwin": {
        "title": "PPT 변환 엔진 필요",
        "message": (
            "PPT 슬라이드를 미리보기로 변환하려면 Microsoft PowerPoint "
            "또는 LibreOffice가 설치되어 있어야 합니다.\n\n"
            "Homebrew 사용 시:\n"
            "    brew install --cask libreoffice\n\n"
            "또는 다운로드 페이지에서 macOS 버전을 받으세요."
        ),
    },
    "linux": {
        "title": "PPT 변환 엔진 필요",
        "message": (
            "PPT 슬라이드 변환을 위해 LibreOffice 설치가 필요합니다.\n\n"
            "Debian/Ubuntu:\n"
            "    sudo apt install libreoffice\n"
            "Fedora:\n"
            "    sudo dnf install libreoffice\n"
            "Arch:\n"
            "    sudo pacman -S libreoffice-fresh"
        ),
    },
}


def flow_show_install_guide(parent, *, platform_name: str = "") -> None:
    """PPT 변환 엔진(PowerPoint/LibreOffice) 부재 시 설치 안내 다이얼로그.

    Args:
        platform_name: sys.platform 값 ("win32", "darwin", "linux"...).
            빈 문자열이면 자동 감지.
    """
    import sys
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QDesktopServices

    plat = platform_name or sys.platform
    info = _INSTALL_GUIDE_BY_OS.get(plat, _INSTALL_GUIDE_BY_OS["linux"])

    dlg = _FlowDialog(parent, title=info["title"])
    dlg.setMinimumWidth(480)

    body = dlg.body_layout()

    header = QHBoxLayout()
    header.setSpacing(SP_MD)
    glyph = QLabel(_WARNING_GLYPH[0])
    glyph.setFixedSize(40, 24)
    glyph.setAlignment(Qt.AlignmentFlag.AlignCenter)
    glyph.setStyleSheet(
        f"background: {SURFACE_SUBTLE}; color: {_WARNING_GLYPH[1]}; "
        f"border-radius: {RADIUS_MD}px; "
        f"font-size: {FONT_MD}px; font-weight: {FW_SEMI};"
    )
    header.addWidget(glyph, 0, Qt.AlignmentFlag.AlignTop)

    msg = QLabel(info["message"])
    msg.setWordWrap(True)
    msg.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    msg.setStyleSheet(
        f"color: {TEXT_PRIMARY}; font-size: {FONT_MD}px; "
        f"font-weight: {FW_REGULAR}; background: transparent; border: none;"
    )
    msg.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    header.addWidget(msg, 1)
    body.addLayout(header)

    buttons = []

    btn_close = _make_button("확인")
    btn_close.clicked.connect(dlg.reject)
    buttons.append(btn_close)

    btn_open = _make_button("LibreOffice 다운로드 페이지 열기", primary=True)
    btn_open.clicked.connect(
        lambda: QDesktopServices.openUrl(QUrl(_LIBREOFFICE_URL))
    )
    btn_open.setDefault(True)
    btn_open.setAutoDefault(True)
    buttons.append(btn_open)
    dlg.add_button_row(buttons)

    dlg.exec()

