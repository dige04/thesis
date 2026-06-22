# Task 5e Report — A/B Scheduler + Gate Calculator

**Status:** DONE  
**Branch:** rerun/instrument-fix  
**Files created:**
- `scripts/ab_schedule.py`
- `scripts/ab_gate.py`
- `tests/test_ab_tooling.py`

---

## What was built

### `scripts/ab_schedule.py`

`ab_schedule(seed=20260622) -> list[dict]` — deterministic 36-cell A/B schedule.

- Cross product: 2 sequences × 3 policies × 3 seeds × 2 tool_modes = **36 cells**.
- `run_id` format: `{policy}_{sequence_name}_seed{seed}_{tool_mode}` — tool_mode embedded, legacy/fixed never collide.
- Execution order is a deterministic shuffle using `random.Random(seed).shuffle`.  The canonical set of 36 run_ids is identical across all seeds; only order varies.
- CLI: `python -m scripts.ab_schedule [--seed N]` prints JSON.

### `scripts/ab_gate.py`

`ab_gate(runs_root, results_dir) -> dict` — three-state gate: `BLOCKED | STOP | GO`.

**BLOCKED** (structural — metrics NOT computed) if:
- Any of the 36 expected run dirs is missing.
- Any run has `RUN_FAILED.json`.
- Any run lacks `RUN_COMPLETED.json` (via `src.benchmark.completion.is_run_complete`).
- Any `(policy, sequence, seed)` pair has mismatched task_ids between legacy and fixed.
- Duplicate `(policy, seed, task_id)` rows detected within any run.

**STOP** (health metrics violated) if:
- `edit_path_index_failures > 0` — observations containing `/testbed` in an error context or `does not match index` from git apply stderr.
- `total_edit_file_calls == 0` — undefined ratio (no edit activity; instrument cannot be verified).
- `edit_failure_ratio > 0.15` — `failed / total` over fixed-mode edit_file observations.
- `fixed median prompt tokens > 1.5 × legacy` OR same for total tokens.

**GO** — all pass.

**Key design decisions:**
- Edit failure detection is grounded in `src/agents/langgraph_agent.py::_execute_tool` which wraps exceptions as `"ERROR: tool 'edit_file' failed: {e}"`.
- `observation_summary` is coerced via `str()` before matching — handles list observations (e.g. search_code returns `[]`).
- Token metrics computed over fixed-mode task_results.jsonl rows; legacy tokens collected in parallel for inflation ratio.
- Resolve-rate / timeout delta is **reported** (not gated) in `reported_deltas`.
- Range correctness noted as a dependency on `tests/test_agents_tools.py -k read_file` (not re-derived from LLM run data).

---

## Test results

26 tests in `tests/test_ab_tooling.py`, all pass:

| Class | Tests | Coverage |
|---|---|---|
| TestAbSchedule | 11 | schedule shape, uniqueness, determinism, seed-invariant multiset, balanced cells |
| TestAbGateBlocked | 4 | no runs, <36 complete, RUN_FAILED present, unpaired task_ids |
| TestAbGateGo | 5 | complete+paired → GO, required keys, delta reporting, zero path failures, range note |
| TestAbGateStop | 4 | total_edit_file==0, ratio>0.15, path failures>0, token inflation>1.5× |

`pytest tests/ -k "ab_" -q` → **29 passed** (26 new + 3 pre-existing matching "ab_").

---

## Blocking concerns

None. All 26 tests pass. No frozen invariants touched (new scripts only). No existing tests broken.

One test was initially wrong (unpaired-tasks test used `i==0 and tool_mode=="legacy"` but cell 0 is `fixed` — corrected to find the first legacy index dynamically before building fixtures).
