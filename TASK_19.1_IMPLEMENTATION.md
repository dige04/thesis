# Task 19.1 Implementation: Pilot Mode Support

## Overview

Implemented comprehensive pilot mode support for calibrating hyperparameters before the full 144-run experiment. This includes:

1. **Pilot mode configuration** in `configs/base.yaml`
2. **Retrieval quality metrics** (precision@k, recall@k, MRR, NDCG@k)
3. **Calibration parameter updates** for top_k, max_context_tokens, and Type-Aware Decay parameters
4. **Calibration locking** after Week 4 to prevent further changes

**Validates: Requirements 30**

## Implementation Details

### 1. Pilot Mode Configuration

Added pilot mode configuration to `configs/base.yaml`:

```yaml
experiment:
  pilot_mode:
    enabled: false                    # Set to true for pilot runs
    num_sequences: 2                  # 2 sequences for pilot (default)
    num_seeds: 1                      # 1 seed for pilot (uses first seed)
    log_retrieval_quality: true       # Log precision@k, recall@k metrics
    calibration_locked: false         # Lock after Week 4 calibration
```

### 2. Retrieval Quality Metrics

Created `src/metrics/retrieval_quality.py` with:

- **`compute_retrieval_quality()`**: Computes precision@k, recall@k, MRR, NDCG@k for a single task
- **`aggregate_retrieval_quality()`**: Aggregates metrics across multiple tasks
- **`RetrievalQualityMetrics`**: Dataclass for storing metrics

**Relevance Criteria:**
- Same repository (required)
- Same memory type (optional)
- Temporal proximity (optional)
- Success after retrieval (optional)

**Metrics Computed:**
- **Precision@k**: Proportion of retrieved memories that are relevant
- **Recall@k**: Proportion of relevant memories that are retrieved
- **MRR**: Mean Reciprocal Rank of first relevant item
- **NDCG@k**: Normalized Discounted Cumulative Gain at k

### 3. Sequence Runner Integration

Updated `src/benchmark/sequence_runner.py` to:

1. Check if pilot mode is enabled from config
2. Compute retrieval quality metrics during memory retrieval
3. Store metrics for each task
4. Save aggregated metrics to `runs/{run_id}/retrieval_quality_metrics.json`

**Output Format:**
```json
{
  "run_id": "django_type_aware_decay_seed1_pilot_abc123",
  "policy_name": "type_aware_decay",
  "aggregated_metrics": {
    "mean_precision_at_k": 0.72,
    "mean_recall_at_k": 0.65,
    "mean_mrr": 0.81,
    "mean_ndcg_at_k": 0.78,
    "std_precision_at_k": 0.12,
    "std_recall_at_k": 0.15,
    "std_mrr": 0.09,
    "std_ndcg_at_k": 0.11,
    "num_tasks": 15
  },
  "per_task_metrics": [...]
}
```

### 4. Calibration Utilities

Created `src/config/calibration.py` with:

- **`analyze_pilot_results()`**: Analyze retrieval quality metrics from pilot runs
- **`update_calibration_params()`**: Update top_k, max_context_tokens, or Type-Aware Decay parameters
- **`lock_calibration()`**: Lock calibration parameters after Week 4
- **`generate_calibration_report()`**: Generate JSON report with recommendations

**Recommendation Logic:**
- If recall < 0.5 and precision > 0.3: Increase top_k (more relevant items needed)
- If precision < 0.3 and recall > 0.5: Decrease top_k (too much noise)
- Otherwise: Keep current top_k (balanced)
- Token budget: ~400 tokens per memory item

### 5. Example Usage

Created `examples/pilot_mode_usage.py` demonstrating:

1. **Run pilot experiment**: 2 sequences × 6 policies × 1 seed = 12 runs
2. **Analyze results**: Compute aggregated metrics and recommendations
3. **Update parameters**: Apply recommended top_k and max_context_tokens
4. **Update Type-Aware Decay**: Adjust decay_d parameters after Week 4 pilot
5. **Lock calibration**: Prevent further changes for full experiment

