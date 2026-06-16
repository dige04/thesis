"""
Generalized Linear Mixed Model (GLMM) for task-level analysis.

This module implements Task 14.4: Task-level GLMM.

Per THESIS_FINAL_v5.md §15.3:
- Binomial GLMM with logit link
- Formula: task_success ~ condition + difficulty + position + (1|seq/seed) + (1|task_id)
- Crossed random effects for sequence/seed and task_id
- Exploratory analysis (sequence-level is primary)

Backend (advisor decision, 2026-06-16): the canonical crossed-effects fit is R
``lme4::glmer`` via :func:`fit_glmm_with_r` (Invariant #14). :func:`fit_glmm` is
a no-R ``statsmodels`` ``BinomialBayesMixedGLM`` fallback — APPROXIMATE
(variational inference), to be labelled as such in any report.
"""

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

try:
    # BinomialBayesMixedGLM is the only mixed binomial GLM statsmodels ships.
    # The original code imported ``statsmodels.formula.api.glmer``, which does
    # NOT exist — so STATSMODELS_AVAILABLE was always False and fit_glmm was dead.
    from statsmodels.genmod.bayes_mixed_glm import (  # noqa: F401
        BinomialBayesMixedGLM,
    )

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
    Fit a binomial/logit task-level mixed model — statsmodels FALLBACK path.

    The canonical Invariant #14 model (crossed random effects on seq_seed AND
    task_id) is fit with R ``lme4::glmer`` via :func:`fit_glmm_with_r`. This
    function is the no-R fallback: ``statsmodels`` ``BinomialBayesMixedGLM``
    (variational inference), which is APPROXIMATE and must be labelled as such in
    any report. It includes both variance components (seq_seed + task_id) to stay
    as close to Invariant #14 as statsmodels permits.

    Model: ``resolved ~ C(policy) + difficulty_numeric + position_normalized``
    with variance components ``(1|seq_seed)`` and — when
    ``include_task_random_effect`` — ``(1|task_id)``.

    Args:
        data: DataFrame from prepare_task_level_data().
        formula: Optional fixed-effects formula (Patsy syntax, NOT lme4 ``(1|x)``
            syntax). Defaults to the spec fixed-effects formula.
        include_task_random_effect: Include the ``(1|task_id)`` variance
            component (set False for the sensitivity check).

    Returns:
        Dict with: method, converged, formula, n_obs, n_groups, fixed_effects
        (term -> {coef, std_err}), random_effects (vc name -> posterior SD), and
        optionally note/error. Never raises.
    """
    if not STATSMODELS_AVAILABLE:
        return {
            "method": "none",
            "error": "statsmodels not available. Install with: pip install statsmodels",
            "formula": formula or "N/A",
            "converged": False,
            "fixed_effects": {},
            "random_effects": {},
        }

    data = data.copy()
    if "resolved" not in data.columns:
        return {
            "method": "none",
            "error": "no 'resolved' column in task-level data",
            "converged": False,
            "fixed_effects": {},
            "random_effects": {},
        }
    data["resolved"] = data["resolved"].astype(int)

    # Fixed-effects formula (Patsy). Random effects go through vc_formulas below.
    base_formula = (
        formula or "resolved ~ C(policy) + difficulty_numeric + position_normalized"
    )
    n_obs = int(len(data))
    n_groups = int(data["seq_seed"].nunique()) if "seq_seed" in data.columns else 0

    # A binomial model needs both outcome classes present.
    if data["resolved"].nunique() < 2:
        return {
            "method": "degenerate",
            "converged": False,
            "formula": base_formula,
            "n_obs": n_obs,
            "n_groups": n_groups,
            "note": "outcome has no variation (all resolved or all failed); no model fit",
            "fixed_effects": {},
            "random_effects": {},
        }

    # Variance components — seq_seed always; task_id when requested (Invariant #14).
    vc: dict[str, str] = {"seq_seed": "0 + C(seq_seed)"}
    if include_task_random_effect and "task_id" in data.columns:
        vc["task_id"] = "0 + C(task_id)"

    # --- primary fallback: statsmodels BinomialBayesMixedGLM (variational) -----
    try:
        from statsmodels.genmod.bayes_mixed_glm import BinomialBayesMixedGLM

        model = BinomialBayesMixedGLM.from_formula(
            base_formula, vc_formulas=vc, data=data
        )
        result = model.fit_vb()

        fixed_effects = {
            name: {
                "coef": float(result.fe_mean[i]),
                "std_err": float(result.fe_sd[i]),
            }
            for i, name in enumerate(result.model.exog_names)
        }
        random_effects: dict[str, float | None] = {}
        for i, name in enumerate(vc):
            try:
                random_effects[name] = float(np.exp(result.vcp_mean[i]))
            except Exception:
                random_effects[name] = None

        re_terms = " + ".join(f"(1 | {k})" for k in vc)
        return {
            "method": "BinomialBayesMixedGLM (variational; APPROXIMATE fallback — R lme4 is canonical)",
            "converged": True,
            "formula": f"{base_formula} + {re_terms}",
            "n_obs": n_obs,
            "n_groups": n_groups,
            "fixed_effects": fixed_effects,
            "random_effects": random_effects,
        }
    except Exception as primary_err:  # noqa: BLE001 — fall back, never crash
        # --- secondary fallback: cluster-robust logit (NOT a mixed model) -----
        try:
            import statsmodels.formula.api as smf

            res = smf.logit(base_formula, data=data).fit(
                disp=False,
                cov_type="cluster",
                cov_kwds={"groups": data["seq_seed"]},
            )
            fixed_effects = {
                name: {
                    "coef": float(res.params[name]),
                    "std_err": float(res.bse[name]),
                    "z": float(res.tvalues[name]),
                    "p_value": float(res.pvalues[name]),
                }
                for name in res.params.index
            }
            return {
                "method": "logit_cluster_robust (FALLBACK — not a mixed model)",
                "converged": True,
                "formula": f"{base_formula}  [cluster-robust SE on seq_seed]",
                "n_obs": n_obs,
                "n_groups": n_groups,
                "fixed_effects": fixed_effects,
                "random_effects": {},
                "note": (
                    "BinomialBayesMixedGLM failed "
                    f"({type(primary_err).__name__}: {primary_err}); fell back to "
                    "cluster-robust logit (exploratory only)."
                ),
            }
        except Exception as fallback_err:  # noqa: BLE001
            return {
                "method": "none",
                "converged": False,
                "formula": base_formula,
                "n_obs": n_obs,
                "n_groups": n_groups,
                "fixed_effects": {},
                "random_effects": {},
                "error": (
                    f"mixed GLM failed ({primary_err}); "
                    f"fallback logit failed ({fallback_err})"
                ),
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
