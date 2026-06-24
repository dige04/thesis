# Codex Preflight Proof — post-hotfix A/B (do NOT launch until approved)

Branch `rerun/instrument-fix` tip **3a0ec45**. Agent freeze **cceb325** (`git diff cceb325..HEAD -- src/agents/` EMPTY). All fixes no-compute + tested; NO compute run.

## Checklist mapping (Codex 2026-06-24)

| # | Requirement | Evidence |
|---|---|---|
| 1 | runner reads tool_mode per unit | `run_matrix_shard.sh` calls `shard_units.py` + sets `AGENT_TOOL_MODE=$eff_mode` per unit + `--tool-mode`; tests `test_shard_units_*` |
| 2 | amended scorer (no 0.15) | `ab_gate_amended.py`; tests `test_amended_gate_*` (BLOCKED sha/mode/cfg/unpaired/missing/failed; STOP instrument/inflation/model-rate; GO; **GO despite 0.5 model-ratio**) |
| 3 | manifest = 36 cells | `test_ab_manifest_36_cells...` + live build below |
| 4 | every (seq,policy,seed) has both modes | same test (18 pairs, 0 unpaired) |
| 5 | worker map co-locates pairs | same test (0 split across workers) |
| 6 | freeze + old STOP persisted (tracked) | git ls-files below |
| 7 | runtime sets SHA/RUNS_ROOT/MANIFEST | freeze.json:ab_runtime_contract |

## Tracked artifacts (force-added past results/ gitignore)
```
results/manifest/ab_gate_STOP_2133b47.json
results/manifest/freeze.json
results/manifest/freeze_2133b47_STOP.json
results/manifest/runs_ab_cceb325.json
results/manifest/worker_map_ab_cceb325.json
```

## Test output (verbose names = the proven properties)
```
test_ab_preflight.py::test_shard_units_worker_field_selects_by_worker_and_emits_tool_mode PASSED [  2%]
test_ab_preflight.py::test_shard_units_modulo_fallback_when_no_worker_field PASSED [  4%]
test_ab_preflight.py::test_shard_units_tool_mode_defaults_empty_when_absent PASSED [  6%]
test_ab_preflight.py::test_ab_manifest_36_cells_all_paired_and_colocated PASSED [  8%]
test_ab_preflight.py::test_worker_map_covers_all_runs PASSED       [ 10%]
test_ab_preflight.py::test_classify_false_security_reject_is_instrument PASSED [ 12%]
test_ab_preflight.py::test_classify_genuine_cross_file_is_correct_reject PASSED [ 14%]
test_ab_preflight.py::test_classify_normalize_gap_is_instrument PASSED [ 16%]
test_ab_preflight.py::test_classify_corrupt_patch_is_model PASSED  [ 18%]
test_ab_preflight.py::test_classify_success_is_none PASSED         [ 20%]
test_ab_preflight.py::test_amended_gate_go_on_clean_tree PASSED    [ 22%]
test_ab_preflight.py::test_amended_gate_blocked_missing_run PASSED [ 24%]
test_ab_preflight.py::test_amended_gate_blocked_run_failed PASSED  [ 26%]
test_ab_preflight.py::test_amended_gate_blocked_wrong_sha PASSED   [ 28%]
test_ab_preflight.py::test_amended_gate_blocked_wrong_tool_mode PASSED [ 30%]
test_ab_preflight.py::test_amended_gate_blocked_wrong_config_hash PASSED [ 32%]
test_ab_preflight.py::test_amended_gate_blocked_unpaired_task_ids PASSED [ 34%]
test_ab_preflight.py::test_amended_gate_stop_on_instrument_failure PASSED [ 36%]
test_ab_preflight.py::test_amended_gate_stop_on_token_inflation PASSED [ 38%]
test_ab_preflight.py::test_amended_gate_stop_when_fixed_model_rate_exceeds_legacy PASSED [ 40%]
test_ab_preflight.py::test_amended_gate_go_despite_high_model_ratio_proves_no_0_15_rule PASSED [ 42%]
test_agents_tools.py::test_tool_call_tracker PASSED                [ 44%]
test_agents_tools.py::test_read_file PASSED                        [ 46%]
test_agents_tools.py::test_write_file PASSED                       [ 48%]
test_agents_tools.py::test_edit_file PASSED                        [ 51%]
test_agents_tools.py::test_list_files PASSED                       [ 53%]
test_agents_tools.py::test_search_code PASSED                      [ 55%]
test_agents_tools.py::test_run_command PASSED                      [ 57%]
test_agents_tools.py::test_run_tests PASSED                        [ 59%]
test_agents_tools.py::test_get_patch PASSED                        [ 61%]
test_agents_tools.py::test_syntax_error_tracking PASSED            [ 63%]
test_agents_tools.py::test_tool_call_error_tracking PASSED         [ 65%]
test_agents_tools.py::test_read_file_range_exact_when_fits PASSED  [ 67%]
test_agents_tools.py::test_read_file_budget_and_no_skip PASSED     [ 69%]
test_agents_tools.py::test_read_file_oversized_line_progresses PASSED [ 71%]
test_agents_tools.py::test_read_file_invalid_and_oob PASSED        [ 73%]
test_agents_tools.py::test_edit_file_testbed_git_prefix_applies PASSED [ 75%]
test_agents_tools.py::test_edit_file_absolute_testbed_path_applies PASSED [ 77%]
test_agents_tools.py::test_edit_file_absolute_path_arg_applies PASSED [ 79%]
test_agents_tools.py::test_edit_file_double_slash_testbed_applies PASSED [ 81%]
test_agents_tools.py::test_edit_file_cross_file_rejected_with_abs_path_arg PASSED [ 83%]
test_agents_tools.py::test_edit_file_double_slash_testbed_git_header_applies PASSED [ 85%]
test_agents_tools.py::test_edit_file_absolute_repo_root_path_arg_applies PASSED [ 87%]
test_agents_tools.py::test_edit_file_path_arg_traversal_rejected PASSED [ 89%]
test_agents_tools.py::test_edit_file_cross_file_rejected PASSED    [ 91%]
test_agents_tools.py::test_edit_file_path_traversal_rejected PASSED [ 93%]
test_agents_tools.py::test_legacy_edit_file_does_not_enforce_cross_file_guard PASSED [ 95%]
test_agents_tools.py::test_read_file_pagination_no_skipped_lines PASSED [ 97%]
test_agents_tools.py::test_read_file_schema_and_no_get_patch PASSED [100%]

============================== 49 passed in 3.54s ==============================
```

