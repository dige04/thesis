"""Tests for the Phase 5.0 build-probe gate (decisions D + E).

Uses the REAL curriculum (data/SWE-Bench-CL-Curriculum.json) with an injected
verified_ids_loader + builder, so the coverage/exclusion/gate logic is exercised
end-to-end without Docker or network.
"""

import json

import pytest

from src.benchmark import build_probe as bp
from src.benchmark.swebenchcl_loader import SWEBenchCLLoader

CURRICULUM = "data/SWE-Bench-CL-Curriculum.json"


@pytest.fixture(scope="module")
def all_ids():
    seqs = SWEBenchCLLoader(CURRICULUM).load_all_sequences()
    return {t.task_id for s in seqs for t in s.tasks}


@pytest.fixture(scope="module")
def django_ids(all_ids):
    return sorted(i for i in all_ids if i.startswith("django__"))


def test_all_buildable_no_exclusions(all_ids):
    summary = bp.probe(
        CURRICULUM,
        verified_ids_loader=lambda: all_ids,
        builder=lambda i: (True, 1.0, None),
    )
    assert summary["exclusions"] == []
    assert summary["escalate_sequences"] == []
    assert summary["not_in_verified"] == []


def test_coverage_only_skips_builder(all_ids):
    calls = []
    summary = bp.probe(
        CURRICULUM,
        verified_ids_loader=lambda: all_ids,
        builder=lambda i: (calls.append(i), (True, 0.0, None))[1],
        build=False,
    )
    assert calls == []  # builder not invoked when build=False
    assert summary["exclusions"] == []


def test_missing_from_verified_is_excluded(all_ids, django_ids):
    drop = django_ids[0]
    summary = bp.probe(
        CURRICULUM,
        verified_ids_loader=lambda: all_ids - {drop},
        builder=lambda i: (True, 1.0, None),
    )
    assert drop in summary["not_in_verified"]
    assert drop in summary["exclusions"]


def test_gate_escalates_over_15_percent(all_ids, django_ids):
    # Fail 10 of django's 50 -> 20% > 15% -> escalate.
    fail = set(django_ids[:10])
    summary = bp.probe(
        CURRICULUM,
        verified_ids_loader=lambda: all_ids,
        builder=lambda i: (i not in fail, 1.0, None if i not in fail else "arm64 build failed"),
    )
    assert "django_django_sequence" in summary["escalate_sequences"]
    info = summary["per_sequence"]["django_django_sequence"]
    assert info["total"] == 50
    assert info["excluded"] == 10
    assert info["fraction"] == 0.2


def test_under_threshold_does_not_escalate(all_ids, django_ids):
    # Fail 5 of 50 -> 10% <= 15% -> no escalation.
    fail = set(django_ids[:5])
    summary = bp.probe(
        CURRICULUM,
        verified_ids_loader=lambda: all_ids,
        builder=lambda i: (i not in fail, 1.0, None),
    )
    assert summary["escalate_sequences"] == []
    assert summary["per_sequence"]["django_django_sequence"]["excluded"] == 5


def test_write_artifact(all_ids, tmp_path):
    summary = bp.probe(
        CURRICULUM,
        verified_ids_loader=lambda: all_ids,
        builder=lambda i: (True, 1.0, None),
    )
    path = bp.write_artifact(summary, tmp_path / "arm64_exclusions.json")
    data = json.loads(path.read_text())
    assert set(data) >= {"exclusions", "not_in_verified", "per_sequence", "escalate_sequences", "threshold"}
    assert data["threshold"] == 0.15
    assert len(data["per_sequence"]) == 8
