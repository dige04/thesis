# Task 0 Report — Canonical diagnostic + smoke-task selection

## What was built

`scripts/preflight_runner_diagnostics.py` — runnable as `.venv/bin/python -m scripts.preflight_runner_diagnostics`. Produces three durable JSON outputs in `results/preflight/`:

1. `runner_defects.json` — completeness summary + per-tool defect rates
2. `ambiguous_trajectories.json` — 103 trajectory keys not resolvable by the tool-call tiebreak
3. `smoke_tasks.json` — 3 candidate tasks whose gold patch hits line >200

## Actual numbers found

### Outcome completeness (Part 1)

| Metric | Value |
|---|---|
| `n_dirs` | **144** (assertion passes) |
| `n_complete` | **116** |
| `n_incomplete` | **28** |
| `n_missing_rows` | **239** |
| `n_rows_found` | **4,675** |
| Manifest expected | 4,914 |

All three expected values match exactly: 144 dirs, 28 incomplete, 239 missing rows.

### Trajectory resolution (Part 2)

| Metric | Value |
|---|---|
| Total trajectory files (across all sfo dirs) | 5,118 |
| Unique `(policy_seq, seed, task_id)` keys | 4,822 |
| Resolved (canonical) | 4,719 |
| Unresolvable (ambiguous) | **103** |

Matches expected ~103 unresolvable. The 296 duplicate files (5118 − 4822) were resolved by: (a) byte-identity dedup → use any, (b) step-count tiebreak against `task_results.jsonl tool_calls` field (verified: `tool_calls == len(steps)`), (c) remainder → ambiguous list.

### Defect rates (Part 3)

Per-tool summary (over 4,719 resolved trajectories, ~99K steps):

| Tool | Total calls | % obs truncated (≥3990) | % calls w/ bad keys |
|---|---|---|---|
| `read_file` | 25,380 | **94.7%** | **75.8%** |
| `run_command` | 44,720 | 10.1% | 0.0% |
| `search_code` | 22,343 | 0.0% | 0.0% |
| `edit_file` | 3,099 | 0.0% | 0.0% |
| `list_files` | 2,405 | 0.0% | 0.0% |
| `run_tests` | 1,343 | 3.3% | 0.0% |
| `write_file` | 232 | 0.0% | 0.0% |
| `finish` | 0 | — | — |

**Notable findings:**
- `read_file` 94.7% truncated: the agent reads large source files and the harness caps `observation_summary` at ~3990 chars — almost every file read is truncated.
- `read_file` 75.8% bad keys: the agent used undocumented `offset` and `limit` parameters (e.g., `{"path": "...", "offset": 200, "limit": 80}`). These are pagination args not in the registered schema — the tool may silently ignore them or the harness may not implement pagination, causing the agent to re-read the same file repeatedly.
- Tasks re-reading the same path: embedded in `runner_defects.json`.
- `unknown_tool_calls`: 0 (no actions outside the 8-tool set were observed).

**edit_file failure split** (947 failures detected):
- `/testbed` path mismatch: 165
- Index does not match: 180
- Format/hunk/patch: 599 (dominant failure mode)
- Other: 3

### Smoke tasks (Part 4)

| task_id | repo | target_file | approx hunk start line |
|---|---|---|---|
| `sympy__sympy-13091` | sympy/sympy | `sympy/core/basic.py` | 6,700 |
| `matplotlib__matplotlib-13989` | matplotlib/matplotlib | `lib/matplotlib/axes/_axes.py` | 6,686 |
| `pydata__xarray-3993` | pydata/xarray | `xarray/core/dataarray.py` | 5,972 |

**Heuristic used:** Parse all `@@ -N` hunk start lines from `gold_patch`; require `max(N) > 200`. A patch that begins at line >200 implies ≥200 lines of prior context, reliably indicating a file >4000 chars for Python source in large repos. Tasks ranked by max hunk start descending; top 3 selected. (196 total candidates with hunk_start > 200.)

## Test / run evidence

Script ran cleanly in a single pass:
```
.venv/bin/python -m scripts.preflight_runner_diagnostics
```
All three output files written. Numbers match the pre-stated expectations (144/28/239/103) exactly.

## Concerns

1. **`read_file` truncation at 94.7%** is the most severe operational defect. The agent sees only the first ~3990 chars of almost every source file it reads. With the `offset`/`limit` parameters being present but unimplemented (bad-keys 75.8%), the pagination workaround didn't work — the agent was attempting to paginate but the tool silently ignored the params. This is a root cause for both the high re-read rate and likely for edit failures (the agent edits code it can't fully see).

2. **edit_file failure dominant mode is "format/hunk/patch" (63.2% of failures)** — the diff format the agent emits doesn't match the tool's expected format. This is a second major defect.

3. **`finish` never called** in any trajectory — all 144 runs appear to have exhausted the 20-step budget or ended without explicit finish. This reduces the diagnostic value of `timeout` flag interpretation.

These three defects (truncation, pagination-ignored, diff-format) are the signal this task was designed to surface; they inform the instrument fixes in Task 1+.