**Complete Workflow:**
```python
# Step 1: Run pilot experiment (Spike Week)
runner = ExperimentRunner(config, curriculum_path)
summary = runner.run_pilot_experiment(num_sequences=2)

# Step 2: Analyze results
analysis = analyze_pilot_results("results/raw")
recommendations = analysis["recommendations"]

# Step 3: Update top_k and max_context_tokens
update_calibration_params(
    "configs/base.yaml",
    top_k=recommendations["top_k"],
    max_context_tokens=recommendations["max_context_tokens"]
)

# Step 4: (Week 4) Update Type-Aware Decay parameters
update_calibration_params(
    "configs/base.yaml",
    type_aware_decay_params={
        "architectural": {"base": 1.0, "decay": 0.05},
        "api_change": {"base": 0.8, "decay": 0.12},
        # ...
    }
)

# Step 5: Lock calibration
lock_calibration("configs/base.yaml")
```

## Testing

Created `tests/test_pilot_mode.py` with comprehensive tests:

### Test Coverage

1. **Pilot Mode Configuration**
   - ✅ Pilot mode config present in base.yaml
   - ✅ Default values correct (enabled=False, num_sequences=2, num_seeds=1)

2. **Retrieval Quality Metrics**
   - ✅ Basic retrieval quality computation
   - ✅ No relevant memories edge case
   - ✅ Aggregation across multiple tasks

3. **Calibration Parameter Updates**
   - ✅ Update top_k
   - ✅ Update max_context_tokens
   - ✅ Lock calibration prevents further updates

4. **Pilot Results Analysis**
   - ✅ Empty directory handling
   - ✅ Analysis with sample metrics
   - ✅ Recommendation generation

**Test Results:**
```
tests/test_pilot_mode.py::TestPilotModeConfiguration::test_pilot_mode_config_present PASSED
tests/test_pilot_mode.py::TestPilotModeConfiguration::test_pilot_mode_defaults PASSED
tests/test_pilot_mode.py::TestRetrievalQualityMetrics::test_compute_retrieval_quality_basic PASSED
tests/test_pilot_mode.py::TestRetrievalQualityMetrics::test_compute_retrieval_quality_no_relevant PASSED
tests/test_pilot_mode.py::TestRetrievalQualityMetrics::test_aggregate_retrieval_quality PASSED
tests/test_pilot_mode.py::TestCalibrationParameterUpdates::test_update_top_k PASSED
tests/test_pilot_mode.py::TestCalibrationParameterUpdates::test_update_max_context_tokens PASSED
tests/test_pilot_mode.py::TestCalibrationParameterUpdates::test_lock_calibration_prevents_updates PASSED
tests/test_pilot_mode.py::TestPilotResultsAnalysis::test_analyze_pilot_results_empty_dir PASSED
tests/test_pilot_mode.py::TestPilotResultsAnalysis::test_analyze_pilot_results_with_metrics PASSED

10 passed in 5.39s
```

## Files Created/Modified

### Created Files

1. **`src/metrics/retrieval_quality.py`** (275 lines)
   - Retrieval quality metrics computation
   - Precision@k, Recall@k, MRR, NDCG@k
   - Aggregation utilities

2. **`src/config/calibration.py`** (295 lines)
   - Pilot results analysis
   - Calibration parameter updates
   - Calibration locking
   - Report generation

3. **`examples/pilot_mode_usage.py`** (180 lines)
   - Complete pilot mode workflow examples
   - Individual function examples
   - Full calibration workflow

4. **`tests/test_pilot_mode.py`** (350 lines)
   - Comprehensive test suite
   - 10 tests covering all functionality

### Modified Files

1. **`configs/base.yaml`**
   - Added `experiment.pilot_mode` section
   - Configuration for pilot runs

2. **`src/benchmark/sequence_runner.py`**
   - Added pilot mode detection
   - Integrated retrieval quality metrics logging
   - Added `_save_retrieval_quality_metrics()` method

## Calibration Workflow

### Spike Week (Friday Gate)

