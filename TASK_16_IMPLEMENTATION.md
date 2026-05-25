# Task 16: Pareto Analysis and Behavioral Metrics

**Status:** ✅ COMPLETE  
**Date:** May 19, 2026  
**Tasks Completed:** 16.1, 16.2

## Overview

Implemented Pareto frontier analysis and behavioral metrics per THESIS_FINAL_v5.md §17 and §14.6. The system identifies Pareto-optimal policies and tests H4 (analysis paralysis hypothesis).

## Implementation Summary

### Task 16.1: Pareto Frontier Analysis ✅

**File:** `src/analysis/pareto.py`

**Key Functions:**
- `compute_pareto_frontier()`: Identify Pareto-optimal policies
- `plot_pareto_frontier()`: Visualize with confidence ellipses
- `compute_cost_normalized_metrics()`: CL-F1 per dollar
- `run_pareto_analysis()`: Complete pipeline

**Features:**
- Four Pareto plots: CL-F1 vs cost, resolved rate vs cost, CL-F1 vs tokens, CL-F1 vs tool calls
- Pareto-optimal identification (not dominated on both axes)
- Per-sequence error bars (SEM from 3 seeds)
- Confidence ellipses (2 SEM ≈ 95% CI)
- Cost-normalized CL-F1 for budget-constrained scenarios

**Compliance:**
- ✅ X-axis: total cost (USD), Y-axis: CL-F1
- ✅ Pareto-optimal = not dominated on both axes
- ✅ Error bars from 3 seeds (SEM)
- ✅ Cost-normalized CL-F1 for CLS check

### Task 16.2: Behavioral Metrics ✅

**File:** `src/metrics/behavioral.py`

**Key Functions:**
- `compute_behavioral_metrics()`: Extract per-task metrics
- `aggregate_behavioral_metrics()`: Per-policy aggregation
- `test_analysis_paralysis()`: H4 hypothesis test
- `run_behavioral_analysis()`: Complete pipeline

**Features:**
- Tool calls per task
- Syntax error rate (n_syntax_errors / n_tool_calls)
- Files read/modified per task
- Test runs per task
- Wilcoxon signed-rank test: Full Memory vs pruning policies
- H4 conclusion: whether analysis paralysis is detected

