"""
Statistical tests for memory pruning experiments.

This module implements Tasks 14.2 and 14.3:
- Wilcoxon signed-rank test with Holm correction
- Bootstrap BCa confidence intervals
- Rank-biserial effect size

Per THESIS_FINAL_v5.md §15.2:
- Primary test: Wilcoxon signed-rank on N=8 sequence means
- 5 pre-registered contrasts with Holm correction
- Effect size: rank-biserial r_rb
- Bootstrap: 5000 iterations, BCa method
"""

from typing import Any

import numpy as np
from scipy import stats


def compute_rank_biserial(
    x: np.ndarray,
    y: np.ndarray,
) -> float:
    """
    Compute rank-biserial correlation effect size for paired samples.

    Per THESIS_FINAL_v5.md §15.2:
    - Effect size metric for Wilcoxon signed-rank test
    - Interpretation: |r_rb| ≈ 0.1 small, ≈ 0.3 medium, ≈ 0.5 large

    Args:
        x: First sample (e.g., policy A sequence means)
        y: Second sample (e.g., policy B sequence means)

    Returns:
        Rank-biserial correlation r_rb in [-1, 1]
    """
    differences = np.asarray(x, dtype=float) - np.asarray(y, dtype=float)

    # Wilcoxon convention: DROP zero differences before ranking, and exclude
    # them from the normalising denominator (THESIS_REVIEW.md #13). The old code
    # ranked the full vector, folded zeros onto the negative side via
    # ``~positive_mask``, and divided by n(n+1)/2 using the full n — all three
    # bias r_rb toward the baseline and return -1.0 for tied/identical policies.
    nonzero = differences[differences != 0.0]
    m = nonzero.size
    if m == 0:
        return 0.0

    ranks = stats.rankdata(np.abs(nonzero))
    r_plus = float(np.sum(ranks[nonzero > 0]))
    r_minus = float(np.sum(ranks[nonzero < 0]))

    # r_rb = (R+ - R-) / (R+ + R-); the denominator equals m(m+1)/2 over the
    # m non-zero differences.
    denom = r_plus + r_minus
    if denom == 0:
        return 0.0
    return float((r_plus - r_minus) / denom)