1. **Run pilot experiment**: 2 sequences × 6 policies × 1 seed = 12 runs
2. **Analyze retrieval quality**: Compute precision@k, recall@k, MRR, NDCG@k
3. **Update top_k and max_context_tokens**: Based on recommendations
4. **Verify**: Re-run pilot if needed

### Week 4 (Type-Aware Decay Calibration)

1. **Run second pilot**: Focus on Type-Aware Decay policy
2. **Analyze memory importance scores**: Evaluate decay_d parameters per type
3. **Update Type-Aware Decay parameters**: Adjust base_value and decay_d per type
4. **Lock calibration**: Freeze all hyperparameters for full experiment

### After Week 4

- All calibration parameters are **LOCKED**
- No further changes allowed without re-running entire experiment
- Full 144-run experiment proceeds with frozen parameters

## Frozen Invariants Preserved

This implementation preserves all frozen invariants from THESIS_FINAL_v5.md §0.1:

- ✅ **Invariant #2**: 3 seeds for ALL 6 conditions (pilot uses 1 seed, full uses 3)
- ✅ **Invariant #5**: Pure cosine retrieval (identical across all policies)
- ✅ **Invariant #8**: Type-Aware Decay formula (parameters calibrated, formula unchanged)
- ✅ **Invariant #16**: Same-repo retrieval only (used in relevance criteria)

## Requirements Validated

**Requirement 30: Calibration Window Support**

1. ✅ System supports pilot mode with 2 sequences × 6 policies × 1 seed = 12 runs
2. ✅ System logs retrieval quality metrics (precision@k, recall@k) during pilot runs
3. ✅ System supports updating top_k and max_context_tokens after pilot analysis
4. ✅ System supports updating Type-Aware Decay decay_d parameters per type after Week 4 pilot
5. ✅ System locks all hyperparameters after calibration

## Usage Instructions

### Enable Pilot Mode

Edit `configs/base.yaml`:
```yaml
experiment:
  pilot_mode:
    enabled: true                     # Enable pilot mode
    log_retrieval_quality: true       # Log metrics
```

### Run Pilot Experiment

```python
from src.benchmark.experiment_runner import ExperimentRunner
from src.config.loader import load_config

config = load_config()
runner = ExperimentRunner(config, "data/SWE-Bench-CL-Curriculum.json")
summary = runner.run_pilot_experiment(num_sequences=2)
```

### Analyze Results

```python
from src.config.calibration import analyze_pilot_results

analysis = analyze_pilot_results("results/raw")
print(analysis["recommendations"])
```

### Update Parameters

```python
from src.config.calibration import update_calibration_params

update_calibration_params(
    "configs/base.yaml",
    top_k=10,
    max_context_tokens=4000
)
```

### Lock Calibration

```python
from src.config.calibration import lock_calibration

lock_calibration("configs/base.yaml")
```

## Next Steps

1. **Run smoke test** (Task 19.2): 3 tasks with No Memory policy
2. **Run pilot experiment**: 12 runs to calibrate top_k and max_context_tokens
3. **Analyze pilot results**: Generate calibration report
4. **Update parameters**: Apply recommendations
5. **Run Week 4 pilot**: Calibrate Type-Aware Decay parameters
6. **Lock calibration**: Freeze all hyperparameters
7. **Run full experiment**: 144 runs with frozen parameters

## Notes

- Pilot mode is **disabled by default** to prevent accidental pilot runs
- Retrieval quality metrics are only logged when `log_retrieval_quality: true`
- Calibration parameters can only be updated before `calibration_locked: true`
- After locking, attempting to update raises `ConfigFrozenError`
- All pilot run results are saved to `runs/{run_id}/retrieval_quality_metrics.json`
- Calibration reports are saved to `results/calibration_report.json`

## References

- **Requirements**: Requirement 30 (Calibration Window Support)
- **Design**: THESIS_FINAL_v5.md §30
- **Frozen Invariants**: THESIS_FINAL_v5.md §0.1 (Invariants #2, #5, #8, #16)
- **Configuration**: configs/base.yaml (experiment.pilot_mode section)
