"""Unit tests for configuration system.

Tests cover:
- Requirement 26: Configuration Management
  - Loading base configuration
  - Merging policy-specific overrides
  - Validation of required keys
  - Validation of positive value constraints
  - Configuration freezing after calibration
"""

import tempfile
from pathlib import Path

import pytest
import yaml

from src.config.loader import (
    ConfigFrozenError,
    ConfigLoader,
    ConfigValidationError,
    get_policy_config,
    load_config,
)


@pytest.fixture
def temp_config_dir():
    """Create temporary directory for test configuration files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir)
        (config_dir / "policies").mkdir()
        yield config_dir


@pytest.fixture
def valid_base_config():
    """Return a valid base configuration dictionary."""
    return {
        "experiment": {
            "name": "test_experiment",
            "benchmark": "swebench_cl",
        },
        "agent": {
            "type": "langgraph_coding_agent",
            "main_model": "gpt-5.4",
            "temperature": 0,
            "max_steps_per_task": 20,
            "max_tool_calls_per_task": 80,
            "max_test_runs_per_task": 5,
            "max_wall_time_minutes": 20,
        },
        "memory": {
            "backend": "sqlite_faiss",
            "top_k": 5,
            "max_context_tokens": 2000,
            "max_records": 100,
            "max_storage_tokens": 30000,
            "embedding_max_tokens": 7500,
        },
        "retrieval": {
            "scoring": "pure_cosine",
        },
        "policies": {
            "no_memory": {"enabled": True},
            "type_aware_decay": {
                "enabled": True,
                "max_records": 100,
                "type_params": {
                    "architectural": {"base": 1.0, "decay": 0.05},
                },
            },
        },
        "execution": {
            "docker_max_workers": 4,
        },
        "logging": {
            "save_raw_trajectory": True,
        },
        "evaluation": {
            "harness": "eval_v3",
            "bootstrap_iterations": 5000,
        },
        "statistical": {
            "primary_test": "wilcoxon_signed_rank",
        },
    }


def test_load_base_config(temp_config_dir, valid_base_config):
    """Test loading base configuration file."""
    # Write base config
    base_path = temp_config_dir / "base.yaml"
    with open(base_path, 'w') as f:
        yaml.dump(valid_base_config, f)

    # Load config
    loader = ConfigLoader(str(base_path))
    config = loader.load()

    assert config["experiment"]["name"] == "test_experiment"
    assert config["memory"]["top_k"] == 5
    assert config["agent"]["max_steps_per_task"] == 20


def test_validate_required_keys_success(temp_config_dir, valid_base_config):
    """Test that validation passes with all required keys present."""
    base_path = temp_config_dir / "base.yaml"
    with open(base_path, 'w') as f:
        yaml.dump(valid_base_config, f)

    loader = ConfigLoader(str(base_path))
    config = loader.load()  # Should not raise

    assert "experiment" in config
    assert "agent" in config
    assert "memory" in config


def test_validate_required_keys_missing(temp_config_dir, valid_base_config):
    """Test that validation fails when required keys are missing."""
    # Remove required key
    del valid_base_config["memory"]

    base_path = temp_config_dir / "base.yaml"
    with open(base_path, 'w') as f:
        yaml.dump(valid_base_config, f)

    loader = ConfigLoader(str(base_path))

    with pytest.raises(ConfigValidationError, match="Missing required configuration keys.*memory"):
        loader.load()


def test_validate_positive_values_success(temp_config_dir, valid_base_config):
    """Test that validation passes with positive values."""
    base_path = temp_config_dir / "base.yaml"
    with open(base_path, 'w') as f:
        yaml.dump(valid_base_config, f)

    loader = ConfigLoader(str(base_path))
    config = loader.load()  # Should not raise

    assert config["memory"]["max_context_tokens"] > 0
    assert config["memory"]["max_records"] > 0


def test_validate_positive_values_zero(temp_config_dir, valid_base_config):
    """Test that validation fails with zero values for critical parameters."""
    valid_base_config["memory"]["max_context_tokens"] = 0

    base_path = temp_config_dir / "base.yaml"
    with open(base_path, 'w') as f:
        yaml.dump(valid_base_config, f)

    loader = ConfigLoader(str(base_path))

    with pytest.raises(ConfigValidationError, match="max_context_tokens must be positive"):
        loader.load()


def test_validate_positive_values_negative(temp_config_dir, valid_base_config):
    """Test that validation fails with negative values for critical parameters."""
    valid_base_config["memory"]["max_records"] = -10

    base_path = temp_config_dir / "base.yaml"
    with open(base_path, 'w') as f:
        yaml.dump(valid_base_config, f)

    loader = ConfigLoader(str(base_path))

    with pytest.raises(ConfigValidationError, match="max_records must be positive"):
        loader.load()


def test_merge_policy_overrides(temp_config_dir, valid_base_config):
    """Test merging policy-specific overrides into base configuration."""
    # Write base config
    base_path = temp_config_dir / "base.yaml"
    with open(base_path, 'w') as f:
        yaml.dump(valid_base_config, f)

    # Write policy override
    policy_override = {
        "memory": {
            "top_k": 10,  # Override base value
        },
        "policies": {
            "type_aware_decay": {
                "max_records": 200,  # Override base value
            },
        },
    }
    policy_path = temp_config_dir / "policies" / "type_aware_decay.yaml"
    with open(policy_path, 'w') as f:
        yaml.dump(policy_override, f)

    # Load with policy override
    loader = ConfigLoader(str(base_path))
    config = loader.load("type_aware_decay")

    # Check overrides applied
    assert config["memory"]["top_k"] == 10
    assert config["policies"]["type_aware_decay"]["max_records"] == 200

    # Check base values preserved
    assert config["memory"]["max_context_tokens"] == 2000
    assert config["agent"]["max_steps_per_task"] == 20


def test_merge_preserves_nested_values(temp_config_dir, valid_base_config):
    """Test that merging preserves nested values not in override."""
    base_path = temp_config_dir / "base.yaml"
    with open(base_path, 'w') as f:
        yaml.dump(valid_base_config, f)

    # Override only one nested value
    policy_override = {
        "policies": {
            "type_aware_decay": {
                "type_params": {
                    "architectural": {"base": 2.0},  # Override only base, not decay
                },
            },
        },
    }
    policy_path = temp_config_dir / "policies" / "type_aware_decay.yaml"
    with open(policy_path, 'w') as f:
        yaml.dump(policy_override, f)

    loader = ConfigLoader(str(base_path))
    config = loader.load("type_aware_decay")

    # Check override applied
    assert config["policies"]["type_aware_decay"]["type_params"]["architectural"]["base"] == 2.0
    # Check original value preserved
    assert config["policies"]["type_aware_decay"]["type_params"]["architectural"]["decay"] == 0.05


def test_configuration_freezing(temp_config_dir, valid_base_config):
    """Test configuration freezing after calibration window."""
    base_path = temp_config_dir / "base.yaml"
    with open(base_path, 'w') as f:
        yaml.dump(valid_base_config, f)

    loader = ConfigLoader(str(base_path))
    loader.load()

    # Should be able to update before freezing
    loader.update_calibration_param(("memory", "top_k"), 10)
    assert loader.get("memory", "top_k") == 10

    # Freeze calibration parameters
    loader.freeze_calibration_params()

    # Should not be able to update after freezing
    with pytest.raises(ConfigFrozenError, match="calibration parameters are frozen"):
        loader.update_calibration_param(("memory", "top_k"), 15)


def test_update_calibration_param_validation(temp_config_dir, valid_base_config):
    """Test that only calibration parameters can be updated via update_calibration_param."""
    base_path = temp_config_dir / "base.yaml"
    with open(base_path, 'w') as f:
        yaml.dump(valid_base_config, f)

    loader = ConfigLoader(str(base_path))
    loader.load()

    # Should allow updating calibration parameters
    loader.update_calibration_param(("memory", "top_k"), 10)
    loader.update_calibration_param(("memory", "max_context_tokens"), 3000)

    # Should reject non-calibration parameters
    with pytest.raises(ConfigValidationError, match="not a calibration parameter"):
        loader.update_calibration_param(("agent", "max_steps_per_task"), 30)


def test_update_calibration_param_validates_positive(temp_config_dir, valid_base_config):
    """Test that calibration parameter updates are validated for positive values."""
    base_path = temp_config_dir / "base.yaml"
    with open(base_path, 'w') as f:
        yaml.dump(valid_base_config, f)

    loader = ConfigLoader(str(base_path))
    loader.load()

    # Should reject zero/negative values
    with pytest.raises(ConfigValidationError, match="must be positive"):
        loader.update_calibration_param(("memory", "top_k"), 0)

    with pytest.raises(ConfigValidationError, match="must be positive"):
        loader.update_calibration_param(("memory", "max_context_tokens"), -100)


def test_get_nested_value(temp_config_dir, valid_base_config):
    """Test getting nested configuration values."""
    base_path = temp_config_dir / "base.yaml"
    with open(base_path, 'w') as f:
        yaml.dump(valid_base_config, f)

    loader = ConfigLoader(str(base_path))
    loader.load()

    assert loader.get("memory", "top_k") == 5
    assert loader.get("agent", "max_steps_per_task") == 20
    assert loader.get("policies", "type_aware_decay", "max_records") == 100


def test_get_nested_value_default(temp_config_dir, valid_base_config):
    """Test getting nested configuration values with default."""
    base_path = temp_config_dir / "base.yaml"
    with open(base_path, 'w') as f:
        yaml.dump(valid_base_config, f)

    loader = ConfigLoader(str(base_path))
    loader.load()

    # Non-existent path should return default
    assert loader.get("nonexistent", "path", default=42) == 42
    assert loader.get("memory", "nonexistent", default="default") == "default"


def test_load_config_convenience_function(temp_config_dir, valid_base_config):
    """Test load_config convenience function."""
    base_path = temp_config_dir / "base.yaml"
    with open(base_path, 'w') as f:
        yaml.dump(valid_base_config, f)

    config = load_config(base_config_path=str(base_path))

    assert config["memory"]["top_k"] == 5
    assert config["agent"]["max_steps_per_task"] == 20


def test_get_policy_config_convenience_function(temp_config_dir, valid_base_config):
    """Test get_policy_config convenience function."""
    base_path = temp_config_dir / "base.yaml"
    with open(base_path, 'w') as f:
        yaml.dump(valid_base_config, f)

    policy_config = get_policy_config("type_aware_decay", base_config_path=str(base_path))

    assert policy_config["enabled"] is True
    assert policy_config["max_records"] == 100
    assert "type_params" in policy_config


def test_get_policy_config_not_found(temp_config_dir, valid_base_config):
    """Test get_policy_config raises error for non-existent policy."""
    base_path = temp_config_dir / "base.yaml"
    with open(base_path, 'w') as f:
        yaml.dump(valid_base_config, f)

    with pytest.raises(KeyError, match="Policy 'nonexistent' not found"):
        get_policy_config("nonexistent", base_config_path=str(base_path))


def test_config_immutability_via_to_dict(temp_config_dir, valid_base_config):
    """Test that to_dict returns a deep copy to prevent external modification."""
    base_path = temp_config_dir / "base.yaml"
    with open(base_path, 'w') as f:
        yaml.dump(valid_base_config, f)

    loader = ConfigLoader(str(base_path))
    loader.load()

    # Get config copy
    config_copy = loader.to_dict()

    # Modify copy
    config_copy["memory"]["top_k"] = 999

    # Original should be unchanged
    assert loader.get("memory", "top_k") == 5


def test_file_not_found_error(temp_config_dir):
    """Test that FileNotFoundError is raised for missing base config."""
    loader = ConfigLoader(str(temp_config_dir / "nonexistent.yaml"))

    with pytest.raises(FileNotFoundError, match="Base configuration not found"):
        loader.load()


def test_policy_override_file_optional(temp_config_dir, valid_base_config):
    """Test that policy override file is optional (no error if missing)."""
    base_path = temp_config_dir / "base.yaml"
    with open(base_path, 'w') as f:
        yaml.dump(valid_base_config, f)

    loader = ConfigLoader(str(base_path))
    # Should not raise even though policy file doesn't exist
    config = loader.load("nonexistent_policy")

    # Should have base config values
    assert config["memory"]["top_k"] == 5
