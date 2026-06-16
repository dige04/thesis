"""Tests for the task-level GLMM (review blocker #14, Invariant #14).

The original module imported ``statsmodels.formula.api.glmer``, which does not
exist, so ``STATSMODELS_AVAILABLE`` was always False and ``fit_glmm`` never ran.
The decision (advisor #3): **R lme4 is the canonical crossed-effects path**
(``fit_glmm_with_r``, honoring Invariant #14's ``(1|seq_seed)+(1|task_id)``),
with a working ``BinomialBayesMixedGLM`` statsmodels *fallback* that includes
both variance components, clearly labelled approximate.

These tests pin the fallback (locally runnable) and the canonical path's
graceful-degradation contract (R verified on Colab).
"""

import numpy as np
import pandas as pd

from src.analysis.glmm import fit_glmm, fit_glmm_with_r


def _toy_task_data(seed: int = 0) -> pd.DataFrame:
    """Crossed seq_seed x task_id task-level frame with both outcome classes."""
    rng = np.random.default_rng(seed)
    rows = []
    policies = ["full_memory", "no_memory", "cls_consolidation"]
    tasks = [f"t{i}" for i in range(8)]
    groups = [f"repo_seed{s}" for s in (1, 2, 3)]
    for g in groups:
        for t in tasks:
            for pol in policies:
                base = 0.5 + (0.12 if pol == "full_memory" else -0.05)
                base += 0.12 if t in ("t0", "t1") else -0.04
                resolved = int(rng.random() < min(max(base, 0.1), 0.9))
                rows.append(
                    {
                        "resolved": resolved,
                        "policy": pol,
                        "difficulty_numeric": int(rng.integers(0, 3)),
                        "position_normalized": float(rng.random()),
                        "seq_seed": g,
                        "task_id": t,
                    }
                )
    return pd.DataFrame(rows)


def test_fit_glmm_returns_working_model_not_dead_import():
    result = fit_glmm(_toy_task_data())
    assert "statsmodels not available" not in str(result.get("error", ""))
    assert result.get("converged") is True
    assert result.get("fixed_effects"), "fixed effects must be populated"


def test_fit_glmm_uses_bayes_mixed_glm_primary():
    result = fit_glmm(_toy_task_data())
    assert "BinomialBayesMixedGLM" in result.get("method", "")


def test_fit_glmm_includes_both_variance_components():
    # Invariant #14: crossed random effects on seq_seed AND task_id.
    result = fit_glmm(_toy_task_data(), include_task_random_effect=True)
    assert set(result["random_effects"].keys()) >= {"seq_seed", "task_id"}


def test_fit_glmm_sensitivity_drops_task_id():
    # The sensitivity check (include_task_random_effect=False) keeps seq_seed only.
    result = fit_glmm(_toy_task_data(), include_task_random_effect=False)
    assert "seq_seed" in result["random_effects"]
    assert "task_id" not in result["random_effects"]


def test_fit_glmm_degenerate_outcome_no_crash():
    df = _toy_task_data()
    df["resolved"] = 1  # no variation — a binomial model cannot be fit
    result = fit_glmm(df)
    assert result["converged"] is False
    assert "fixed_effects" in result  # present (empty), no exception raised


def test_fit_glmm_with_r_degrades_gracefully():
    # Canonical path. Without rpy2/R it must return a dict, never raise.
    result = fit_glmm_with_r(_toy_task_data())
    assert "converged" in result