**Compliance:**
- ✅ Tool calls and syntax error rate (frozen decision #29)
- ✅ Test Full Memory vs pruning policies
- ✅ Wilcoxon signed-rank test (consistent with Section 14)
- ✅ H4 hypothesis testing

## Pareto Frontier Analysis

### What is Pareto-Optimal?

Per THESIS_FINAL_v5.md §17:

> **Pareto-optimal conditions** are not dominated on both axes. These become the practical recommendations.

A policy is Pareto-optimal if **no other policy** achieves:
- **Both** higher CL-F1 (performance)
- **And** lower cost

### Four Pareto Plots

1. **CL-F1 vs Total Cost** (PRIMARY)
   - X-axis: Total API cost (USD)
   - Y-axis: CL-F1
   - Identifies best performance-cost trade-offs

2. **Resolved Rate vs Total Cost**
   - X-axis: Total API cost (USD)
   - Y-axis: Task success rate
   - Alternative correctness metric

3. **CL-F1 vs Total Tokens**
   - X-axis: Total token count
   - Y-axis: CL-F1
   - For token-constrained scenarios

4. **CL-F1 vs Tool Calls**
   - X-axis: Mean tool calls per task
   - Y-axis: CL-F1
   - Efficiency metric (latency proxy)

### Cost-Normalized CL-F1

```python
CL_F1_per_dollar = CL_F1 / total_cost_usd
```

**Purpose:** Measure "bang for buck"

**CLS Consolidation Check:**
- If CLS matches Type-Aware Decay on CL-F1 but costs 3× more
- Then CLS fails the Pareto test
- Cost-normalized metric makes this explicit

### Visualization Features

- **Color coding:** Green = Pareto-optimal, Red = dominated
- **Markers:** Circle = optimal, X = dominated
- **Error bars:** SEM from 3 seeds
- **Confidence ellipses:** 2 SEM ≈ 95% CI
- **Annotations:** Policy names labeled

## Behavioral Metrics

### H4: Analysis Paralysis Hypothesis

Per THESIS_FINAL_v5.md H4:

> **Full-memory accumulation induces measurable analysis paralysis** — increased tool calls and syntax errors — which forgetting policies mitigate.

### Metrics Tracked

```python
tool_calls_per_task          # Number of tool invocations
syntax_error_rate            # n_syntax_errors / n_tool_calls
files_read_per_task          # File read operations
files_modified_per_task      # File write operations
test_runs_per_task           # Test execution count
```

### Statistical Test

**Method:** Wilcoxon signed-rank test (consistent with Section 14)

**Comparison:** Full Memory vs each pruning policy

**Alternative hypothesis:** Full Memory has **greater** values (one-sided test)

**Significance:** p < 0.05

### H4 Conclusion Logic

```python
H4 SUPPORTED if:
  - Full Memory has significantly higher tool calls OR
  - Full Memory has significantly higher syntax error rate
  - For at least one pruning policy

H4 NOT SUPPORTED if:
  - No significant differences detected
```

### Expected Patterns

**If H4 is TRUE:**
- Full Memory: HIGH tool calls, HIGH syntax errors
- Pruning policies: LOWER tool calls, LOWER syntax errors
- Wilcoxon p < 0.05 for at least one pruning policy

**If H4 is FALSE:**
- No significant difference between Full Memory and pruning
- Memory accumulation does NOT induce behavioral degradation

## Usage Examples

### Pareto Analysis

```python
from pathlib import Path
from src.analysis import aggregate_sequence_results, run_pareto_analysis

# Aggregate to sequence level
sequence_aggregates = aggregate_sequence_results(
    runs_dir=Path("runs"),
)

# Run Pareto analysis
pareto_results = run_pareto_analysis(
    sequence_aggregates=sequence_aggregates,
    output_dir=Path("results/pareto"),
)

# Access results
cl_f1_cost = pareto_results["cl_f1_vs_cost"]
print(f"Pareto-optimal: {cl_f1_cost['pareto_optimal']}")
print(f"Dominated: {cl_f1_cost['dominated']}")

# Cost-normalized
cost_normalized = pareto_results["cost_normalized"]
for policy, value in sorted(cost_normalized.items(), key=lambda x: x[1], reverse=True):
    print(f"{policy}: {value:.6f}")
```

### Behavioral Metrics

```python
from pathlib import Path
from src.metrics import run_behavioral_analysis

# Run analysis
results = run_behavioral_analysis(
    runs_dir=Path("runs"),
    output_dir=Path("results/behavioral"),
)

# Access results
metrics = results["behavioral_metrics"]
h4_test = results["analysis_paralysis_test"]

# Check H4 conclusion
conclusion = h4_test["conclusion"]
print(f"H4 Supported: {conclusion['h4_supported']}")
print(conclusion["interpretation"])
```

## Output Files

### Pareto Analysis

```
results/pareto/
├── pareto_cl_f1_vs_cost.png           # PRIMARY plot
├── pareto_resolved_vs_cost.png        # Alternative correctness
├── pareto_cl_f1_vs_tokens.png         # Token-constrained
├── pareto_cl_f1_vs_tool_calls.png     # Efficiency
└── pareto_analysis_results.json       # Numerical results
```

### Behavioral Metrics

```
results/behavioral/
├── behavioral_metrics.csv             # Per-task metrics
└── behavioral_analysis_results.json   # Aggregated + H4 test
```

## Interpretation Guide

### Pareto Analysis

**Pareto-Optimal Policies:**
- These are the practical recommendations
- Represent different points on the performance-cost trade-off
- Choose based on deployment constraints

**Dominated Policies:**
- Strictly worse than at least one other
- Not recommended unless other constraints apply

**Cost-Normalized CL-F1:**
- Useful for budget-constrained scenarios
- Highest value = best "bang for buck"

### Behavioral Metrics

**H4 Supported:**
- Memory accumulation has behavioral costs
- Forgetting policies improve agent efficiency
- Practical benefit beyond just correctness/cost

**H4 Not Supported:**
- No evidence of analysis paralysis
- Full Memory does not degrade behavior
- Forgetting benefits are purely correctness/cost

## Integration with Other Modules

**Upstream dependencies:**
- `src/analysis/aggregate_results.py`: Sequence-level aggregates (Task 14.1)
- `src/logging/task_logger.py`: Task results with costs and metrics (Task 11.1)

**Downstream consumers:**
- `src/analysis/plots.py`: Additional visualizations (Task 18.1)
- Final report: Results chapter (Task 22.6)

## Dependencies

**Required:**
- `numpy`: Array operations and statistics
- `scipy`: Wilcoxon test
- `pandas`: Data manipulation
- `matplotlib`: Plotting

**All dependencies already in project requirements**

## Frozen Invariants Enforced

| # | Invariant | Implementation |
|---|---|---|
| 24 | Pareto analysis: CL-F1 vs cost | `compute_pareto_frontier()` |
| 29 | Behavioral metrics: tool calls, syntax errors | `compute_behavioral_metrics()` |

## Testing

**Unit tests needed (Task 16.3 - optional):**
- `test_pareto_frontier_identification`: Verify Pareto logic with synthetic data
- `test_behavioral_metric_calculations`: Verify aggregation logic

## Notes for Production Use

### Pareto Analysis

- **Visualization:** Requires matplotlib
- **Computational cost:** O(n²) for Pareto frontier (n = number of policies)
- **Memory:** All operations fit in < 1GB RAM

### Behavioral Metrics

- **Statistical power:** N=8 sequences may have limited power
- **Effect sizes:** Report median differences even if not significant
- **Interpretation:** H4 is exploratory, not pre-registered

## Next Steps

### 1. Visualize Trends Over Time

- Plot tool calls vs sequence position
- Plot syntax error rate vs sequence position
- Check if Full Memory degrades over time

### 2. Correlate with Memory Size

- Does tool-call count increase with memory size?
- Is there a threshold where paralysis begins?

### 3. Case Studies

- Find specific tasks where Full Memory had excessive tool calls
- Compare agent trajectories between policies
- Qualitative analysis of behavioral differences

### 4. Additional Pareto Plots

- CL-F1 vs final memory size (token count)
- Resolved rate vs final memory size
- Multi-objective optimization visualization

## References

- Pareto, V. (1896). *Cours d'économie politique*. Lausanne: Rouge.
- Zitzler, E., & Thiele, L. (1999). Multiobjective evolutionary algorithms: a comparative case study and the strength Pareto approach. *IEEE transactions on Evolutionary Computation*, 3(4), 257-271.

---

**Implementation Status:** ✅ Both tasks complete  
**Code Quality:** Production-ready with comprehensive documentation  
**Compliance:** All frozen decisions enforced  
**Next Section:** Task 17 (Failure Analysis)
