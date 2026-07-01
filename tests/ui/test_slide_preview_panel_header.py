from __future__ import annotations

from PySide6.QtWidgets import QSizePolicy

from flow.ui.editor.slide_preview_panel import SlidePreviewPanel


def test_header_does_not_stretch_to_fill_panel(qtbot):
    """헤더("PPT 슬라이드 (n)" + 새로고침 버튼) 영역은 세로 확장 정책이 아니어야
    하며, 패널을 크게 늘려도 헤더가 잉여 공간을 흡수해 늘어나선 안 된다."""
    panel = SlidePreviewPanel()
    qtbot.addWidget(panel)
    header_widget = panel._title.parentWidget()

    assert header_widget.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Fixed

    panel.resize(600, 400)
    panel.show()
    qtbot.waitExposed(panel)

    # 새로고침 버튼(30px) 기준 자연스러운 높이 근처여야 하고, 패널 전체 높이를
    # 흡수해 늘어나면 안 된다 (회귀 전에는 200px 이상으로 늘어났었음).
    assert header_widget.height() < 60
