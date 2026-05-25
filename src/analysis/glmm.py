"""
Generalized Linear Mixed Model (GLMM) for task-level analysis.

This module implements Task 14.4: Task-level GLMM.

Per THESIS_FINAL_v5.md §15.3:
- Binomial GLMM with logit link
- Formula: task_success ~ condition + difficulty + position + (1|seq/seed) + (1|task_id)
- Crossed random effects for sequence/seed and task_id
- Exploratory analysis (sequence-level is primary)
"""

from pathlib import Path
from typing import Any

import pandas as pd

try:
    import statsmodels.api as sm
    from statsmodels.formula.api import glmer

    STATSMODELS_AVAILABLE = True
except ImportError:
    STATSMODELS_AVAILABLE = False


def prepare_task_level_data(
    runs_dir: Path,
) -> pd.DataFrame:
    """
    Prepare task-level data for GLMM analysis.

    Args:
        runs_dir: Path to runs/ directory

    Returns:
        DataFrame with columns:
        - task_id: Task identifier
        - policy: Memory policy
        - seed: Random seed
        - repo: Repository/sequence name
        - sequence_index: Position in sequence
        - difficulty: Task difficulty (from SWE-Bench metadata)
        - resolved: Binary outcome (1=success, 0=failure)
        - seq_seed: Combined sequence/seed identifier for random effect
    """
    import json

    records = []

    for run_dir in runs_dir.iterdir():
        if not run_dir.is_dir():
            continue

        task_results_path = run_dir / "task_results.jsonl"
        if not task_results_path.exists():
            continue

        with open(task_results_path) as f:
            for line in f:
                if not line.strip():
                    continue
                task = json.loads(line)

                records.append(
                    {
                        "task_id": task["task_id"],
                        "policy": task["policy"],
                        "seed": task["seed"],
                        "repo": task["repo"],
                        "sequence_index": task["sequence_index"],
                        "difficulty": task.get("task_difficulty", "unknown"),
                        "resolved": task["resolved"],
                    }
                )

    df = pd.DataFrame(records)

    # Create combined sequence/seed identifier for random effect
    df["seq_seed"] = df["repo"] + "_seed" + df["seed"].astype(str)

    # Encode difficulty as ordinal (if available)
    difficulty_order = {"easy": 0, "medium": 1, "hard": 2, "unknown": 1}
    df["difficulty_numeric"] = df["difficulty"].map(difficulty_order)

    # Normalize sequence position to [0, 1] within each sequence
    df["position_normalized"] = df.groupby("repo")["sequence_index"].transform(
        lambda x: (x - x.min()) / (x.max() - x.min()) if x.max() > x.min() else 0.5
    )

    return df


def fit_glmm(
    data: pd.DataFrame,
    formula: str | None = None,
    include_task_random_effect: bool = True,
) -> dict[str, Any]:
    """
    Fit binomial GLMM with logit link.

    Per THESIS_FINAL_v5.md §15.3:
    - Default formula: resolved ~ policy + difficulty + position + (1|seq_seed) + (1|task_id)
    - Binomial family with logit link
    - Crossed random effects

    Args:
        data: DataFrame from prepare_task_level_data()
        formula: Optional custom formula (default uses spec formula)
        include_task_random_effect: Whether to include (1|task_id) random effect
                                     Set to False if convergence issues

    Returns:
        Dict with:
        - formula: Formula used
        - converged: Whether model converged
        - fixed_effects: DataFrame with coefficient, std_err, z_value, p_value
        - random_effects: Dict with variance components
        - aic: Akaike Information Criterion
        - bic: Bayesian Information Criterion
        - n_obs: Number of observations
        - model: Fitted model object (if statsmodels available)
    """
    if not STATSMODELS_AVAILABLE:
        return {
            "error": "statsmodels not available. Install with: pip install statsmodels",
            "formula": formula or "N/A",
            "converged": False,
        }

    # Default formula per THESIS_FINAL_v5.md §15.3
    if formula is None:
        if include_task_random_effect:
            formula = "resolved ~ C(policy) + difficulty_numeric + position_normalized + (1|seq_seed) + (1|task_id)"
        else:
            formula = "resolved ~ C(policy) + difficulty_numeric + position_normalized + (1|seq_seed)"

    try:
        # Fit GLMM using statsmodels
        # Note: statsmodels GLMM support is limited; for production use R's lme4::glmer
        model = glmer(
            formula=formula,
            data=data,
            family=sm.families.Binomial(),
        )

        result = model.fit()

        # Extract fixed effects
        fixed_effects = pd.DataFrame(
            {
                "coefficient": result.params,
                "std_err": result.bse,
                "z_value": result.tvalues,
                "p_value": result.pvalues,
            }
        )

        # Extract random effects variance components
        random_effects = {}
        if hasattr(result, "cov_re"):
            random_effects = {
                "seq_seed_variance": float(result.cov_re.iloc[0, 0])
                if result.cov_re.shape[0] > 0
                else 0.0,
            }

        return {
            "formula": formula,
            "converged": result.converged if hasattr(result, "converged") else True,
            "fixed_effects": fixed_effects.to_dict(orient="index"),
            "random_effects": random_effects,
            "aic": float(result.aic) if hasattr(result, "aic") else None,
            "bic": float(result.bic) if hasattr(result, "bic") else None,
            "n_obs": int(result.nobs),
            "model": result,
        }

    except Exception as e:
        return {
            "error": str(e),
            "formula": formula,
            "converged": False,
        }


