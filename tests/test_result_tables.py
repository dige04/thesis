"""
Unit tests for result tables generation.

Tests Task 18.2: Implement result tables.
"""

import tempfile
from pathlib import Path

import pandas as pd
import pytest

from src.analysis.result_tables import (
    generate_all_result_tables,
    generate_cost_breakdown_table,
    generate_effect_size_table,
    generate_performance_summary_table,
    generate_statistical_test_table,
)


@pytest.fixture
def mock_sequence_aggregates():
    """Mock sequence aggregates for testing."""
    return {
        "full_memory": {
            "django": {
                "mean_cl_f1": 0.75,
                "std_cl_f1": 0.05,
                "mean_resolved_rate": 0.70,
                "std_resolved_rate": 0.04,
                "mean_total_cost": 100.0,
                "std_total_cost": 10.0,
                "mean_total_tokens": 50000,
                "std_total_tokens": 5000,
                "mean_tool_calls": 50.0,
                "std_tool_calls": 5.0,
                "mean_wall_time": 300.0,
                "std_wall_time": 30.0,
                "n_seeds": 3,
                "n_tasks": 20,
            },
            "flask": {
                "mean_cl_f1": 0.72,
                "std_cl_f1": 0.06,
                "mean_resolved_rate": 0.68,
                "std_resolved_rate": 0.05,
                "mean_total_cost": 95.0,
                "std_total_cost": 9.0,
                "mean_total_tokens": 48000,
                "std_total_tokens": 4800,
                "mean_tool_calls": 48.0,
                "std_tool_calls": 4.8,
                "mean_wall_time": 290.0,
                "std_wall_time": 29.0,
                "n_seeds": 3,
                "n_tasks": 18,
            },
        },
        "type_aware_decay": {
            "django": {
                "mean_cl_f1": 0.78,
                "std_cl_f1": 0.04,
                "mean_resolved_rate": 0.73,
                "std_resolved_rate": 0.03,
                "mean_total_cost": 80.0,
                "std_total_cost": 8.0,
                "mean_total_tokens": 40000,
                "std_total_tokens": 4000,
                "mean_tool_calls": 45.0,
                "std_tool_calls": 4.5,
                "mean_wall_time": 280.0,
                "std_wall_time": 28.0,
                "n_seeds": 3,
                "n_tasks": 20,
            },
            "flask": {
                "mean_cl_f1": 0.76,
                "std_cl_f1": 0.05,
                "mean_resolved_rate": 0.71,
                "std_resolved_rate": 0.04,
                "mean_total_cost": 75.0,
                "std_total_cost": 7.5,
                "mean_total_tokens": 38000,
                "std_total_tokens": 3800,
                "mean_tool_calls": 43.0,
                "std_tool_calls": 4.3,
                "mean_wall_time": 270.0,
                "std_wall_time": 27.0,
                "n_seeds": 3,
                "n_tasks": 18,
            },
        },
    }


@pytest.fixture
def mock_wilcoxon_results():
    """Mock Wilcoxon results for testing."""
    return {
        "metric": "mean_cl_f1",
        "baseline_policy": "full_memory",
        "n_contrasts": 2,
        "contrasts": [
            {
                "policy": "type_aware_decay",
                "baseline": "full_memory",
                "n": 2,
                "sequences": ["django", "flask"],
                "median_diff": 0.035,
                "rank_biserial": 0.45,
                "statistic": 3.0,
                "p_value": 0.025,
                "holm_p_value": 0.050,
                "significant": False,
                "bootstrap_ci": {
                    "median_diff": 0.035,
                    "ci_lower": 0.010,
                    "ci_upper": 0.060,
                    "bias_correction": 0.05,
                    "acceleration": 0.01,
                    "n_iterations": 5000,
                    "alpha": 0.05,
                },
            },
            {
                "policy": "random_prune",
                "baseline": "full_memory",
                "n": 2,
                "sequences": ["django", "flask"],
                "median_diff": -0.015,
                "rank_biserial": -0.25,
                "statistic": 1.0,
                "p_value": 0.180,
                "holm_p_value": 0.180,
                "significant": False,
            },
        ],
    }


