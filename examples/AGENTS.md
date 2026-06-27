<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-06-02 | Updated: 2026-06-02 -->

# examples

## Purpose
Runnable usage scripts — one per major module — that double as executable documentation. They show how to call a component in isolation (construct config, log a task, run the cost tracker, generate plots) without standing up the full 144-run pipeline. Useful as the fastest way to learn an interface.

## Key Files
| File | Module it demonstrates |
|------|------------------------|
| `config_usage.py` / `loader_usage.py` | `src/config/loader.py` |
| `task_logger_usage.py`, `memory_event_logger_usage.py`, `trajectory_logger_usage.py`, `memory_snapshot_usage.py`, `memory_snapshot_simple.py` | `src/logging/*` |
| `cost_tracker_usage.py`, `behavioral_metrics_usage.py` | `src/metrics/*` |
| `loader_usage.py`, `task_env_usage.py`, `evaluator_usage.py`, `sequence_runner_usage.py`, `experiment_runner_usage.py`, `cl_metrics_usage.py`, `pilot_mode_usage.py` | `src/benchmark/*` |
| `statistical_analysis_usage.py`, `feature_importance_usage.py`, `pareto_analysis_usage.py`, `failure_analysis_usage.py`, `plots_usage.py`, `generate_result_tables_example.py` | `src/analysis/*` |

## For AI Agents

### Working In This Directory
- Examples should stay runnable and mirror current interfaces — if you change a module's API, update its example here.
- Keep examples mock-backed where they would otherwise need a live model or Docker.
- These are documentation, not experiment runs — they must never write to `runs/` schemas in a way that pollutes real results.

## Dependencies

### Internal
- Each example imports the `src/` module it demonstrates.

<!-- MANUAL: -->
