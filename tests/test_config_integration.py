"""Integration tests for configuration system with actual config files.

Tests the configuration system against the real base.yaml file to ensure
it loads correctly and all frozen decisions are properly configured.
"""

import pytest
from src.config import load_config, get_policy_config, ConfigLoader


def test_load_actual_base_config():
    """Test loading the actual base.yaml configuration file."""
    config = load_config()
    
    # Verify top-level sections exist
    assert "experiment" in config
    assert "agent" in config
    assert "memory" in config
    assert "retrieval" in config
    assert "policies" in config
    assert "execution" in config
    assert "logging" in config
    assert "evaluation" in config
    assert "statistical" in config


def test_frozen_decisions_in_base_config():
    """Test that frozen decisions from THESIS_FINAL_v5.md §0.1 are correctly configured."""
    config = load_config()
    
    # Frozen decision: temperature = 0 for reproducibility
    assert config["agent"]["temperature"] == 0
    
    # Frozen decision: max_steps_per_task = 20 (hard limit)
    assert config["agent"]["max_steps_per_task"] == 20
    
    # Frozen decision: embedding_max_tokens = 7500 (prevent truncation)
    assert config["memory"]["embedding_max_tokens"] == 7500
    
    # Frozen decision: injection_order = "best_last" (Lost-in-the-Middle mitigation)
    assert config["memory"]["injection_order"] == "best_last"
    
    # Frozen decision: scoring = "pure_cosine" (identical across all policies)
    assert config["retrieval"]["scoring"] == "pure_cosine"
    
    # Frozen decision: bootstrap_iterations = 5000
    assert config["evaluation"]["bootstrap_iterations"] == 5000
    
    # Frozen decision: bootstrap_method = "BCa"
    assert config["evaluation"]["bootstrap_method"] == "BCa"
    
    # Frozen decision: primary_test = "wilcoxon_signed_rank"
    assert config["statistical"]["primary_test"] == "wilcoxon_signed_rank"
    
    # Frozen decision: primary_n = 8 (sequence-level means)
    assert config["statistical"]["primary_n"] == 8


def test_calibration_parameters_present():
    """Test that calibration parameters are present with default values."""
    config = load_config()
    
    # Calibration parameters (locked after Week 4)
    assert config["memory"]["top_k"] == 5
    assert config["memory"]["max_context_tokens"] == 2000
    
    # Type-Aware Decay parameters
    type_params = config["policies"]["type_aware_decay"]["type_params"]
    assert type_params["architectural"]["base"] == 1.0
    assert type_params["architectural"]["decay"] == 0.05
    assert type_params["api_change"]["base"] == 0.8
    assert type_params["api_change"]["decay"] == 0.15
    assert type_params["bug_fix"]["base"] == 0.6
    assert type_params["bug_fix"]["decay"] == 0.25
    assert type_params["test_update"]["base"] == 0.4
    assert type_params["test_update"]["decay"] == 0.35
    assert type_params["config"]["base"] == 0.3
    assert type_params["config"]["decay"] == 0.40


def test_all_six_policies_configured():
    """Test that all 6 policies are configured in base.yaml."""
    config = load_config()
    
    policies = config["policies"]
    
    # All 6 policies must be present
    assert "no_memory" in policies
    assert "full_memory" in policies
    assert "random_prune" in policies
    assert "recency_prune" in policies
    assert "type_aware_decay" in policies
    assert "cls_consolidation" in policies
    
    # All policies should be enabled
    assert policies["no_memory"]["enabled"] is True
    assert policies["full_memory"]["enabled"] is True
    assert policies["random_prune"]["enabled"] is True
    assert policies["recency_prune"]["enabled"] is True
    assert policies["type_aware_decay"]["enabled"] is True
    assert policies["cls_consolidation"]["enabled"] is True


def test_random_prune_three_seeds():
    """Test that Random Prune policy has 3 seeds configured."""
    config = load_config()
    
    seeds = config["policies"]["random_prune"]["seeds"]
    assert len(seeds) == 3
    assert seeds == [1, 2, 3]


def test_cls_consolidation_parameters():
    """Test that CLS Consolidation policy has correct parameters."""
    config = load_config()
    
    cls_config = config["policies"]["cls_consolidation"]
    
    # Fixed schedule: every 5 tasks
    assert cls_config["interval_tasks"] == 5
    
    # Minimum cluster size
    assert cls_config["min_cluster_size"] == 3
    
    # Maximum summary tokens
    assert cls_config["max_summary_tokens"] == 350
    
    # Old memory threshold
    assert cls_config["old_memory_threshold"] == 10
    
    # Fallback to Type-Aware Decay
    assert cls_config["fallback_prune"] == "type_aware_decay"


