# Configuration System

This directory contains the configuration files for the memory pruning research system.

## Structure

```
configs/
├── base.yaml                    # Base configuration with all parameters
├── policies/                    # Policy-specific overrides
│   └── type_aware_decay.yaml   # Example policy override
└── README.md                    # This file
```

## Usage

### Loading Base Configuration

```python
from src.config import load_config

# Load base configuration
config = load_config()
top_k = config["memory"]["top_k"]  # 5
```

### Loading with Policy Overrides

```python
from src.config import load_config

# Load configuration with policy-specific overrides
config = load_config("type_aware_decay")
# Values from configs/policies/type_aware_decay.yaml override base.yaml
```

### Getting Policy-Specific Configuration

```python
from src.config import get_policy_config

# Get configuration for a specific policy
policy_config = get_policy_config("type_aware_decay")
max_records = policy_config["max_records"]
```

### Advanced Usage with ConfigLoader

```python
from src.config import ConfigLoader

# Create loader
loader = ConfigLoader("configs/base.yaml")
config = loader.load("type_aware_decay")

# Get nested values
top_k = loader.get("memory", "top_k")
max_steps = loader.get("agent", "max_steps_per_task")

# Update calibration parameters (before freezing)
loader.update_calibration_param(("memory", "top_k"), 10)
loader.update_calibration_param(("memory", "max_context_tokens"), 3000)

# Freeze calibration parameters after Week 4
loader.freeze_calibration_params()

# Attempting to update after freezing raises ConfigFrozenError
# loader.update_calibration_param(("memory", "top_k"), 15)  # Error!
```

## Configuration Validation

The configuration system validates:

1. **Required Keys**: All top-level sections must be present
   - `experiment`, `agent`, `memory`, `retrieval`, `policies`, `execution`, `logging`, `evaluation`, `statistical`

2. **Positive Values**: Critical parameters must be positive (> 0)
   - `memory.max_context_tokens`
   - `memory.max_records`
   - `memory.max_storage_tokens`
   - `memory.embedding_max_tokens`
   - `memory.top_k`
   - `agent.max_steps_per_task`
   - `agent.max_tool_calls_per_task`
   - `agent.max_test_runs_per_task`
   - `agent.max_wall_time_minutes`
   - `execution.docker_max_workers`
   - `evaluation.bootstrap_iterations`

## Calibration Parameters

The following parameters are locked after the calibration window (Week 4):

- `memory.top_k` - Number of memories to retrieve (confirmed in Spike Week)
- `memory.max_context_tokens` - Maximum tokens for retrieved memories (confirmed in Spike Week)
- `policies.type_aware_decay.type_params` - Type-specific decay parameters (confirmed in Week 4)

Use `update_calibration_param()` to modify these parameters during calibration, then call `freeze_calibration_params()` to lock them for the full 144-run experiment.

## Policy Override Files

Policy-specific override files in `configs/policies/` allow you to customize configuration per policy without modifying the base configuration.

### Creating a Policy Override

1. Create a YAML file named `{policy_name}.yaml` in `configs/policies/`
2. Include only the parameters you want to override
3. The override will be deep-merged with base configuration

Example (`configs/policies/custom_policy.yaml`):

```yaml
# Override memory parameters
memory:
  top_k: 10
  max_context_tokens: 3000

# Override policy-specific parameters
policies:
  custom_policy:
    max_records: 200
    custom_param: "value"
```

### Deep Merge Behavior

Overrides are deep-merged, preserving nested values not specified in the override:

```yaml
# base.yaml
policies:
  type_aware_decay:
    max_records: 100
    type_params:
      architectural: { base: 1.0, decay: 0.05 }
      api_change:    { base: 0.8, decay: 0.15 }

# policies/type_aware_decay.yaml (override)
policies:
  type_aware_decay:
    type_params:
      architectural: { base: 2.0 }  # Override only base, not decay

# Result after merge:
policies:
  type_aware_decay:
    max_records: 100                # Preserved from base
    type_params:
      architectural: { base: 2.0, decay: 0.05 }  # base overridden, decay preserved
      api_change:    { base: 0.8, decay: 0.15 }  # Preserved from base
```

## Frozen Decisions

The following configuration values are **frozen** per THESIS_FINAL_v5.md §0.1 and should not be modified without explicit documentation:

- `agent.temperature`: 0 (reproducibility)
- `agent.max_steps_per_task`: 20 (hard limit)
- `memory.embedding_max_tokens`: 7500 (prevent truncation)
- `memory.injection_order`: "best_last" (Lost-in-the-Middle mitigation)
- `retrieval.scoring`: "pure_cosine" (identical across all policies)
- `evaluation.bootstrap_iterations`: 5000
- `evaluation.bootstrap_method`: "BCa"
- `statistical.primary_test`: "wilcoxon_signed_rank"
- `statistical.primary_n`: 8

## Error Handling

### ConfigValidationError

Raised when configuration validation fails:
- Missing required keys
- Zero or negative values for critical parameters
- Invalid calibration parameter updates

### ConfigFrozenError

Raised when attempting to modify frozen configuration:
- Updating calibration parameters after `freeze_calibration_params()` is called

### FileNotFoundError

Raised when configuration files are not found:
- Base configuration file missing
- (Policy override files are optional and do not raise errors if missing)

## Requirements

This configuration system implements **Requirement 26: Configuration Management**:

1. ✅ Load configuration from base.yaml
2. ✅ Merge policy-specific overrides from configs/policies/{policy_name}.yaml
3. ✅ Validate required keys are present
4. ✅ Validate positive value constraints for critical parameters
5. ✅ Support configuration freezing after calibration window
6. ✅ Log full merged configuration at start of each run
