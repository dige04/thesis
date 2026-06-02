"""Tests for the SWE-bench_Verified loader (decision E)."""

from src.benchmark import verified_loader as vl


def _fake_rows():
    return [
        {
            "instance_id": "django__django-1",
            "repo": "django/django",
            "base_commit": "base1",
            "environment_setup_commit": "env1",
            "version": "4.0",
            "test_patch": "tp",
            "patch": "gold",
            "FAIL_TO_PASS": '["test_a", "test_b"]',   # JSON-encoded string
            "PASS_TO_PASS": '["test_c"]',
        },
        {
            "instance_id": "pytest-dev__pytest-2",
            "repo": "pytest-dev/pytest",
            "base_commit": "base2",
            "environment_setup_commit": "env2",
            "version": "7.1",
            "test_patch": "tp2",
            "patch": "gold2",
            "FAIL_TO_PASS": '["t1"]',
            "PASS_TO_PASS": "[]",
        },
    ]


def _loader(_name, _split):
    return _fake_rows()


def setup_function():
    vl.clear_cache()


def test_index_keyed_by_instance_id():
    idx = vl.load_verified_index(loader=_loader)
    assert set(idx) == {"django__django-1", "pytest-dev__pytest-2"}


def test_fail_to_pass_pass_to_pass_json_decoded():
    inst = vl.get_verified_instance("django__django-1", loader=_loader)
    assert inst["fail_to_pass"] == ["test_a", "test_b"]
    assert inst["pass_to_pass"] == ["test_c"]
    assert inst["environment_setup_commit"] == "env1"
    assert inst["version"] == "4.0"


def test_missing_instance_returns_none():
    assert vl.get_verified_instance("absent__absent-9", loader=_loader) is None


def test_verified_instance_ids_set():
    ids = vl.verified_instance_ids(loader=_loader)
    assert ids == {"django__django-1", "pytest-dev__pytest-2"}


def test_cache_reused_until_cleared():
    calls = {"n": 0}

    def counting_loader(_n, _s):
        calls["n"] += 1
        return _fake_rows()

    vl.load_verified_index(loader=counting_loader)
    vl.load_verified_index(loader=counting_loader)
    assert calls["n"] == 1  # second call served from cache
    vl.clear_cache()
    vl.load_verified_index(loader=counting_loader)
    assert calls["n"] == 2
