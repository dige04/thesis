"""Tests for the anchor-probe producer (THESIS_FINAL_v5.md §14.2, review blocker E2).

The metric function (``compute_anchor_probe_cl_metrics``) and the loader
(``load_anchor_probe_data``) already exist; E2 is the missing *producer* of the
per-run ``anchor_probe.json``. The schedule math is pure and pinned here against
the §14.2 formulas; the live re-evaluation (restore memory after task p, re-run
the agent on each anchor, score) is injected so the orchestration is unit-tested
with mocks and the output round-trips through the real aggregation path.
"""

import json

import pytest

from src.analysis.aggregate_results import _anchor_probe_cl_f1, load_anchor_probe_data
from src.benchmark.anchor_probe import (
    anchor_indices,
    build_anchor_probe_record,
    online_resolved_from_task_results,
    probe_points,
    write_anchor_probe,
)

# ---------------------------------------------------------------------------
# Schedule math (§14.2): k=5 anchors, 4 probe points
# ---------------------------------------------------------------------------


def test_anchor_indices_t30():
    # {ceil(T/10), ceil(3T/10), ceil(5T/10), ceil(7T/10), ceil(9T/10)}
    assert anchor_indices(30) == [3, 9, 15, 21, 27]


def test_probe_points_t30():
    # {ceil(T/4), ceil(T/2), ceil(3T/4), T}
    assert probe_points(30) == [8, 15, 23, 30]


def test_anchor_indices_shortest_sequence_t19():
    assert anchor_indices(19) == [2, 6, 10, 14, 18]


def test_probe_points_shortest_sequence_t19():
    assert probe_points(19) == [5, 10, 15, 19]


def test_schedule_bounded_and_within_range():
    for t in (19, 22, 32, 34, 44, 50):
        a = anchor_indices(t)
        p = probe_points(t)
        assert len(a) <= 5 and len(p) <= 4
        assert all(1 <= x <= t for x in a + p)
        assert max(p) == t  # final probe is the end-of-sequence T


# ---------------------------------------------------------------------------
# Producer orchestration (mocked restore + solve/eval)
# ---------------------------------------------------------------------------


def _mock_build(online_resolved, solve_fn):
    calls = {"restore": [], "solve": []}

    def restore_memory_fn(p):
        calls["restore"].append(p)
        return p  # stand-in: the memory state "after task p" is just p here

    def solve_and_eval_fn(task_id, memory_state):
        calls["solve"].append((task_id, memory_state))
        return solve_fn(task_id, memory_state)

    n = len(online_resolved)
    anchor_task_ids = {i: f"t{i}" for i in anchor_indices(n)}
    record = build_anchor_probe_record(
        policy="cls_consolidation",
        repo="django_django_sequence",
        seed=1,
        online_resolved=online_resolved,
        anchor_task_ids=anchor_task_ids,
        restore_memory_fn=restore_memory_fn,
        solve_and_eval_fn=solve_and_eval_fn,
    )
    return record, calls


def test_record_schema_and_only_existing_anchors_probed():
    record, calls = _mock_build([1] * 30, lambda _tid, _m: 1.0)

    assert set(record) == {
        "policy", "repo", "seed", "n_tasks",
        "anchor_indices", "probe_points", "online_resolved", "probed_accuracy",
    }
    assert record["n_tasks"] == 30
    assert len(record["online_resolved"]) == 30
    # restore called exactly once per probe point.
    assert calls["restore"] == [8, 15, 23, 30]
    # only anchors with i <= p are probed (no future-anchor leakage).
    for cell in record["probed_accuracy"]:
        assert cell["i"] <= cell["p"]
    # every anchor has the mandatory final-probe (i, T) cell.
    final = max(record["probe_points"])
    probed_pairs = {(c["i"], c["p"]) for c in record["probed_accuracy"]}
    for i in record["anchor_indices"]:
        assert (i, final) in probed_pairs


def test_record_feeds_metric_no_forgetting_gives_cl_f1_one():
    # All anchors solved at every probe + all online tasks resolved -> P=S=1.
    record, _ = _mock_build([1] * 30, lambda _tid, _m: 1.0)
    probed = {(c["i"], c["p"]): c["acc"] for c in record["probed_accuracy"]}

    from src.benchmark.cl_metrics import compute_anchor_probe_cl_metrics

    metrics = compute_anchor_probe_cl_metrics(
        online_resolved=record["online_resolved"],
        anchor_indices=record["anchor_indices"],
        probe_points=record["probe_points"],
        probed_accuracy=probed,
        n_tasks=record["n_tasks"],
    )
    assert metrics.stability == pytest.approx(1.0)
    assert metrics.cl_f1 == pytest.approx(1.0)


def test_record_captures_forgetting():
    # Anchor t3 is solved at early probes but FAILS at the final probe -> forgetting.
    def solve_fn(task_id, mem):
        return 0.0 if (task_id == "t3" and mem == 30) else 1.0

    record, _ = _mock_build([1] * 30, solve_fn)
    probed = {(c["i"], c["p"]): c["acc"] for c in record["probed_accuracy"]}

    from src.benchmark.cl_metrics import compute_anchor_probe_cl_metrics

    metrics = compute_anchor_probe_cl_metrics(
        online_resolved=record["online_resolved"],
        anchor_indices=record["anchor_indices"],
        probe_points=record["probe_points"],
        probed_accuracy=probed,
        n_tasks=record["n_tasks"],
    )
    # One of five anchors forgot completely -> mean_forgetting = 0.2, stability = 0.8.
    assert metrics.mean_forgetting == pytest.approx(0.2)
    assert metrics.stability == pytest.approx(0.8)


# ---------------------------------------------------------------------------
# Round-trip through the real aggregation loader
# ---------------------------------------------------------------------------


def test_write_and_load_round_trip(tmp_path):
    record, _ = _mock_build([1] * 30, lambda _tid, _m: 1.0)
    run_dir = tmp_path / "cls_consolidation_django_seed1"
    write_anchor_probe(run_dir, record)

    loaded = load_anchor_probe_data(tmp_path)
    key = ("cls_consolidation", "django_django_sequence", 1)
    assert key in loaded
    # The real consumption path computes a finite CL-F1 from the produced file.
    assert _anchor_probe_cl_f1(loaded[key]) == pytest.approx(1.0)


def test_online_resolved_read_in_sequence_order(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    rows = [
        {"sequence_index": 2, "resolved": 1},
        {"sequence_index": 0, "resolved": 0},
        {"sequence_index": 1, "resolved": 1},
    ]
    with open(run_dir / "task_results.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    assert online_resolved_from_task_results(run_dir) == [0, 1, 1]
