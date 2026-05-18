"""Example usage of the configuration system.

This script demonstrates how to use the configuration loader for the
memory pruning research system.
"""

from src.config import load_config, get_policy_config, ConfigLoader


def example_basic_usage():
    """Example: Basic configuration loading."""
    print("=" * 60)
    print("Example 1: Basic Configuration Loading")
    print("=" * 60)
    
    # Load base configuration
    config = load_config()
    
    print(f"Experiment name: {config['experiment']['name']}")
    print(f"Benchmark: {config['experiment']['benchmark']}")
    print(f"Agent model: {config['agent']['main_model']}")
    print(f"Temperature: {config['agent']['temperature']}")
    print(f"Max steps per task: {config['agent']['max_steps_per_task']}")
    print(f"Memory top_k: {config['memory']['top_k']}")
    print(f"Max context tokens: {config['memory']['max_context_tokens']}")
    print()


def example_policy_specific():
    """Example: Loading policy-specific configuration."""
    print("=" * 60)
    print("Example 2: Policy-Specific Configuration")
    print("=" * 60)
    
    # Get configuration for Type-Aware Decay policy
    policy_config = get_policy_config("type_aware_decay")
    
    print(f"Policy enabled: {policy_config['enabled']}")
    print(f"Max records: {policy_config['max_records']}")
    print(f"Frequency exponent: {policy_config['frequency_exponent']}")
    print("\nType parameters:")
    for type_name, params in policy_config['type_params'].items():
        print(f"  {type_name:15s}: base={params['base']:.1f}, decay={params['decay']:.2f}")
    print()


def example_all_policies():
    """Example: Iterate through all policies."""
    print("=" * 60)
    print("Example 3: All Policies Configuration")
    print("=" * 60)
    
    config = load_config()
    policies = config['policies']
    
    print(f"Total policies: {len(policies)}")
    print("\nPolicy details:")
    for policy_name, policy_config in policies.items():
        enabled = policy_config.get('enabled', False)
        max_records = policy_config.get('max_records', 'N/A')
        print(f"  {policy_name:20s}: enabled={enabled}, max_records={max_records}")
    print()


def example_config_loader():
    """Example: Using ConfigLoader for advanced operations."""
    print("=" * 60)
    print("Example 4: Advanced ConfigLoader Usage")
    print("=" * 60)
    
    # Create loader
    loader = ConfigLoader("configs/base.yaml")
    loader.load()
    
    # Get nested values
    top_k = loader.get("memory", "top_k")
    max_steps = loader.get("agent", "max_steps_per_task")
    
    print(f"Memory top_k: {top_k}")
    print(f"Max steps per task: {max_steps}")
    
    # Get with default value
    custom_value = loader.get("custom", "nonexistent", default=42)
    print(f"Custom value (with default): {custom_value}")
    print()


def example_calibration_workflow():
    """Example: Calibration parameter update workflow."""
    print("=" * 60)
    print("Example 5: Calibration Parameter Update Workflow")
    print("=" * 60)
    
    # Create loader
    loader = ConfigLoader("configs/base.yaml")
    loader.load()
    
    # Initial values
    print("Initial calibration parameters:")
    print(f"  top_k: {loader.get('memory', 'top_k')}")
    print(f"  max_context_tokens: {loader.get('memory', 'max_context_tokens')}")
    
    # Simulate calibration (e.g., after Spike Week)
    print("\nUpdating calibration parameters after Spike Week...")
    loader.update_calibration_param(("memory", "top_k"), 10)
    loader.update_calibration_param(("memory", "max_context_tokens"), 3000)
    
    print("Updated calibration parameters:")
    print(f"  top_k: {loader.get('memory', 'top_k')}")
    print(f"  max_context_tokens: {loader.get('memory', 'max_context_tokens')}")
    
    # Freeze calibration parameters
    print("\nFreezing calibration parameters after Week 4...")
    loader.freeze_calibration_params()
    print(f"Calibration frozen: {loader._calibration_frozen}")
    
    # Attempting to update after freezing would raise ConfigFrozenError
    print("\nAttempting to update after freezing would raise ConfigFrozenError")
    print("(Not executing to avoid error)")
    print()


def example_frozen_decisions():
    """Example: Verify frozen decisions from THESIS_FINAL_v5.md."""
    print("=" * 60)
    print("Example 6: Frozen Decisions Verification")
    print("=" * 60)
    
    config = load_config()
    
    print("Frozen decisions from THESIS_FINAL_v5.md §0.1:")
    print(f"  Temperature: {config['agent']['temperature']} (must be 0)")
    print(f"  Max steps per task: {config['agent']['max_steps_per_task']} (must be 20)")
    print(f"  Embedding max tokens: {config['memory']['embedding_max_tokens']} (must be 7500)")
    print(f"  Injection order: {config['memory']['injection_order']} (must be 'best_last')")
    print(f"  Retrieval scoring: {config['retrieval']['scoring']} (must be 'pure_cosine')")
    print(f"  Bootstrap iterations: {config['evaluation']['bootstrap_iterations']} (must be 5000)")
    print(f"  Bootstrap method: {config['evaluation']['bootstrap_method']} (must be 'BCa')")
    print(f"  Primary test: {config['statistical']['primary_test']} (must be 'wilcoxon_signed_rank')")
    print(f"  Primary N: {config['statistical']['primary_n']} (must be 8)")
    print()


def example_statistical_contrasts():
    """Example: View pre-registered statistical contrasts."""
    print("=" * 60)
    print("Example 7: Pre-Registered Statistical Contrasts")
    print("=" * 60)
    
    config = load_config()
    contrasts = config['statistical']['planned_contrasts']
    
    print(f"Total contrasts: {len(contrasts)}")
    print("\nPre-registered contrasts (with Holm correction):")
    for i, contrast in enumerate(contrasts, 1):
        print(f"  {i}. {contrast[0]} vs {contrast[1]}")
    print()


def main():
    """Run all examples."""
    print("\n" + "=" * 60)
    print("Configuration System Usage Examples")
    print("=" * 60 + "\n")
    
    example_basic_usage()
    example_policy_specific()
    example_all_policies()
    example_config_loader()
    example_calibration_workflow()
    example_frozen_decisions()
    example_statistical_contrasts()
    
    print("=" * 60)
    print("All examples completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()
