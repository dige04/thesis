# Task 4b (smoke) disposition — recorded before the A/B (2026-06-23)

**Verdict: PARTIAL — 2/3, NOT "PASS".** (CLI exits 1; one task fails the strict per-task check.)

## Results
- `matplotlib__matplotlib-13989` — **PASS** (ranged read reached ~line 6686, edit succeeded, `RUN_COMPLETED`, 131.9s).
- `pydata__xarray-3993` — **PASS** (ranged read ~line 5972, edit succeeded, `RUN_COMPLETED`, 67.6s).
- `sympy__sympy-13091` — **FAIL** (×2). Ran a full agent loop (~150s, LLM calls, no crash) but did not navigate a ranged read to the gold region (~line 6700 of the 6700+-line `basic.py`) and made no qualifying edit. **Model/task-difficulty outcome on the hardest task — NOT a tool defect** (the tool demonstrably reaches that depth: matplotlib hit 6686). The old head-only agent reached 0/3 such targets.

## Positive evidence the instrument fix works
Two independent tasks did deep ranged reads + successful edits + valid completion in the real Docker/`/testbed` environment with the live `deepseek-v4-flash` provider — exactly what the pre-fix agent (4000-char head cap, no ranges, 30% edit failure) could never do.

## Harness caveats (why the smoke is NOT the authoritative gate)
- **Mis-configured:** `scripts/run_smoke.py:288` hardcodes `temperature=0` and `execution_backend=local`, violating the production invariants (temp=1 per A2; container backend per D5). The smoke ran in NON-production config.
- **Non-durable evidence:** the harness does not persist a trajectory/result for a failed task (only `memory.db`), so failed-smoke evidence lives only in the log.
- These are frozen (no code commits post-Freeze); not fixed here. The harness is a diagnostic, superseded by the A/B.

## Disposition / protocol
The **36-run A/B at production config** (SHA `2133b47`, temperature=1, container backend, fresh namespace `runs_ab/`, `AGENT_TOOL_MODE` legacy vs fixed per cell, no code commits) is a **stronger validation** than the mis-configured smoke and is the authoritative instrument-health gate. **Scale to the full 144 ONLY if 36/36 `RUN_COMPLETED` AND `ab_gate` = GO.** Do not rabbit-hole sympy (model behavior). Do not scale straight to 144.

## Confirmed (rerun safety)
`sequence_runner._execute_task` writes the trajectory (`:506`) and `patches/{task_id}.patch` (`:514`) **unconditionally** — empty/no-edit patches still produce an (empty) patch file — so no-edit tasks complete the unit normally in the production rerun (no infinite-retry risk). The smoke's "only memory.db for sympy" was a `run_smoke` harness quirk, not the rerun path.
