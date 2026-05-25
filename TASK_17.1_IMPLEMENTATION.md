# Task 17.1 Implementation: Failure Categorization

## Summary

Successfully implemented comprehensive failure analysis module for the memory pruning research system.

## Files Created

### 1. `src/analysis/failure_analysis.py`
Main implementation module containing:

- **FailureCategory enum**: 5 failure types (timeout, test_failure, syntax_error, tool_error, unknown)
- **FailureRecord dataclass**: Structured representation of task failures
- **categorize_failure()**: Categorizes failures based on task result fields
- **extract_failure_records()**: Extracts all failure records from runs directory
- **compute_failure_rates_by_category()**: Computes per-policy failure rates
- **identify_boundary_tasks()**: Identifies tasks where Full Memory fails but pruning succeeds
- **generate_failure_analysis_report()**: Generates comprehensive failure analysis report
- **print_failure_analysis_summary()**: Prints human-readable summary

### 2. `tests/test_failure_analysis.py`
Comprehensive unit tests covering:

- Failure categorization logic (8 tests)
- Failure record extraction (4 tests)
- Failure rate computation (3 tests)
- Boundary task identification (4 tests)
- Report generation (3 tests)

**Total: 22 tests, all passing**

### 3. `examples/failure_analysis_usage.py`
Usage examples demonstrating:

- How to categorize individual failures
- How to extract failure records from runs
- How to identify boundary tasks
- How to generate comprehensive reports

## Requirements Satisfied

Per **Requirement 28: Failure Analysis Protocol**:

✅ **Categorize task failures** into 5 types:
- `timeout`: Task exceeded step or time limits
- `test_failure`: Patch generated but failed eval_v3 tests
- `syntax_error`: Code contained syntax errors
- `tool_error`: Tool execution or environment errors
- `unknown`: Unclassified or unclear failure mode

✅ **Log both error message and stack trace** when available:
- `error_message` field extracted from task results
- `stack_trace` field supported (for future enhancement)

✅ **Compute per-policy failure rates by category**:
- `compute_failure_rates_by_category()` function
- Returns nested dict: `{policy: {category: rate}}`
- Includes total failure count per policy

✅ **Identify boundary tasks** (Full Memory fails, pruning succeeds):
- `identify_boundary_tasks()` function
- Critical for testing Hypothesis H5
- Returns list of tasks with Full Memory error category and successful policies

## Implementation Details

### Failure Categorization Logic

Priority order (most specific first):
1. **TIMEOUT**: `timeout=True`
2. **SYNTAX_ERROR**: `syntax_error=True`
3. **TEST_FAILURE**: `patch_generated=True` AND `patch_applied=True` (but `resolved=0`)
4. **TOOL_ERROR**: `patch_generated=False` OR `patch_applied=False`
5. **UNKNOWN**: All other failure modes

### Boundary Task Detection

A task is a "boundary task" if:
- Full Memory policy fails (`resolved=0`)
- At least one pruning policy succeeds (`resolved=1`)
- Pruning policies: `random_prune`, `recency_prune`, `type_aware_decay`, `cls_consolidation`

This is the **opposite** of H5's concern (pruning harming performance). These tasks show where Full Memory's unbounded accumulation actually harms performance.

### Data Flow

```
runs/
  └── run_id/
      └── task_results.jsonl  →  extract_failure_records()
                                          ↓
                                  FailureRecord objects
                                          ↓
                          ┌───────────────┴───────────────┐
                          ↓                               ↓
              compute_failure_rates()        identify_boundary_tasks()
                          ↓                               ↓
                  {policy: {category: rate}}    [boundary_task_dicts]
                          ↓                               ↓
                          └───────────────┬───────────────┘
                                          ↓
                          generate_failure_analysis_report()
                                          ↓
                              failure_report.json
```

## Testing Results

```bash
$ python -m pytest tests/test_failure_analysis.py -v
================ 22 passed in 4.48s ================
```

### Test Coverage

- **Failure categorization**: 71% line coverage
- All core functions tested with edge cases
- Empty directory handling
- Multiple runs and policies
- Boundary task detection

### Linting

```bash
$ python -m ruff check src/analysis/failure_analysis.py
All checks passed!

$ python -m ruff check tests/test_failure_analysis.py
All checks passed!
```

## Usage Example

```python
from pathlib import Path
from src.analysis.failure_analysis import (
    generate_failure_analysis_report,
    print_failure_analysis_summary,
)

# Generate comprehensive report
runs_dir = Path("runs")
output_path = Path("results/failure_analysis_report.json")

report = generate_failure_analysis_report(runs_dir, output_path)

# Print human-readable summary
print_failure_analysis_summary(report)
```

## Integration Points

### Input
- Reads from `runs/{run_id}/task_results.jsonl`
- Expects standard task result schema (per Requirement 18)

### Output
- Saves to `results/failure_analysis_report.json`
- Contains:
  - `failure_rates`: Per-policy failure rates by category
  - `boundary_tasks`: Tasks where Full Memory fails but pruning succeeds
  - `summary`: Overall statistics

### Dependencies
- `src.analysis.aggregate_results`: Uses same data loading pattern
- Standard library only (no external dependencies)

## Future Enhancements

1. **Stack trace logging**: Currently supported in schema but not yet populated by agent
2. **Temporal analysis**: Track failure rates over sequence progression
3. **Error message clustering**: Group similar errors for pattern detection
4. **Visualization**: Plot failure rates by category and policy

## Frozen Invariants Preserved

✅ **Requirement 28**: All acceptance criteria satisfied
✅ **Logging schema**: Compatible with existing task_results.jsonl format
✅ **Policy names**: Uses standard 6 policy names
✅ **Statistical unit**: Works with sequence-level and task-level data

## Notes

- The module is **read-only** — it analyzes existing task results without modifying them
- Boundary task detection is critical for H5 analysis (see THESIS_FINAL_v5.md §0.1)
- Failure categorization is deterministic and reproducible
- All functions handle empty directories gracefully

## Completion Status

✅ Task 17.1 complete
- Implementation: ✅
- Unit tests: ✅ (22/22 passing)
- Linting: ✅ (no issues)
- Documentation: ✅
- Examples: ✅
