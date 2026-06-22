"""Tests for fatal provider quota/usage-limit detection and propagation (fail-fast)."""

from unittest.mock import MagicMock

import pytest

from src.errors import ReflectionError, UsageLimitError, is_usage_limit_error
from src.memory import reflection


class _Resp:
    def __init__(self, status_code):
        self.status_code = status_code


class _ApiErr(Exception):
    def __init__(self, msg, status_code=None):
        super().__init__(msg)
        self.status_code = status_code


# The actual OpenCode go message that corrupted half the pilot.
OPENCODE_GO = (
    "Error code: 429 - {'type': 'error', 'error': {'type': 'GoUsageLimitError', "
    "'message': 'Weekly usage limit reached. Resets in 5 days.'}}"
)


def test_detects_opencode_go_usage_limit():
    assert is_usage_limit_error(Exception(OPENCODE_GO)) is True


def test_detects_openai_insufficient_quota():
    assert is_usage_limit_error(_ApiErr("insufficient_quota: ...", status_code=429)) is True


def test_detects_429_with_usage_limit_text():
    assert is_usage_limit_error(_ApiErr("usage limit reached", status_code=429)) is True


def test_detects_via_response_status():
    e = Exception("quota exceeded")
    e.response = _Resp(429)
    assert is_usage_limit_error(e) is True


def test_transient_rate_limit_is_not_fatal():
    # A plain 429 "rate limit" (no quota/usage-limit wording) is transient, not fatal.
    assert is_usage_limit_error(_ApiErr("Rate limit exceeded, please retry", status_code=429)) is False


def test_unrelated_errors_not_fatal():
    assert is_usage_limit_error(ValueError("bad json")) is False
    assert is_usage_limit_error(_ApiErr("internal server error", status_code=500)) is False


# The actual 0G router billing error (the M3 free tier is balance-metered).
ZEROG_BALANCE = (
    "Error code: 402 - {'error': {'message': 'Insufficient balance', "
    "'type': 'payment_error', 'code': 'insufficient_balance'}}"
)


def test_detects_0g_insufficient_balance():
    # A balance-depletion 402 must be FATAL (fail-closed), not a silent
    # resolved=0 — otherwise it corrupts the matrix when 0G credit runs out.
    assert is_usage_limit_error(_ApiErr(ZEROG_BALANCE, status_code=402)) is True


def test_detects_insufficient_balance_text_without_status():
    assert is_usage_limit_error(Exception("insufficient_balance")) is True


def test_402_payment_required_is_fatal():
    # Any 402 Payment Required is a billing/balance wall — fatal.
    assert is_usage_limit_error(_ApiErr("payment required", status_code=402)) is True


# --- C5 propagation: quota during reflection must NOT be downgraded ---------

class _Task:
    task_id = "repo__repo-1"


def _reflection_kwargs():
    return dict(
        task=_Task(),
        trajectory={},
        patch="",
        evaluation_result={},
        memory_store=MagicMock(),
        policy=MagicMock(),
        retrieved_memory_ids=[],
        sequence_index=0,
        model="fake-model",
        temperature=0,
    )


def test_reflection_reraises_usage_limit_not_wrapped(monkeypatch):
    """A quota error raised by the classifier must propagate as UsageLimitError.

    Regression for THESIS_REVIEW C5/#8: the classifier raises UsageLimitError (a
    sibling of ClassifierError), which fell through to reflection's generic handler
    and was re-wrapped as ReflectionError — which the runner swallows with "continue
    without memory", silently mutating the experimental condition.
    """
    monkeypatch.setattr(
        reflection, "_extract_reflection_data",
        lambda **kw: {
            "issue_summary": "x", "patch_summary": "y",
            "files_touched": [], "functions_touched": [],
        },
    )

    def _raise_quota(**kw):
        raise UsageLimitError("429 weekly usage limit reached")

    monkeypatch.setattr(reflection, "classify_memory_type", _raise_quota)

    with pytest.raises(UsageLimitError):
        reflection.reflect_and_write_memory(**_reflection_kwargs())


def test_reflection_still_wraps_generic_failures_as_reflection_error(monkeypatch):
    """Non-quota failures keep the existing (non-fatal) ReflectionError semantics."""
    monkeypatch.setattr(
        reflection, "_extract_reflection_data",
        lambda **kw: {
            "issue_summary": "x", "patch_summary": "y",
            "files_touched": [], "functions_touched": [],
        },
    )

    def _raise_generic(**kw):
        raise RuntimeError("transient model glitch")

    monkeypatch.setattr(reflection, "classify_memory_type", _raise_generic)

    with pytest.raises(ReflectionError):
        reflection.reflect_and_write_memory(**_reflection_kwargs())
