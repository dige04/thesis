<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-06-02 | Updated: 2026-06-02 -->

# tests

## Purpose
The pytest suite. Beyond ordinary unit coverage, its load-bearing job is to **assert that frozen invariants hold** — e.g. embedding payload < 7500 tokens, identical retrieval across all policies, max-step limits, locked decay formula, k=5 CLS cadence. Every new `src/` file must arrive with a corresponding test here (root golden rule #6 / v5 workflow).

## Key Files (by area)
| Area | Tests |
|------|-------|
| Memory core | `test_memory_record.py`, `test_memory_store.py`, `test_memory_store_faiss.py`, `test_memory_retriever.py`, `test_memory_policy_base.py` |
| Policies | `test_no_memory_policy.py`, `test_full_memory_policy.py`, `test_random_prune_policy.py`, `test_recency_prune_policy.py`, `test_type_aware_decay_policy.py`, `test_cls_consolidation_policy.py` |
| Classifier / reflection | `test_classifier_basic.py`, `test_reflection_integration.py` |
| Agent | `test_agent_limits.py`, `test_agent_react_loop.py`, `test_agents_tools.py`, `agents/test_limit_tracker.py` |
| Benchmark | `test_swebenchcl_loader.py`, `test_task_env.py`, `test_evaluator_parsing.py`, `test_sequence_runner_integration.py`, `test_experiment_runner.py`, `test_cl_metrics.py`, `test_benchmark_models.py`, `test_smoke_test.py`, `test_pilot_mode.py` |
| Analysis | `test_aggregate_results.py`, `test_failure_analysis.py`, `test_result_tables.py`, `test_plots.py` |
| Logging | `test_task_logger.py`, `test_memory_event_logger.py`, `test_trajectory_logger.py`, `test_memory_snapshot_logger.py` |
| Config / cost / errors | `test_config.py`, `test_config_integration.py`, `test_llm_factory.py`, `test_cost_tracker.py`, `test_error_handling.py`, `test_setup.py` |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| `agents/` | Agent-specific tests (`test_limit_tracker.py`) (see `agents/AGENTS.md`). |

## For AI Agents

### Working In This Directory
- Prefer **invariant tests** over snapshot tests — e.g. `test_retrieval_is_identical_across_policies`, `test_embedding_size_assert`.
- Tests must not require a live model where avoidable — mock the `llm_factory` clients. Live-model and Docker-dependent paths are integration-gated.
- Run with `make test`; lint with `make lint` before declaring done.

### Common Patterns
- Fixtures construct `MemoryRecord`s and a temp `MemoryStore`; policies are exercised through the shared retriever.

## Dependencies

### External
- `pytest`, `pytest` fixtures, `unittest.mock`.

<!-- MANUAL: -->
