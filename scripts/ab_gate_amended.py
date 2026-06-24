"""Amended A/B instrument-health gate (Codex 2026-06-24 review).

Replaces the original §5 gate's ``edit_failure_ratio <= 0.15`` criterion, which
conflated MODEL-quality diff errors (malformed diffs / wrong paths — a fixed
property of the frozen model, present in both arms) with INSTRUMENT health.
See ``docs/amended-gate-2026-06-24.md`` for the PRE-RUN criteria and rationale.

Verdicts
--------
BLOCKED  Structural/provenance: <36 complete, any RUN_FAILED.json, any run
         missing, any run whose RUN_COMPLETED provenance mismatches
         (experiment_sha / tool_mode-vs-run_id / config_hash), or incomplete
         pairing (a (sequence,policy,seed) lacking legacy or fixed, or task_ids
         not matching across the pair). Metrics NOT computed when blocked.

STOP     Health failed: instrument-attributable edit failures > 0, OR token
         inflation > 1.5x (fixed median vs legacy median, prompt OR total), OR
         model-quality edit-error rate(fixed) > rate(legacy).

GO       All health criteria pass.

The 0.15 total edit-failure-ratio is INTENTIONALLY NOT a criterion here.

Usage
-----
    python -m scripts.ab_gate_amended --runs-root runs_ab_cceb325 \
        --expected-sha cceb3253d7b7cfeae16123af30197a8271e1d84a \
        --expected-config-hash 2e7f341cc35d31c2
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
from pathlib import Path
from typing import Any

from scripts.ab_schedule import ab_schedule
from scripts.ab_gate import _load_task_results, _load_trajectories
from src.agents.tools import _strip_container_prefix

# ---------------------------------------------------------------------------
# Edit-failure classification (reproduces the verified 2026-06-24 decomposition:
# instrument=79 [77 false-security + 2 normalize-gap], correct_reject=1, model=92)
# ---------------------------------------------------------------------------

_SEC_RX = re.compile(r"diff touches '([^']+)' but path='([^']+)'")
_GIT_PREFIX_TESTBED_RX = re.compile(r"[ab]/testbed/")


def classify_edit_failure(obs: str) -> str | None:
    """Classify an edit_file observation_summary.

    Returns ``None`` (success / not an error), ``"instrument"`` (a defect the
    tool's path handling caused), ``"model"`` (the model emitted a bad diff /
    wrong path — the instrument reported it correctly), or ``"correct_reject"``
    (the security guard correctly refused a genuine multi-file diff).
    """
    o = str(obs)
    if not o.startswith("ERROR:"):
        return None
    low = o.lower()

    # Security-guard rejections: false iff the touched file and the path arg are
    # the SAME file after normalisation (the bug); genuine multi-file otherwise.
    m = _SEC_RX.search(o)
    if m:
        if _strip_container_prefix(m.group(1)) == _strip_container_prefix(m.group(2)):
            return "instrument"
        return "correct_reject"

    # A surviving git-prefix + container root in the git error ('b/testbed/...:
    # No such file') means the normaliser failed to strip it -> instrument.
    if _GIT_PREFIX_TESTBED_RX.search(o):
        return "instrument"

    # Everything else that errored (corrupt patch, context 'does not match index',
    # clean relative file-not-found) is the model's diff quality -> model.
    return "model"


# ---------------------------------------------------------------------------
# Provenance helpers
# ---------------------------------------------------------------------------


def _expected_mode(run_id: str) -> str | None:
    if run_id.endswith("_legacy"):
        return "legacy"
    if run_id.endswith("_fixed"):
        return "fixed"
    return None


def _read_completed(run_dir: Path) -> dict | None:
    p = run_dir / "RUN_COMPLETED.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _median(xs: list[int | float]) -> float:
    return float(statistics.median(xs)) if xs else 0.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def ab_gate_amended(
    runs_root: Path | str,
    expected_sha: str | None = None,
    expected_config_hash: str | None = None,
    schedule_seed: int = 20260622,
    inflation_max: float = 1.5,
) -> dict[str, Any]:
    runs_root = Path(runs_root)
    schedule = ab_schedule(seed=schedule_seed)
    note = (
        "Amended gate (docs/amended-gate-2026-06-24.md): instrument-attributable "
        "failures==0; the 0.15 total-ratio is NOT a criterion."
    )

    # -- Phase 0: structural completeness + RUN_FAILED ----------------------
    missing, failed, incomplete = [], [], []
    for c in schedule:
        rd = runs_root / c["run_id"]
        if not rd.is_dir():
            missing.append(c["run_id"])
            continue
        if (rd / "RUN_FAILED.json").exists():
            failed.append(c["run_id"])
        if not (rd / "RUN_COMPLETED.json").exists():
            incomplete.append(c["run_id"])
    structural = []
    if missing:
        structural.append(f"{len(missing)} run dir(s) missing: {missing[:5]}")
    if failed:
        structural.append(f"{len(failed)} run(s) have RUN_FAILED.json: {failed[:5]}")
    if incomplete:
        structural.append(f"{len(incomplete)} run(s) lack RUN_COMPLETED.json: {incomplete[:5]}")
    if structural:
        return _blocked(structural, note)

    # -- Phase 1: provenance (sha / tool_mode-vs-run_id / config_hash) ------
    prov = []
    for c in schedule:
        rd = runs_root / c["run_id"]
        sent = _read_completed(rd)
        if sent is None:
            prov.append(f"{c['run_id']}: RUN_COMPLETED.json unreadable")
            continue
        if expected_sha and sent.get("experiment_sha") != expected_sha:
            prov.append(f"{c['run_id']}: experiment_sha {sent.get('experiment_sha')!r} != {expected_sha!r}")
        exp_mode = _expected_mode(c["run_id"])
        if sent.get("tool_mode") != c["tool_mode"] or (exp_mode and sent.get("tool_mode") != exp_mode):
            prov.append(f"{c['run_id']}: tool_mode {sent.get('tool_mode')!r} != expected {c['tool_mode']!r}")
        if expected_config_hash and sent.get("config_hash") != expected_config_hash:
            prov.append(f"{c['run_id']}: config_hash {sent.get('config_hash')!r} != {expected_config_hash!r}")
        # Row-level provenance: every task_results row's recorded tool_mode must
        # match the cell's expected mode. A CORRECT sentinel with WRONG rows means
        # data from the other mode was written into this run dir (Codex 2026-06-24
        # reproduction) — the sentinel check alone does not catch it.
        row_modes = {
            r.get("tool_mode")
            for r in _load_task_results(rd)
            if r.get("tool_mode") is not None
        }
        bad_rows = sorted(m for m in row_modes if m != c["tool_mode"])
        if bad_rows:
            prov.append(
                f"{c['run_id']}: task_results rows have tool_mode {bad_rows} != "
                f"expected {c['tool_mode']!r}"
            )
    if prov:
        return _blocked(prov, note)

    # -- Phase 2: pairing (every (seq,policy,seed) has both modes; task_ids match)
    by_key: dict[tuple, dict[str, str]] = {}
    for c in schedule:
        by_key.setdefault((c["policy"], c["sequence_name"], c["seed"]), {})[c["tool_mode"]] = c["run_id"]
    pairing = []
    for key, modes in by_key.items():
        lid, fid = modes.get("legacy"), modes.get("fixed")
        if not lid or not fid:
            pairing.append(f"Key {key} missing a mode: {modes}")
            continue
        ltasks = {r["task_id"] for r in _load_task_results(runs_root / lid) if "task_id" in r}
        ftasks = {r["task_id"] for r in _load_task_results(runs_root / fid) if "task_id" in r}
        if ltasks != ftasks:
            pairing.append(
                f"Unmatched task_ids for {key}: legacy-only={sorted(ltasks - ftasks)[:3]}, "
                f"fixed-only={sorted(ftasks - ltasks)[:3]}"
            )
    if pairing:
        return _blocked(pairing, note)

    # -- Phase 3: health metrics -------------------------------------------
    def arm_stats(mode: str) -> dict:
        ptoks, ttoks = [], []
        edit_calls = instrument = model = correct = 0
        for c in schedule:
            if c["tool_mode"] != mode:
                continue
            rd = runs_root / c["run_id"]
            for r in _load_task_results(rd):
                ptoks.append(int(r.get("prompt_tokens", 0) or 0))
                ttoks.append(int(r.get("total_tokens", 0) or 0))
            for traj in _load_trajectories(rd):
                for step in traj.get("steps", []):
                    if step.get("action") != "edit_file":
                        continue
                    edit_calls += 1
                    cls = classify_edit_failure(step.get("observation_summary", ""))
                    if cls == "instrument":
                        instrument += 1
                    elif cls == "model":
                        model += 1
                    elif cls == "correct_reject":
                        correct += 1
        return {
            "edit_calls": edit_calls,
            "instrument_failures": instrument,
            "model_failures": model,
            "correct_rejects": correct,
            "model_quality_rate": (model / edit_calls) if edit_calls else 0.0,
            "prompt_median": _median(ptoks),
            "total_median": _median(ttoks),
        }

    fixed = arm_stats("fixed")
    legacy = arm_stats("legacy")

    prompt_infl = (fixed["prompt_median"] / legacy["prompt_median"]) if legacy["prompt_median"] else 0.0
    total_infl = (fixed["total_median"] / legacy["total_median"]) if legacy["total_median"] else 0.0

    reasons = []
    # (3) instrument-attributable failures == 0 (fixed arm is the one under test)
    if fixed["instrument_failures"] != 0:
        reasons.append(
            f"instrument-attributable edit failures (fixed) == {fixed['instrument_failures']} (must be 0)"
        )
    # (4) token inflation <= 1.5x
    if prompt_infl > inflation_max:
        reasons.append(f"prompt-token inflation {prompt_infl:.3f} > {inflation_max}")
    if total_infl > inflation_max:
        reasons.append(f"total-token inflation {total_infl:.3f} > {inflation_max}")
    # (5) model-quality rate fixed <= legacy (sanity lower-bound)
    if fixed["model_quality_rate"] > legacy["model_quality_rate"]:
        reasons.append(
            f"model-quality rate fixed {fixed['model_quality_rate']:.3f} > legacy "
            f"{legacy['model_quality_rate']:.3f} (fix must not regress diff quality)"
        )

    metrics = {
        "fixed": fixed,
        "legacy": legacy,
        "prompt_inflation_ratio": round(prompt_infl, 4),
        "total_inflation_ratio": round(total_infl, 4),
    }
    return {
        "gate": "GO" if not reasons else "STOP",
        "metrics": metrics,
        "reasons": reasons,
        "criteria": "complete+paired+provenance, instrument-attributable==0, "
        "inflation<=1.5x, model-quality fixed<=legacy (NOT 0.15 total-ratio)",
        "note": note,
    }


def _blocked(reasons: list[str], note: str) -> dict:
    return {"gate": "BLOCKED", "reason": reasons[0], "reasons": reasons, "metrics": {}, "note": note}


def main() -> None:
    p = argparse.ArgumentParser(description="Amended A/B instrument-health gate.")
    p.add_argument("--runs-root", required=True)
    p.add_argument("--expected-sha", default=None)
    p.add_argument("--expected-config-hash", default=None)
    p.add_argument("--schedule-seed", type=int, default=20260622)
    a = p.parse_args()
    result = ab_gate_amended(
        runs_root=a.runs_root,
        expected_sha=a.expected_sha,
        expected_config_hash=a.expected_config_hash,
        schedule_seed=a.schedule_seed,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
