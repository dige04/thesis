# THESIS_FINAL_v5.md — Priority-1 Revision Edits (P1.1–P1.5 + D2/D3)

> **Status:** Proposal. Per CLAUDE.md, locked files are not auto-modified. Review and tell me "apply" to write these into `THESIS_FINAL_v5.md`, or edit inline and I'll match your phrasing.
>
> **Scope:** All five P1 items from the editorial decision (`v5_editorial_decision.md`), plus the D2 (retrieval bottleneck) and D3 (a_{i,j} cost) resolutions named in the coaching note.

---

## Pre-edit findings — Alqithami 2025

Fetched arXiv:2512.12856 ("Forgetful but Faithful: A Cognitive Memory Architecture and Benchmark for Privacy-Aware Generative Agents", Saad Alqithami, 2025).

| Axis | Alqithami 2025 | This thesis |
|---|---|---|
| Domain | Privacy-aware *generative agents* (long-term interactive scenarios; social recall, narrative coherence) | AI *coding agents* (sequential bug-fix / API-change tasks) |
| Benchmark | **FiFA** (custom, introduced by the paper) | **SWE-Bench-CL** (Joshi et al. 2025; standard) |
| Six policies | FIFO, LRU, Priority Decay, Reflection-Summary, Random-Drop, Hybrid | No Memory, Full Memory, Random Prune, Recency Prune, Type-Aware Decay, CLS Consolidation |
| Conceptual overlap | FIFO ≈ Recency; Priority Decay ≈ Type-Aware (loose); Reflection-Summary ≈ CLS; Random-Drop = Random | three cousins; **no No-Memory / Full-Memory baselines in Alqithami** |
| Primary metric | Composite (narrative coherence + goal completion + social recall + privacy + cost) | CL-F1 (Plasticity × Stability harmonic mean from a_{i,j} matrix) |
| Retrieval held constant across policies? | Not stated in paper | **Yes — pure cosine, identical across all 6 conditions (locked invariant #19)** |
| Statistical framework | Composite-score reporting; tests not specified in abstract or §1 HTML | Pre-registered Wilcoxon + Holm + rank-biserial + BCa bootstrap on N=8 sequence means |
| Scale | 300 runs on FiFA | 144 runs on SWE-Bench-CL + 12 multi-model |
| Pre-registration of interpretations | Not stated | §19 (this revision: gated framings) |

**Verdict:** The works are non-replicating. The contribution claim of *this* thesis is unique on four axes: (1) coding-agent domain on a standard benchmark, (2) identical retrieval scoring as confound control, (3) No-Memory and Full-Memory boundary baselines, (4) pre-registered estimation-over-NHST analysis. No framing pivot needed; a §1.4 differentiation subsection suffices.

---

## EDIT 1 — Insert new §1.4 *Positioning vs. prior work* (after §1.3, before §2)

**Action:** Insert the following block immediately after the H5 line in §1.3 and before the `---` separator preceding §2. Renumber nothing else.

```markdown
## 1.4 Positioning vs. prior work

The six policies tested here overlap in name with prior work, but the *contribution claim is methodological*, not policy-set novelty. We use the standard SWE-Bench-CL benchmark (Joshi et al. 2025), hold retrieval scoring identical across all six conditions (locked invariant #19), include both No-Memory and Full-Memory boundary baselines, and pre-register the analysis (estimation-over-NHST per Cumming 2014; Wasserstein et al. 2019). The closest prior work in name — Alqithami (2025), six forgetting policies on a custom *FiFA* benchmark for privacy-aware generative agents — does not share the domain, benchmark, baselines, retrieval control, or statistical framework.

| Axis | Xiong 2025 (#5) | Alqithami 2025 (#13) | Lindenbauer 2025 (#6) | Joshi 2025 SWE-Bench-CL (#8) | **This work** |
|---|---|---|---|---|---|
| Domain | LLM agents, general | Privacy-aware generative agents | Coding agents (in-task) | Coding agents (sequential) | Coding agents (sequential) |
| Benchmark | mixed | FiFA (custom) | mixed | SWE-Bench-CL (standard) | **SWE-Bench-CL (standard)** |
| # forgetting policies | 1 (add-all) vs. 1 (none) | 6 | 1 (observation masking) | 1 (FAISS top-k) | **6** |
| Retrieval held constant across policies? | n/a (single policy) | not stated | n/a (different layer) | n/a (single policy) | **Yes — pure cosine, identical** |
| No-Memory / Full-Memory boundary baselines | partial | absent | absent | absent | **both included** |
| Primary metric | task success | composite (narrative + privacy + cost) | task success | CL-Plasticity / CL-Stability / CL-F1 | **CL-F1** |
| Statistical unit | per-task | per-run | per-task | per-sequence | **per-sequence (N=8)** |
| Pre-registered analysis / interpretation rules | no | no | no | no | **yes (§19)** |
| Effect-size + bootstrap CI as primary evidence | no | no | no | no | **yes (§15.1, §15.2)** |
| Scale | varies | 300 runs (custom benchmark) | varies | varies | **144 runs + 12 multi-model** |

**Delta contribution.** Combining (a) the SWE-Bench-CL benchmark with full a_{i,j} or anchor-probe CL-Stability estimation, (b) identical retrieval as confound control isolating *storage* policy from *retrieval* policy, (c) the No-Memory ↔ Full-Memory bracketing, and (d) pre-committed effect-size-gated interpretation framings, this thesis produces the first Pareto map of forgetting policies for coding agents on a standard CL benchmark, with the experimental contrast cleanly attributable to storage-side decisions. The price of this discipline is narrowness: we operate at fixed `top_k`, fixed retrieval scoring, same-repo retrieval, and a single base model in the primary experiment. We do not claim novelty of policy invention; we claim novelty of controlled measurement.
```

---

## EDIT 2 — Replace H1 in §1.3 with falsifiable two-part hypothesis (P1.1)

**Action:** Replace the H1 bullet in §1.3 with the block below. H2–H5 unchanged.

**Find:**

```markdown
- **H1.** Selective pruning policies achieve equal or better sequential performance compared to full-memory accumulation, while reducing operational cost. *(Win-win framing: if Full Memory doesn't degrade → forgetting validated as zero-cost optimization; if it degrades → forgetting validated as performance improvement.)*
```

**Replace with:**

```markdown
- **H1.** Selective pruning policies achieve **at least one** of: (H1a) non-inferior sequential performance vs. Full Memory, AND/OR (H1b) materially lower operational cost.
  - **H1a (performance non-inferiority).** For each pruning policy P ∈ {Random, Recency, Type-Aware, CLS}, the paired difference (P − Full Memory) in CL-F1 across the N=8 SWE-Bench-CL sequences lies within the equivalence margin **SESOI = ±0.03 CL-F1**, evaluated by a **two one-sided tests (TOST) procedure** with 95% BCa bootstrap CI (5000 iterations) on the sequence-level median paired difference.
    - *Outcome A (equivalence):* both one-sided tests reject; CI of median paired Δ ⊂ (−0.03, +0.03) → H1a confirmed for P.
    - *Outcome B (P superior):* one-sided test for "P ≤ Full Memory" rejects AND median Δ > 0 → H1a strictly satisfied for P.
    - *Outcome C (P degraded):* CI escapes the lower bound (median Δ < −0.03 with CI not crossing −0.03) → H1a rejected for P.
    - *Outcome D (inconclusive):* CI overlaps an SESOI bound → H1a inconclusive at N=8.
  - **H1b (cost reduction).** For each pruning policy P, the median paired Δ(total task API cost USD) vs. Full Memory satisfies median Δ ≤ **−20%** with 95% BCa CI upper bound below 0.
  - **H1 as a whole** is rejected for policy P iff H1a outcome is C (P degraded) AND H1b is not satisfied. Otherwise H1 stands for P, with the qualifying interpretation drawn from §19 according to which sub-outcome obtains.
  - **SESOI rationale.** ±0.03 in CL-F1 corresponds to ≈1 task out of 30 changing outcome per sequence on average — the smallest practitioner-meaningful difference at SWE-Bench-CL's typical sequence length. The threshold is pre-registered before Spike Week and locked.
```

**Also edit §1.1 wording (drop the "win-win" rhetoric):**

**Find** (in §1.1):

```markdown
**Do proactive forgetting and consolidation policies improve the sequential coding performance and operational efficiency of AI coding agents — including frontier models — compared with full-memory accumulation or no persistent memory?**
```

**Replace with:**

```markdown
**Under controlled retrieval, do proactive forgetting and consolidation policies achieve performance non-inferior to full-memory accumulation on sequential coding tasks while materially reducing operational cost — and which content-aware structure of forgetting matters most?**
```

Rationale: removes "including frontier models" (the 12-run multi-model arm cannot support a transfer claim — see P2.8); "win-win" replaced by the explicit dual-criterion structure of H1a/H1b; "controlled retrieval" foregrounds the methodological contribution.

---

## EDIT 3 — Replace §19 with effect-size-triggered framings (P1.5)

**Action:** Replace the entire §19 (sections 19.1 through 19.6) with the following block. Each framing is now gated on a specific triggering condition; non-triggered framings are unused.

**Find:** Sections 19.1–19.6 (from `# 19. Result interpretation rules` through the next `---` separator).

**Replace with:**

```markdown
# 19. Result interpretation rules (triggered framings)

Each interpretation framing is gated on a pre-specified effect-size trigger. Triggers are evaluated against the primary CL-F1 sequence-level Wilcoxon + r_rb + BCa CI for the 5 planned contrasts, plus the Pareto frontier on (CL-F1, total cost). Only the framing whose trigger fires is invoked in the Discussion. Multiple triggers may fire (e.g., 19.2 and 19.5 simultaneously); silently re-purposing a non-triggered framing post-hoc is prohibited.

## 19.1 If Full Memory wins
**Trigger.** For at least 3 of 4 pruning policies P ∈ {Random, Recency, Type-Aware, CLS}: median paired Δ CL-F1 (P − Full Memory) < −0.03 with 95% BCa CI excluding 0 (i.e., H1a outcome C), AND Full Memory is non-dominated on the Pareto (CL-F1, cost) frontier.

**Framing.** "Full memory accumulation may be beneficial when prior tasks contain reusable repository-specific knowledge. Within the SWE-Bench-CL same-repo regime tested here, pruning policies removed memories whose marginal value exceeded the noise they introduced. The value of forgetting is conditional, not universal." Strong contribution: identifies conditions where pruning is unsafe — feeds §18 failure-analysis case studies on which records pruning removed.

## 19.2 If Type-Aware Decay wins
**Trigger.** Type-Aware vs. Full Memory: H1a outcome A or B AND r_rb ≥ 0.3 AND Type-Aware strictly dominates Full Memory on the Pareto (CL-F1, cost) frontier. Additionally, Type-Aware vs. Random Prune: median paired Δ CL-F1 ≥ +0.02 with CI excluding 0.

**Framing.** "Memory quality matters more than memory quantity. Structured pruning by content type can preserve useful memories while reducing noise and cost. The failure-mode tier framework operationalizes this distinction." Gated analyses: §16 feature-importance trained on the data; §18 case studies on Type-Aware's correctly-retained `architectural` / `api_change` records.

## 19.3 If Random Prune matches Type-Aware Decay
**Trigger.** Type-Aware vs. Random Prune: |median paired Δ CL-F1| < 0.02 AND 95% BCa CI ⊂ (−0.03, +0.03) (TOST equivalence). AND both beat Full Memory on Pareto.

**Framing.** "Volume reduction may be the main benefit; the type/relevance heuristics tested here did not dominate naive sampling at N=8. The classifier-as-policy confound (§20.12) limits causal attribution. Future work: stronger content signals, classifier accuracy floor higher than the §10.3 threshold." Gated analyses: re-analysis with classifier-confidence covariate (P2.5); Anti-Type baseline (P2.4) is essential here.

## 19.4 If Recency Prune wins
**Trigger.** Recency vs. Full Memory: H1a outcome A or B AND Recency dominates Full Memory on Pareto AND Recency vs. Type-Aware: median paired Δ CL-F1 ≥ +0.02 with CI excluding 0.

**Framing.** "Recent experiences are most predictive on SWE-Bench-CL. Chronological locality dominates content-type signals at this sequence scale; the Anderson-Schooler power-law form is functionally indistinguishable from a recency cutoff for the d-values tested. Type-aware structure may pay off at longer sequence horizons or in domains with stronger content recurrence patterns."

## 19.5 If CLS Consolidation loses on Pareto
**Trigger.** CLS vs. Type-Aware (or whichever extractive policy ranks highest): median paired Δ CL-F1 within ±0.03 (statistically tied) AND median paired Δ(total cost) ≥ +20% (CLS more expensive) AND CLS is strictly dominated by Type-Aware on the Pareto frontier.

**Framing.** "Abstractive summarization paid the LLM-on-write tax without recovering a CL-F1 advantage at this sequence length. The dual-store CLS analogy (McClelland et al. 1995) is not realized by single-store cluster-summarize; we use 'Periodic Abstractive Consolidation' descriptively. CLS may be advantaged at sequence lengths beyond SWE-Bench-CL's 15–80-task range, or under harder context-budget constraints." Gated analyses: report CLS firing rate (P2.12) — if firing rate is < 30%, the result is uninformative.

## 19.6 If No Memory is competitive
**Trigger.** No Memory vs. Full Memory: H1a outcome A (equivalence) — CI of median paired Δ CL-F1 ⊂ (−0.03, +0.03). AND No Memory non-dominated on Pareto.

**Framing.** "The task sequence may have weak inter-task dependency. The retrieval system may not surface useful memories. The base model may already encode enough general coding knowledge to make episodic memory marginal at SWE-Bench-CL's task complexity. This is a strong publishable negative result; the implication for production memory systems is that vector-DB infrastructure should be evaluated against the No-Memory baseline directly." Gated analyses: §16 feature-importance becomes purely descriptive (memory had no average effect to explain).

## 19.7 If the retrieval Jaccard probe shows no contrast between storage policies
**Trigger.** Median across (task, condition-pair) of Jaccard overlap of retrieved memory-ID sets > 0.9 for most pruning-vs-Full-Memory pairs (see §11.5 and §20.11).

**Framing.** "At the locked retrieval budget (top_k=5, max_context_tokens=2000), storage-side pruning policies feed nearly identical prompts to the agent on most tasks; the experimental contrast on CL-F1 measures small-tail effects. This is itself a finding: in the frontier-model + top-k regime, the storage policy is dominated by the retrieval policy. Future work must vary the retrieval layer to isolate storage effects." This framing co-fires with whichever of 19.1–19.6 applies and modifies the causal claim attached to it.

## 19.8 Multi-framing combination rule
If multiple triggers fire, report each in order, and explicitly mark which framings are *primary* (based on the planned 5 contrasts) vs. *secondary* (based on derived metrics). HARKing — narrating a finding under a non-triggered framing — is prohibited.
```

---

## EDIT 4 — D2 resolution (retrieval bottleneck): Jaccard sanity probe (option A + option C)

### 4a. Insert new §11.5 *Cross-condition retrieval comparison log*

**Action:** Append the following subsection to §11 (after §11.4 Memory snapshots).

```markdown
## 11.5 Cross-condition retrieval comparison → `runs/{run_id}/retrieval_overlap.jsonl`

For each (task_id, condition-pair) where both conditions ran the same task with the same seed, compute and log:

```json
{
  "task_id": "django__django-12345",
  "seed": 2,
  "condition_a": "full_memory",
  "condition_b": "type_aware_decay",
  "retrieved_ids_a": ["MEM-001","MEM-007","MEM-091","MEM-188","MEM-303"],
  "retrieved_ids_b": ["MEM-001","MEM-007","MEM-091","MEM-188","MEM-303"],
  "jaccard_overlap": 1.0,
  "rank_correlation_spearman": 1.0
}
```

`jaccard_overlap = |A ∩ B| / |A ∪ B|`. Computed offline from existing `retrieved_memory_ids` fields in `task_results.jsonl`; no extra runs required.

**Pre-registered sanity check (§20.11):** if median Jaccard overlap across (task, condition-pair, seed) > 0.9 for the four pruning-vs-Full-Memory pairs, the storage-side contrast at the prompt is empirically small; §19.7 framing fires and the contribution claim restricts to "characterization of storage policies under fixed retrieval, in a regime where the retrieval bottleneck dominates."
```

### 4b. Insert new §20.11 *Retrieval-bottleneck confound and its empirical probe*

**Action:** Add as the next subsection in §20 (after §20.10, before §21).

```markdown
## 20.11 Retrieval-bottleneck confound (and how we detect it)

By locked invariant #19, retrieval is identical (pure cosine top-k) across all six conditions. By locked configuration `top_k=5` and `max_context_tokens=2000`, the *prompt* receives at most ~5 memories regardless of how many records the storage policy keeps. If pruning policies and Full Memory return overlapping top-5 sets on most tasks (e.g., because the highest-cosine records survive pruning by all policies), the experimental contrast on CL-F1 measures a small-tail effect, not the headline "memory policy matters" claim.

This is empirically testable via the Jaccard overlap probe (§11.5). Pre-registered decision rule:

- **Median Jaccard ≤ 0.5** across the four pruning-vs-Full-Memory pairs: contrast is well-identified at the prompt; storage policies drive observable retrieval differences.
- **Median Jaccard ∈ (0.5, 0.9):** moderate; storage policies differ on a substantial minority of tasks; standard interpretation applies but reported.
- **Median Jaccard > 0.9:** §19.7 fires; contribution claim restricts to "storage-side policy characterization under fixed retrieval, in a regime where retrieval dominates"; §1.1 title remains but §1.4 contribution paragraph is updated in the Discussion accordingly.

Reporting: §20 includes the Jaccard distribution histogram per condition-pair. Acceptance criterion #18 (§23): the probe must be reported regardless of outcome.
```

### 4c. Add to §23 acceptance criteria

```markdown
18. ✅ Cross-condition retrieval Jaccard-overlap report (§11.5, §20.11) for the four pruning-vs-Full-Memory pairs across all 8 sequences and 3 seeds.
```

---

## EDIT 5 — D3 resolution (a_{i,j} cost): demote full matrix; anchor probe becomes primary

### 5a. Rewrite §14.2 and §14.3 to swap primary/supplementary

**Action:** Replace §14.2 and §14.3 (everything from `## 14.2 Continual-learning (PRIMARY...` through the start of `## 14.4 Efficiency`).

**Replace with:**

```markdown
## 14.2 Continual-learning — Stability (PRIMARY: anchor-probe schedule)

Computing the full a_{i,j} matrix (Section 14.3) requires T(T−1)/2 re-evaluations per (sequence, condition, seed), which at 8 sequences × 6 conditions × 3 seeds and typical T ≈ 30–80 produces O(10⁴) extra agent runs. Under the §22 budget projection this is infeasible. We therefore make the **anchor-probe schedule** primary and the full matrix supplementary.

**Anchor-probe schedule.** For each sequence of length T, fix a deterministic anchor index set A = {1, 1+⌈T/k⌉, 1+2⌈T/k⌉, …} with **k=5 anchors** (so 5 anchor tasks per sequence; indices locked before Spike Week). At sequence positions p ∈ {⌈T/4⌉, ⌈T/2⌉, ⌈3T/4⌉, T} (four probe points), re-evaluate every anchor `a ∈ A with a ≤ p` against the memory snapshot taken after task `p`. Total re-evaluations per (sequence, condition, seed) is bounded above by 4·5 = 20, vs. ~T(T−1)/2 ≈ 435 for the full matrix at T=30.

**a_{i,j} entries collected:** for i ∈ A, j ∈ {⌈T/4⌉, ⌈T/2⌉, ⌈3T/4⌉, T}. The diagonal a_{i,i} for non-anchor i is read from per-task online results (always collected). Probed-stability is the only off-diagonal information collected in the primary protocol.

**CL metrics from the anchor probe:**

```python
# Online accuracy (Plasticity) — uses ALL tasks (diagonal)
CL_Plasticity = mean(a_{i,i} for i in range(T))

# End-of-sequence accuracy on anchors only
end_acc = mean(a_{i, T} for i in A)

# Anchor forgetting
forgetting_i = max(a_{i, p} for p in PROBES with p >= i) - a_{i, T}
CL_Stability_anchor = 1 - mean(forgetting_i for i in A)

# Primary metric
CL_F1 = 2 * CL_Plasticity * CL_Stability_anchor / max(CL_Plasticity + CL_Stability_anchor, 1e-8)
```

**Stochasticity handling.** `re_evaluate(task_i, snapshot_after_j)` re-runs the *agent* (not just re-scores a fixed patch) with the historical memory state from after task j and a clean repo checkout. At temperature 0 the agent is approximately deterministic but not guaranteed (provider-side load, tool-call tie-breaking). The primary protocol pre-registers **n=1 re-evaluation per (i, j) cell with the resulting variance treated as part of within-sequence noise**, mitigated by reporting Stability with 3-seed pooling. If a future budget supplement allows, the protocol upgrades to n=3 majority vote.

## 14.3 Continual-learning — full a_{i,j} matrix (SUPPLEMENTARY)

If the §22 budget permits at Week 7, the full off-diagonal a_{i,j} reconstruction (per Section 25.6) is run for **2 sequences × top-2 conditions × 1 seed = 4 cells**, providing a comparison between anchor-probed and densely-probed Stability estimates. This is sensitivity, not primary.
```

### 5b. Amend §17 to clarify Pareto cost axis

**Action:** Insert a clarifying paragraph at the top of §17.

**Find:**

```markdown
# 17. Pareto analysis

For each of 6 conditions, plot:
```

**Replace with:**

```markdown
# 17. Pareto analysis

**Cost-axis definition (lock).** The Pareto X-axis "total system API cost (USD)" includes only the operational cost the agent would pay in deployment: per-task LLM calls (main model + reflection model + classifier model) + consolidation LLM calls. It **excludes** the methodological cost of the a_{i,j} / anchor-probe re-evaluation (§14.2), which is a measurement overhead not borne by a production system using the same policy.

For each of 6 conditions, plot:
```

### 5c. Amend §23 to add fallback acceptance criterion

**Action:** Replace the existing "Minimum-acceptable scope" block in §23.

**Find:**

```markdown
**Minimum-acceptable scope** (if compute tight at Week 6):

```
6 sequences × 6 conditions × 3 seeds = 108 runs   (drop 2 hardest sequences)
or
8 sequences × 6 conditions × 2 seeds = 96 runs   (drop 1 seed)
```

Document the trade-off in Limitations.
```

**Replace with:**

```markdown
**Minimum-acceptable scope** (if compute tight at Week 6, listed by priority of fallback):

1. **Anchor-probe Stability only** (§14.2) with no §14.3 supplementary full matrix. Default and primary; no scope reduction needed.
2. **Drop 1 seed** if total cost projection at Week 6 ≥ stop-loss threshold (§22): 8 sequences × 6 conditions × 2 seeds = 96 runs. Document in Limitations.
3. **Drop 2 hardest sequences** if (2) is also exceeded: 6 sequences × 6 conditions × 3 seeds = 108 runs. Document in Limitations.
4. **Drop CLS Consolidation** if (3) is also exceeded: 8 sequences × 5 conditions × 3 seeds = 120 runs minus CLS = 120. CLS is the most expensive policy due to LLM-on-write tax; dropping it preserves the H1a/H1b core contrasts.

Document any invocation of (2)–(4) explicitly in the Limitations chapter with the cost projection that triggered it.
```

---

## EDIT 6 — §22 budget projection + stop-loss (P3-priority but the user requested in step 3)

### 6a. Insert §22.1 *Budget projection and stop-loss*

**Action:** Insert as the first subsection of §22 (push the existing risk-registry table to §22.2).

```markdown
## 22.1 Budget projection and stop-loss

**Per-task cost model (rounded estimates, GPT-5.4 at assumed $0.005/1K input + $0.015/1K output tokens; refine after Spike Day 2 cost telemetry):**

| Component | Per-task tokens (typ.) | Per-task USD (typ.) |
|---|---|---|
| Main model (20 steps × ~3000 in + ~500 out / step) | ~70K | ~$0.40 |
| Reflection (§9.2, gpt-4o-mini) | ~5K | ~$0.005 |
| Classifier (§9.3, gpt-4o-mini) | ~1K | ~$0.001 |
| **Total per online task** | **~76K** | **~$0.41** |

**Forward run projection (144 runs × average 30 tasks/sequence):**

- 4320 online tasks × $0.41 ≈ **$1,770** primary forward cost.

**Anchor-probe re-evaluation projection (§14.2):**

- Per (sequence, condition, seed): up to 20 re-evaluations × $0.41 ≈ $8.20.
- Across 144 cells: 144 × $8.20 ≈ **$1,180** anchor-probe cost.

**Consolidation LLM cost (CLS only, §8 P5):**

- ~6 consolidation rounds per sequence × ~5 records summarized × 350 output tokens ≈ ~15K tokens per round → ~$0.05/round.
- Across CLS cells (24 cells × 6 rounds) ≈ **$8** consolidation cost.

**Multi-model validation (12 runs, Haiku/4o-mini at lower per-token cost):**

- 12 runs × 30 tasks × ~$0.10 ≈ **$36**.

**Total expected cost: ~$3,000** (forward + anchor probe + consolidation + multi-model). Spike Week pilot adds ~$50. Eval_v3 Docker compute is paid by the VPS (sunk).

**Stop-loss triggers and decision tree:**

| Trigger | Threshold | Action |
|---|---|---|
| Week-1 spike actual > 1.5× projected | > $75 for 3 smoke tasks | Recompute per-task cost; abort if real per-task > $1.50 |
| Week-3 pilot actual > 1.5× projected | > $300 for 12 pilot runs | Reduce `max_steps_per_task` from 20 → 15 (re-document as a tighter limit, locked) |
| Week-5 projected total > $5,000 | Linear extrapolation | Invoke §23 fallback (2): drop 1 seed → 96 runs |
| Week-6 projected total > $7,000 | Linear extrapolation | Invoke §23 fallback (3): drop 2 hardest sequences → 72 runs |
| Week-6 projected total > $10,000 | Linear extrapolation | Invoke §23 fallback (4): drop CLS Consolidation → 120 runs |
| Any single day burn > $400 | Daily cost telemetry | Pause runs; investigate; do not auto-restart |

**Pre-registered: the actual cost numbers (per-task, per-sequence, total) are reported in the thesis Limitations section regardless of outcome, alongside the realized scope after any fallback.**

**Note on `a_{i,j}` supplementary (§14.3).** The supplementary full-matrix sensitivity (4 cells × ~T²/2 re-evaluations ≈ 1800 extra re-evaluations × $0.41 ≈ $740) is only invoked if Week-7 cumulative cost is < $3,000 and remaining budget ≥ $1,000.
```

### 6b. Move existing §22 risk table to §22.2

**Action:** Rename existing `# 22. Risk registry` to `## 22.2 Risk registry` and add a new top-level heading `# 22. Budget, risks, and stop-loss` above both subsections.

---

## EDIT 7 — Small companion edits for coherence

### 7a. §1.4 reference list update

Confirm Alqithami citation #13 in §26 reads:

```markdown
| 13 | Alqithami (2025). *Forgetful but Faithful: A Cognitive Memory Architecture and Benchmark for Privacy-Aware Generative Agents.* arXiv:2512.12856. | 6 forgetting policies, FiFA benchmark — closest by name, different domain (generative agents, privacy) |
```

### 7b. §0.1 frozen decisions table: add SESOI + Jaccard probe

Append two rows to the frozen-decisions table in §0.1:

```markdown
| 27 | SESOI for H1a TOST | ±0.03 CL-F1 (sequence-level median paired Δ) |
| 28 | Jaccard overlap probe (§11.5, §20.11) | Median ≤ 0.5 = well-identified; > 0.9 = §19.7 fires |
| 29 | Primary CL-Stability estimator | Anchor probe (§14.2), k=5, 4 probe points; full matrix is supplementary |
```

### 7c. §15.5 reporting template — add TOST line

**Find** (in §15.5 Reporting template):

```markdown
  Conclusion: Type-Aware Decay matches Full Memory on correctness (CI includes zero)
  while substantially reducing token cost. Pareto-favorable.
```

**Replace with:**

```markdown
  TOST (H1a, SESOI=0.03): equivalence rejected for the lower bound (p_TOST_lower = 0.012)
                          equivalence rejected for the upper bound (p_TOST_upper = 0.008)
                          ⇒ Type-Aware Decay is statistically equivalent to Full Memory on CL-F1.

  Conclusion: Type-Aware Decay achieves H1a equivalence with Full Memory on correctness
  AND substantially reduces token cost (H1b satisfied). Pareto-favorable.
```

---

## Application checklist

When you say "apply", I will execute these edits to `THESIS_FINAL_v5.md` in this order, with a verification read after each, and add a final git-diff summary in `results/reviews/v5_p1_revision_applied.md`:

- [ ] EDIT 1 — Insert §1.4 (~750 words; net document growth)
- [ ] EDIT 2a — Replace H1 in §1.3
- [ ] EDIT 2b — Edit §1.1 central question wording
- [ ] EDIT 3 — Replace §19 (six subsections → eight gated subsections + multi-framing rule)
- [ ] EDIT 4a — Insert §11.5
- [ ] EDIT 4b — Insert §20.11
- [ ] EDIT 4c — Append §23 acceptance criterion #18
- [ ] EDIT 5a — Replace §14.2 and §14.3 (primary/supplementary swap)
- [ ] EDIT 5b — Insert clarifying paragraph at top of §17
- [ ] EDIT 5c — Replace §23 minimum-acceptable-scope block
- [ ] EDIT 6a — Insert §22.1
- [ ] EDIT 6b — Restructure §22 headings
- [ ] EDIT 7a — Update reference #13 detail in §26
- [ ] EDIT 7b — Append rows 27–29 to §0.1 frozen-decisions table
- [ ] EDIT 7c — Update §15.5 reporting template

**Items NOT touched in P1** (deferred to Week-3+):
- P2 items (Anti-Type baseline, classifier-as-policy probe, H4 rewording, §20.11 ecological validity, CLS clustering algo spec, missing references)
- P3 minor items
- Implementation work (Jaccard probe is a logging change in `task_results.jsonl` post-processing; Spike-Week task)

---

*Awaiting your "apply", or inline edits to this proposal file before application.*
