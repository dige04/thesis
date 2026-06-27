# Gate-3 Interdependence / Memory-Lift Findings — PRELIMINARY

> ⚠️ **PRELIMINARY PILOT ANALYSIS — NOT a thesis result. Do not cite.**
> 1 seed, 2 of 8 sequences, **resolved-count proxy — NOT the primary CL-F1 metric**
> (CL-F1 requires the E2 anchor-probe re-evaluation, not yet run). Directional only.
> Date: 2026-06-17. Produced with the E7 machinery on branch `feat/analysis-e3-e2-e7`.

## What was run
- Pushed `feat/analysis-e3-e2-e7` (`6f1f2ae`) to `origin`.
- Pulled all 12 gate-3 `task_results.jsonl` **read-only** from the droplet.
- Ran E7: `structural_interdependence` (on the full curriculum's gold patches) + `memory_lift_by_position` and per-policy first/second-half resolved rates (on gate-3).
- **Droplet state:** nothing running (gate-3 done; no E2 job). `/root/thesis` is **rsync-deployed, not a git checkout** → syncing my code there needs rsync, not `git pull`.

## Finding 1 — Structural interdependence: real but modest (~⅓)

Across all 8 official sequences (gold-patch file overlap with earlier tasks):

| | mean prior-file-overlap | frac tasks w/ dependency |
|---|---|---|
| **mean over 8 sequences** | **0.30** | **0.32** |
| range | sympy/sklearn/astropy ~0.13 → sphinx/xarray ~0.50 | — |

→ ~⅔ of tasks are file-disjoint from *every* predecessor. Memory can only plausibly help the interdependent ~⅓ — so a sequence-level *average* benefit was always going to be diluted. This is the user's own RQ ("not every task needs memory") made measurable.

## Finding 2 — Memory doesn't help on aggregate; Full memory decays MOST late

Per-policy resolved rate, first vs second half of each sequence (gate-3, 1 seed):

**django (T=50):**

| policy | total | 1st-half | 2nd-half | Δ late−early |
|---|---|---|---|---|
| no_memory | 24/50 | 0.52 | 0.44 | −0.08 |
| **full_memory** | 25/50 | 0.64 | 0.36 | **−0.28** |
| random_prune | 22/50 | 0.48 | 0.40 | −0.08 |
| recency_prune | 26/50 | 0.56 | 0.48 | −0.08 |
| type_aware_decay | 22/50 | 0.56 | 0.32 | −0.24 |
| cls_consolidation | 25/50 | 0.52 | 0.48 | −0.04 |

**pytest (T=19):**

| policy | total | 1st-half | 2nd-half | Δ late−early |
|---|---|---|---|---|
| no_memory | 10/19 | 0.78 | 0.30 | −0.48 |
| **full_memory** | 8/19 | 0.89 | 0.00 | **−0.89** |
| random_prune | 10/19 | 0.89 | 0.20 | −0.69 |
| recency_prune | 6/19 | 0.56 | 0.10 | −0.46 |
| type_aware_decay | 8/19 | 0.67 | 0.20 | −0.47 |
| cls_consolidation | 7/19 | 0.67 | 0.10 | −0.57 |

**Memory-attributable late penalty** (Full minus No-Memory, `late_minus_early`): **−0.20 (django), −0.41 (pytest)**.

## Interpretation (directional, heavily caveated)

- On both sequences, **Full memory shows the steepest late-task decline** — worse than No-Memory. Accumulated memory appears to *hurt* later tasks, consistent with **context pollution**. That is precisely the mechanism forgetting policies are meant to fix → **encouraging for the thesis (forgetting may ≥ Full), not a death-knell null.**
- There is a **general** late-decline across *all* policies (even No-Memory), likely task-ordering/difficulty — so the memory-specific effect is the *difference* from No-Memory (the −0.20 / −0.41 above), and analysis must control for position (the GLMM position term).
- **Do not over-read:** policy rankings are unstable across just 2 sequences (recency best on django, near-worst on pytest); Full's pytest 2nd-half is 0/9; everything here is the **resolved-count proxy on 1 seed**.

## Implications for the 144-run matrix

A **GO is plausible** — there may be a real forgetting-≥-Full effect, the strongest thesis outcome — but gated on three things first:
1. **Confirm on CL-F1** — run **E2 anchor-probe** on the gate-3 runs. The proxy must not drive the decision (anchor-probe also measures the stability dimension the proxy misses).
2. **Fix CLS** (advisor) — inert at cap=10 (the frozen #23 "≥10-tasks-old" candidate threshold conflicts with the A1 cap=10; no record is ever old enough to consolidate). As-is, the CLS arm tests nothing distinct = 1/6 of the matrix wasted.
3. **Control for position** in the model (the late-decline confound).

## UPDATE — real CL-F1 (E2 anchor-probe, linchpin subset) — 2026-06-17

E2 live wiring built (`src/benchmark/anchor_probe_live.py`) and run end-to-end on the droplet (52 re-evals, 0 errors) for full_memory + no_memory × django + pytest.

| run | plasticity | stability | CL-F1 |
|---|---|---|---|
| pytest no_memory | 0.526 | 1.000 | 0.690 |
| pytest full_memory | 0.421 | 1.000 | 0.593 |
| django no_memory | 0.480 | 1.000 | 0.649 |
| django full_memory | 0.500 | 1.000 | 0.667 |

**Linchpin (CL-F1, full − no_memory): pytest −0.097, django +0.018.** Memory does **not** help on the primary metric — confirms the resolved-count proxy.

**Stability saturated at 1.000 (zero detected forgetting)** on the 5-anchor sample → CL-F1 reduces to a function of plasticity (≈ the proxy). So "memory doesn't help" is a **plasticity** (new-task) effect, NOT catastrophic forgetting of earlier tasks. The proxy's "full decays late" is about *new* late tasks, not forgetting. (Caveat: 5 anchors × 1 seed is low-power for stability; django anchor outcomes were identical across conditions → difficulty-dominated.)

**Implication for the thesis:** the defensible story is **non-inferiority + efficiency** ("forgetting matches full memory at lower footprint/cost"), not "forgetting recovers lost performance." Likely a careful **null / non-inferiority** result; the Pareto footprint axis (where forgetting clearly wins) is the robust contribution. Anchor-probe stability may be low-power here — validate it discriminates before spending the full matrix's anchor-probe budget.
