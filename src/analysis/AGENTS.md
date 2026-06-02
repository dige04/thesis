<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-06-02 | Updated: 2026-06-02 -->

# analysis

## Purpose
The post-experiment statistical pipeline that turns 144 runs into the thesis results. Sequence-level non-parametric tests are **primary**; task-level GLMM is exploratory. Implements v5 §15 (statistics), §16 (helpful/harmful prediction), §17 (Pareto), §18 (failure analysis). The statistical choices here are frozen invariants — do not swap tests.

## Key Files
| File | Description |
|------|-------------|
| `aggregate_results.py` | Aggregates task-level results across 3 seeds into **sequence-level means (N=8)** — the primary statistical unit (v5 §15.2). Computes mean CL-F1 (anchor-probe §14.2), resolved rate, costs; carries `cl_f1_source` provenance with a labeled `resolved_rate_proxy` fallback. |
| `statistical_tests.py` | **Primary test: Wilcoxon signed-rank on N=8 sequence means**, 5 pre-registered contrasts with **Holm** correction. Effect size = **rank-biserial r_rb** (NOT Cliff's delta). Bootstrap = **5000 iterations, BCa**. Invariants #11/#12/#15. |
| `glmm.py` | Task-level binomial/logit GLMM, crossed random effects `(1|seq/seed) + (1|task_id)` (invariant #14). Exploratory only. (Note: fake `glmer` import flagged in build status.) |
| `feature_importance.py` | Helpful/harmful memory prediction on (task, retrieved_memory) pairs. **PR-AUC + VIF check** (NOT accuracy, NOT ROC-AUC; class ~20% positive), invariant #13. (Scaler-leak / GBM-weight / placeholder-feature bugs flagged.) |
| `pareto.py` | CL-F1 vs total cost frontier across the 6 policies; identifies non-dominated policies; per-sequence SEM error bars; cost-normalized CL-F1 for CLS. v5 §17. |
| `failure_analysis.py` | Categorizes failures (timeout, test_failure, syntax_error, tool_error, unknown); per-policy rates; finds tasks where Full Memory fails but a pruning policy succeeds (H5 boundary). v5 §18. |
| `plots.py` | Pareto frontier, sequence-level comparisons, memory-growth-over-time, behavioral, failure plots. Reqs 24/29. |
| `result_tables.py` | Stat-test tables (Wilcoxon+Holm), effect-size tables (r_rb + BCa CI), per-policy summaries, cost breakdowns. |

## For AI Agents

### Working In This Directory
- **Do not change the statistical tests.** Wilcoxon-on-sequence-means (not McNemar on per-task — that pseudo-replicates), rank-biserial r_rb (not Cliff's delta), PR-AUC (not accuracy/ROC-AUC). These are locked and load-bearing.
- Memory-item labels are **associated, not causal** (invariant #10) — phrase findings accordingly.
- This stage does not need a live model to run, but it needs valid logs from `runs/`. Fix the analysis bugs (build status) before reporting numbers.

### Testing Requirements
- `tests/test_aggregate_results.py`, `test_statistical_tests` paths, `test_failure_analysis.py`, `test_result_tables.py`, `test_plots.py`.

### Common Patterns
- Read `runs/{run_id}/*.jsonl` → aggregate → test → plot/table. Estimation-over-NHST: effect sizes + CIs are primary evidence, p-values supplement.

## Dependencies

### Internal
- Consumes `logging/` outputs and `metrics/` (cost, behavioral, retrieval quality).

### External
- `scipy`, `numpy`, `statsmodels`, `scikit-learn`, `matplotlib`, `pandas`.

<!-- MANUAL: -->
