"""Integration test for the E8 analysis pipeline (scripts/run_analysis.py).

Builds a tiny fixture run matrix (3 sequences × 3 policies, 3 seeds) and runs
the full driver, asserting it turns runs/ into the results artifacts (aggregated
JSON, stats CSVs, memory-lift CSV) without crashing. This is the one-command
pipeline that converts the real 144-run matrix into thesis results.
"""

import csv
import json

from scripts.run_analysis import main


def _write_runs(runs_dir, repos, policies, seeds=(1, 2, 3)):
    """Fixture: one run dir per (policy, repo, seed), each with a task_results.jsonl.

    Seeds default to (1, 2, 3) to match the completeness contract introduced by
    Task 5 / D-5 — the memory-lift stage now requires all three expected seeds for
    both no_memory and full_memory before computing a cell's lift.
    """
    for repo in repos:
        n = 6
        for policy in policies:
            for seed in seeds:
                rd = runs_dir / f"pilot_{policy}_{repo}_seed{seed}"
                rd.mkdir(parents=True, exist_ok=True)
                # full_memory resolves slightly more than the others (so contrasts have signal)
                base_hits = {"full_memory": 4, "no_memory": 3, "random_prune": 2}.get(policy, 3)
                with open(rd / "task_results.jsonl", "w") as f:
                    for i in range(n):
                        f.write(json.dumps({
                            "policy": policy, "repo": repo, "seed": seed,
                            "sequence_index": i,
                            "resolved": 1 if i < base_hits else 0,
                            "total_tokens": 1000 + 100 * i + {"full_memory": 500, "no_memory": 0, "random_prune": 200}.get(policy, 0),
                            # footprint: Full grows unboundedly; pruned stays flat; no-memory = 0
                            "memory_tokens_after": {"full_memory": 300 * (i + 1), "no_memory": 0, "random_prune": 800}.get(policy, 0),
                            "estimated_cost_usd": 0.0,
                            "tool_calls": 5, "wall_time_seconds": 10.0,
                        }) + "\n")


def test_pipeline_produces_results(tmp_path):
    runs_dir = tmp_path / "runs"
    out = tmp_path / "results"
    repos = ["repo_a", "repo_b", "repo_c"]  # >=3 sequences so Wilcoxon runs
    # Write all 3 seeds so the completeness contract in stage_interdependence is met.
    _write_runs(runs_dir, repos, ["full_memory", "no_memory", "random_prune"], seeds=(1, 2, 3))

    rc = main([
        "--runs-dir", str(runs_dir), "--out", str(out),
        "--curriculum", str(tmp_path / "no_curriculum.json"),  # absent -> structural skipped gracefully
        "--n-boot", "200",
    ])
    assert rc == 0

    # aggregated
    agg_path = out / "aggregated" / "sequence_aggregates.json"
    assert agg_path.exists()
    agg = json.loads(agg_path.read_text())
    assert "full_memory" in agg and len(agg["full_memory"]) == 3

    # footprint axis (A4/H1b): Full's memory footprint exceeds No-Memory's (= 0)
    fm = agg["full_memory"]["repo_a"]
    assert "mean_footprint_tokens" in fm
    assert fm["mean_footprint_tokens"] > agg["no_memory"]["repo_a"]["mean_footprint_tokens"]

    # stats tables
    stats_csv = out / "tables" / "stats.csv"
    assert stats_csv.exists()
    rows = list(csv.DictReader(open(stats_csv)))
    assert any(r["Policy"] == "no_memory" for r in rows)

    # contrasts json carries a TOST outcome per contrast
    contrasts = json.loads((out / "tables" / "contrasts.json").read_text())
    assert all("tost" in c for c in contrasts["contrasts"])

    # memory-lift (full vs no_memory) computed per sequence — all 3 repos pass
    # the 3-seed completeness check, so all 3 appear in the CSV.
    lift_csv = out / "tables" / "memory_lift.csv"
    assert lift_csv.exists()
    lift_rows = list(csv.DictReader(open(lift_csv)))
    assert len(lift_rows) == 3  # one per repo (all complete — 3 seeds × 2 conditions)
    # n_seeds column added by D-5 fix for auditability
    assert "n_seeds" in lift_rows[0], "memory_lift.csv must carry an n_seeds column"
    assert all(int(r["n_seeds"]) == 3 for r in lift_rows), "all cells should average 3 seeds"

    # dropped_incomplete sidecar must exist (empty list when all cells are complete)
    sidecar = out / "tables" / "memory_lift_dropped.json"
    assert sidecar.exists()
    dropped = json.loads(sidecar.read_text())
    assert dropped == [], f"no cells should be dropped; got {dropped}"


def test_stage_aggregate_only(tmp_path):
    runs_dir = tmp_path / "runs"
    out = tmp_path / "results"
    _write_runs(runs_dir, ["repo_a"], ["full_memory", "no_memory"])
    rc = main(["--runs-dir", str(runs_dir), "--out", str(out), "--stage", "aggregate"])
    assert rc == 0
    assert (out / "aggregated" / "sequence_aggregates.json").exists()
