"""
Task 0 — Canonical diagnostic + smoke-task selection.

Outputs (all under results/preflight/):
  runner_defects.json        — completeness summary + per-tool defect rates
  ambiguous_trajectories.json — dup trajectory keys that could not be resolved
  smoke_tasks.json           — ≥3 tasks whose gold patch hits line >200 in a large file

Run with:
    .venv/bin/python -m scripts.preflight_runner_diagnostics
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
K27_ROOT = REPO_ROOT / "runs_k27_merged"
LEGACY_ROOT = REPO_ROOT / "runs_legacy_merged"
MANIFEST_FILE = REPO_ROOT / "results" / "manifest" / "runs_144.json"
CURRICULUM_FILE = REPO_ROOT / "data" / "SWE-Bench-CL-Curriculum.json"
PREFLIGHT_OUT = REPO_ROOT / "results" / "preflight"

PREFLIGHT_OUT.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Tool schemas — only positional keys matter for the "keys outside schema" check
# ---------------------------------------------------------------------------
TOOL_SCHEMAS: dict[str, set[str]] = {
    "read_file":   {"path"},
    "write_file":  {"path", "content"},
    "edit_file":   {"path", "diff"},
    "search_code": {"query", "file_pattern"},
    "list_files":  {"path", "pattern"},
    "run_command": {"command"},
    "run_tests":   {"test_command"},
    "finish":      set(),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def policy_seq_from_dir(name: str) -> tuple[str, int]:
    """
    Returns (policy_sequence_name, seed) parsed from a run directory name.

    Strips an optional 'pilot_' prefix, then extracts the trailing '_seed<N>'
    suffix.  The remainder (everything before the seed suffix) is the combined
    policy+sequence string, e.g. 'no_memory_django_django_sequence'.

    Returns:
        (policy_sequence_name, seed)  — a 2-tuple of (str, int).
    """
    name_no_pilot = name.removeprefix("pilot_")
    m = re.search(r"_seed(\d+)$", name_no_pilot)
    if not m:
        raise ValueError(f"Cannot parse seed from: {name!r}")
    seed = int(m.group(1))
    rest = name_no_pilot[: m.start()]
    return rest, seed  # rest = "policy_sequence_name"


def load_manifest() -> tuple[dict, list[dict]]:
    with open(MANIFEST_FILE) as f:
        manifest = json.load(f)
    return manifest, manifest["runs"]


def load_curriculum() -> dict[str, dict]:
    """Returns task_id → task dict (with gold_patch, repo, sequence_name, etc.)."""
    with open(CURRICULUM_FILE) as f:
        data = json.load(f)
    result: dict[str, dict] = {}
    for seq in data["sequences"]:
        for task in seq["tasks"]:
            task_with_seq = dict(task)
            task_with_seq.setdefault("sequence_name", seq["sequence_name"])
            result[task["task_id"]] = task_with_seq
    return result


# ---------------------------------------------------------------------------
# Part 1 — Outcome completeness
# ---------------------------------------------------------------------------

def check_completeness(manifest_runs: list[dict]) -> dict:
    """
    For each of the 144 manifest units find the matching dir in runs_k27_merged,
    read task_results.jsonl, and report completeness.
    """
    n_dirs = 0
    n_complete = 0
    n_incomplete = 0
    missing_rows_total = 0
    incomplete_units: list[dict] = []
    total_rows_found = 0

    for run in manifest_runs:
        run_id = run["run_id"]
        dir_name = "pilot_" + run_id
        run_dir = K27_ROOT / dir_name
        manifest_task_ids = set(run["task_ids"])
        task_count = run["task_count"]

        if not run_dir.is_dir():
            missing_rows_total += task_count
            incomplete_units.append({
                "run_id": run_id,
                "issue": "dir_missing",
                "n_manifest_tasks": task_count,
                "n_found_rows": 0,
                "missing_task_ids": run["task_ids"],
            })
            n_incomplete += 1
            continue

        n_dirs += 1
        results_file = run_dir / "task_results.jsonl"
        if not results_file.exists():
            missing_rows_total += task_count
            incomplete_units.append({
                "run_id": run_id,
                "issue": "dir_missing_jsonl",
                "n_manifest_tasks": task_count,
                "n_found_rows": 0,
                "missing_task_ids": run["task_ids"],
            })
            n_incomplete += 1
            continue

        found_task_ids: set[str] = set()
        with open(results_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                    found_task_ids.add(row["task_id"])
                except (json.JSONDecodeError, KeyError):
                    pass

        total_rows_found += len(found_task_ids)
        missing_ids = manifest_task_ids - found_task_ids
        extra_ids = found_task_ids - manifest_task_ids

        if missing_ids:
            missing_rows_total += len(missing_ids)
            incomplete_units.append({
                "run_id": run_id,
                "issue": "missing_rows",
                "n_manifest_tasks": task_count,
                "n_found_rows": len(found_task_ids),
                "n_missing": len(missing_ids),
                "n_extra": len(extra_ids),
                "missing_task_ids": sorted(missing_ids),
            })
            n_incomplete += 1
        else:
            n_complete += 1

    return {
        "n_dirs": n_dirs,
        "n_complete": n_complete,
        "n_incomplete": n_incomplete,
        "n_missing_rows": missing_rows_total,
        "n_rows_found": total_rows_found,
        "n_manifest_expected": sum(r["task_count"] for r in manifest_runs),
        "incomplete_units": incomplete_units,
    }


# ---------------------------------------------------------------------------
# Part 2 — Trajectory matching + duplicate resolution
# ---------------------------------------------------------------------------

def collect_all_trajectories() -> dict[tuple[str, int, str], list[Path]]:
    """
    Collect all trajectory files from runs_legacy_merged, keyed by
    (policy_seq_name, seed, task_id).
    'policy_seq_name' = 'policy_sequence_name' concatenated (same as manifest
    run_id without seed suffix).
    """
    key_to_files: dict[tuple[str, int, str], list[Path]] = defaultdict(list)

    for sfo_dir in sorted(LEGACY_ROOT.iterdir()):
        if not sfo_dir.is_dir():
            continue
        for run_dir in sfo_dir.iterdir():
            if not run_dir.is_dir():
                continue
            if not run_dir.name.startswith("pilot_"):
                continue
            try:
                policy_seq, seed = policy_seq_from_dir(run_dir.name)
            except ValueError:
                continue
            traj_dir = run_dir / "trajectories"
            if not traj_dir.is_dir():
                continue
            for traj_file in traj_dir.glob("*.json"):
                task_id = traj_file.stem
                key = (policy_seq, seed, task_id)
                key_to_files[key].append(traj_file)

    return key_to_files


def load_canonical_tool_calls(manifest_runs: list[dict]) -> dict[tuple[str, int, str], int]:
    """
    Returns (policy_seq, seed, task_id) → tool_calls from task_results.jsonl.
    """
    result: dict[tuple[str, int, str], int] = {}
    for run in manifest_runs:
        run_id = run["run_id"]
        dir_name = "pilot_" + run_id
        run_dir = K27_ROOT / dir_name
        results_file = run_dir / "task_results.jsonl"
        if not results_file.exists():
            continue
        # parse policy_seq from run_id (no pilot_ prefix, no seed suffix)
        m = re.search(r"_seed(\d+)$", run_id)
        if not m:
            continue
        seed = int(m.group(1))
        policy_seq = run_id[: m.start()]
        with open(results_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                    tc = int(row.get("tool_calls", -1))
                    result[(policy_seq, seed, row["task_id"])] = tc
                except (json.JSONDecodeError, KeyError):
                    pass
    return result


def resolve_trajectories(
    key_to_files: dict[tuple[str, int, str], list[Path]],
    canonical_tool_calls: dict[tuple[str, int, str], int],
) -> tuple[dict[tuple[str, int, str], Path], list[dict]]:
    """
    For each key:
    - If only one candidate → use it (dedup byte-identical files first).
    - If multiple byte-identical → use any one.
    - If multiple distinct files, exactly one whose len(steps) == canonical tool_calls → use it.
    - Otherwise → unresolvable (goes to ambiguous list).

    Returns (resolved_map, ambiguous_list).
    """
    resolved: dict[tuple[str, int, str], Path] = {}
    ambiguous: list[dict] = []

    for key, files in key_to_files.items():
        if len(files) == 1:
            resolved[key] = files[0]
            continue

        # Dedup by content (byte identity)
        content_map: dict[bytes, Path] = {}
        for f in files:
            try:
                content = f.read_bytes()
                if content not in content_map:
                    content_map[content] = f
            except OSError:
                pass

        if len(content_map) == 1:
            # All identical — pick any
            resolved[key] = next(iter(content_map.values()))
            continue

        # Multiple distinct files — attempt tiebreak via tool_calls
        canonical_tc = canonical_tool_calls.get(key)
        if canonical_tc is None:
            # No canonical row — unresolvable
            ambiguous.append({
                "key": {"policy_seq": key[0], "seed": key[1], "task_id": key[2]},
                "candidate_files": [str(f) for f in files],
                "reason": "no_canonical_row",
            })
            continue

        matching_files: list[Path] = []
        for content, f in content_map.items():
            try:
                data = json.loads(content)
                n_steps = len(data.get("steps", []))
                if n_steps == canonical_tc:
                    matching_files.append(f)
            except (json.JSONDecodeError, ValueError):
                pass

        if len(matching_files) == 1:
            resolved[key] = matching_files[0]
        else:
            ambiguous.append({
                "key": {"policy_seq": key[0], "seed": key[1], "task_id": key[2]},
                "candidate_files": [str(f) for f in files],
                "canonical_tool_calls": canonical_tc,
                "n_step_matching": len(matching_files),
                "reason": "ambiguous_step_count" if len(matching_files) > 1 else "no_step_match",
            })

    return resolved, ambiguous


# ---------------------------------------------------------------------------
# Part 3 — Defect rates
# ---------------------------------------------------------------------------

def compute_defect_rates(
    resolved: dict[tuple[str, int, str], Path],
    canonical_tool_calls: dict[tuple[str, int, str], int],
) -> dict:
    """
    Compute per-tool defect statistics over all resolved trajectory steps.
    """
    # Per tool: total_calls, truncated_obs, bad_key_calls
    tool_total: dict[str, int] = defaultdict(int)
    tool_truncated: dict[str, int] = defaultdict(int)
    tool_bad_keys: dict[str, int] = defaultdict(int)

    # edit_file failure buckets
    edit_fail_path_testbed = 0
    edit_fail_index_mismatch = 0
    edit_fail_format = 0
    edit_fail_other = 0

    unknown_tool_count = 0
    total_tasks = 0
    tasks_rereading: int = 0  # tasks that re-read the same path

    for key, traj_file in resolved.items():
        try:
            with open(traj_file) as f:
                traj = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        steps = traj.get("steps", [])
        total_tasks += 1
        read_paths: list[str] = []
        task_reread = False

        for step in steps:
            action = step.get("action", "")
            action_input = step.get("action_input") or {}
            obs = step.get("observation_summary", "") or ""

            if action not in TOOL_SCHEMAS:
                unknown_tool_count += 1
                continue

            tool_total[action] += 1

            # Truncation check
            if len(obs) >= 3990:
                tool_truncated[action] += 1

            # Bad key check — keys in action_input not in tool schema
            if isinstance(action_input, dict):
                valid_keys = TOOL_SCHEMAS[action]
                extra_keys = set(action_input.keys()) - valid_keys
                if extra_keys:
                    tool_bad_keys[action] += 1

            # edit_file failure classification
            if action == "edit_file":
                obs_lower = obs.lower()
                if "could not apply" in obs_lower or "error" in obs_lower:
                    if "/testbed" in obs:
                        edit_fail_path_testbed += 1
                    elif "does not match index" in obs_lower:
                        edit_fail_index_mismatch += 1
                    elif "format" in obs_lower or "hunk" in obs_lower or "patch" in obs_lower:
                        edit_fail_format += 1
                    else:
                        edit_fail_other += 1

            # re-read detection
            if action == "read_file":
                path = action_input.get("path", "")
                if path in read_paths:
                    task_reread = True
                read_paths.append(path)

        if task_reread:
            tasks_rereading += 1

    # Build per-tool stats
    per_tool: dict[str, dict] = {}
    all_tools = set(tool_total.keys())
    for tool in sorted(all_tools):
        total = tool_total[tool]
        per_tool[tool] = {
            "total_calls": total,
            "pct_obs_truncated": round(100 * tool_truncated[tool] / total, 2) if total else 0,
            "pct_calls_bad_keys": round(100 * tool_bad_keys[tool] / total, 2) if total else 0,
        }

    edit_total_fails = edit_fail_path_testbed + edit_fail_index_mismatch + edit_fail_format + edit_fail_other
    return {
        "n_resolved_trajectories": len(resolved),
        "n_tasks_analyzed": total_tasks,
        "unknown_tool_calls": unknown_tool_count,
        "pct_tasks_rereading_same_path": round(100 * tasks_rereading / total_tasks, 2) if total_tasks else 0,
        "per_tool": per_tool,
        "edit_file_failure_split": {
            "total_failures_detected": edit_total_fails,
            "path_testbed_mismatch": edit_fail_path_testbed,
            "index_does_not_match": edit_fail_index_mismatch,
            "format_hunk_patch": edit_fail_format,
            "other": edit_fail_other,
            "note": (
                "Failure detected when observation_summary contains "
                "'Could not apply' or 'ERROR' (case-insensitive). "
                "Buckets: path=/testbed in obs; index='does not match index'; "
                "format=format/hunk/patch keywords; other=remainder."
            ),
        },
    }


# ---------------------------------------------------------------------------
# Part 4 — Smoke task selection
# ---------------------------------------------------------------------------

def select_smoke_tasks(curriculum: dict[str, dict], n: int = 3) -> dict:
    """
    Pick ≥n task_ids whose gold_patch modifies a file AND the largest @@ -N hunk
    start > 200.  We approximate file size by this heuristic (no Docker available):
      - The patch hunk starts at a large line (>200) → the file has at least that
        many lines before the patch.  Combined with the fact that well-known Python
        source files in large repos that are patched past line 200 are reliably >4000 chars.
      - We choose patches with the largest hunk-start line first so the sample is
        most likely to correspond to genuinely large files.
    """
    # Parse: for each task, find the max @@ -N hunk start line in gold_patch
    candidates: list[dict] = []
    hunk_re = re.compile(r"^@@[^@]*-(\d+)", re.MULTILINE)

    for task_id, task in curriculum.items():
        patch = task.get("gold_patch", "")
        if not patch:
            continue
        matches = hunk_re.findall(patch)
        if not matches:
            continue
        max_start = max(int(x) for x in matches)
        if max_start <= 200:
            continue

        # Extract target file from "diff --git a/... b/..." line
        file_match = re.search(r"^\+\+\+ b/(.+)$", patch, re.MULTILINE)
        if not file_match:
            continue
        target_file = file_match.group(1).strip()

        candidates.append({
            "task_id": task_id,
            "repo": task["repo"],
            "target_file": target_file,
            "approx_hunk_start_line": max_start,
            "sequence_name": None,  # filled below
        })

    # Sort by hunk start descending to pick most convincing first
    candidates.sort(key=lambda c: c["approx_hunk_start_line"], reverse=True)

    # Label sequence_name from the already-loaded curriculum dict
    # (load_curriculum injects sequence_name into each task record)
    for c in candidates:
        c["sequence_name"] = curriculum[c["task_id"]].get("sequence_name")

    chosen = candidates[:max(n, 3)]

    return {
        "smoke_tasks": chosen,
        "heuristic": (
            "Approximate file size heuristic (no Docker/base_commit checkout available): "
            "parse all '@@ -N' hunk start lines from gold_patch; require max(N) > 200. "
            "A patch that starts at line >200 implies the file has at least 200+ lines of context "
            "before the change, reliably indicating >4000 chars for typical Python source files. "
            "Tasks are ranked by max hunk start (descending) and top ≥3 selected. "
            "Evidence from trajectory read_file observations (truncated at ≥3990 chars) would "
            "provide direct confirmation but was not required to select candidates."
        ),
        "n_total_candidates_line_gt_200": len(candidates),
        "n_selected": len(chosen),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=== preflight_runner_diagnostics ===")
    print(f"K27_ROOT:    {K27_ROOT}")
    print(f"LEGACY_ROOT: {LEGACY_ROOT}")
    print()

    # Load manifest
    manifest, manifest_runs = load_manifest()
    print(f"Manifest: {len(manifest_runs)} units, expected rows={manifest.get('n_task_rows_expected')}")

    # --- Part 1: Completeness ---
    print("\n[1/4] Checking outcome completeness …")
    completeness = check_completeness(manifest_runs)
    print(f"  n_dirs={completeness['n_dirs']}  (asserted=144, actual={completeness['n_dirs']})")
    print(f"  n_complete={completeness['n_complete']}")
    print(f"  n_incomplete={completeness['n_incomplete']}")
    print(f"  n_missing_rows={completeness['n_missing_rows']}")
    print(f"  n_rows_found={completeness['n_rows_found']}")

    if completeness["n_dirs"] != 144:
        print(f"  WARNING: expected 144 dirs, found {completeness['n_dirs']}", file=sys.stderr)

    # --- Part 2: Trajectory resolution ---
    print("\n[2/4] Collecting and resolving trajectories …")
    key_to_files = collect_all_trajectories()
    total_traj_files = sum(len(v) for v in key_to_files.values())
    print(f"  total keys: {len(key_to_files)}")
    print(f"  total trajectory files (across all sfo dirs): {total_traj_files}")

    canonical_tool_calls = load_canonical_tool_calls(manifest_runs)
    print(f"  canonical tool_calls entries: {len(canonical_tool_calls)}")

    resolved, ambiguous = resolve_trajectories(key_to_files, canonical_tool_calls)
    print(f"  resolved: {len(resolved)}")
    print(f"  ambiguous (unresolvable): {len(ambiguous)}")

    ambig_out = PREFLIGHT_OUT / "ambiguous_trajectories.json"
    with open(ambig_out, "w") as f:
        json.dump(ambiguous, f, indent=2)
    print(f"  → wrote {ambig_out}")

    # --- Part 3: Defect rates ---
    print("\n[3/4] Computing defect rates …")
    defects = compute_defect_rates(resolved, canonical_tool_calls)
    defects["completeness"] = completeness
    defects["trajectory_resolution"] = {
        "n_total_traj_files": total_traj_files,
        "n_unique_keys": len(key_to_files),
        "n_resolved": len(resolved),
        "n_ambiguous": len(ambiguous),
    }

    defects_out = PREFLIGHT_OUT / "runner_defects.json"
    with open(defects_out, "w") as f:
        json.dump(defects, f, indent=2)
    print(f"  → wrote {defects_out}")

    # Print a summary
    for tool, stats in defects["per_tool"].items():
        print(f"    {tool:20s}  calls={stats['total_calls']:5d}  "
              f"truncated={stats['pct_obs_truncated']:5.1f}%  "
              f"bad_keys={stats['pct_calls_bad_keys']:5.1f}%")

    # --- Part 4: Smoke tasks ---
    print("\n[4/4] Selecting smoke tasks …")
    curriculum = load_curriculum()
    smoke = select_smoke_tasks(curriculum)
    print(f"  Candidates with hunk_start > 200: {smoke['n_total_candidates_line_gt_200']}")
    print(f"  Selected: {smoke['n_selected']}")
    for t in smoke["smoke_tasks"]:
        print(f"    {t['task_id']}  file={t['target_file']}  line={t['approx_hunk_start_line']}")

    smoke_out = PREFLIGHT_OUT / "smoke_tasks.json"
    with open(smoke_out, "w") as f:
        json.dump(smoke, f, indent=2)
    print(f"  → wrote {smoke_out}")

    print("\nDone.")


if __name__ == "__main__":
    main()
