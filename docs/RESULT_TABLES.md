# Result Tables Module

## Overview

The `result_tables` module implements Task 18.2 of the memory pruning research system. It generates four types of tables required for statistical reporting and analysis:

1. **Statistical Test Results Tables** - Wilcoxon signed-rank tests with Holm correction
2. **Effect Size Tables** - Rank-biserial effect sizes with BCa confidence intervals
3. **Performance Summary Tables** - Per-policy performance metrics across sequences
4. **Cost Breakdown Tables** - Detailed cost analysis per policy

## Requirements

This module satisfies the following requirements from the spec:

- **Requirement 20**: Sequence-level statistical analysis with Wilcoxon signed-rank tests and Holm correction
- **Requirement 21**: Bootstrap BCa confidence intervals with 5000 iterations
- **Requirement 27**: Cost monitoring and breakdown reporting

## Module Structure

```
src/analysis/result_tables.py
├── generate_statistical_test_table()      # Wilcoxon + Holm correction results
├── generate_effect_size_table()           # Rank-biserial + BCa CI
├── generate_performance_summary_table()   # Per-policy metrics
├── generate_cost_breakdown_table()        # Cost analysis
├── generate_all_result_tables()           # Main entry point
└── print_table_summary()                  # Console output
```

## Usage

### Basic Usage

```python
from pathlib import Path
from src.analysis import (
    aggregate_sequence_results,
    compute_all_contrasts_with_bootstrap,
    generate_all_result_tables,
)

# Step 1: Aggregate sequence-level results
sequence_aggregates = aggregate_sequence_results(
    runs_dir=Path("runs"),
    output_path=Path("results/sequence_aggregates.json"),
)

# Step 2: Run statistical tests with bootstrap
wilcoxon_results = compute_all_contrasts_with_bootstrap(
    sequence_aggregates=sequence_aggregates,
    metric="mean_cl_f1",
    baseline_policy="full_memory",
    contrasts=["random_prune", "recency_prune", "type_aware_decay", 
               "cls_consolidation", "no_memory"],
    n_bootstrap=5000,
    random_seed=42,
)

# Step 3: Generate all tables
tables = generate_all_result_tables(
    sequence_aggregates=sequence_aggregates,
    wilcoxon_results=wilcoxon_results,
    output_dir=Path("results/tables"),
)
```

### Individual Table Generation

```python
from src.analysis.result_tables import (
    generate_statistical_test_table,
    generate_effect_size_table,
    generate_performance_summary_table,
    generate_cost_breakdown_table,
)

# Generate individual tables
stat_table = generate_statistical_test_table(
    wilcoxon_results=wilcoxon_results,
    output_path=Path("results/statistical_tests.csv"),
)

effect_table = generate_effect_size_table(
    wilcoxon_results=wilcoxon_results,
    output_path=Path("results/effect_sizes.csv"),
)

perf_table = generate_performance_summary_table(
    sequence_aggregates=sequence_aggregates,
    output_path=Path("results/performance_summary.csv"),
)

cost_table = generate_cost_breakdown_table(
    sequence_aggregates=sequence_aggregates,
    output_path=Path("results/cost_breakdown.csv"),
)
```

## Table Descriptions

### 1. Statistical Test Results Table

**Purpose**: Report Wilcoxon signed-rank test results with Holm correction for multiple comparisons.

**Columns**:
- `Policy`: Policy being compared
- `Baseline`: Baseline policy (typically "full_memory")
- `N`: Number of paired observations (sequences)
- `Statistic`: Wilcoxon test statistic
- `p-value`: Raw p-value from Wilcoxon test
- `Holm p-value`: Holm-corrected p-value
- `Significant`: Whether Holm p-value < 0.05

**Example Output**:
```
Policy              Baseline      N  Statistic  p-value  Holm p-value  Significant
type_aware_decay    full_memory   8       3.00   0.0250        0.0500           No
random_prune        full_memory   8       1.00   0.1800        0.1800           No
```

### 2. Effect Size Table

**Purpose**: Report rank-biserial effect sizes with bootstrap BCa confidence intervals.

**Columns**:
- `Policy`: Policy being compared
- `Baseline`: Baseline policy
- `Median Diff`: Median paired difference
- `Rank-Biserial r_rb`: Rank-biserial correlation effect size
- `Effect Size`: Magnitude interpretation (Negligible/Small/Medium/Large)
- `95% BCa CI`: Bootstrap BCa 95% confidence interval
- `Significant`: Whether statistically significant

**Effect Size Interpretation**:
- |r_rb| < 0.1: Negligible
- 0.1 ≤ |r_rb| < 0.3: Small
- 0.3 ≤ |r_rb| < 0.5: Medium
- |r_rb| ≥ 0.5: Large

**Example Output**:
```
Policy              Baseline      Median Diff  Rank-Biserial r_rb  Effect Size  95% BCa CI           Significant
type_aware_decay    full_memory        0.0350              0.4500       Medium  [0.0100, 0.0600]              No
random_prune        full_memory       -0.0150             -0.2500        Small  N/A                           No
```

