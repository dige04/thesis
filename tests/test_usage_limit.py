"""Tests for fatal provider quota/usage-limit detection (fail-fast)."""

from src.errors import is_usage_limit_error


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
