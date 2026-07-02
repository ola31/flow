from __future__ import annotations

from flow.ui.dialogs import DisplayTarget


def test_display_target_dataclass():
    t = DisplayTarget(mode="web")
    assert t.mode == "web"
    assert t.screen is None
    assert t.windowed is False


def test_select_screen_dialog_web_radio_returns_web_target(qapp, monkeypatch):
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtWidgets import QDialog, QRadioButton

    import flow.ui.dialogs as dialogs

    captured = {}

    def fake_exec(self):
        radios = self.findChildren(QRadioButton)
        web = [r for r in radios if "웹" in r.text()]
        captured["has_web"] = bool(web)
        if web:
            web[0].setChecked(True)
        return QDialog.DialogCode.Accepted

    # _FlowDialog.exec()는 PYTEST_CURRENT_TEST가 설정되어 있으면 real exec()
    # 호출 없이 즉시 Accept를 반환한다 (모달이 테스트를 막지 않도록) — 이 테스트는
    # 실제 라디오 상호작용을 검증해야 하므로 해당 단축 경로를 일시적으로 해제한다.
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setattr(QDialog, "exec", fake_exec)
    result = dialogs.flow_select_screen(None, QGuiApplication.screens())
    assert captured["has_web"]
    assert isinstance(result, DisplayTarget)
    assert result.mode == "web"


def test_select_screen_dialog_screen_target_default(qapp, monkeypatch):
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtWidgets import QDialog

    import flow.ui.dialogs as dialogs

    monkeypatch.setattr(
        QDialog, "exec", lambda self: QDialog.DialogCode.Accepted
    )
    screens = QGuiApplication.screens()
    result = dialogs.flow_select_screen(None, screens)
    assert isinstance(result, DisplayTarget)
    assert result.mode == "screen"
    assert result.screen is not None


def test_web_radio_prechecked_from_saved_name(qapp, monkeypatch):
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtWidgets import QDialog, QRadioButton

    import flow.ui.dialogs as dialogs

    checked = {}

    def fake_exec(self):
        radios = self.findChildren(QRadioButton)
        web = [r for r in radios if "웹" in r.text()]
        checked["web_prechecked"] = bool(web) and web[0].isChecked()
        return QDialog.DialogCode.Rejected

    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setattr(QDialog, "exec", fake_exec)
    dialogs.flow_select_screen(
        None, QGuiApplication.screens(), current_name="__web__"
    )
    assert checked["web_prechecked"]