## Real-data validation of the amended gate
```
# (a) old A/B data + demand NEW sha -> must BLOCK on provenance:
gate: BLOCKED | no_memory_pytest-dev_pytest_sequence_seed3_fixed: experiment_sha '2133b47' != 'c
# (b) old A/B data, no sha -> classifier anchor (must reproduce decomposition instrument=79):
gate: STOP
fixed instrument=79 model=92 correct=1 (rate 0.162); legacy model rate 0.251
```

## Code diff (scripts only; manifest JSON omitted for brevity)
```diff
diff --git a/scripts/ab_gate_amended.py b/scripts/ab_gate_amended.py
new file mode 100644
index 0000000..e617c2b
--- /dev/null
+++ b/scripts/ab_gate_amended.py
@@ -0,0 +1,282 @@
+"""Amended A/B instrument-health gate (Codex 2026-06-24 review).
+
+Replaces the original §5 gate's ``edit_failure_ratio <= 0.15`` criterion, which
+conflated MODEL-quality diff errors (malformed diffs / wrong paths — a fixed
+property of the frozen model, present in both arms) with INSTRUMENT health.
+See ``docs/amended-gate-2026-06-24.md`` for the PRE-RUN criteria and rationale.
+
+Verdicts
+--------
+BLOCKED  Structural/provenance: <36 complete, any RUN_FAILED.json, any run
+         missing, any run whose RUN_COMPLETED provenance mismatches
+         (experiment_sha / tool_mode-vs-run_id / config_hash), or incomplete
+         pairing (a (sequence,policy,seed) lacking legacy or fixed, or task_ids
+         not matching across the pair). Metrics NOT computed when blocked.
+
+STOP     Health failed: instrument-attributable edit failures > 0, OR token
+         inflation > 1.5x (fixed median vs legacy median, prompt OR total), OR
+         model-quality edit-error rate(fixed) > rate(legacy).
+
+GO       All health criteria pass.
+
+The 0.15 total edit-failure-ratio is INTENTIONALLY NOT a criterion here.
+
+Usage
+-----
+    python -m scripts.ab_gate_amended --runs-root runs_ab_cceb325 \
+        --expected-sha cceb3253d7b7cfeae16123af30197a8271e1d84a \
+        --expected-config-hash 2e7f341cc35d31c2
+"""
+from __future__ import annotations
+
+import argparse
+import json
+import re
+import statistics
+from pathlib import Path
+from typing import Any
+
+from scripts.ab_schedule import ab_schedule
+from scripts.ab_gate import _load_task_results, _load_trajectories
+from src.agents.tools import _strip_container_prefix
+
+# ---------------------------------------------------------------------------
+# Edit-failure classification (reproduces the verified 2026-06-24 decomposition:
+# instrument=79 [77 false-security + 2 normalize-gap], correct_reject=1, model=92)
+# ---------------------------------------------------------------------------
+
+_SEC_RX = re.compile(r"diff touches '([^']+)' but path='([^']+)'")
+_GIT_PREFIX_TESTBED_RX = re.compile(r"[ab]/testbed/")
+
+
+def classify_edit_failure(obs: str) -> str | None:
+    """Classify an edit_file observation_summary.
+
+    Returns ``None`` (success / not an error), ``"instrument"`` (a defect the
+    tool's path handling caused), ``"model"`` (the model emitted a bad diff /
+    wrong path — the instrument reported it correctly), or ``"correct_reject"``
+    (the security guard correctly refused a genuine multi-file diff).
+    """
+    o = str(obs)
+    if not o.startswith("ERROR:"):
+        return None
+    low = o.lower()
+
+    # Security-guard rejections: false iff the touched file and the path arg are
+    # the SAME file after normalisation (the bug); genuine multi-file otherwise.
+    m = _SEC_RX.search(o)
+    if m:
+        if _strip_container_prefix(m.group(1)) == _strip_container_prefix(m.group(2)):
+            return "instrument"
+        return "correct_reject"
+
+    # A surviving git-prefix + container root in the git error ('b/testbed/...:
+    # No such file') means the normaliser failed to strip it -> instrument.
+    if _GIT_PREFIX_TESTBED_RX.search(o):
+        return "instrument"
+
+    # Everything else that errored (corrupt patch, context 'does not match index',
+    # clean relative file-not-found) is the model's diff quality -> model.
+    return "model"
+
+
+# ---------------------------------------------------------------------------
+# Provenance helpers
+# ---------------------------------------------------------------------------
+
+
+def _expected_mode(run_id: str) -> str | None:
+    if run_id.endswith("_legacy"):
+        return "legacy"
+    if run_id.endswith("_fixed"):
+        return "fixed"
+    return None
+
+
+def _read_completed(run_dir: Path) -> dict | None:
+    p = run_dir / "RUN_COMPLETED.json"
+    if not p.exists():
+        return None
+    try:
+        return json.loads(p.read_text(encoding="utf-8"))
+    except (json.JSONDecodeError, OSError):
+        return None
+
+
+def _median(xs: list[int | float]) -> float:
+    return float(statistics.median(xs)) if xs else 0.0
+
+
+# ---------------------------------------------------------------------------
+# Public API
+# ---------------------------------------------------------------------------
+
+
+def ab_gate_amended(
+    runs_root: Path | str,
+    expected_sha: str | None = None,
+    expected_config_hash: str | None = None,
+    schedule_seed: int = 20260622,
+    inflation_max: float = 1.5,
+) -> dict[str, Any]:
+    runs_root = Path(runs_root)
+    schedule = ab_schedule(seed=schedule_seed)
+    note = (
+        "Amended gate (docs/amended-gate-2026-06-24.md): instrument-attributable "
+        "failures==0; the 0.15 total-ratio is NOT a criterion."
+    )
+
+    # -- Phase 0: structural completeness + RUN_FAILED ----------------------
+    missing, failed, incomplete = [], [], []
+    for c in schedule:
+        rd = runs_root / c["run_id"]
+        if not rd.is_dir():
+            missing.append(c["run_id"])
+            continue
+        if (rd / "RUN_FAILED.json").exists():
+            failed.append(c["run_id"])
+        if not (rd / "RUN_COMPLETED.json").exists():
+            incomplete.append(c["run_id"])
+    structural = []
+    if missing:
+        structural.append(f"{len(missing)} run dir(s) missing: {missing[:5]}")
+    if failed:
+        structural.append(f"{len(failed)} run(s) have RUN_FAILED.json: {failed[:5]}")
+    if incomplete:
+        structural.append(f"{len(incomplete)} run(s) lack RUN_COMPLETED.json: {incomplete[:5]}")
+    if structural:
+        return _blocked(structural, note)
+
+    # -- Phase 1: provenance (sha / tool_mode-vs-run_id / config_hash) ------
+    prov = []
+    for c in schedule:
+        rd = runs_root / c["run_id"]
+        sent = _read_completed(rd)
+        if sent is None:
+            prov.append(f"{c['run_id']}: RUN_COMPLETED.json unreadable")
+            continue
+        if expected_sha and sent.get("experiment_sha") != expected_sha:
+            prov.append(f"{c['run_id']}: experiment_sha {sent.get('experiment_sha')!r} != {expected_sha!r}")
+        exp_mode = _expected_mode(c["run_id"])
+        if sent.get("tool_mode") != c["tool_mode"] or (exp_mode and sent.get("tool_mode") != exp_mode):
+            prov.append(f"{c['run_id']}: tool_mode {sent.get('tool_mode')!r} != expected {c['tool_mode']!r}")
+        if expected_config_hash and sent.get("config_hash") != expected_config_hash:
+            prov.append(f"{c['run_id']}: config_hash {sent.get('config_hash')!r} != {expected_config_hash!r}")
+    if prov:
+        return _blocked(prov, note)
+
+    # -- Phase 2: pairing (every (seq,policy,seed) has both modes; task_ids match)
+    by_key: dict[tuple, dict[str, str]] = {}
+    for c in schedule:
+        by_key.setdefault((c["policy"], c["sequence_name"], c["seed"]), {})[c["tool_mode"]] = c["run_id"]
+    pairing = []
+    for key, modes in by_key.items():
+        lid, fid = modes.get("legacy"), modes.get("fixed")
+        if not lid or not fid:
+            pairing.append(f"Key {key} missing a mode: {modes}")
+            continue
+        ltasks = {r["task_id"] for r in _load_task_results(runs_root / lid) if "task_id" in r}
+        ftasks = {r["task_id"] for r in _load_task_results(runs_root / fid) if "task_id" in r}
+        if ltasks != ftasks:
+            pairing.append(
+                f"Unmatched task_ids for {key}: legacy-only={sorted(ltasks - ftasks)[:3]}, "
+                f"fixed-only={sorted(ftasks - ltasks)[:3]}"
+            )
+    if pairing:
+        return _blocked(pairing, note)
+
+    # -- Phase 3: health metrics -------------------------------------------
+    def arm_stats(mode: str) -> dict:
+        ptoks, ttoks = [], []
+        edit_calls = instrument = model = correct = 0
+        for c in schedule:
+            if c["tool_mode"] != mode:
+                continue
+            rd = runs_root / c["run_id"]
+            for r in _load_task_results(rd):
+                ptoks.append(int(r.get("prompt_tokens", 0) or 0))
+                ttoks.append(int(r.get("total_tokens", 0) or 0))
+            for traj in _load_trajectories(rd):
+                for step in traj.get("steps", []):
+                    if step.get("action") != "edit_file":
+                        continue
+                    edit_calls += 1
+                    cls = classify_edit_failure(step.get("observation_summary", ""))
+                    if cls == "instrument":
+                        instrument += 1
+                    elif cls == "model":
+                        model += 1
+                    elif cls == "correct_reject":
+                        correct += 1
+        return {
+            "edit_calls": edit_calls,
+            "instrument_failures": instrument,
+            "model_failures": model,
+            "correct_rejects": correct,
+            "model_quality_rate": (model / edit_calls) if edit_calls else 0.0,
+            "prompt_median": _median(ptoks),
+            "total_median": _median(ttoks),
+        }
+
+    fixed = arm_stats("fixed")
+    legacy = arm_stats("legacy")
+
+    prompt_infl = (fixed["prompt_median"] / legacy["prompt_median"]) if legacy["prompt_median"] else 0.0
+    total_infl = (fixed["total_median"] / legacy["total_median"]) if legacy["total_median"] else 0.0
+
+    reasons = []
+    # (3) instrument-attributable failures == 0 (fixed arm is the one under test)
+    if fixed["instrument_failures"] != 0:
+        reasons.append(
+            f"instrument-attributable edit failures (fixed) == {fixed['instrument_failures']} (must be 0)"
+        )
+    # (4) token inflation <= 1.5x
+    if prompt_infl > inflation_max:
+        reasons.append(f"prompt-token inflation {prompt_infl:.3f} > {inflation_max}")
+    if total_infl > inflation_max:
+        reasons.append(f"total-token inflation {total_infl:.3f} > {inflation_max}")
+    # (5) model-quality rate fixed <= legacy (sanity lower-bound)
+    if fixed["model_quality_rate"] > legacy["model_quality_rate"]:
+        reasons.append(
+            f"model-quality rate fixed {fixed['model_quality_rate']:.3f} > legacy "
+            f"{legacy['model_quality_rate']:.3f} (fix must not regress diff quality)"
+        )
+
+    metrics = {
+        "fixed": fixed,
+        "legacy": legacy,
+        "prompt_inflation_ratio": round(prompt_infl, 4),
+        "total_inflation_ratio": round(total_infl, 4),
+    }
+    return {
+        "gate": "GO" if not reasons else "STOP",
+        "metrics": metrics,
+        "reasons": reasons,
+        "criteria": "complete+paired+provenance, instrument-attributable==0, "
+        "inflation<=1.5x, model-quality fixed<=legacy (NOT 0.15 total-ratio)",
+        "note": note,
+    }
+
+
+def _blocked(reasons: list[str], note: str) -> dict:
+    return {"gate": "BLOCKED", "reason": reasons[0], "reasons": reasons, "metrics": {}, "note": note}
+
+
+def main() -> None:
+    p = argparse.ArgumentParser(description="Amended A/B instrument-health gate.")
+    p.add_argument("--runs-root", required=True)
+    p.add_argument("--expected-sha", default=None)
+    p.add_argument("--expected-config-hash", default=None)
+    p.add_argument("--schedule-seed", type=int, default=20260622)
+    a = p.parse_args()
+    result = ab_gate_amended(
+        runs_root=a.runs_root,
+        expected_sha=a.expected_sha,
+        expected_config_hash=a.expected_config_hash,
+        schedule_seed=a.schedule_seed,
+    )
+    print(json.dumps(result, indent=2))
+
+
+if __name__ == "__main__":
+    main()
diff --git a/scripts/build_ab_manifest.py b/scripts/build_ab_manifest.py
new file mode 100644
index 0000000..2f178fa
--- /dev/null
+++ b/scripts/build_ab_manifest.py
@@ -0,0 +1,136 @@
+"""Build the tracked A/B re-validation manifest + worker map (Codex 2026-06-24).
+
+The post-hotfix 36-cell A/B (experiment_sha cceb325) needs an explicit, tracked
+manifest so the runner consumes a fixed unit list (never accidentally the 144
+manifest) and provenance is auditable.
+
+- 36 cells come from :func:`scripts.ab_schedule.ab_schedule` (canonical).
+- Each row carries ``tool_mode`` (legacy|fixed) so the runner sets
+  ``AGENT_TOOL_MODE`` per unit (NOT globally).
+- Each row carries a ``worker`` assignment that CO-LOCATES the legacy & fixed
+  cells of the same (sequence, policy, seed) pair on the same worker, so a pair
+  is never split across machines.
+- ``task_count``/``task_ids`` are sourced from ``runs_144.json`` for the same two
+  sequences, guaranteeing consistency with the 144 manifest.
+
+Usage::
+
+    python -m scripts.build_ab_manifest        # writes the two artifacts
+"""
+from __future__ import annotations
+
+import argparse
+import hashlib
+import json
+from pathlib import Path
+
+from scripts.ab_schedule import ab_schedule
+
+# Frozen provenance for this A/B (must match results/manifest/freeze.json).
+EXPERIMENT_SHA = "cceb3253d7b7cfeae16123af30197a8271e1d84a"
+CONFIG_HASH = "2e7f341cc35d31c2"
+DEFAULT_N_WORKERS = 9
+DEFAULT_RUNS_144 = "results/manifest/runs_144.json"
+
+
+def _seq_task_index(runs_144_path: str | Path) -> dict[str, dict]:
+    """Map sequence_name -> {task_count, task_ids} from the 144 manifest."""
+    data = json.loads(Path(runs_144_path).read_text(encoding="utf-8"))
+    idx: dict[str, dict] = {}
+    for r in data["runs"]:
+        s = r["sequence_name"]
+        if s not in idx:
+            ids = r.get("task_ids", [])
+            idx[s] = {"task_count": r.get("task_count", len(ids)), "task_ids": ids}
+    return idx
+
+
+def build_ab_manifest(
+    schedule_seed: int = 20260622,
+    n_workers: int = DEFAULT_N_WORKERS,
+    runs_144_path: str | Path = DEFAULT_RUNS_144,
+) -> dict:
+    """Return the A/B manifest dict (36 cells, tool_mode + co-located worker)."""
+    cells = ab_schedule(schedule_seed)
+    seq_idx = _seq_task_index(runs_144_path)
+
+    # Pair assignment: legacy+fixed of the same (seq, policy, seed) share a worker.
+    pair_keys = sorted({(c["sequence_name"], c["policy"], c["seed"]) for c in cells})
+    pair_worker = {pk: i % n_workers for i, pk in enumerate(pair_keys)}
+
+    runs: list[dict] = []
+    for c in cells:
+        pk = (c["sequence_name"], c["policy"], c["seed"])
+        ti = seq_idx.get(c["sequence_name"], {"task_count": 0, "task_ids": []})
+        runs.append(
+            {
+                "run_id": c["run_id"],
+                "policy": c["policy"],
+                "sequence_name": c["sequence_name"],
+                "seed": c["seed"],
+                "tool_mode": c["tool_mode"],
+                "pair_key": f'{c["sequence_name"]}|{c["policy"]}|seed{c["seed"]}',
+                "worker": pair_worker[pk],
+                "task_count": ti["task_count"],
+                "task_ids": ti["task_ids"],
+            }
+        )
+
+    payload = json.dumps(
+        [(r["run_id"], r["tool_mode"], r["worker"]) for r in sorted(runs, key=lambda r: r["run_id"])],
+        sort_keys=True,
+    )
+    mhash = hashlib.sha256(payload.encode()).hexdigest()[:16]
+
+    return {
+        "generated_for": "A/B re-validation (post-hotfix) at experiment_sha cceb325",
+        "experiment_sha": EXPERIMENT_SHA,
+        "config_hash": CONFIG_HASH,
+        "manifest_hash": mhash,
+        "schedule_seed": schedule_seed,
+        "n_workers": n_workers,
+        "policies": sorted({c["policy"] for c in cells}),
+        "seeds": sorted({c["seed"] for c in cells}),
+        "sequences": sorted({c["sequence_name"] for c in cells}),
+        "tool_modes": ["legacy", "fixed"],
+        "n_runs": len(runs),
+        "amended_gate": "docs/amended-gate-2026-06-24.md",
+        "note": (
+            "36-cell A/B; each (sequence,policy,seed) has BOTH legacy+fixed, "
+            "co-located on one worker. Runner sets AGENT_TOOL_MODE per row. "
+            "Gate: scripts/ab_gate_amended.py. RUNS_ROOT=runs_ab_cceb325."
+        ),
+        "runs": runs,
+    }
+
+
+def build_worker_map(manifest: dict) -> dict:
+    """Return {worker -> [run_ids]} for human/Codex audit."""
+    workers: dict[str, list[str]] = {}
+    for r in manifest["runs"]:
+        workers.setdefault(str(r["worker"]), []).append(r["run_id"])
+    return {
+        "n_workers": manifest["n_workers"],
+        "experiment_sha": manifest["experiment_sha"],
+        "manifest_hash": manifest["manifest_hash"],
+        "workers": {k: sorted(v) for k, v in sorted(workers.items(), key=lambda kv: int(kv[0]))},
+    }
+
+
+def main() -> None:
+    p = argparse.ArgumentParser(description="Build the tracked A/B manifest + worker map.")
+    p.add_argument("--out", default="results/manifest/runs_ab_cceb325.json")
+    p.add_argument("--worker-map", default="results/manifest/worker_map_ab_cceb325.json")
+    p.add_argument("--n-workers", type=int, default=DEFAULT_N_WORKERS)
+    a = p.parse_args()
+
+    manifest = build_ab_manifest(n_workers=a.n_workers)
+    wmap = build_worker_map(manifest)
+    Path(a.out).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
+    Path(a.worker_map).write_text(json.dumps(wmap, indent=2), encoding="utf-8")
+    print(f"wrote {a.out}: {manifest['n_runs']} runs, manifest_hash {manifest['manifest_hash']}")
+    print(f"wrote {a.worker_map}: {len(wmap['workers'])} workers")
+
+
+if __name__ == "__main__":
+    main()
diff --git a/scripts/run_matrix_shard.sh b/scripts/run_matrix_shard.sh
index 27dc4c3..fc0a99d 100644
--- a/scripts/run_matrix_shard.sh
+++ b/scripts/run_matrix_shard.sh
@@ -44,21 +44,12 @@ if [ "$SHARD" -ge "$NUM" ]; then
 fi
 
 # ---------------------------------------------------------------------------
-# Extract this shard's unit list from the manifest using Python
-# (avoids jq dependency on VPS droplets).
-# Emits one line per unit:  <global_index>|<run_id>|<policy>|<seed>|<seq_name>
+# Extract this shard's unit list via scripts/shard_units.py — the single source
+# of truth for sharding + per-unit tool_mode (unit-tested).
+# Emits one line per unit:  <idx>|<run_id>|<policy>|<seed>|<seq_name>|<tool_mode>
+# Worker-field manifests (A/B) shard by the row's "worker"; else modulo by index.
 # ---------------------------------------------------------------------------
-mapfile -t units < <(
-  .venv/bin/python - "$MANIFEST" "$SHARD" "$NUM" <<'PYEOF'
-import json, sys
-manifest_path, shard, num = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
-with open(manifest_path) as f:
-    data = json.load(f)
-for i, r in enumerate(data["runs"]):
-    if i % num == shard:
-        print(f"{i}|{r['run_id']}|{r['policy']}|{r['seed']}|{r['sequence_name']}")
-PYEOF
-)
+mapfile -t units < <(.venv/bin/python scripts/shard_units.py "$MANIFEST" "$SHARD" "$NUM")
 
 mkdir -p "$RUNS_ROOT"
 echo "SHARD $SHARD/$NUM : ${#units[@]} units, conc=$CONC, RUNS_ROOT=$RUNS_ROOT, AGENT_TOOL_MODE=$AGENT_TOOL_MODE $(date -u +%H:%M:%S)"
@@ -71,7 +62,14 @@ echo "SHARD $SHARD/$NUM : ${#units[@]} units, conc=$CONC, RUNS_ROOT=$RUNS_ROOT,
 # ---------------------------------------------------------------------------
 run_unit() {
   local entry="$1"
-  IFS='|' read -r _idx run_id pol seed seq <<< "$entry"
+  IFS='|' read -r _idx run_id pol seed seq mode <<< "$entry"
+
+  # Per-unit tool_mode: the manifest row is authoritative. Fall back to the
+  # global AGENT_TOOL_MODE env (default "fixed") only when the row omits it
+  # (e.g. the all-fixed 144 manifest). NEVER let a mixed A/B manifest run a
+  # whole shard in one global mode.
+  local eff_mode="${mode:-}"
+  [ -z "$eff_mode" ] && eff_mode="${AGENT_TOOL_MODE:-fixed}"
 
   # Done-check: delegate to unit_status.py (RUN_COMPLETED.json sentinel).
   # Fail-closed: if status is not exactly one of complete|failed|incomplete
@@ -103,12 +101,13 @@ from src.benchmark.completion import archive_prior_attempt
 archive_prior_attempt(Path(sys.argv[2]) / sys.argv[1])
 PYEOF
 
-  echo "START $run_id (status=$status) $(date -u +%H:%M:%S)"
-  .venv/bin/python -u -m scripts.run_pilot_policy \
+  echo "START $run_id (status=$status mode=$eff_mode) $(date -u +%H:%M:%S)"
+  AGENT_TOOL_MODE="$eff_mode" .venv/bin/python -u -m scripts.run_pilot_policy \
       --policy    "$pol"  \
       --seed      "$seed" \
       --sequences "$seq"  \
       --run-id    "$run_id" \
+      --tool-mode "$eff_mode" \
       > "${RUNS_ROOT}/unit_${run_id}.log" 2>&1
   local exit_code=$?
   echo "DONE  $run_id EXIT=$exit_code $(date -u +%H:%M:%S)"
diff --git a/scripts/run_pilot_policy.py b/scripts/run_pilot_policy.py
index 70f01d3..ff1b342 100644
--- a/scripts/run_pilot_policy.py
+++ b/scripts/run_pilot_policy.py
@@ -22,6 +22,7 @@ import argparse
 import dataclasses
 import json
 import logging
+import os
 import sys
 from pathlib import Path
 
@@ -72,8 +73,25 @@ def main(argv: list[str] | None = None) -> int:
             "Defaults to pilot_{policy}_{seq}_seed{seed} for legacy compatibility."
         ),
     )
+    p.add_argument(
+        "--tool-mode",
+        default=None,
+        choices=["legacy", "fixed"],
+        help=(
+            "Explicit AGENT_TOOL_MODE for this unit (legacy|fixed). Set BEFORE the "
+            "runner builds tools, so tool_mode() and the RUN_COMPLETED/RUN_FAILED "
+            "sentinels record it. Overrides the AGENT_TOOL_MODE env; if omitted the "
+            "env (default 'fixed') is used. Required for mixed-mode A/B units."
+        ),
+    )
     args = p.parse_args(argv)
 
+    # Pin tool_mode up-front (explicit arg wins) so provenance is recorded
+    # consistently: tools.py::tool_mode() and completion.py sentinels both read
+    # AGENT_TOOL_MODE. This is the per-unit seam the A/B runner relies on.
+    if args.tool_mode is not None:
+        os.environ["AGENT_TOOL_MODE"] = args.tool_mode
+
     config = load_config()
     max_records = config.get("memory", {}).get("max_records", 100)
     loader = SWEBenchCLLoader(args.curriculum)
diff --git a/scripts/shard_units.py b/scripts/shard_units.py
new file mode 100644
index 0000000..daa0838
--- /dev/null
+++ b/scripts/shard_units.py
@@ -0,0 +1,62 @@
+"""Enumerate the units a shard/worker must run from a manifest (Codex 2026-06-24).
+
+Single source of truth for "which units, in which tool_mode" — the bash runner
+(`run_matrix_shard.sh`) is a thin shell over this, so the per-unit tool_mode
+threading is unit-testable in Python.
+
+Sharding modes (auto-detected):
+  - worker-field: if ANY manifest row has a ``worker`` field, select rows where
+    ``int(row["worker"]) == shard``. Used by the A/B manifest to co-locate the
+    legacy & fixed cells of a pair on one worker.
+  - modulo: otherwise select rows where ``(global_index % num) == shard`` (the
+    144 matrix default).
+
+Every emitted unit carries ``tool_mode`` (``""`` if the row omits it -> the
+runner falls back to the ``AGENT_TOOL_MODE`` env / "fixed").
+"""
+from __future__ import annotations
+
+import json
+import sys
+from pathlib import Path
+
+
+def enumerate_units(manifest_path: str | Path, shard: int, num: int) -> list[dict]:
+    """Return the list of unit dicts assigned to ``shard``.
+
+    Each unit: ``{index, run_id, policy, seed, sequence_name, tool_mode}``.
+    """
+    data = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
+    runs = data["runs"]
+    by_worker = any("worker" in r for r in runs)
+
+    units: list[dict] = []
+    for i, r in enumerate(runs):
+        if by_worker:
+            if int(r.get("worker", -1)) != shard:
+                continue
+        else:
+            if i % num != shard:
+                continue
+        units.append(
+            {
+                "index": i,
+                "run_id": r["run_id"],
+                "policy": r["policy"],
+                "seed": r["seed"],
+                "sequence_name": r["sequence_name"],
+                "tool_mode": r.get("tool_mode", ""),
+            }
+        )
+    return units
+
+
+def main() -> None:
+    manifest_path, shard, num = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
+    for u in enumerate_units(manifest_path, shard, num):
+        # index|run_id|policy|seed|sequence_name|tool_mode
+        print(f'{u["index"]}|{u["run_id"]}|{u["policy"]}|{u["seed"]}|{u["sequence_name"]}|{u["tool_mode"]}')
+
+
+if __name__ == "__main__":
+    main()
```
