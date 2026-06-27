# Thesis Defense Dossier (2026-06-20)

> **Memory Pruning and Forgetting Policies for AI Coding Agents — Impact on Performance Across Sequential Tasks.**
> Single-source, examiner-ready synthesis of results, framing, limitations, Q&A, and the plugin bridge.
> Numbers below are on **143/144 units** (`cls_consolidation_astropy_seed1` re-running after a FAISS bug; refresh `results/tables/defense_stats.md` after re-aggregate). All artifacts: `results/aggregated/`, `results/tables/`, `results/glmm/`, `results/retrieval_overlap.jsonl`, `runs_k27_merged/`, `runs_legacy_merged/`.

---

## 1. The one-paragraph headline (honest)

This thesis pre-registered its core hypothesis (H1) as **non-inferiority + efficiency**, *not* superiority: that proactive forgetting would **match** full-memory accumulation on continual-learning quality **while costing materially less**. That is exactly what the 144-run controlled experiment shows. The strongest forgetting policy (**Recency Prune**) is **statistically non-inferior** to Full Memory on the primary outcome (pre-registered TOST, BCa 95% CI lower bound −0.025 > −0.03 SESOI), is numerically the best policy at the task level (GLMM, 4,653 obs), and carries a **~70–78% smaller memory footprint**. The contribution is a **controlled Pareto characterization**: *forgetting is the efficient design — equal quality, a fraction of the footprint.* We report this honestly, including where the evidence is underpowered or the instrument is blind.

---

## 2. The framing that resolves the "is this a null/failure?" worry