def run_wilcoxon_with_holm(
    sequence_aggregates: dict[str, dict[str, dict[str, Any]]],
    metric: str = "mean_cl_f1",
    baseline_policy: str = "full_memory",
    contrasts: list[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """
    Run Wilcoxon signed-rank tests with Holm correction.

    Per THESIS_FINAL_v5.md §15.2:
    - 5 pre-registered contrasts (each pruning policy vs Full Memory)
    - Wilcoxon signed-rank on N=8 sequence means
    - Holm correction for family-wise error rate control
    - Report rank-biserial effect size and median paired difference

    Args:
        sequence_aggregates: Output from aggregate_sequence_results()
        metric: Metric to test (default: "mean_cl_f1")
        baseline_policy: Baseline policy for contrasts (default: "full_memory")
        contrasts: List of policies to compare against baseline
                   Default: ["random_prune", "recency_prune", "type_aware_decay",
                            "cls_consolidation", "no_memory"]

    Returns:
        Dict with keys:
        - contrasts: List of contrast results, each containing:
          - policy: Policy name
          - baseline: Baseline policy name
          - n: Number of sequences
          - median_diff: Median paired difference
          - rank_biserial: Rank-biserial effect size
          - statistic: Wilcoxon test statistic
          - p_value: Raw p-value
          - holm_p_value: Holm-corrected p-value
          - significant: Whether Holm-corrected p < 0.05
    """
    if contrasts is None:
        contrasts = [
            "random_prune",
            "recency_prune",
            "type_aware_decay",
            "cls_consolidation",
            "no_memory",
        ]

    # Extract baseline values for all sequences
    baseline_values = {}
    if baseline_policy not in sequence_aggregates:
        raise ValueError(f"Baseline policy '{baseline_policy}' not found in data")

    for sequence, metrics in sequence_aggregates[baseline_policy].items():
        baseline_values[sequence] = metrics[metric]

    # Compute contrasts
    contrast_results = []

    for policy in contrasts:
        if policy not in sequence_aggregates:
            print(f"Warning: Policy '{policy}' not found in data, skipping")
            continue

        # Extract policy values for matching sequences
        policy_values = {}
        for sequence, metrics in sequence_aggregates[policy].items():
            if sequence in baseline_values:
                policy_values[sequence] = metrics[metric]

        # Ensure same sequences
        common_sequences = sorted(set(baseline_values.keys()) & set(policy_values.keys()))
        n = len(common_sequences)

        if n < 3:
            print(
                f"Warning: Only {n} common sequences for {policy} vs {baseline_policy}, skipping"
            )
            continue

        # Create paired arrays
        x = np.array([policy_values[seq] for seq in common_sequences])
        y = np.array([baseline_values[seq] for seq in common_sequences])

        # Compute statistics
        differences = x - y
        median_diff = float(np.median(differences))

        # Wilcoxon signed-rank test
        statistic, p_value = stats.wilcoxon(x, y, alternative="two-sided")

        # Rank-biserial effect size
        r_rb = compute_rank_biserial(x, y)

        contrast_results.append(
            {
                "policy": policy,
                "baseline": baseline_policy,
                "n": n,
                "sequences": common_sequences,
                "median_diff": median_diff,
                "rank_biserial": r_rb,
                "statistic": float(statistic),
                "p_value": float(p_value),
            }
        )

    # Apply Holm correction
    if len(contrast_results) > 0:
        p_values = [c["p_value"] for c in contrast_results]
        holm_corrected = holm_correction(p_values)

        for i, result in enumerate(contrast_results):
            result["holm_p_value"] = holm_corrected[i]
            result["significant"] = holm_corrected[i] < 0.05

    return {
        "metric": metric,
        "baseline_policy": baseline_policy,
        "n_contrasts": len(contrast_results),
        "contrasts": contrast_results,
    }


def holm_correction(p_values: list[float], alpha: float = 0.05) -> list[float]:
    """
    Apply Holm-Bonferroni correction to p-values.

    Per THESIS_FINAL_v5.md §15.2:
    - Controls family-wise error rate for multiple comparisons
    - More powerful than Bonferroni correction

    Args:
        p_values: List of raw p-values
        alpha: Family-wise error rate (default: 0.05)

    Returns:
        List of Holm-corrected p-values
    """
    # ``alpha`` is retained for API compatibility; Holm-adjusted p-values do not
    # depend on it (it only governs the reject decision, made by the caller).
    _ = alpha

    p = np.asarray(p_values, dtype=float)
    n = p.size
    if n == 0:
        return []

    # Correct Holm step-down (the version statsmodels implements):
    #   1. sort raw p ascending; 2. scale the k-th smallest (0-indexed) by (n-k);
    #   3. take the cumulative maximum IN RAW-P-SORTED ORDER; 4. clip to 1.0.
    # The old code re-sorted the already-multiplied values and ran the
    # monotonicity pass over that wrong ordering (THESIS_REVIEW.md #12), which is
    # anti-conservative when the raw p-values are not pre-sorted.
    order = np.argsort(p, kind="stable")
    multipliers = n - np.arange(n)
    adjusted_sorted = np.clip(np.maximum.accumulate(p[order] * multipliers), 0.0, 1.0)

    adjusted = np.empty(n, dtype=float)
    adjusted[order] = adjusted_sorted
    return [float(v) for v in adjusted]


def run_bootstrap_bca(
    x: np.ndarray,
    y: np.ndarray,
    n_iterations: int = 5000,
    alpha: float = 0.05,
    random_seed: int | None = None,
) -> dict[str, float]:
    """
    Compute bootstrap BCa confidence interval for median paired difference.

    Per THESIS_FINAL_v5.md §15.2:
    - 5000 bootstrap iterations
    - BCa (bias-corrected and accelerated) method
    - 95% confidence interval

    Args:
        x: First sample (e.g., policy A sequence means)
        y: Second sample (e.g., policy B sequence means)
        n_iterations: Number of bootstrap iterations (default: 5000)
        alpha: Significance level (default: 0.05 for 95% CI)
        random_seed: Random seed for reproducibility

    Returns:
        Dict with keys:
        - median_diff: Observed median difference
        - ci_lower: Lower bound of BCa CI
        - ci_upper: Upper bound of BCa CI
        - bias_correction: BCa bias correction factor
        - acceleration: BCa acceleration factor
    """
    if random_seed is not None:
        np.random.seed(random_seed)

    n = len(x)
    differences = x - y
    observed_median = np.median(differences)

    # Bootstrap resampling
    bootstrap_medians = []
    for _ in range(n_iterations):
        indices = np.random.choice(n, size=n, replace=True)
        boot_diff = differences[indices]
        bootstrap_medians.append(np.median(boot_diff))

    bootstrap_medians = np.array(bootstrap_medians)

    # Bias correction (z0)
    # Proportion of bootstrap estimates less than observed
    p_less = np.mean(bootstrap_medians < observed_median)
    if p_less == 0:
        z0 = -3.0  # Avoid -inf
    elif p_less == 1:
        z0 = 3.0  # Avoid +inf
    else:
        z0 = stats.norm.ppf(p_less)

    # Acceleration (a) via jackknife
    jackknife_medians = []
    for i in range(n):
        jack_diff = np.delete(differences, i)
        jackknife_medians.append(np.median(jack_diff))

    jackknife_medians = np.array(jackknife_medians)
    jack_mean = np.mean(jackknife_medians)
    numerator = np.sum((jack_mean - jackknife_medians) ** 3)
    denominator = 6 * (np.sum((jack_mean - jackknife_medians) ** 2) ** 1.5)

    if denominator == 0:
        a = 0.0
    else:
        a = numerator / denominator

    # BCa confidence interval
    z_alpha_lower = stats.norm.ppf(alpha / 2)
    z_alpha_upper = stats.norm.ppf(1 - alpha / 2)

    # Adjusted percentiles
    p_lower = stats.norm.cdf(z0 + (z0 + z_alpha_lower) / (1 - a * (z0 + z_alpha_lower)))
    p_upper = stats.norm.cdf(z0 + (z0 + z_alpha_upper) / (1 - a * (z0 + z_alpha_upper)))

    # Clip to valid range
    p_lower = np.clip(p_lower, 0.0, 1.0)
    p_upper = np.clip(p_upper, 0.0, 1.0)

    ci_lower = np.percentile(bootstrap_medians, p_lower * 100)
    ci_upper = np.percentile(bootstrap_medians, p_upper * 100)

    return {
        "median_diff": float(observed_median),
        "ci_lower": float(ci_lower),
        "ci_upper": float(ci_upper),
        "bias_correction": float(z0),
        "acceleration": float(a),
        "n_iterations": n_iterations,
        "alpha": alpha,
    }


def compute_all_contrasts_with_bootstrap(
    sequence_aggregates: dict[str, dict[str, dict[str, Any]]],
    metric: str = "mean_cl_f1",
    baseline_policy: str = "full_memory",
    contrasts: list[str] | None = None,
    n_bootstrap: int = 5000,
    random_seed: int | None = None,
) -> dict[str, Any]:
    """
    Run complete statistical analysis: Wilcoxon + Holm + Bootstrap BCa.

    Combines Tasks 14.2 and 14.3 into a single comprehensive analysis.

    Args:
        sequence_aggregates: Output from aggregate_sequence_results()
        metric: Metric to test (default: "mean_cl_f1")
        baseline_policy: Baseline policy (default: "full_memory")
        contrasts: List of policies to compare
        n_bootstrap: Number of bootstrap iterations (default: 5000)
        random_seed: Random seed for reproducibility

    Returns:
        Dict with Wilcoxon results + bootstrap CIs for each contrast
    """
    # Run Wilcoxon with Holm correction
    wilcoxon_results = run_wilcoxon_with_holm(
        sequence_aggregates=sequence_aggregates,
        metric=metric,
        baseline_policy=baseline_policy,
        contrasts=contrasts,
    )

    # Add bootstrap BCa CIs to each contrast
    baseline_values = {}
    for sequence, metrics in sequence_aggregates[baseline_policy].items():
        baseline_values[sequence] = metrics[metric]

    for contrast in wilcoxon_results["contrasts"]:
        policy = contrast["policy"]
        sequences = contrast["sequences"]

        # Extract paired values
        x = np.array(
            [sequence_aggregates[policy][seq][metric] for seq in sequences]
        )
        y = np.array([baseline_values[seq] for seq in sequences])

        # Compute bootstrap BCa CI
        bca_result = run_bootstrap_bca(
            x=x,
            y=y,
            n_iterations=n_bootstrap,
            random_seed=random_seed,
        )

        # Add to contrast result
        contrast["bootstrap_ci"] = bca_result

    return wilcoxon_results


# ---------------------------------------------------------------------------
# TOST equivalence test + H1a outcome labels (A/B/C/D) — review blocker #11
# ---------------------------------------------------------------------------

# Pre-registered H1a outcome labels (THESIS_FINAL_v5.md §15.2): pruning vs
# full_memory on CL-F1, with paired difference defined as policy - baseline.
H1A_EQUIVALENT = "A_equivalent"
H1A_SUPERIOR = "B_superior"
H1A_DEGRADED = "C_degraded"
H1A_INCONCLUSIVE = "D_inconclusive"


def _one_sided_wilcoxon(shifted: np.ndarray, alternative: str) -> float:
    """One-sided Wilcoxon signed-rank p-value on a shifted difference vector.

    Returns 1.0 (cannot reject) when every value is zero — the conservative,
    non-crashing behaviour needed on degenerate (all-tied) fixtures.
    """
    shifted = np.asarray(shifted, dtype=float)
    if np.all(shifted == 0.0):
        return 1.0
    try:
        _, p = stats.wilcoxon(shifted, alternative=alternative, zero_method="wilcox")
        return float(p)
    except ValueError:
        return 1.0


def bootstrap_bca_ci(
    differences: np.ndarray,
    n_iterations: int = 5000,
    alpha: float = 0.05,
    random_seed: int | None = 12345,
) -> dict[str, float]:
    """BCa 95% CI for the median of a paired-difference vector.

    Difference-based companion to :func:`run_bootstrap_bca` (which takes ``x, y``),
    used by :func:`tost`. Same BCa construction: percentile bootstrap with
    bias-correction ``z0`` and jackknife acceleration ``a`` (Invariant #15:
    5000 iterations, BCa method).
    """
    d = np.asarray(differences, dtype=float)
    n = d.size
    observed = float(np.median(d))

    if n < 2:
        # No spread to bootstrap; degenerate CI at the point estimate.
        return {
            "median_diff": observed,
            "ci_lower": observed,
            "ci_upper": observed,
            "bias_correction": 0.0,
            "acceleration": 0.0,
        }

    rng = np.random.default_rng(random_seed)
    idx = rng.integers(0, n, size=(n_iterations, n))
    boot = np.median(d[idx], axis=1)

    # Bias-correction z0.
    p_less = float(np.mean(boot < observed))
    if p_less <= 0.0:
        z0 = -8.0
    elif p_less >= 1.0:
        z0 = 8.0
    else:
        z0 = float(stats.norm.ppf(p_less))

    # Acceleration via jackknife.
    jack = np.array([np.median(np.delete(d, i)) for i in range(n)])
    jack_mean = jack.mean()
    num = np.sum((jack_mean - jack) ** 3)
    den = 6.0 * (np.sum((jack_mean - jack) ** 2) ** 1.5)
    a = 0.0 if den == 0 else float(num / den)

    z_lo = stats.norm.ppf(alpha / 2)
    z_hi = stats.norm.ppf(1 - alpha / 2)

    def _adjust(z: float) -> float:
        denom = 1 - a * (z0 + z)
        if denom == 0:
            denom = 1e-12
        return float(stats.norm.cdf(z0 + (z0 + z) / denom))

    p_lo = float(np.clip(_adjust(z_lo), 0.0, 1.0))
    p_hi = float(np.clip(_adjust(z_hi), 0.0, 1.0))

    return {
        "median_diff": observed,
        "ci_lower": float(np.percentile(boot, p_lo * 100)),
        "ci_upper": float(np.percentile(boot, p_hi * 100)),
        "bias_correction": z0,
        "acceleration": a,
    }


def tost(
    differences: list[float] | np.ndarray,
    sesoi: float = 0.03,
    n_iterations: int = 5000,
    alpha: float = 0.05,
    random_seed: int | None = 12345,
) -> dict[str, Any]:
    """Two one-sided tests (TOST) for equivalence on the median paired diff.

    The paired difference is ``policy - baseline`` (a positive median means the
    policy beats full_memory). Equivalence is assessed against the symmetric
    SESOI band ``(-sesoi, +sesoi)`` using the BCa 95% CI of the median plus the
    one-sided Wilcoxon tail for the superiority call. Returns the pre-registered
    H1a label:

      A_equivalent  : CI strictly inside (-sesoi, +sesoi).
      C_degraded    : median < -sesoi AND ci_upper < -sesoi (a real regression).
      B_superior    : one-sided Wilcoxon rejects median <= 0 AND median > 0.
      D_inconclusive: anything else (the CI straddles a SESOI bound).

    Labels are checked in the order A, C, B, D so a clean equivalence or
    degradation is reported even when the superiority tail is also nominally
    significant in the same direction.
    """
    d = np.asarray(differences, dtype=float)
    median_diff = float(np.median(d))

    bca = bootstrap_bca_ci(
        d, n_iterations=n_iterations, alpha=alpha, random_seed=random_seed
    )
    ci_lower = bca["ci_lower"]
    ci_upper = bca["ci_upper"]

    # One-sided Wilcoxon p-values for the two TOST nulls and the superiority test.
    p_lower = _one_sided_wilcoxon(d + sesoi, alternative="greater")
    p_upper = _one_sided_wilcoxon(d - sesoi, alternative="less")
    p_tost = max(p_lower, p_upper)
    p_superiority = _one_sided_wilcoxon(d, alternative="greater")

    ci_inside_band = (ci_lower > -sesoi) and (ci_upper < sesoi)
    ci_below_lower_bound = ci_upper < -sesoi

    if ci_inside_band:
        outcome = H1A_EQUIVALENT
    elif (median_diff < -sesoi) and ci_below_lower_bound:
        outcome = H1A_DEGRADED
    elif (p_superiority < alpha) and (median_diff > 0):
        outcome = H1A_SUPERIOR
    else:
        outcome = H1A_INCONCLUSIVE

    return {
        "median_diff": median_diff,
        "ci_lower": ci_lower,
        "ci_upper": ci_upper,
        "sesoi": sesoi,
        "p_lower": p_lower,
        "p_upper": p_upper,
        "p_tost": p_tost,
        "p_superiority": p_superiority,
        "outcome": outcome,
        "n": int(d.size),
    }
