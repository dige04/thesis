"""Golden tests for the corrected statistics in ``src/analysis/statistical_tests.py``.

Ported from ``scripts/simulate/sim_stats.py`` (review blocker E3). These pin the
three frozen-invariant statistics against an external reference so the bugs the
deep review found (THESIS_REVIEW.md #11–#13) cannot regress:

  * Holm step-down adjusted p-values must match
    ``statsmodels.stats.multitest.multipletests(method='holm')`` (Invariant #11).
  * Rank-biserial r_rb must follow the Wilcoxon convention: zero differences are
    DROPPED from both the ranking and the denominator (Invariant #12).
  * TOST must emit the pre-registered H1a outcome labels A/B/C/D (§15.2; the test
    that was entirely absent — blocker #11).
"""

import numpy as np
import pytest

from src.analysis.statistical_tests import compute_rank_biserial, holm_correction

# ---------------------------------------------------------------------------
# Holm-Bonferroni step-down (vs statsmodels)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw_p",
    [
        [0.01, 0.04, 0.05],
        [0.04, 0.01, 0.05],  # unsorted input — the case the old code mishandled
        [0.05, 0.04, 0.01],
        [0.001, 0.5, 0.02, 0.04, 0.2],
        [0.2, 0.2, 0.2, 0.2, 0.2],
        [0.0001],
    ],
)
def test_holm_matches_statsmodels(raw_p):
    multipletests = pytest.importorskip("statsmodels.stats.multitest").multipletests
    mine = np.array(holm_correction(raw_p))
    _, reference, _, _ = multipletests(raw_p, alpha=0.05, method="holm")
    assert np.allclose(mine, reference, atol=1e-9), (
        f"mine={list(np.round(mine, 6))} statsmodels={list(np.round(reference, 6))}"
    )


def test_holm_explicit_counterexample():
    # The buggy implementation returned [0.03, 0.08, 0.05]; the correct
    # step-down (cumulative max in raw-p order) gives [0.03, 0.08, 0.08].
    assert np.allclose(
        holm_correction([0.01, 0.04, 0.05]), [0.03, 0.08, 0.08], atol=1e-9
    )


def test_holm_preserves_input_order():
    # Adjusted values must be returned in the SAME order as the input.
    out = holm_correction([0.05, 0.01, 0.04])
    assert np.allclose(out, [0.08, 0.03, 0.08], atol=1e-9)


# ---------------------------------------------------------------------------
# Rank-biserial r_rb (Wilcoxon convention: zeros dropped)
# ---------------------------------------------------------------------------


def test_rank_biserial_all_positive_is_plus_one():
    r = compute_rank_biserial(np.array([0.1, 0.2, 0.3, 0.4]), np.zeros(4))
    assert abs(r - 1.0) < 1e-12


def test_rank_biserial_all_negative_is_minus_one():
    r = compute_rank_biserial(np.array([-0.1, -0.2, -0.3]), np.zeros(3))
    assert abs(r + 1.0) < 1e-12


def test_rank_biserial_drops_zero_differences():
    # [+, +, 0, 0] must behave exactly like [+, +] -> +1: zero differences are
    # excluded from both the rank assignment and the normalising denominator.
    with_zeros = compute_rank_biserial(np.array([0.1, 0.2, 0.0, 0.0]), np.zeros(4))
    no_zeros = compute_rank_biserial(np.array([0.1, 0.2]), np.zeros(2))
    assert abs(with_zeros - no_zeros) < 1e-12
    assert abs(with_zeros - 1.0) < 1e-12


def test_rank_biserial_all_zero_is_zero():
    # Operationally-identical policies (all paired diffs == 0) must give r_rb = 0,
    # NOT -1 (the old code ranked the zeros onto the negative side).
    assert compute_rank_biserial(np.zeros(4), np.zeros(4)) == 0.0


# ---------------------------------------------------------------------------
# TOST equivalence + H1a outcome labels (A/B/C/D)
# ---------------------------------------------------------------------------


def test_tost_outcome_labels():
    from src.analysis.statistical_tests import (
        H1A_DEGRADED,
        H1A_EQUIVALENT,
        H1A_INCONCLUSIVE,
        H1A_SUPERIOR,
        tost,
    )

    rng = np.random.default_rng(0)

    # A — tight cluster around 0, well inside +/-SESOI.
    assert tost(rng.normal(0.0, 0.004, size=8), sesoi=0.03)["outcome"] == H1A_EQUIVALENT
    # B — clearly positive, above +SESOI.
    superior = np.array([0.06, 0.07, 0.08, 0.05, 0.09, 0.06, 0.07, 0.08])
    assert tost(superior, sesoi=0.03)["outcome"] == H1A_SUPERIOR
    # C — clearly negative, CI entirely below -SESOI.
    degraded = np.array([-0.08, -0.07, -0.09, -0.06, -0.08, -0.07, -0.09, -0.08])
    assert tost(degraded, sesoi=0.03)["outcome"] == H1A_DEGRADED
    # D — wide spread straddling a SESOI bound.
    inconclusive = np.array([-0.05, 0.06, -0.04, 0.05, 0.02, -0.03, 0.04, -0.02])
    assert tost(inconclusive, sesoi=0.03)["outcome"] == H1A_INCONCLUSIVE


def test_tost_returns_bca_ci_and_tost_p():
    from src.analysis.statistical_tests import tost

    result = tost(np.array([0.06, 0.07, 0.08, 0.05, 0.09, 0.06, 0.07, 0.08]), sesoi=0.03)
    assert result["ci_lower"] <= result["median_diff"] <= result["ci_upper"]
    assert result["p_tost"] == max(result["p_lower"], result["p_upper"])
