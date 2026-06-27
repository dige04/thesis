<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-06-02 | Updated: 2026-06-02 -->

# benchmark

## Purpose
Everything that turns SWE-Bench-CL into runnable, scored, continual-learning data: dataset loading, per-task Docker environments, the eval_v3 wrapper, the per-sequence and full-matrix runners, and the CL metric computation. Implements v5 §2 (benchmark/scope), §3 (pipeline), §11 (logging hooks), §14.2 (CL metrics), §12 (144-run matrix). This is the **integration spine** — see root build status for what is still partial.

## Key Files
| File | Description |
|------|-------------|
| `models.py` | `Task` / sequence dataclasses (task_id, repo, base_commit, issue, test_patch, gold_patch, created_at, sequence_index, difficulty). |
| `swebenchcl_loader.py` | Loads all **8 official sequences** from `data/SWE-Bench-CL-Curriculum.json`. Frozen decision #1: no self-generated, **no re-ordering**, chronological order preserved, ≥15 tasks/sequence. |
| `task_env.py` | Docker container + clean repo checkout at `base_commit` per task. Repo checkout failure → **fail the entire sequence** (frozen decision #2). |
| `evaluator.py` | eval_v3 wrapper. Invokes the SWE-Bench Docker harness per (task, patch), parses the JSON report (real parse, not substring), returns pass/fail + FAIL_TO_PASS/PASS_TO_PASS + timing. Harness execution pending live Docker + `swebench` dep. |
| `sequence_runner.py` | Per-sequence orchestrator: init store with the policy, then per task retrieve → agent → eval → reflect → maintain, snapshot before/after, log everything. Reqs 18, 27. |
| `experiment_runner.py` | Full matrix: 8 sequences × 6 policies × 3 seeds = **144 runs**. Generates the matrix, runs each via `SequenceRunner`, tracks progress, supports resume. (CLI entry point still missing — see build status.) |
| `cl_metrics.py` | Continual-learning metrics (v5 §14.2): accuracy matrix `a_{i,j}`, Plasticity (diagonal), Stability (lower triangle / anchor-probe), **CL-F1 = 2·P·S/(P+S)**, forward/backward transfer. |
| `smoke_test.py` | Spike-Week Day-1 gate: 3 tasks, No Memory, verify Docker + logging schemas, **>15% pass = GO**. v5 §21. |

## For AI Agents

### Working In This Directory
- The 8 sequences, their order, and the eval harness are **not to be modified** (benchmark integrity, invariants #1/#16).
- Every task the runner executes must emit all four log artifacts (see `logging/AGENTS.md`) and snapshots — wire `TrajectoryLogger` + `CostTracker` (currently unwired per build status).
- Cost is operationalized as **token count** under deviation D3 (Ollama is flat-rate); see `metrics/cost_tracker.py`.
- **Compute host is arm64 macOS (deviation D5):** `task_env.py` / `evaluator.py` build `linux/arm64` Docker images and use swebench **arm64** instance images. A Spike-Week build-probe produces a deterministic **exclusion list** of arm64-unbuildable tasks, excluded **identically across all 6 conditions** (sanctioned as a documented compute trade-off). Disclose per-sequence exclusion counts; escalate to an x86_64 host if >15% of any sequence is unbuildable.
- Limit checks must be `>=` (off-by-one bug noted in build status allows 21 steps).

### Testing Requirements
- `tests/test_swebenchcl_loader.py`, `test_task_env.py`, `test_evaluator_parsing.py`, `test_sequence_runner_integration.py`, `test_experiment_runner.py`, `test_cl_metrics.py`, `test_benchmark_models.py`, `test_smoke_test.py`, `test_pilot_mode.py`.

### Common Patterns
- Sequence = unit of CL analysis (N=8). Per-task rows aggregate up to sequence means for stats.

## Dependencies

### Internal
- `agents/langgraph_agent.py`, `memory/` (store + policy), `logging/`, `metrics/cost_tracker.py`, `config/loader.py`.

### External
- `docker`, `swebench` (eval_v3), `numpy`.

<!-- MANUAL: -->
