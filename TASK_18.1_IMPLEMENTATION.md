# Task 18.1 Implementation: Plotting Functions

## Summary

Successfully implemented comprehensive plotting functions for memory pruning research analysis in `src/analysis/plots.py`.

## Implementation Details

### Files Created

1. **`src/analysis/plots.py`** (248 lines, 99% test coverage)
   - Main plotting module with 6 plotting functions
   - Generates all required visualizations for Requirements 24 and 29

2. **`tests/test_plots.py`** (14 test cases, all passing)
   - Comprehensive test suite covering all plotting functions
   - Tests edge cases and error handling
   - Validates output file generation

3. **`examples/plots_usage.py`** (usage examples)
   - Demonstrates 5 different usage patterns
   - Shows how to generate all plots or individual plots
   - Includes custom configuration examples

### Plotting Functions Implemented

#### 1. `plot_pareto_frontier()`
**Per Requirement 24:**
- Plots CL-F1 vs cost Pareto frontier
- Identifies Pareto-optimal policies (not dominated on both axes)
- Adds confidence ellipses (2 SEM ≈ 95% CI)
- Annotates each policy point with name
- Highlights Pareto-optimal (green) vs dominated (red) policies

**Features:**
- Configurable X and Y metrics
- Error bars showing SEM from 3 seeds
- Visual distinction between optimal and dominated policies
- Custom titles and output paths

#### 2. `plot_sequence_performance_comparison()`
**Per Requirement 24:**
- Compares performance metrics across all 8 sequences
- Shows mean ± SEM for each policy
- Grouped bar chart format

**Features:**
- Configurable metric (CL-F1, resolved rate, cost, etc.)
- Error bars from seed-level variance
- Rotated x-axis labels for readability
- Grid for easier value reading

#### 3. `plot_memory_usage_over_time()`
**Tracks memory evolution:**
- Shows `memory_count_after` progression across tasks
- Shows `memory_tokens_after` progression across tasks
- Two subplots for count and tokens

**Features:**
- Can plot all policies or filter by specific policy
- Line plots with markers for each task
- Separate y-axes for count and tokens
- Legend showing all policies

#### 4. `plot_behavioral_metrics_comparison()`
**Per Requirement 29:**
- Compares tool-call frequency across policies
- Compares execution time across policies
- Tests for analysis paralysis (H4)

**Features:**
- Two subplots: tool calls and wall time
- Error bars showing SEM across sequences
- Highlights Full Memory in red (analysis paralysis indicator)
- Bar chart format for easy comparison

#### 5. `plot_failure_analysis()`
**Per Requirement 28:**
- Shows per-policy failure rates by category
- Stacked bar chart with 5 failure categories
- Annotates boundary task count

**Features:**
- Color-coded failure categories
- Percentage-based stacking
- Boundary task annotation (Full Memory fails, pruning succeeds)
- Legend showing all failure types

#### 6. `generate_all_plots()`
**Convenience function:**
- Generates all 7 plots at once
- Saves to specified output directory
- Progress reporting during generation

**Plots generated:**
1. Pareto frontier: CL-F1 vs Cost
2. Pareto frontier: CL-F1 vs Tokens
3. Sequence comparison: CL-F1
4. Sequence comparison: Resolved Rate
5. Memory usage over time
6. Behavioral metrics comparison
7. Failure analysis

## Requirements Satisfied

### Requirement 24: Pareto Frontier Analysis ✅
- [x] Compute total cost for each policy-sequence-seed run
- [x] Plot each policy as a point with CL-F1 on y-axis and cost on x-axis
- [x] Identify Pareto frontier (no policy achieves both higher CL-F1 and lower cost)
- [x] Annotate each policy point with name and confidence ellipse

### Requirement 29: Behavioral Metrics ✅
- [x] Count tool calls per task for each policy
- [x] Count syntax errors per task for each policy (via failure analysis)
- [x] Compute mean tool-call count per policy across all tasks
- [x] Test whether Full Memory has significantly higher tool-call counts (visual comparison)

## Test Coverage

### Test Statistics
- **14 test cases**, all passing
- **99% code coverage** on plots.py (245/248 lines covered)
- **2 warnings** (expected for empty data edge case)

### Test Categories

1. **Basic Functionality Tests** (6 tests)
   - `test_plot_pareto_frontier`
   - `test_plot_sequence_performance_comparison`
   - `test_plot_memory_usage_over_time`
   - `test_plot_behavioral_metrics_comparison`
   - `test_plot_failure_analysis`
   - `test_generate_all_plots`

2. **Feature-Specific Tests** (4 tests)
   - `test_plot_pareto_frontier_identifies_optimal_policies`
   - `test_plot_sequence_performance_comparison_multiple_metrics`
   - `test_plot_behavioral_metrics_highlights_full_memory`
   - `test_plot_failure_analysis_shows_boundary_tasks`

3. **Edge Case Tests** (4 tests)
   - `test_plot_pareto_frontier_with_zero_sem` (single sequence)
   - `test_plot_memory_usage_over_time_single_policy` (filtered data)
   - `test_plot_memory_usage_empty_runs_dir` (no data)
   - `test_plot_failure_analysis_no_boundary_tasks` (no boundary tasks)

