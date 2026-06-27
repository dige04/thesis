<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-06-02 | Updated: 2026-06-02 -->

# metrics

## Purpose
Per-run measurement that feeds the analysis stage: operational cost, retrieval quality (for calibration), and behavioral signals (for the analysis-paralysis hypothesis H4). Implements v5 §14.4 (efficiency), §14.6 (behavioral), §14.7 (retrieval quality).

## Key Files
| File | Description |
|------|-------------|
| `cost_tracker.py` | Tracks every LLM + embedding call at call / task / run / experiment levels. Under deviation **D3** the Pareto cost axis is **token count** (`COST_METRIC_MODE=tokens`), since Ollama is flat-rate GPU-time; `usd` and `walltime` modes also supported. Provider-independent compute proxy. |
| `retrieval_quality.py` | Precision@k, Recall@k, MRR, NDCG@k — used during pilot mode to **calibrate `top_k` and `max_context_tokens`** (Req 30). Re-validate under the new embedder (D2). |
| `behavioral.py` | Tool-calls-per-task and syntax-error rate to test **H4** (does Full Memory induce analysis paralysis that forgetting policies mitigate?). v5 §14.6. |

## For AI Agents

### Working In This Directory
- The cost metric is operationalized per D3 — disclose "tokens" as the cost axis in the thesis. Don't silently switch to USD (meaningless on flat-rate Ollama).
- Retrieval-quality metrics drive a **one-time calibration** window; after lock, `top_k`/`max_context_tokens` are frozen.
- Behavioral metrics are descriptive signals for H4 — labels are associated, not causal (invariant #10).

### Testing Requirements
- `tests/test_cost_tracker.py`; behavioral/retrieval covered via runner integration and examples (`examples/cost_tracker_usage.py`, `examples/behavioral_metrics_usage.py`).

### Common Patterns
- Counters accumulate during a run and are flushed into the task/run logs.

## Dependencies

### Internal
- Wired by `benchmark/sequence_runner.py`; consumed by `analysis/pareto.py` (cost) and `analysis/` behavioral plots.

### External
- `tiktoken` (token counting), `numpy`.

<!-- MANUAL: -->