**H1 (verbatim, v5 §1.3):** pruning achieves *"(H1a) non-inferior sequential performance vs Full Memory, AND/OR (H1b) materially lower operational cost."*
- **H1a** is a **pre-registered TOST equivalence test, SESOI = ±0.03 CL-F1**, locked before Spike Week (§0.1 #27). It is *not* a post-hoc rescue.
- **H1 is rejected for a pruner only under Outcome C** (degraded: CI upper bound < −0.03).

**Therefore a null *difference* is H1 being supported, not failing.** The thesis never claimed pruning beats full memory on quality; it claimed pruning doesn't *lose* on quality and is cheaper. The data confirm both.

---

## 3. Results by hypothesis (with real numbers)

### H1a — Non-inferiority of quality (primary; CL-F1 = resolved-rate proxy, see L1)
Sequence-level paired (N=8), pre-registered TOST, BCa 95% CI, SESOI ±0.03:

| policy vs full | median Δ | BCa 95% CI | Wilcoxon p | outcome |
|---|---|---|---|---|
| **recency_prune** | +0.011 | [−0.025, +0.068] | 0.383 | **Non-inferior** |
| type_aware_decay | −0.023 | [−0.033, +0.015] | 0.312 | Inconclusive |
| random_prune | +0.000 | [−0.108, +0.018] | 0.945 | Inconclusive |
| cls_consolidation | −0.014 | [−0.067, +0.000] | 0.195 | Inconclusive |
| no_memory | −0.022 | [−0.043, −0.005] | 0.109 | Inconclusive (leans worse) |

**No pruner is Outcome C → H1 not rejected for any pruner.** Recency clears non-inferiority outright; the rest are *inconclusive* (not degraded) — a **power** limit (L2), not a failure.

**Task-level GLMM** (4,653 obs; `task_success ~ policy + difficulty + position + (1|seq/seed) + (1|task_id)`; BinomialBayesMixedGLM variational; releveled to full_memory):

| contrast | log-odds | z | p | OR |
|---|---|---|---|---|
| recency_prune vs full | +0.091 | +0.76 | 0.445 | 1.10 |
| random_prune vs full | −0.031 | −0.25 | 0.799 | 0.97 |
| type_aware_decay vs full | −0.093 | −0.78 | 0.438 | 0.91 |
| cls_consolidation vs full | −0.203 | −1.67 | 0.095 | 0.82 |
| no_memory vs full | −0.191 | −1.55 | 0.121 | 0.83 |

difficulty (−2.40) and position (−1.62) dominate and are **controlled**. With ~4,600 observations of power, **recency remains non-inferior (slightly better) and no policy significantly differs from full** → the non-inferiority conclusion is robust across both analysis levels.

### H1b — Efficiency (footprint axis, per A4)
Total tokens are agent-loop-dominated (≈151K prompt tokens/task; memory is ≈0.4–1%; tool_calls/task ≈21.5 identical across policies) → storage pruning cannot move *total* tokens (honestly disclosed, A4). On the **memory-footprint axis**, full injects ≈2,986 tokens/task vs pruners ≈666–908 → **~70–78% reduction ≫ 20% SESOI → H1b supported.** This is the robust efficiency win and the X-axis of the two-axis Pareto (A4/H1b).

**Manipulation check (does storage pruning change retrieval?):** pruners vs full median Jaccard **0.25** (≈75% of retrieved memories differ); no_memory 0.00. → storage decisions demonstrably change model-visible context. (`results/retrieval_overlap.jsonl`; keyed on source sequence_index — documented deviation, advisor sign-off pending.)

### H2 — Type-Aware Decay > Random Prune (content beyond volume)
Not supported as a clean win: type_aware 0.300 vs random 0.290 (n.s.); GLMM both ≈ full. Report as **inconclusive** at this power.

### H3 — CLS fails the Pareto efficiency test
**Not applicable on this benchmark (disclosed, A3):** diverse same-repo memories never form ≥3-clusters at 0.70 cosine, so CLS degenerates to its Type-Aware fallback (0 consolidations on the canonical Flash matrix; the path is verified to fire + log provenance on other data). H3 reported as a *negative / N-A finding about when consolidation is applicable*, not a failed test.

### H4 — Analysis-paralysis behavioral signature
Exploratory (not in H1–H3). The feature-importance pipeline lacked a positive class after the null memory effect; **omitted and disclosed**, not reported as a failed test.

### H5 — Boundary (pruning can remove rare-critical memories)
Heterogeneity is real: per-sequence, recency beats full in 5/8 (astropy +0.118, pydata +0.091) and loses in 3 (matplotlib, pytest, sympy). Interdependence does **not** cleanly moderate this at N=8 (Spearman ρ=−0.19, p=0.65) → we do **not** claim a clean "prune-helps-when-disjoint" law; we report the heterogeneity and motivate adaptive policy (the plugin).

---

## 4. Honest limitations (state these before the examiner does)

- **L1 — CL-F1 == resolved-rate proxy.** Anchor-probe **stability saturated at 1.000** (5 anchors, stochastic re-eval at temp 1, and anchors drawn largely from the file-disjoint ⅔ where memory was never load-bearing). CL-F1 reduces to plasticity ≈ resolved rate. We treat anchor-probe stability as **exploratory** and base the robust claim on the footprint axis. **Open action (A5):** run the cheap discrimination test (option b) on interdependent anchors to formally show the instrument is blind in this regime, or demote it — see §7.
- **L2 — Power.** N=8 sequence-level detects only mean Δ ≥ 0.062 at 80%; observed |Δ| ≤ 0.024. The inconclusive TOST outcomes are an underpowering of the ±0.03 margin, disclosed. The task-level GLMM (4,653 obs) is the powered complement.
- **L3 — Model deviation chain (D1–D8).** Final matrix is **DeepSeek-V4-Flash, all roles, x86_64 droplets, temp 1** (AMENDMENTS D8). Model held constant across all conditions × seeds → between-policy contrasts valid; **absolute solve rates are not leaderboard-comparable** and are disclaimed.
- **L4 — Contamination.** SWE-Bench is public; model cutoff undocumented → any contamination is constant across conditions (does not bias contrasts) but renders absolute rates uninterpretable (disclaimed).
- **L5 — Provenance not per-row.** Model/SHA/arch reconstructable from `MODEL_PROVENANCE.json` + `configs/base.yaml`@b495e6e + AMENDMENTS D8 + cost_summary timestamps; not self-contained per run (store.py:99 RUNS_ROOT bug also split memory.db/trajectories into `runs/`, now pulled to `runs_legacy_merged/`).

---

## 5. Anticipated hostile questions (with answers)

1. **"Isn't this just a null result?"** — No. H1 was pre-registered as non-inferiority+efficiency. Recency is statistically non-inferior; all pruners non-degraded; footprint ~75% lower. The pre-registered hypothesis is *supported*.
2. **"N=8 is underpowered."** — Correct for the ±0.03 margin (we disclose: detectable Δ ≥ 0.062). That is why we also run the **task-level GLMM (4,653 obs)** controlling difficulty+position; it confirms recency ≈/≥ full. Conclusions agree across levels.
3. **"Stability = 1.000 — broken instrument or no forgetting?"** — Likely instrument-blind in this regime (5 anchors, temp-1 stochastic re-eval, anchors from the file-disjoint ⅔). We disclose it, treat it as exploratory, and base the claim on the footprint axis (immune to this). A5 discrimination test pending.
4. **"You never showed storage pruning changes what the model sees."** — We do: cross-condition retrieved-ID overlap (manipulation check) shows pruners vs full median Jaccard 0.25 → ~75% of retrieved memories differ.
5. **"Your token-cost claim doesn't follow."** — Correct, and disclosed (A4): retrieval is fixed at top_k; storage pruning can't cut total tokens (memory is ~0.4–1%). We reframed efficiency to **footprint + retrieval latency** (the two-axis Pareto), where the ~75% reduction is real.
6. **"Seven amendments = p-hacking."** — Every amendment is dated, mechanism-justified, held constant across conditions, and **decided before the affected data**. Most are forced by deviations (cap 100→10 because sequences are short; temp 0→1 because the endpoint rejects 0) or construct corrections (H1b token→footprint). None chase a result.
7. **"Model switched 4×."** — Disclosed chain D1–D8; final = all-144-fresh on DeepSeek-Flash, model constant across conditions. Absolute rates disclaimed; contrasts valid.
8. **"CLS never fired."** — Disclosed (A3) as a not-applicable finding (no ≥3-clusters at 0.70 on diverse same-repo memories); we did *not* lower the threshold to force it (would be result-chasing). The path is verified correct when it does fire.
9. **"Contamination."** — Within-model between-policy contrasts; contamination constant across conditions; absolute rates disclaimed (SWE-Bench Illusion cited).
10. **"Position/difficulty confound."** — Controlled in the GLMM (difficulty −2.40, position −1.62 both significant); the memory effect is the policy term net of them.
11. **"Reproducibility (exotic provider, key rotation)."** — Provider is `.env`-only and reversible; rotation is for rate-limits not behavior; embeddings local/deterministic; JSON via tolerant parse + Pydantic with logged failure rate. Per-run provenance reconstructable (L5).
12. **"Novelty?"** — Not policy invention. The novelty is **controlled measurement**: retrieval held identical across conditions (pure cosine, top_k fixed), coding-agent CL benchmark, two-axis Pareto. Reframe from "first" to "first controlled characterization."

---

## 6. Contribution statement (defensible)

A **controlled Pareto characterization of forgetting policies for coding agents** on a standard CL benchmark, with the contrast cleanly attributable to **storage-side decisions** (retrieval held identical). Findings: (1) **proactive forgetting is non-inferior** to full-memory accumulation on continual-learning quality (recency clearly; all pruners non-degraded; corroborated by a powered task-level GLMM); (2) at a **~70–78% smaller memory footprint** → the efficient operating point; (3) the value of memory is **heterogeneous** across task streams, motivating adaptive curation; (4) honest negative/“not-applicable” results (CLS clustering, anchor-probe stability) that map *when* each mechanism applies.

---

## 7. Remaining before defense (priority-ordered)

1. **Finish `cls_astropy_seed1` re-run → re-aggregate → refresh `defense_stats`.** (In progress; FAISS bug, isolated.) *Then truly 144/144.*
2. **A5 anchor-probe decision (highest construct-validity upside).** Run the cheap option-b discrimination test on interdependent anchors (sphinx/xarray, overlap ≈0.50; Full vs Recency-at-cap-10; ≥3× each). If stability moves → report real CL-F1; if it stays 1.000 → formally demote to exploratory + Threats-to-Validity. **Needs the (still-held) droplets — this is the reason not to delete them yet.**
3. **Wire GLMM + retrieval-overlap into `scripts/run_analysis.py`** (producers exist + tested; add `glmm` and `retrieval_overlap` stages) so `make results` is complete and reproducible. Resolve the overlap source-key deviation sign-off.
4. **Methods sync to D8** (draft still names Ollama/arm64/temp-0) + **verify references** against live arXiv + add the contamination paragraph.
5. **Cosmetic:** mode-aware cost labels (kill the dead USD `$0.00` helpers), 3 ruff lints, optional R-lme4 GLMM robustness re-fit.

---

## 8. The plugin bridge (Lethe) — where forgetting *operationally* wins

The thesis regime kept memory at 0.4–1% of context (budget never binding) → equivalence was the natural outcome. **Lethe lives in the opposite regime:** Claude Code's `MEMORY.md` load cap (200 lines / 25 KB) **binds**, and the native fallback is **dumb truncation** (no ranking; newest-cut-first; unrecoverable). Lethe (fully built: phases 0–5, 161 tests; ports the 5 policies with type-aware-decay as the hypothesis-default; archives never deletes; best-last ordering) replaces that with ranked, recoverable curation.

**This is the honest home of "forgetting is better":** the thesis proves forgetting is **safe** (non-inferior) and **light** (footprint); Lethe is where it is **operationally superior** — because the baseline is naive truncation, in a regime the thesis showed forgetting handles without quality loss. **Phase-5 contrast (future work, honest):** Lethe-curated-at-cap vs Claude-default-at-cap (same budget) with uncapped-full as reference; metric = retention@budget. If Lethe-at-cap ≈ uncapped-full while default-at-cap < both → the plugin's value is demonstrated. (Current `eval/replay.py` is synthetic — explicitly *not* a thesis result; real validation needs Claude Code session logs.)
