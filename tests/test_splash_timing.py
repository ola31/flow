"""스플래시 최소 노출 시간 계산.

띄운 시점을 기준으로 남은 시간만 기다려야 한다. 창을 다 만든 뒤부터
고정 시간을 세면 그 값이 시작 시간에 통째로 더해진다 — 느린 PC일수록
이미 오래 기다린 사용자를 더 붙잡는 셈이 된다.
"""
from __future__ import annotations

import pytest

from flow.main import SPLASH_MIN_VISIBLE_S, _splash_wait_seconds


def test_no_wait_when_startup_already_took_longer_than_the_minimum():
    shown_at = 100.0
    now = shown_at + SPLASH_MIN_VISIBLE_S + 1.2  # 창 만드느라 이미 초과

    assert _splash_wait_seconds(shown_at, now) == 0.0


def test_waits_only_the_remainder_of_the_minimum():
    shown_at = 100.0
    now = shown_at + 0.1

    assert _splash_wait_seconds(shown_at, now) == pytest.approx(
        SPLASH_MIN_VISIBLE_S - 0.1
    )


def test_no_wait_when_the_splash_never_appeared():
    """이미지가 없어 스플래시를 못 띄운 실행은 기다릴 이유가 없다."""
    assert _splash_wait_seconds(None, 100.0) == 0.0


def test_minimum_is_short_enough_to_not_dominate_startup():
    """노출 하한이 시작 시간의 주된 항목이 되면 안 된다."""
    assert 0 < SPLASH_MIN_VISIBLE_S <= 1.0