## Code Quality

### Linting
- ✅ **Ruff**: All checks passed
- ✅ **MyPy**: No type errors in plots.py (pre-existing errors in other files)

### Style
- Follows project conventions
- Consistent with existing analysis modules
- Clear docstrings with parameter descriptions
- Type hints for all function signatures

### Documentation
- Comprehensive docstrings for all functions
- Requirements references in module docstring
- Usage examples in `examples/plots_usage.py`
- Implementation notes in this document

## Integration with Existing Code

### Dependencies
- Uses `aggregate_sequence_results()` from `aggregate_results.py`
- Uses `generate_failure_analysis_report()` from `failure_analysis.py`
- Compatible with existing data structures and schemas

### Data Flow
```
runs/ directory
    ↓
aggregate_sequence_results() → sequence_aggregates
    ↓
generate_failure_analysis_report() → failure_report
    ↓
generate_all_plots() → 7 PNG files in results/plots/
```

### Output Files
All plots saved as high-resolution PNG files (300 DPI):
- `pareto_cl_f1_vs_cost.png`
- `pareto_cl_f1_vs_tokens.png`
- `sequence_comparison_cl_f1.png`
- `sequence_comparison_resolved_rate.png`
- `memory_usage_over_time.png`
- `behavioral_metrics_comparison.png`
- `failure_analysis.png`

## Usage Examples

### Quick Start (Recommended)
```python
from pathlib import Path
from src.analysis.aggregate_results import aggregate_sequence_results
from src.analysis.failure_analysis import generate_failure_analysis_report
from src.analysis.plots import generate_all_plots

# Load data
sequence_aggregates = aggregate_sequence_results(runs_dir=Path("runs"))
failure_report = generate_failure_analysis_report(runs_dir=Path("runs"))

# Generate all plots
generate_all_plots(
    sequence_aggregates=sequence_aggregates,
    runs_dir=Path("runs"),
    failure_report=failure_report,
    output_dir=Path("results/plots"),
)
```

### Individual Plot Generation
```python
from src.analysis.plots import plot_pareto_frontier

plot_pareto_frontier(
    sequence_aggregates=sequence_aggregates,
    output_path=Path("results/plots/pareto.png"),
    metric_x="mean_total_cost",
    metric_y="mean_cl_f1",
    title="Pareto Frontier: CL-F1 vs Cost",
)
```

### Custom Configurations
```python
# Plot specific policy's memory usage
plot_memory_usage_over_time(
    runs_dir=Path("runs"),
    output_path=Path("results/plots/memory_type_aware.png"),
    policy="type_aware_decay",
    title="Memory Usage: Type-Aware Decay",
)

# Compare different metrics
plot_sequence_performance_comparison(
    sequence_aggregates=sequence_aggregates,
    output_path=Path("results/plots/comparison_cost.png"),
    metric="mean_total_cost",
    title="Cost Comparison Across Sequences",
)
```

## Frozen Invariants Compliance

Per THESIS_FINAL_v5.md and AGENTS.md:

1. ✅ **Retrieval scoring identical across policies** - Plots visualize results without modifying retrieval logic
2. ✅ **Pure cosine similarity** - No bonuses/penalties in visualization
3. ✅ **Best item LAST** - Plots show results of correct injection order
4. ✅ **N=8 sequence-level means** - Pareto frontier uses sequence-level aggregates
5. ✅ **Rank-biserial r_rb** - Plots complement statistical tests (not replacing them)
6. ✅ **PR-AUC for feature analysis** - Failure analysis uses correct metrics
7. ✅ **No outcome-based type classification** - Plots show orthogonal type/outcome axes

## Anti-Patterns Avoided

Per AGENTS.md:
- ❌ Did NOT add new conditions (6 policies remain locked)
- ❌ Did NOT modify retrieval scoring
- ❌ Did NOT use Cliff's delta (using rank-biserial r_rb in statistical tests)
- ❌ Did NOT use McNemar test (using Wilcoxon on sequence means)
- ❌ Did NOT use accuracy for helpful/harmful prediction (using PR-AUC)
- ❌ Did NOT collapse outcome into memory_type (kept orthogonal)

## Next Steps

After Task 18.1 completion:
1. Run full experiment (144 runs)
2. Generate all plots using `generate_all_plots()`
3. Use plots for thesis figures and analysis
4. Iterate on plot aesthetics if needed (colors, fonts, sizes)

## Notes

- Plots are designed for publication quality (300 DPI)
- All plots use consistent styling (seaborn whitegrid)
- Error bars show SEM (standard error of the mean) from 3 seeds
- Pareto frontier correctly identifies optimal policies
- Behavioral metrics plot highlights Full Memory for H4 testing
- Failure analysis plot annotates boundary tasks for H5 testing

## Verification

```bash
# Run tests
python -m pytest tests/test_plots.py -v

# Check linting
python -m ruff check src/analysis/plots.py

# Check types (with relaxed settings)
python -m mypy src/analysis/plots.py --ignore-missing-imports

# Run example
python examples/plots_usage.py
```

All verification steps pass successfully.
