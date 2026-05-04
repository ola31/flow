from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt

from flow.ui.styles import (
    BG_ELEVATED, TEXT_PRIMARY, TEXT_SECONDARY, BORDER_STANDARD_RGBA,
    SURFACE_GHOST, FONT_MD, FONT_LG, FW_MEDIUM, FW_SEMI,
    RADIUS_MD, RADIUS_LG, SP_MD, SP_LG, SP_XL,
)


_RES_PRESETS: tuple[tuple[str, tuple[int, int]], ...] = (
    ("FHD (1920 × 1080)", (1920, 1080)),
    ("2K (2560 × 1440)", (2560, 1440)),
    ("4K (3840 × 2160)", (3840, 2160)),
    ("HD (1280 × 720)", (1280, 720)),
)


class OutputResolutionPicker(QWidget):
    """Radio group + custom WxH input for output resolution."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._group = QButtonGroup(self)
        self._radios: list[tuple[QRadioButton, tuple[int, int]]] = []
        for label, value in _RES_PRESETS:
            rb = QRadioButton(label)
            rb.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: {FONT_MD}px;")
            self._group.addButton(rb)
            layout.addWidget(rb)
            self._radios.append((rb, value))

        custom_row = QHBoxLayout()
        custom_row.setContentsMargins(0, 0, 0, 0)
        self._rb_custom = QRadioButton("사용자 정의")
        self._rb_custom.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: {FONT_MD}px;")
        self._group.addButton(self._rb_custom)
        custom_row.addWidget(self._rb_custom)
        self._custom_input = QLineEdit()
        self._custom_input.setPlaceholderText("WxH (예: 1600x900)")
        self._custom_input.setEnabled(False)
        self._custom_input.setStyleSheet(
            f"QLineEdit {{ background-color: {SURFACE_GHOST}; color: {TEXT_PRIMARY}; "
            f"border: 1px solid {BORDER_STANDARD_RGBA}; "
            f"padding: 4px 8px; border-radius: {RADIUS_MD}px; }}"
        )
        custom_row.addWidget(self._custom_input, 1)
        layout.addLayout(custom_row)

        self._rb_custom.toggled.connect(self._custom_input.setEnabled)

    def set_value(self, w: int, h: int) -> None:
        for rb, (rw, rh) in self._radios:
            if (w, h) == (rw, rh):
                rb.setChecked(True)
                return
        self._rb_custom.setChecked(True)
        self._custom_input.setText(f"{w}x{h}")

    def value(self) -> tuple[int, int] | None:
        if self._rb_custom.isChecked():
            txt = self._custom_input.text().strip().lower().replace(" ", "")
            if "x" not in txt:
                return None
            try:
                w_s, h_s = txt.split("x", 1)
                return (int(w_s), int(h_s))
            except ValueError:
                return None
        for rb, value in self._radios:
            if rb.isChecked():
                return value
        return None


class SettingsDialog(QDialog):
    """애플리케이션 환경설정 다이얼로그"""

    def __init__(self, config_service, parent=None):
        super().__init__(parent)
        self.config_service = config_service
        self.setWindowTitle("환경설정")
        self.setMinimumWidth(420)
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SP_XL, SP_XL, SP_XL, SP_XL)
        layout.setSpacing(SP_LG)

        title = QLabel("일반 설정")
        title.setStyleSheet(
            f"font-weight: {FW_SEMI}; color: {TEXT_PRIMARY}; font-size: {FONT_LG}px;"
        )
        layout.addWidget(title)

        group = QFrame()
        group.setStyleSheet(
            f"QFrame {{ background-color: {BG_ELEVATED}; "
            f"border: 1px solid {BORDER_STANDARD_RGBA}; "
            f"border-radius: {RADIUS_LG}px; }}"
        )
        form = QFormLayout(group)
        form.setContentsMargins(SP_LG, SP_LG, SP_LG, SP_LG)
        form.setSpacing(SP_MD)

        self.verse_count = QSpinBox()
        self.verse_count.setRange(1, 10)
        self.verse_count.setFixedWidth(80)
        self.verse_count.setStyleSheet(
            f"QSpinBox {{ background-color: {SURFACE_GHOST}; color: {TEXT_PRIMARY}; "
            f"border: 1px solid {BORDER_STANDARD_RGBA}; "
            f"padding: 4px; border-radius: {RADIUS_MD}px; "
            f"font-weight: {FW_MEDIUM}; }}"
        )

        lbl_verse = QLabel("최대 절(Layer) 수:")
        lbl_verse.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: {FONT_MD}px;")
        form.addRow(lbl_verse, self.verse_count)

        self.res_picker = OutputResolutionPicker()
        lbl_res = QLabel("송출 해상도:")
        lbl_res.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: {FONT_MD}px;")
        lbl_res.setAlignment(Qt.AlignmentFlag.AlignTop)
        form.addRow(lbl_res, self.res_picker)

        layout.addWidget(group)
        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_cancel = QPushButton("취소")
        btn_cancel.setFixedSize(80, 32)
        btn_cancel.clicked.connect(self.reject)

        btn_save = QPushButton("확인")
        btn_save.setFixedSize(80, 32)
        btn_save.setProperty("variant", "primary")
        btn_save.clicked.connect(self._on_save_clicked)

        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_save)
        layout.addLayout(btn_layout)

    def _load_settings(self):
        max_verses = self.config_service.get_max_verses()
        self.verse_count.setValue(max_verses)
        w, h = self.config_service.get_output_resolution()
        self.res_picker.set_value(w, h)

    def _on_save_clicked(self):
        self.config_service.set_max_verses(self.verse_count.value())
        res = self.res_picker.value()
        if res is not None:
            self.config_service.set_output_resolution(res[0], res[1])
        self.accept()
