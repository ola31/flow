"""커스텀 다이얼로그 테스트.

핵심 보장:
1. pytest 실행 환경에서는 dlg.exec()가 차단 없이 즉시 Accepted 반환
   (모달이 자동 테스트 흐름을 막지 않도록 — PYTEST_CURRENT_TEST 환경변수
   감지)
2. flow_question / flow_input_text 등의 헬퍼가 환경 감지 흐름과
   일관되게 동작
"""

from __future__ import annotations

import os

import pytest


def test_pytest_current_test_env_is_set():
    """이 테스트가 실행되는 동안 PYTEST_CURRENT_TEST가 설정되어 있어야
    다이얼로그 자동 닫기 기능이 발동함."""
    assert os.environ.get("PYTEST_CURRENT_TEST"), (
        "pytest가 PYTEST_CURRENT_TEST를 설정하지 않음 — 다이얼로그 자동"
        "스킵이 동작하지 않을 수 있음"
    )


def test_flow_dialog_does_not_block_under_pytest(qapp):
    """_FlowDialog.exec()가 pytest 환경에서 즉시 Accepted 반환."""
    from flow.ui.dialogs import _FlowDialog
    from PySide6.QtWidgets import QDialog

    dlg = _FlowDialog(parent=None, title="테스트")
    result = dlg.exec()  # 정상 실행되면 즉시 반환되어야 함
    assert result == QDialog.DialogCode.Accepted


def test_flow_question_returns_true_under_pytest(qapp):
    """flow_question이 사용자 입력 대기 없이 Accept(True) 반환."""
    from flow.ui.dialogs import flow_question
    result = flow_question(None, "확인", "테스트 메시지")
    assert result is True


def test_flow_warning_returns_under_pytest(qapp):
    """flow_warning도 즉시 반환 (블로킹 없음)."""
    from flow.ui.dialogs import flow_warning
    # 호출만 잘 되면 됨 (반환값은 사용 안 함)
    result = flow_warning(None, "경고", "테스트")
    assert result is True


def test_flow_input_text_returns_default_under_pytest(qapp):
    """pytest 모드에서는 입력값으로 default 그대로 반환."""
    from flow.ui.dialogs import flow_input_text
    text, ok = flow_input_text(None, "입력", "값:", default="abc")
    assert ok is True
    assert text == "abc"


def test_monkeypatch_can_still_override_in_specific_tests(qapp, monkeypatch):
    """특정 동작 검증이 필요한 테스트는 monkeypatch로 헬퍼를 직접 패치 가능."""
    from flow.ui import dialogs as _dialogs

    calls = []
    def fake_question(parent, title, msg, **kw):
        calls.append((title, msg))
        return False  # cancel 시나리오 시뮬레이션

    monkeypatch.setattr(_dialogs, "flow_question", fake_question)
    result = _dialogs.flow_question(None, "T", "M")
    assert result is False
    assert calls == [("T", "M")]
