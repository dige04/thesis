<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-06-02 | Updated: 2026-06-02 -->

# logging

## Purpose
The mandatory logging layer. **Every task must produce four artifacts** (v5 §11) — a missing field at run time cannot be recovered, and a schema change mid-experiment invalidates prior runs. Log everything from Day 1. These loggers define the exact JSONL/snapshot schemas the analysis stage depends on.

## Key Files
| File | Description |
|------|-------------|
| `task_logger.py` | One row per completed task → `runs/{run_id}/task_results.jsonl` (v5 §11.1). Atomic writes (temp file + rename). All required fields must be present. |
| `memory_event_logger.py` | Append memory `write` / `archive` / `consolidate` events → `runs/{run_id}/memory_events.jsonl` (v5 §11.2): event_id, step, policy, event_type, memory_id, replacement_id. |
| `trajectory_logger.py` | Per-task agent trace → `runs/{run_id}/trajectories/{task_id}.json` (v5 §11.3). **CRITICAL: no private chain-of-thought** — log WHAT the agent did (tool calls, actions) and WHAT it observed (results), never WHY (reasoning/planning). |
| `memory_snapshot_logger.py` | Full memory state at every task boundary → `before_task_{n}.json` / `after_task_{n}.json` in `runs/{run_id}/memory/snapshots/` (v5 §11.4). Enables post-hoc memory-evolution analysis without re-running. |

## For AI Agents

### Working In This Directory
- **Do not write chain-of-thought to trajectories** (root golden rule #4). Actions + observations only.
- **Do not change a schema mid-experiment** — it invalidates all prior runs. Schemas are pinned to v5 §11.
- Outputs land under `runs/` which is **gitignored** — never check in `runs/`, `*.faiss`, `*.sqlite`, or wandb cache.
- The `sequence_runner` must call all four loggers per task (trajectory + cost wiring is currently incomplete — see root build status).

### Testing Requirements
- `tests/test_task_logger.py`, `test_memory_event_logger.py`, `test_trajectory_logger.py`, `test_memory_snapshot_logger.py`. Assert schema completeness and atomicity.

### Common Patterns
- JSON Lines (newline-delimited) for streaming logs; pretty-printed JSON for snapshots.

## Dependencies

### Internal
- Called by `benchmark/sequence_runner.py`; consumed by `analysis/` and `metrics/`.

### External
- stdlib `json`, `os` (atomic rename).

<!-- MANUAL: -->