def test_generate_statistical_test_table(mock_wilcoxon_results):
    """Test statistical test table generation."""
    df = generate_statistical_test_table(mock_wilcoxon_results)

    # Check structure
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2  # 2 contrasts

    # Check columns
    expected_columns = [
        "Policy",
        "Baseline",
        "N",
        "Statistic",
        "p-value",
        "Holm p-value",
        "Significant",
    ]
    assert list(df.columns) == expected_columns

    # Check content
    assert df.iloc[0]["Policy"] == "type_aware_decay"
    assert df.iloc[0]["Baseline"] == "full_memory"
    assert df.iloc[0]["N"] == 2
    assert df.iloc[0]["Significant"] == "No"

    assert df.iloc[1]["Policy"] == "random_prune"
    assert df.iloc[1]["Significant"] == "No"


def test_generate_effect_size_table(mock_wilcoxon_results):
    """Test effect size table generation."""
    df = generate_effect_size_table(mock_wilcoxon_results)

    # Check structure
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2

    # Check columns
    expected_columns = [
        "Policy",
        "Baseline",
        "Median Diff",
        "Rank-Biserial r_rb",
        "Effect Size",
        "95% BCa CI",
        "Significant",
    ]
    assert list(df.columns) == expected_columns

    # Check content
    assert df.iloc[0]["Policy"] == "type_aware_decay"
    assert df.iloc[0]["Effect Size"] == "Medium"  # |0.45| is medium
    assert "[" in df.iloc[0]["95% BCa CI"]  # Has CI

    assert df.iloc[1]["Policy"] == "random_prune"
    assert df.iloc[1]["Effect Size"] == "Small"  # |0.25| is small
    assert df.iloc[1]["95% BCa CI"] == "N/A"  # No bootstrap CI


def test_generate_performance_summary_table(mock_sequence_aggregates):
    """Test performance summary table generation."""
    df = generate_performance_summary_table(mock_sequence_aggregates)

    # Check structure
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2  # 2 policies

    # Check columns
    expected_columns = [
        "Policy",
        "N Sequences",
        "N Seeds",
        "CL-F1 (Mean ± SD)",
        "Resolved Rate (Mean ± SD)",
        "Tool Calls (Mean ± SD)",
        "Wall Time (Mean ± SD)",
    ]
    assert list(df.columns) == expected_columns

    # Check content
    assert df.iloc[0]["N Sequences"] == 2
    assert df.iloc[0]["N Seeds"] == 3

    # Check sorting (by CL-F1 descending)
    # type_aware_decay has higher CL-F1 (0.77) than full_memory (0.735)
    assert df.iloc[0]["Policy"] == "type_aware_decay"
    assert df.iloc[1]["Policy"] == "full_memory"


def test_generate_cost_breakdown_table(mock_sequence_aggregates):
    """Test cost breakdown table generation."""
    df = generate_cost_breakdown_table(mock_sequence_aggregates)

    # Check structure
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2

    # Check columns
    expected_columns = [
        "Policy",
        "Total Cost (Mean ± SD)",
        "Total Tokens (Mean ± SD)",
        "Cost per Task",
        "CL-F1 per Dollar",
    ]
    assert list(df.columns) == expected_columns

    # Check sorting (by cost ascending)
    # type_aware_decay has lower cost (77.5) than full_memory (97.5)
    assert df.iloc[0]["Policy"] == "type_aware_decay"
    assert df.iloc[1]["Policy"] == "full_memory"

    # Check cost per task calculation
    # type_aware_decay: mean_cost=77.5, mean_n_tasks=19 → 77.5/19 ≈ 4.08
    cost_per_task_str = df.iloc[0]["Cost per Task"]
    cost_per_task = float(cost_per_task_str.replace("$", ""))
    assert 4.0 < cost_per_task < 4.2

    # Check CL-F1 per dollar calculation
    # type_aware_decay: mean_cl_f1=0.77, mean_cost=77.5 → 0.77/77.5 ≈ 0.0099
    cl_f1_per_dollar_str = df.iloc[0]["CL-F1 per Dollar"]
    cl_f1_per_dollar = float(cl_f1_per_dollar_str)
    assert 0.009 < cl_f1_per_dollar < 0.011