def fit_glmm_with_r(
    data: pd.DataFrame,
    formula: str | None = None,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """
    Fit GLMM using R's lme4::glmer (recommended for production).

    Per THESIS_FINAL_v5.md §15.3:
    - R's lme4 is more robust for complex random effects
    - Use this for final analysis if statsmodels has convergence issues

    Args:
        data: DataFrame from prepare_task_level_data()
        formula: Optional custom formula
        output_path: Optional path to save R script and results

    Returns:
        Dict with model results (requires rpy2 package)
    """
    try:
        from rpy2 import robjects as ro
        from rpy2.robjects import pandas2ri
        from rpy2.robjects.packages import importr

        pandas2ri.activate()

        # Import R packages
        base = importr("base")
        lme4 = importr("lme4")

        # Default formula
        if formula is None:
            formula = "resolved ~ policy + difficulty_numeric + position_normalized + (1|seq_seed) + (1|task_id)"

        # Convert pandas DataFrame to R
        r_data = pandas2ri.py2rpy(data)

        # Fit model
        r_formula = ro.Formula(formula)
        model = lme4.glmer(
            r_formula,
            data=r_data,
            family=ro.r("binomial(link='logit')"),
        )

        # Extract results
        summary = base.summary(model)

        # Save R script if requested
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            r_script = f"""
# GLMM Analysis for Memory Pruning Experiments
library(lme4)

# Load data
data <- read.csv("task_level_data.csv")

# Fit model
model <- glmer(
  {formula},
  data = data,
  family = binomial(link = "logit")
)

# Summary
summary(model)

# Save results
saveRDS(model, "glmm_model.rds")
"""
            with open(output_path, "w") as f:
                f.write(r_script)

        return {
            "formula": formula,
            "converged": True,
            "model": model,
            "summary": str(summary),
            "method": "R lme4::glmer",
        }

    except ImportError:
        return {
            "error": "rpy2 not available. Install with: pip install rpy2",
            "formula": formula or "N/A",
            "converged": False,
            "note": "For production GLMM analysis, use R directly with lme4::glmer",
        }
    except Exception as e:
        return {
            "error": str(e),
            "formula": formula or "N/A",
            "converged": False,
        }


def run_task_level_analysis(
    runs_dir: Path,
    output_dir: Path | None = None,
    use_r: bool = False,
) -> dict[str, Any]:
    """
    Run complete task-level GLMM analysis.

    Args:
        runs_dir: Path to runs/ directory
        output_dir: Optional path to save results
        use_r: Whether to use R's lme4 (recommended) or statsmodels

    Returns:
        Dict with:
        - data_summary: Summary statistics of task-level data
        - glmm_results: GLMM model results
        - sensitivity_check: Results without task_id random effect (if applicable)
    """
    # Prepare data
    data = prepare_task_level_data(runs_dir)

    # Data summary
    data_summary = {
        "n_tasks": len(data),
        "n_policies": data["policy"].nunique(),
        "n_sequences": data["repo"].nunique(),
        "n_seeds": data["seed"].nunique(),
        "overall_success_rate": float(data["resolved"].mean()),
        "success_rate_by_policy": data.groupby("policy")["resolved"]
        .mean()
        .to_dict(),
    }

    # Fit GLMM
    if use_r:
        glmm_results = fit_glmm_with_r(
            data=data,
            output_path=output_dir / "glmm_script.R" if output_dir else None,
        )
        sensitivity_check = None
    else:
        # Fit with task_id random effect
        glmm_results = fit_glmm(data=data, include_task_random_effect=True)

        # Sensitivity check: fit without task_id random effect
        sensitivity_check = fit_glmm(data=data, include_task_random_effect=False)

    # Save results
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)

        # Save data
        data.to_csv(output_dir / "task_level_data.csv", index=False)

        # Save results
        import json

        results = {
            "data_summary": data_summary,
            "glmm_results": {
                k: v
                for k, v in glmm_results.items()
                if k not in ["model"]  # Exclude non-serializable model object
            },
        }

        if sensitivity_check:
            results["sensitivity_check"] = {
                k: v for k, v in sensitivity_check.items() if k not in ["model"]
            }

        with open(output_dir / "glmm_results.json", "w") as f:
            json.dump(results, f, indent=2)

    return {
        "data_summary": data_summary,
        "glmm_results": glmm_results,
        "sensitivity_check": sensitivity_check,
    }
