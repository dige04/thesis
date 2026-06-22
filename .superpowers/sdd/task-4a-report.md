# Task 4a Report — Integration Tests + Smoke Harness

**Date:** 2026-06-23
**Branch:** `rerun/instrument-fix`
**Status:** COMPLETE

---

## Summary

Task 4a delivered:
1. **`tests/test_agent_largefile_integration.py`** — 18 offline integration tests, all passing.
2. **`tests/test_smoke_harness.py`** — 21 tests (19 pass offline, 2 skipped `@pytest.mark.skip(reason="network; run in Task 4b")`).
3. **`scripts/run_smoke.py`** — committed smoke harness; the actual network run is Task 4b.

---

## Part 1 — `tests/test_agent_largefile_integration.py`

### What was tested

**Bullet 1 — `read_file` range / budget / continuation hint:**
- `test_ranged_read_past_line_200_returns_exact_range`: calls `agent._execute_tool("read_file", {start_line=250, end_line=260})` on a 500-line, >12000-char fixture file; asserts lines 250-260 present and lines outside range absent.
- `test_ranged_read_does_not_return_head`: verifies start_line=300 read does not contain line 1 content.
- `test_whole_file_read_is_budget_bounded`: asserts `len(obs) <= MAX_READ_CHARS` (12000).
- `test_whole_file_read_has_continuation_hint`: asserts "to continue" or "read_file(path," present.
- `test_ranged_read_files_tracked_in_state`: asserts `state.files_read` updated.

**Bullet 2 — `_truncate_obs` on ~30KB pytest failure:**
- `test_failure_tail_survives_truncation`: tail failure text ("AssertionError: assert 42 == 99", "1 failed, 700 passed") survives.
- `test_truncated_output_within_max_obs`: len ≤ `_MAX_OBS` (12000).
- `test_omitted_marker_present_for_large_input`: "omitted" marker present.
- `test_legacy_mode_head_truncates`: legacy mode cuts at 4000 chars, tail lost (regression guard).

**Bullet 3 — `edit_file` `/testbed/`-style paths + cross-file rejection:**
- `test_testbed_absolute_path_diff_applies`: `/testbed/m.py` absolute paths → patch applies, file updated.
- `test_cross_file_diff_raises_value_error`: diff touching `other.py` while `path='m.py'` → `ValueError`, both files untouched.
- `test_standard_diff_applies`: plain `a/b` unified diff applies correctly.

**Bullet 4 — MemoryStore + TrajectoryLogger + TaskResultLogger artifact placement:**
- `test_memory_db_under_run_dir`: memory.db under `run_dir/memory/memory.db`.
- `test_memory_faiss_under_run_dir`: memory.faiss under `run_dir/memory/memory.faiss`.
- `test_memory_snapshots_under_run_dir`: snapshots dir under `run_dir/memory/snapshots/`.
- `test_trajectory_under_run_dir`: trajectory written to `run_dir/trajectories/{task_id}.json`.
- `test_task_row_under_run_dir`: task_results.jsonl written under `run_dir/`.
- `test_all_four_artifacts_under_single_run_dir`: end-to-end all four artifact types under one run_dir, `./runs/` never created.

### Key design decisions
- Fixture file built with padded lines (~40 chars each × 500 lines) to ensure content exceeds both MAX_READ_LINES (400) and MAX_READ_CHARS (12000).
- `AGENT_TOOL_MODE=fixed` pinned via `monkeypatch.setenv` to avoid mode-branching surprises.
- `_truncate_obs` called with `mode="fixed"` explicitly for clarity.
- `edit_file` tests call `tools.edit_file()` directly (not through `_execute_tool`) for cross-file test, since `_execute_tool` swallows exceptions into error strings.

---

## Part 2 — `scripts/run_smoke.py` + `tests/test_smoke_harness.py`

### Smoke harness architecture