def test_positive_value_constraints():
    """Test that all critical parameters have positive values."""
    config = load_config()
    
    # Memory parameters
    assert config["memory"]["top_k"] > 0
    assert config["memory"]["max_context_tokens"] > 0
    assert config["memory"]["max_records"] > 0
    assert config["memory"]["max_storage_tokens"] > 0
    assert config["memory"]["embedding_max_tokens"] > 0
    
    # Agent parameters
    assert config["agent"]["max_steps_per_task"] > 0
    assert config["agent"]["max_tool_calls_per_task"] > 0
    assert config["agent"]["max_test_runs_per_task"] > 0
    assert config["agent"]["max_wall_time_minutes"] > 0
    
    # Execution parameters
    assert config["execution"]["docker_max_workers"] > 0
    
    # Evaluation parameters
    assert config["evaluation"]["bootstrap_iterations"] > 0


def test_statistical_planned_contrasts():
    """Test that 5 pre-registered contrasts are configured."""
    config = load_config()
    
    contrasts = config["statistical"]["planned_contrasts"]
    
    # Must have exactly 5 contrasts
    assert len(contrasts) == 5
    
    # All contrasts compare against full_memory
    expected_contrasts = [
        ["full_memory", "no_memory"],
        ["full_memory", "random_prune"],
        ["full_memory", "recency_prune"],
        ["full_memory", "type_aware_decay"],
        ["full_memory", "cls_consolidation"],
    ]
    
    assert contrasts == expected_contrasts


def test_get_policy_config_for_each_policy():
    """Test that get_policy_config works for all 6 policies."""
    policies = [
        "no_memory",
        "full_memory",
        "random_prune",
        "recency_prune",
        "type_aware_decay",
        "cls_consolidation",
    ]
    
    for policy_name in policies:
        policy_config = get_policy_config(policy_name)
        assert policy_config["enabled"] is True


def test_config_loader_with_actual_files():
    """Test ConfigLoader with actual configuration files."""
    loader = ConfigLoader("configs/base.yaml")
    config = loader.load()
    
    # Test get method
    assert loader.get("memory", "top_k") == 5
    assert loader.get("agent", "max_steps_per_task") == 20
    
    # Test nested get
    assert loader.get("policies", "type_aware_decay", "max_records") == 100
    
    # Test default value
    assert loader.get("nonexistent", "key", default=42) == 42


def test_calibration_param_update_workflow():
    """Test the calibration parameter update workflow."""
    loader = ConfigLoader("configs/base.yaml")
    loader.load()
    
    # Initial values
    assert loader.get("memory", "top_k") == 5
    assert loader.get("memory", "max_context_tokens") == 2000
    
    # Update during calibration (before freezing)
    loader.update_calibration_param(("memory", "top_k"), 10)
    loader.update_calibration_param(("memory", "max_context_tokens"), 3000)
    
    # Verify updates
    assert loader.get("memory", "top_k") == 10
    assert loader.get("memory", "max_context_tokens") == 3000
    
    # Freeze calibration parameters
    loader.freeze_calibration_params()
    
    # Verify frozen
    assert loader._calibration_frozen is True


def test_logging_configuration():
    """Test that logging configuration is properly set."""
    config = load_config()
    
    logging_config = config["logging"]
    
    # All logging flags should be True
    assert logging_config["save_raw_trajectory"] is True
    assert logging_config["save_patches"] is True
    assert logging_config["save_test_output"] is True
    assert logging_config["save_retrieved_memories"] is True
    assert logging_config["save_prompt_tokens"] is True
    assert logging_config["save_completion_tokens"] is True
    assert logging_config["save_memory_snapshots"] is True
    assert logging_config["snapshot_at_every_task_boundary"] is True


def test_experiment_configuration():
    """Test that experiment configuration is properly set."""
    config = load_config()
    
    exp_config = config["experiment"]
    
    assert exp_config["name"] == "memory_pruning_coding_agents"
    assert exp_config["benchmark"] == "swebench_cl"
    assert exp_config["sequence_mode"] == "chronological_by_repo"
    assert exp_config["same_repo_retrieval_only"] is True
    assert exp_config["master_seed"] == 42


def test_execution_configuration():
    """Test that execution configuration is properly set."""
    config = load_config()
    
    exec_config = config["execution"]
    
    assert exec_config["docker_max_workers"] == 4
    assert exec_config["vps_arch"] == "x86_64"
    assert exec_config["vps_ram_gb"] == 32
    assert exec_config["vps_disk_gb"] == 250
    assert exec_config["vps_cores"] == 8


def test_retrieval_configuration():
    """Test that retrieval configuration matches frozen decisions."""
    config = load_config()
    
    retrieval_config = config["retrieval"]
    
    # Pure cosine similarity (identical across all policies)
    assert retrieval_config["scoring"] == "pure_cosine"
    
    # Tie-break with most recent
    assert retrieval_config["tie_break"] == "most_recent"
    
    # Drop lowest similarity when over budget
    assert retrieval_config["overflow"] == "drop_lowest_similarity"
    
    # No item truncation (drop whole items)
    assert retrieval_config["item_truncation"] is False
