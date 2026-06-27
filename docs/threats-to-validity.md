# Threats to Validity

> Drop-in thesis prose (English). Fold into the paper's Methods/Discussion. Grounded in
> `AMENDMENTS.md` (A1–A7, D1–D6) and gate-3 findings; no fabricated numbers.

**Construct & measurement validity.** Our primary stability instrument — anchor-probe
re-evaluation of earlier tasks against later memory states — saturated at 1.000 in the
gate-3 pilot, detecting zero forgetting on a five-anchor sample. We cannot yet
distinguish a genuine absence of catastrophic forgetting from an insensitive instrument:
with only five anchors, and with anchor re-evaluation itself stochastic under a reasoning
model at temperature 1, the metric has near-zero power to register degradation even where
it occurs. We therefore treat anchor-probe stability as exploratory and base our
efficiency claim on the directly-measured memory-footprint axis, which is immune to this
sensitivity problem. Relatedly, CLS Consolidation never triggered on the benchmark's
diverse same-repository memories (no DBSCAN cluster of ≥3 records at ≥0.70 cosine), so H3
is reported as not-applicable rather than supported; we declined to relax the frozen
similarity threshold, which would have manufactured incoherent summaries. Finally, because
the executed model emits reasoning tokens that are counted in completion length, the
token-cost axis is inflated relative to a non-reasoning model; the inflation is uniform
across conditions, so between-policy cost contrasts hold, but absolute token costs are not
comparable across studies.

**Internal validity.** Retrieval is held identical (pure cosine, fixed top-k) across all
six conditions, so the contrast is attributable to the storage/forgetting policy rather
than to retrieval. The base model, embedder, temperature, and memory budget are fixed
factors held constant across conditions and seeds. The principal residual threat is
benchmark contamination: SWE-Bench tasks are public and the model's training cutoff is
undocumented. Because any contamination is constant across conditions, it does not bias
between-policy contrasts; it does, however, render absolute solve rates uninterpretable as
capability measures, and we disclaim them accordingly. Per-run provenance (model alias,
configuration hash, dataset revision) is logged to detect alias drift under the
rotating-key router.

**External validity.** Results derive from a single base model (MiniMax M3, the third
link in a declared deviation chain from the pre-registered GPT-5.4), a single benchmark
family (SWE-Bench-CL), same-repository retrieval only, and a fixed top-k. We make no
cross-model or cross-benchmark generalization claim; an optional cross-model probe (top
conditions, a subset of sequences, one seed) provides descriptive, non-inferential
evidence of transfer direction only. A deeper boundary on generalization is intrinsic to
the task distribution: only roughly one-third of tasks structurally depend on a
predecessor, so conclusions about memory's benefit apply to that interdependent subset,
not to sequential coding in general.

**Statistical conclusion validity.** The primary test is Wilcoxon signed-rank on N = 8
sequence-level means with Holm correction over five pre-registered contrasts, accompanied
by rank-biserial effect sizes and BCa bootstrap intervals (5000 resamples);
non-inferiority is assessed by TOST against a SESOI of ±0.03 CL-F1. With N = 8 the design
is honestly underpowered for small effects, which we address by leading with estimation
(effect sizes and intervals) rather than dichotomous significance. Run-level variance from
the agent's stochasticity is estimated from the three seeds and reported separately from
task-level bootstrap intervals; the two are not pooled.