`scripts/run_smoke.py` is split into:
- **`evaluate_smoke_trajectory(trajectory, result, task_meta) → dict`** — pure function, zero network. Tests all 4 checks on an already-collected trajectory. Importable offline.
- **`run_smoke(task_ids, runs_root, smoke_tasks_json) → dict`** — the only network-calling function. Reads `results/preflight/smoke_tasks.json`, sets `AGENT_TOOL_MODE=fixed`, invokes `CodingAgent.solve_task()`, calls the checker, writes `RUN_COMPLETED.json` on pass.

### Four checks
1. **`ranged_read_reaching_target`**: at least one `read_file` with `start_line` such that the range spans `approx_hunk_start_line`.
2. **`no_identical_repeat_read_loop`**: no two consecutive `read_file` calls with identical `(path, start_line, end_line)`.
3. **`at_least_one_successful_edit`**: at least one `edit_file` with `observation_summary.startswith("Edited ")` or `write_file` with `"Wrote "`.
4. **`termination_reason_recorded`**: result `termination_reason` is not None and not empty.

### `tests/test_smoke_harness.py` — 21 tests
- `TestGoodTrajectoryPasses` (5 tests): fixture trajectory satisfying all 4 checks → all pass.
- `TestIdenticalRepeatReadLoopFails` (4 tests): consecutive identical reads → `no_identical_repeat_read_loop=False`; non-consecutive identical reads → OK.
- `TestMissingSuccessfulEditFails` (3 tests): failed/error edit → check fails; `write_file` success counts.
- `TestMissingTerminationReason` (4 tests): None/""/"" → fails; "step_limit" → passes.
- `TestRangedReadNotReachingTarget` (3 tests): head-only reads → check fails.
- 2 standalone tests + 2 `@pytest.mark.skip(reason="network; run in Task 4b")` tests.

---

## Test results

```
# Integration tests only
.venv/bin/pytest tests/test_agent_largefile_integration.py -q
→ 18 passed in 3.41s

# Smoke harness only
.venv/bin/pytest tests/test_smoke_harness.py -q
→ 21 passed, 2 skipped in 1.03s

# Grader filter
.venv/bin/pytest tests/ -k "largefile or smoke or integration" -q
→ 93 passed, 2 skipped, 1036 deselected in 6.41s

# Full suite (sanity)
.venv/bin/pytest tests/ -q --tb=no
→ 2 failed (pre-existing), 1127 passed, 2 skipped
```

Pre-existing failures (not introduced by Task 4a):
- `tests/test_container_backend.py::test_agent_tools_routes_through_container_backend`
- `tests/test_task_logger.py::test_task_result_to_dict`

---

## Post-write fixes (applied before commit)

Two freeze-sensitive issues found during final advisor review and fixed:

**1. `run_smoke()` broken callsites** (would crash in Task 4b at frozen SHA):
- `SWEBenchCLLoader()` called without `curriculum_path` → fixed to read from `CURRICULUM_PATH` env var (defaulting to `data/SWE-Bench-CL-Curriculum.json`).
- `loader.get_task(task_id)` — method does not exist → fixed to call `load_all_sequences()` and build a flat `task_id → Task` lookup dict.
- `TaskEnvironment(task_id=..., repo=..., base_commit=...)` — constructor takes a single `Task` dataclass → fixed to construct a `Task` object and pass it as `TaskEnvironment(task=task_obj)`.
- `env.checkout()` — method is `checkout_clean_repo()` → fixed.

**2. Check-1 (`ranged_read_reaching_target`) false-pass on head reads with large `end_line`** (would miss the defect it guards):
- Old condition: `start <= target <= end_val or end_val >= target` — a call `(start=1, end=9999)` passes even though `MAX_READ_LINES=400` means the agent never sees line 6700.
- New condition: `start > target_line - MAX_READ_LINES` — requires the window to actually start within 400 lines of the target.
- Added `test_large_end_line_head_read_still_fails` to `tests/test_smoke_harness.py` to document and guard this case.

**Test results after fixes:** 40 passed, 2 skipped (all new tests).

## Blocking concerns

None. All new tests pass offline. The smoke harness is committed and ready for the Task 4b network run.