def test_generate_all_result_tables(mock_sequence_aggregates, mock_wilcoxon_results):
    """Test generation of all result tables."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "tables"

        tables = generate_all_result_tables(
            sequence_aggregates=mock_sequence_aggregates,
            wilcoxon_results=mock_wilcoxon_results,
            output_dir=output_dir,
        )

        # Check all tables generated
        assert "statistical_tests" in tables
        assert "effect_sizes" in tables
        assert "performance_summary" in tables
        assert "cost_breakdown" in tables

        # Check all files saved
        assert (output_dir / "statistical_tests.csv").exists()
        assert (output_dir / "effect_sizes.csv").exists()
        assert (output_dir / "performance_summary.csv").exists()
        assert (output_dir / "cost_breakdown.csv").exists()

        # Check tables are DataFrames
        for table in tables.values():
            assert isinstance(table, pd.DataFrame)


def test_effect_size_interpretation():
    """Test effect size magnitude interpretation."""
    # Create mock results with different effect sizes
    mock_results = {
        "metric": "mean_cl_f1",
        "baseline_policy": "full_memory",
        "n_contrasts": 4,
        "contrasts": [
            {
                "policy": "negligible",
                "baseline": "full_memory",
                "n": 8,
                "sequences": [],
                "median_diff": 0.01,
                "rank_biserial": 0.05,  # Negligible
                "statistic": 1.0,
                "p_value": 0.5,
                "holm_p_value": 0.5,
                "significant": False,
            },
            {
                "policy": "small",
                "baseline": "full_memory",
                "n": 8,
                "sequences": [],
                "median_diff": 0.02,
                "rank_biserial": 0.15,  # Small
                "statistic": 2.0,
                "p_value": 0.3,
                "holm_p_value": 0.3,
                "significant": False,
            },
            {
                "policy": "medium",
                "baseline": "full_memory",
                "n": 8,
                "sequences": [],
                "median_diff": 0.04,
                "rank_biserial": 0.35,  # Medium
                "statistic": 3.0,
                "p_value": 0.1,
                "holm_p_value": 0.1,
                "significant": False,
            },
            {
                "policy": "large",
                "baseline": "full_memory",
                "n": 8,
                "sequences": [],
                "median_diff": 0.08,
                "rank_biserial": 0.65,  # Large
                "statistic": 4.0,
                "p_value": 0.01,
                "holm_p_value": 0.01,
                "significant": True,
            },
        ],
    }

    df = generate_effect_size_table(mock_results)

    # Check interpretations
    assert df.iloc[0]["Effect Size"] == "Negligible"
    assert df.iloc[1]["Effect Size"] == "Small"
    assert df.iloc[2]["Effect Size"] == "Medium"
    assert df.iloc[3]["Effect Size"] == "Large"


def test_table_saves_to_file():
    """Test that tables are correctly saved to CSV files."""
    mock_results = {
        "metric": "mean_cl_f1",
        "baseline_policy": "full_memory",
        "n_contrasts": 1,
        "contrasts": [
            {
                "policy": "type_aware_decay",
                "baseline": "full_memory",
                "n": 8,
                "sequences": [],
                "median_diff": 0.03,
                "rank_biserial": 0.4,
                "statistic": 3.0,
                "p_value": 0.02,
                "holm_p_value": 0.02,
                "significant": True,
            }
        ],
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "test_table.csv"

        df = generate_statistical_test_table(mock_results, output_path=output_path)

        # Check file exists
        assert output_path.exists()

        # Check file can be read back
        df_loaded = pd.read_csv(output_path)
        assert len(df_loaded) == len(df)
        assert list(df_loaded.columns) == list(df.columns)
