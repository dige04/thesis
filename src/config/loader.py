"""Configuration loader with validation and freezing support.

This module implements the configuration system for the memory pruning research system.
It loads base configuration from base.yaml and merges policy-specific overrides.

Requirements:
- Requirement 26: Configuration Management
"""

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

try:
    from dotenv import load_dotenv as _load_dotenv
except Exception:  # pragma: no cover - dependency optional during setup
    _load_dotenv = None

from src.errors import ConfigFrozenError, ConfigValidationError


class ConfigLoader:
    """Loads and validates configuration with support for policy overrides and freezing.
    
    The configuration system supports:
    1. Loading base configuration from configs/base.yaml
    2. Merging policy-specific overrides from configs/policies/{policy_name}.yaml
    3. Validation of required keys and value constraints
    4. Configuration freezing after calibration window
    
    Attributes:
        config: The merged configuration dictionary
        is_frozen: Whether the configuration is frozen (immutable)
    """

    # Required top-level keys that must be present in base.yaml
    REQUIRED_KEYS = [
        "experiment",
        "agent",
        "memory",
        "retrieval",
        "policies",
        "execution",
        "logging",
        "evaluation",
        "statistical",
    ]

    # Parameters that must be positive (> 0)
    POSITIVE_PARAMS = [
        ("memory", "max_context_tokens"),
        ("memory", "max_records"),
        ("memory", "max_storage_tokens"),
        ("memory", "embedding_max_tokens"),
        ("memory", "top_k"),
        ("agent", "max_steps_per_task"),
        ("agent", "max_tool_calls_per_task"),
        ("agent", "max_test_runs_per_task"),
        ("agent", "max_wall_time_minutes"),
        ("execution", "docker_max_workers"),
        ("evaluation", "bootstrap_iterations"),
    ]

    # Parameters that are locked after calibration (Week 4)
    CALIBRATION_PARAMS = [
        ("memory", "top_k"),
        ("memory", "max_context_tokens"),
        ("policies", "type_aware_decay", "type_params"),
    ]

    def __init__(self, base_config_path: str = "configs/base.yaml"):
        """Initialize configuration loader.
        
        Args:
            base_config_path: Path to base configuration file
        """
        self.base_config_path = Path(base_config_path)
        self.config: dict[str, Any] = {}
        self.is_frozen = False
        self._calibration_frozen = False

    def load(self, policy_name: str | None = None) -> dict[str, Any]:
        """Load configuration with optional policy-specific overrides.
        
        Args:
            policy_name: Name of policy for loading policy-specific overrides
            
        Returns:
            Merged configuration dictionary
            
        Raises:
            ConfigValidationError: If validation fails
            FileNotFoundError: If configuration files not found
        """
        # Load .env first so provider/base_url/model env vars are available to
        # src/config/llm_factory.py and any os.environ reads downstream. Env
        # vars override the YAML model defaults (see AGENTS.md).
        if _load_dotenv is not None:
            _load_dotenv()

        # Load base configuration
        if not self.base_config_path.exists():
            raise FileNotFoundError(f"Base configuration not found: {self.base_config_path}")

        with open(self.base_config_path) as f:
            self.config = yaml.safe_load(f)

        # Validate base configuration
        self._validate_required_keys()
        self._validate_positive_values()

        # Load and merge policy-specific overrides if provided
        if policy_name:
            policy_config_path = self.base_config_path.parent / "policies" / f"{policy_name}.yaml"
            if policy_config_path.exists():
                with open(policy_config_path) as f:
                    policy_overrides = yaml.safe_load(f)
                # Only merge if file contains actual data (not just comments/empty)
                if policy_overrides:
                    self._merge_overrides(policy_overrides)
                    # Re-validate after merge
                    self._validate_positive_values()

        return deepcopy(self.config)

    def _validate_required_keys(self) -> None:
        """Validate that all required top-level keys are present.
        
        Raises:
            ConfigValidationError: If required keys are missing
        """
        missing_keys = [key for key in self.REQUIRED_KEYS if key not in self.config]
        if missing_keys:
            raise ConfigValidationError(
                f"Missing required configuration keys: {', '.join(missing_keys)}"
            )

    def _validate_positive_values(self) -> None:
        """Validate that critical parameters have positive values.
        
        Raises:
            ConfigValidationError: If parameters have zero or negative values
        """
        errors = []
        for path in self.POSITIVE_PARAMS:
            value = self._get_nested_value(path)
            if value is not None and (not isinstance(value, (int, float)) or value <= 0):
                param_name = ".".join(path)
                errors.append(f"{param_name} must be positive (got {value})")

        if errors:
            raise ConfigValidationError(
                "Configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
            )

    def _get_nested_value(self, path: tuple) -> Any:
        """Get value from nested dictionary using path tuple.
        
        Args:
            path: Tuple of keys representing path in nested dict
            
        Returns:
            Value at path, or None if path doesn't exist
        """
        current = self.config
        for key in path:
            if not isinstance(current, dict) or key not in current:
                return None
            current = current[key]
        return current

    def _set_nested_value(self, path: tuple, value: Any) -> None:
        """Set value in nested dictionary using path tuple.
        
        Args:
            path: Tuple of keys representing path in nested dict
            value: Value to set
        """
        current = self.config
        for key in path[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        current[path[-1]] = value

    def _merge_overrides(self, overrides: dict[str, Any]) -> None:
        """Merge policy-specific overrides into base configuration.
        
        Args:
            overrides: Dictionary of override values
        """
        self._deep_merge(self.config, overrides)

    def _deep_merge(self, base: dict[str, Any], override: dict[str, Any]) -> None:
        """Recursively merge override dictionary into base dictionary.
        
        Args:
            base: Base dictionary (modified in place)
            override: Override dictionary
        """
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value

    def freeze(self) -> None:
        """Freeze configuration to prevent further modifications.
        
        This should be called after the calibration window (Week 4) to lock
        all hyperparameters for the full 144-run experiment.
        """
        self.is_frozen = True

    def freeze_calibration_params(self) -> None:
        """Freeze calibration-specific parameters after Week 4.
        
        This locks top_k, max_context_tokens, and type_aware_decay parameters
        while allowing other configuration changes.
        """
        self._calibration_frozen = True

    def update_calibration_param(self, path: tuple, value: Any) -> None:
        """Update a calibration parameter (only allowed before freezing).
        
        Args:
            path: Tuple of keys representing parameter path
            value: New value for parameter
            
        Raises:
            ConfigFrozenError: If calibration parameters are frozen
            ConfigValidationError: If parameter is not a calibration parameter
        """
        if self._calibration_frozen:
            raise ConfigFrozenError(
                f"Cannot update {'.'.join(path)}: calibration parameters are frozen"
            )

        # Verify this is a calibration parameter
        if path not in self.CALIBRATION_PARAMS:
            raise ConfigValidationError(
                f"{'.'.join(path)} is not a calibration parameter. "
                f"Calibration parameters: {['.'.join(p) for p in self.CALIBRATION_PARAMS]}"
            )

        self._set_nested_value(path, value)
        self._validate_positive_values()

    def get(self, *path: str, default: Any = None) -> Any:
        """Get configuration value using dot-notation path.
        
        Args:
            *path: Path components (e.g., "memory", "top_k")
            default: Default value if path doesn't exist
            
        Returns:
            Configuration value or default
        """
        value = self._get_nested_value(path)
        return value if value is not None else default

    def to_dict(self) -> dict[str, Any]:
        """Return a deep copy of the configuration dictionary.
        
        Returns:
            Configuration dictionary
        """
        return deepcopy(self.config)


# Convenience functions for common use cases

def load_config(policy_name: str | None = None,
                base_config_path: str = "configs/base.yaml") -> dict[str, Any]:
    """Load configuration with optional policy overrides.
    
    Args:
        policy_name: Name of policy for loading policy-specific overrides
        base_config_path: Path to base configuration file
        
    Returns:
        Merged configuration dictionary
        
    Example:
        >>> config = load_config("type_aware_decay")
        >>> top_k = config["memory"]["top_k"]
    """
    loader = ConfigLoader(base_config_path)
    return loader.load(policy_name)


def get_policy_config(policy_name: str,
                      base_config_path: str = "configs/base.yaml") -> dict[str, Any]:
    """Get configuration for a specific policy.
    
    Args:
        policy_name: Name of policy
        base_config_path: Path to base configuration file
        
    Returns:
        Policy-specific configuration dictionary
        
    Raises:
        KeyError: If policy not found in configuration
        
    Example:
        >>> policy_config = get_policy_config("type_aware_decay")
        >>> max_records = policy_config["max_records"]
    """
    config = load_config(policy_name, base_config_path)

    if "policies" not in config or policy_name not in config["policies"]:
        raise KeyError(f"Policy '{policy_name}' not found in configuration")

    return config["policies"][policy_name]
