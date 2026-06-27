"""Tests for SWEBenchEvaluator JSON report parsing (plan 5.1).

The evaluator must read the harness's JSON `resolved` verdict and must NOT fall
back to substring matching (an issue body containing "failed" must not flip the
verdict). The actual Docker/swebench harness invocation is validated in the live
environment; these tests cover the parsing contract only.
"""

from types import SimpleNamespace

from src.benchmark.evaluator import SWEBenchEvaluator


def _result(stdout="", stderr="", returncode=0):
    return SimpleNamespace(stdout=stdout, stderr=stderr, returncode=returncode)


def _ev():
    return SWEBenchEvaluator(docker_image="fake", timeout_seconds=1)


def test_parse_single_instance_resolved_true():
    out = _ev()._parse_evaluation_output(_result('{"resolved": true}'), "django__django-1")
    assert out["success"] is True and out["passed"] is True


def test_parse_single_instance_resolved_false():
    out = _ev()._parse_evaluation_output(_result('{"resolved": false}'), "django__django-1")
    assert out["success"] is True and out["passed"] is False


def test_parse_per_instance_map():
    report = '{"django__django-1": {"resolved": false}, "other": {"resolved": true}}'
    out = _ev()._parse_evaluation_output(_result(report), "django__django-1")
    assert out["success"] is True and out["passed"] is False


def test_parse_resolved_ids_list():
    report = '{"resolved_ids": ["django__django-1", "x"]}'
    assert _ev()._parse_evaluation_output(_result(report), "django__django-1")["passed"] is True
    assert _ev()._parse_evaluation_output(_result(report), "absent")["passed"] is False


def test_parse_report_on_last_line():
    stdout = 'building image...\nrunning FAIL_TO_PASS...\n{"resolved": true}'
    out = _ev()._parse_evaluation_output(_result(stdout), "django__django-1")
    assert out["passed"] is True


def test_docker_failure_no_report():
    out = _ev()._parse_evaluation_output(_result(stdout="", stderr="boom", returncode=1), "t")
    assert out["success"] is False and out["passed"] is False
    assert "exit code 1" in out["error"]


def test_unparseable_success_exit_is_error_not_pass():
    out = _ev()._parse_evaluation_output(_result(stdout="all good", returncode=0), "t")
    assert out["success"] is False
    assert "Could not parse" in out["error"]


def test_substring_failed_does_not_flip_verdict():
    # No JSON report, just prose mentioning "failed" — must NOT be read as a verdict.
    out = _ev()._parse_evaluation_output(
        _result(stdout="the issue mentions tests failed in the past", returncode=0), "t"
    )
    assert out["success"] is False  # no report → cannot determine, not a false "pass"