### 3. Performance Summary Table

**Purpose**: Summarize per-policy performance metrics across all sequences.

**Columns**:
- `Policy`: Policy name
- `N Sequences`: Number of sequences
- `N Seeds`: Number of seeds per sequence
- `CL-F1 (Mean ± SD)`: Continual learning F1-score
- `Resolved Rate (Mean ± SD)`: Task success rate
- `Tool Calls (Mean ± SD)`: Average tool calls per task
- `Wall Time (Mean ± SD)`: Average wall time per task (seconds)

**Sorting**: By CL-F1 descending (best policies first)

**Example Output**:
```
Policy              N Sequences  N Seeds  CL-F1 (Mean ± SD)    Resolved Rate (Mean ± SD)  Tool Calls (Mean ± SD)  Wall Time (Mean ± SD)
type_aware_decay              8        3  0.7700 ± 0.0450      0.7200 ± 0.0350            44.00 ± 4.65            275.0 ± 27.5
full_memory                   8        3  0.7350 ± 0.0550      0.6900 ± 0.0450            49.00 ± 4.90            295.0 ± 29.5
```

### 4. Cost Breakdown Table

**Purpose**: Analyze total costs and cost-efficiency per policy.

**Columns**:
- `Policy`: Policy name
- `Total Cost (Mean ± SD)`: Total API cost in USD
- `Total Tokens (Mean ± SD)`: Total token count
- `Cost per Task`: Average cost per task
- `CL-F1 per Dollar`: Cost-normalized performance metric

**Sorting**: By total cost ascending (cheapest policies first)

**Example Output**:
```
Policy              Total Cost (Mean ± SD)  Total Tokens (Mean ± SD)  Cost per Task  CL-F1 per Dollar
type_aware_decay    $77.50 ± $8.25          39000 ± 3900              $4.0789        0.0099
full_memory         $97.50 ± $9.50          49000 ± 4900              $5.1316        0.0075
```

## Integration with Analysis Pipeline

The result tables module integrates with the broader analysis pipeline:

```
Task Results (JSONL)
    ↓
aggregate_sequence_results()
    ↓
Sequence Aggregates (JSON)
    ↓
compute_all_contrasts_with_bootstrap()
    ↓
Wilcoxon Results (dict)
    ↓
generate_all_result_tables()
    ↓
CSV Tables + DataFrames
```

## Testing

The module includes comprehensive unit tests in `tests/test_result_tables.py`:

- `test_generate_statistical_test_table`: Verify statistical test table structure and content
- `test_generate_effect_size_table`: Verify effect size table with CI
- `test_generate_performance_summary_table`: Verify performance summary sorting and metrics
- `test_generate_cost_breakdown_table`: Verify cost calculations
- `test_generate_all_result_tables`: Verify end-to-end table generation
- `test_effect_size_interpretation`: Verify effect size magnitude classification
- `test_table_saves_to_file`: Verify CSV file output

Run tests:
```bash
pytest tests/test_result_tables.py -v
```

## Example Script

See `examples/generate_result_tables_example.py` for a complete working example.

## Design Decisions

### 1. Pandas DataFrames
Tables are returned as pandas DataFrames for flexibility:
- Easy to manipulate and filter
- Can be saved to multiple formats (CSV, Excel, LaTeX)
- Can be displayed in Jupyter notebooks
- Can be converted to other formats as needed

### 2. Formatted Strings
Numeric values are formatted as strings in the tables:
- Consistent decimal places for readability
- Mean ± SD format for summary statistics
- Confidence intervals in bracket notation
- Dollar signs for costs

### 3. Effect Size Interpretation
Automatic classification of effect sizes:
- Based on standard conventions (Cohen, 1988)
- Helps non-statisticians interpret results
- Consistent with THESIS_FINAL_v5.md guidelines

### 4. Sorting
Tables are sorted by the most relevant metric:
- Performance summary: by CL-F1 descending (best first)
- Cost breakdown: by total cost ascending (cheapest first)
- Statistical tests: by policy name (alphabetical)

## Frozen Invariants

Per THESIS_FINAL_v5.md §0.1, the following are enforced:

1. **N=8 sequence means**: Statistical tests use sequence-level aggregates
2. **Wilcoxon signed-rank**: Primary non-parametric test
3. **Holm correction**: Controls family-wise error rate
4. **Rank-biserial r_rb**: Effect size metric (NOT Cohen's d or Cliff's delta)
5. **5000 BCa bootstrap**: Confidence interval method
6. **5 pre-registered contrasts**: All pruning policies vs Full Memory

## References

- THESIS_FINAL_v5.md §15.2: Statistical Analysis
- THESIS_FINAL_v5.md §17: Pareto Analysis
- Requirements 20, 21, 27
- Design Document: Statistical Analysis section

## Future Enhancements

Potential extensions (NOT in current scope):

- LaTeX table generation for thesis
- Excel export with formatting
- Interactive HTML tables
- Automated table captions
- Multi-metric comparison tables
- Sequence-specific breakdown tables
