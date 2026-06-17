"""E8 — one-command analysis pipeline: runs/ -> aggregated -> stats -> tables -> plots -> E7.

Turns a completed run matrix into the thesis's results artifacts by chaining the
src/analysis modules (E3-corrected stats, E7 interdependence). Stages are
selectable so the Make targets (aggregate / stats / plots) can call individual
phases; `--stage all` (default) runs everything. Defensive: a stage that lacks
its input is skipped with a warning rather than crashing the pipeline.

Usage:
  .venv/bin/python -m scripts.run_analysis --runs-dir runs --out results
  make aggregate | make stats | make plots | make results
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from src.analysis.aggregate_results import aggregate_sequence_results
from src.analysis.interdependence import (
    memory_lift_by_position,
    sequence_task_files,
    structural_interdependence,
)
from src.analysis.plots import plot_pareto_frontier
from src.analysis.result_tables import (
    generate_effect_size_table,
    generate_statistical_test_table,
)
from src.analysis.statistical_tests import compute_all_contrasts_with_bootstrap, tost

# The 5 pre-registered contrasts vs full_memory (Invariant #11).
CONTRASTS = [
    "random_prune",
    "recency_prune",
    "type_aware_decay",
    "cls_consolidation",
    "no_memory",
]


def stage_aggregate(runs_dir: Path, out: Path) -> dict[str, Any]:
    agg_path = out / "aggregated" / "sequence_aggregates.json"
    agg = aggregate_sequence_results(runs_dir, output_path=agg_path)
    n_seq = len({s for pol in agg.values() for s in pol})
    print(f"[aggregate] {len(agg)} policies x {n_seq} sequences -> {agg_path}")
    return agg


def stage_stats(agg: dict[str, Any], out: Path, n_boot: int, seed: int) -> dict | None:
    if "full_memory" not in agg:
        print("[stats] SKIP — no full_memory baseline present")
        return None
    contrasts = [c for c in CONTRASTS if c in agg]
    res = compute_all_contrasts_with_bootstrap(
        agg,
        metric="mean_cl_f1",
        baseline_policy="full_memory",
        contrasts=contrasts,
        n_bootstrap=n_boot,
        random_seed=seed,
    )
    base = {s: m["mean_cl_f1"] for s, m in agg["full_memory"].items()}
    for c in res["contrasts"]:
        diffs = [agg[c["policy"]][s]["mean_cl_f1"] - base[s] for s in c["sequences"]]
        c["tost"] = tost(diffs, random_seed=seed) if len(diffs) >= 2 else None

    tdir = out / "tables"
    tdir.mkdir(parents=True, exist_ok=True)
    generate_statistical_test_table(res, tdir / "stats.csv")
    generate_effect_size_table(res, tdir / "effect_sizes.csv")
    (tdir / "contrasts.json").write_text(json.dumps(res, indent=2, default=str))

    srcs = {s.get("cl_f1_source") for pol in agg.values() for s in pol.values()}
    print(f"[stats] {res['n_contrasts']} contrasts (cl_f1_source={sorted(srcs)}) -> {tdir}")
    if srcs == {"resolved_rate_proxy"}:
        print("[stats] WARNING: CL-F1 is the resolved-rate PROXY (no anchor_probe.json present).")
    return res


def stage_plots(agg: dict[str, Any], out: Path) -> None:
    pdir = out / "plots"
    pdir.mkdir(parents=True, exist_ok=True)
    # The two-axis Pareto IS the headline contribution: forgetting wins on the
    # footprint axis even where it ties on compute (A4/H1b).
    for axis, metric_x, fname in [
        ("compute (total tokens)", "mean_total_tokens", "pareto_compute.png"),
        ("memory footprint (tokens)", "mean_footprint_tokens", "pareto_footprint.png"),
    ]:
        try:
            plot_pareto_frontier(
                agg,
                pdir / fname,
                metric_x=metric_x,
                metric_y="mean_cl_f1",
                title=f"CL-F1 vs {axis}",
            )
            print(f"[plots] Pareto ({axis}) -> {pdir / fname}")
        except Exception as e:  # noqa: BLE001 — never crash the pipeline on a plot
            print(f"[plots] Pareto ({axis}) skipped: {type(e).__name__}: {e}")


def _resolved_by_index(runs_dir: Path) -> dict[tuple[str, str], dict[int, int]]:
    """Map {(policy, repo): {sequence_index: resolved}} across all run dirs."""
    out: dict[tuple[str, str], dict[int, int]] = defaultdict(dict)
    for rd in Path(runs_dir).iterdir():
        trp = rd / "task_results.jsonl"
        if not (rd.is_dir() and trp.exists()):
            continue
        for line in trp.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            pol, repo, idx = d.get("policy"), d.get("repo"), d.get("sequence_index")
            if pol is None or repo is None or idx is None:
                continue
            out[(pol, repo)][int(idx)] = int(bool(d.get("resolved", 0)))
    return out


def stage_interdependence(runs_dir: Path, out: Path, curriculum: Path | None) -> None:
    tdir = out / "tables"
    tdir.mkdir(parents=True, exist_ok=True)

    # E7 memory-lift: full_memory vs no_memory per sequence (the does-memory-help verdict).
    by_idx = _resolved_by_index(runs_dir)
    repos = sorted({repo for (_, repo) in by_idx})
    rows = []
    for repo in repos:
        nm, fl = by_idx.get(("no_memory", repo)), by_idx.get(("full_memory", repo))
        if not nm or not fl:
            continue
        common = sorted(set(nm) & set(fl))
        if len(common) < 2:
            continue
        lift = memory_lift_by_position([nm[i] for i in common], [fl[i] for i in common])
        rows.append({"repo": repo, **{k: lift[k] for k in (
            "overall_lift", "first_half_lift", "second_half_lift", "late_minus_early", "n_tasks")}})
    if rows:
        with open(tdir / "memory_lift.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f"[interdependence] memory-lift for {len(rows)} sequences -> {tdir / 'memory_lift.csv'}")
    else:
        print("[interdependence] memory-lift SKIP — need no_memory + full_memory runs per sequence")

    # E7 structural interdependence: gold-patch file overlap with earlier tasks.
    if curriculum and Path(curriculum).exists():
        try:
            cur = json.loads(Path(curriculum).read_text())
            seqs = cur.get("sequences", cur) if isinstance(cur, dict) else cur
            srows = []
            for s in seqs:
                patches = [t.get("gold_patch", "") for t in s.get("tasks", [])]
                r = structural_interdependence(sequence_task_files(patches))
                srows.append({
                    "sequence": s.get("sequence_name") or s.get("repo"),
                    "mean_prior_overlap": round(r["mean_prior_overlap"], 4),
                    "frac_tasks_with_dependency": round(r["frac_tasks_with_dependency"], 4),
                    "n_tasks": r["n_tasks"],
                })
            if srows:
                with open(tdir / "structural_interdependence.csv", "w", newline="") as f:
                    w = csv.DictWriter(f, fieldnames=list(srows[0].keys()))
                    w.writeheader()
                    w.writerows(srows)
                print(f"[interdependence] structural for {len(srows)} sequences -> {tdir / 'structural_interdependence.csv'}")
        except Exception as e:  # noqa: BLE001
            print(f"[interdependence] structural skipped: {type(e).__name__}: {e}")
    else:
        print("[interdependence] structural SKIP — curriculum not found")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="E8 analysis pipeline (runs -> results).")
    p.add_argument("--runs-dir", type=Path, default=Path("runs"))
    p.add_argument("--out", type=Path, default=Path("results"))
    p.add_argument("--curriculum", type=Path, default=Path("data/SWE-Bench-CL-Curriculum.json"))
    p.add_argument(
        "--stage",
        choices=["aggregate", "stats", "plots", "interdependence", "all"],
        default="all",
    )
    p.add_argument("--n-boot", type=int, default=5000)
    p.add_argument("--random-seed", type=int, default=12345)
    a = p.parse_args(argv)

    agg = stage_aggregate(a.runs_dir, a.out)  # always needed downstream
    if a.stage in ("stats", "all"):
        stage_stats(agg, a.out, a.n_boot, a.random_seed)
    if a.stage in ("plots", "all"):
        stage_plots(agg, a.out)
    if a.stage in ("interdependence", "all"):
        stage_interdependence(a.runs_dir, a.out, a.curriculum)
    print("[run_analysis] done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
