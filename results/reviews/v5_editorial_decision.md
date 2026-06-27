# Editorial Decision — THESIS_FINAL_v5.md

**Manuscript:** *Memory Pruning and Forgetting Policies for AI Coding Agents — Impact on Performance Across Sequential Tasks* (master's thesis design/protocol, pre-data)
**Review panel:** EIC + Methodology (R1) + Domain (R2) + Perspective (R3) + Devil's Advocate (DA)
**Date:** 2026-05-25
**Mode:** academic-paper-reviewer · full

---

## Decision: **MAJOR REVISION (of the protocol, before Spike Week locks)**

This is not a rejection of the project. The methodological discipline (locked retrieval scoring, orthogonal type/outcome axes, estimation-over-NHST, pre-committed interpretation rules, comprehensive logging) is **well above the median for a master's protocol**, and the design is internally tighter than most published agent-memory comparisons. As a master's thesis the project is a clear pass; the major revision applies to publishability-beyond-thesis and to the protocol's own internal coherence on three load-bearing claims.

**IRON RULE invoked:** Devil's Advocate raised six CRITICAL findings (C1–C6). Per the panel's standing rule, Accept is precluded. The CRITICAL findings concentrate on **falsifiability of H1**, **the retrieval bottleneck collapsing the experimental contrast**, and **the a_{i,j} cost model**. Two of three are also independently flagged at CRITICAL/MAJOR severity by Methodology and EIC. This is panel consensus, not an outlier.

---

## Panel consensus map (who flagged what, at what severity)

| # | Issue | EIC | R1 (Method) | R2 (Domain) | R3 (Perspect.) | DA | Consensus |
|---|---|---|---|---|---|---|---|
| 1 | **H1 framed as unfalsifiable "win-win"** | Major | — | — | High | CRITICAL | **CRITICAL** (3/5) |
| 2 | **Differentiation from Alqithami 2025 missing** | Major | — | Critical | — | Major | **CRITICAL** (3/5) |
| 3 | **`a_{i,j}` matrix cost & feasibility** | Major | CRITICAL | — | High | CRITICAL | **CRITICAL** (4/5) |
| 4 | **Top-k=5 / 2000-token retrieval bottleneck makes all 6 conditions feed identical 5-item prompts; storage-side policy effects only fire on long-tail records the agent never sees** | — | Major | Medium | — | CRITICAL | **CRITICAL** (3/5) |
| 5 | **Equivalence claims w/o TOST; CI-includes-zero ≠ equivalence** | — | Minor | — | High | Major | **MAJOR** (3/5) |
| 6 | **Type-Aware decay parameters: 5 free knobs from 12-run pilot; blog-grounded weights** | Major | MAJOR | High | High | Major | **MAJOR** (5/5)** |
| 7 | **Type-Aware Decay ≡ Recency Prune with type-knobs (Anti-Type baseline absent)** | — | — | — | — | Major | **MAJOR** (DA-only but uncontested) |
| 8 | **Classifier accuracy contaminates Type-Aware policy (confound between policy and classifier quality)** | — | Major (§10.3 CI logic) | — | — | Major | **MAJOR** (2/5) |
| 9 | **Multi-model validation (12 runs) too small to support transfer claim in title** | Major | — | — | — | Minor | **MAJOR** (2/5) |
| 10 | **CLS theoretical grounding decorative, not load-bearing; missing dual-store** | — | — | High | High | — | **MAJOR** (2/5) |
| 11 | **Anderson-Schooler analogy is structural, not mechanistic — frequency exponent 0.5 uncited** | — | — | Low | High | Major (M2) | **MAJOR** (3/5) |
| 12 | **5-type taxonomy anchored on a blog (Fastpaca), not a peer-reviewed source** | — | — | High | — | Major | **MAJOR** (2/5) |
| 13 | **Missing core agentic-memory references (MemoryBank, A-MEM, Reflexion, Generative Agents retrieval triplet)** | — | — | High | — | — | **MAJOR** (R2-only, uncontested) |
| 14 | **H4 "analysis paralysis" proxy weak; max_steps=20 may also truncate the very behavior H4 measures** | Minor | Major (#9: H4 incompatible with locked retrieval budget) | — | Medium | — | **MAJOR** (3/5) |
| 15 | **GLMM `(1|task_id)` should be PRIMARY, not sensitivity** | — | Major | — | — | — | **MAJOR** (R1-only) |
| 16 | **Multiple-comparison family-wise control only covers 5 contrasts, not efficiency / GLMM / feature-importance families** | — | Major | — | — | — | **MAJOR** (R1-only) |
| 17 | **Ecological validity (frozen issues, no user state, single-thread, clean repo each task) not in §20** | — | — | — | High | — | **MAJOR** (R3-only) |
| 18 | **Same-repo-only retrieval undermines "continual learning" framing in title** | — | — | Medium | Medium | — | **MAJOR** (2/5) |
| 19 | **Pre-registration is partial: §19 pre-writes a publishable narrative for every outcome** | Minor | — | — | Medium | CRITICAL (C4) | **MAJOR** (3/5) |
| 20 | **CLS pre-condemned (§19.5 already writes its eulogy); why spend 24 runs on a strawman?** | — | — | — | — | Major | **MAJOR** (DA-only) |
| 21 | **Reflection/classifier LLM calls confound the cost axis (cost story may measure reflection volume, not memory cost)** | — | — | — | — | Major | **MAJOR** (DA-only) |
| 22 | **Sequence-level Wilcoxon assumes paired sequences are i.i.d., but within-sequence dependence varies *with the treatment* (Full Memory ≠ No Memory)** | — | — | — | — | Major | **MAJOR** (DA-only) |
| 23 | **`max_records=100` rarely binds on short sequences → pruning policies are no-ops on most cells** | — | — | — | — | Major | **MAJOR** (DA-only) |
| 24 | **Budget stop-loss number absent; risk of mid-experiment scope collapse** | — | — | — | High | — | **MAJOR** (R3-only) |
| 25 | **Open-science deliverables (OSF pre-reg timestamp, code/data release plan) under-specified** | — | — | — | Low | — | **MINOR** |
| 26 | **"GPT-5.4" model identity & embedder closure → reproducibility decay** | — | — | — | — | Minor (m3, m5) | **MINOR** |
| 27 | **OpenMem (Week 10) appears once, never specified** | Minor | — | — | Medium | — | **MINOR-MAJOR** |
| 28 | **Embedding payload omits reflection summary; budget has headroom** | — | — | Low-Med | — | — | **MINOR** |

** Item #6 is the only issue all five reviewers independently flagged.

---

## Devil's Advocate CRITICAL findings (cannot be ignored per IRON RULE #4)

- **C1.** H1 is structurally unfalsifiable. Every outcome confirms it.
- **C2.** Six "memory policies" are six *storage* policies all funneled through identical top-k=5, 2000-token retrieval. The contrast operates only on the unretrieved tail.
- **C3.** Wilcoxon at N=8 with Holm cannot fire except under near-unanimous agreement; §15.5 then interprets non-significance as equivalence without TOST.
- **C4.** §19 pre-writes a publishable interpretation for every possible outcome — pre-registration becomes a hedge net.
- **C5.** Sequence-level i.i.d. paired assumption violated treatment-dependently (Full Memory has high within-sequence dependence; No Memory has zero).
- **C6.** `a_{i,j}` off-diagonal reconstruction is ~T²/2 agent re-runs per cell; total ≈ tens of thousands of extra Docker runs; either silently dropped to anchor probes (invalidating the primary CL-F1 estimator) or budget is wildly under-stated.

All six must be addressed in writing before Spike Week locks.

---

## Editorial Decision Letter

**Recommendation: Major Revision.** The protocol is publishable as a master's thesis design and (with revision) as a workshop pre-registration (NeurIPS Memory in Foundation Models, ICLR DL4C, NeurIPS Agents workshop). For a main-conference ML or SE venue, the contribution claim needs sharpening (#2, #9, #13) and at least two of the three CRITICAL design issues (#1, #4) need structural fixes — #3 needs a defensible cost-and-fallback plan.

The strengths are **real and unusual** for this stage of work: identical retrieval scoring across conditions, orthogonal type/outcome, estimation-over-NHST, full snapshot logging, explicit anti-creep manifesto, and pre-committed result framings. These should be preserved. The concerns are about **how the story is told and which claims the design actually licenses**, not about the underlying engineering plan.

The DA's central observation is correct and panel-confirmed: as written, this is a clean test of *storage* policies under a tight retrieval bottleneck, not a clean test of *memory* policies in the broader sense. That can be a contribution — but only if it is *named* as such and not sold as "do forgetting policies improve sequential coding performance."

---

## Revision Roadmap — Priority Ordered

Each item formatted to drop directly into `academic-paper` revision mode.

### Priority 1 — CRITICAL (must address before Spike Week locks)

**P1.1 Make H1 falsifiable.** *Source: EIC §2; DA C1, C4; R3 §4.*
- Replace §1.3 H1 single statement with two sub-hypotheses, each with a pre-specified effect-size threshold:
  - **H1a (performance non-inferiority):** Type-Aware Decay's CL-F1 lies within ±0.03 of Full Memory's CL-F1, evaluated as TOST equivalence on the paired sequence-level differences with smallest-effect-size-of-interest (SESOI) = 0.03, 95% CI. Rejected if CI escapes ±0.03 in either direction.
  - **H1b (cost reduction):** Type-Aware Decay's median paired Δ(total cost) ≤ −20% vs Full Memory.
- Drop the "win-win" language in the abstract and §1.1.
- Add: "H1 is rejected if H1a fails." This is the falsifier the manuscript currently lacks.

**P1.2 Address the retrieval bottleneck or rename the contribution.** *Source: DA C2; R1 #9; R2 #7.*
- Option A (recommended): Add an explicit experimental section testing whether storage-side policy differences are observable at the retrieval layer. Pre-register a sanity probe: for each (task, condition-pair), log the Jaccard overlap of retrieved memory-ID sets. If overlap > 0.9 in the median, the conditions are indistinguishable at the prompt and any observed CL-F1 difference is attributable to something other than the policy mechanism.
- Option B: Promote Ablation E (append-all) into the main matrix on 2 sequences × 1 seed (12 extra runs), so a genuine prompt-side contrast exists.
- Option C: Rename the contribution as "Storage-side memory budget policies under fixed retrieval." Honest, but narrows the headline.
- Whichever option, document in §1 and §20.

**P1.3 Reconcile `a_{i,j}` cost with realistic budget.** *Source: EIC §3; R1 #1; R3 §9; DA C6.*
- Compute and publish in §22 (Risk registry) an explicit budget projection: USD + wall-clock + Docker-hours for the full off-diagonal reconstruction at 8 seq × 6 cond × 3 seeds.
- Decide whether `re_evaluate(sequence[i], snapshot, config)` (§25.6) re-runs the agent (expensive, stochastic) or re-scores an existing patch against the snapshot (cheap, deterministic but limited). Specify in pseudocode. If the former, pre-register `n=3` re-runs with majority vote.
- Define a stop-loss: "If Week-5 cumulative cost exceeds $X, fall back to a fixed-anchor-probe schedule (every 5 tasks, 5 anchors) and note Stability is estimated from the anchor probe, not the full matrix."
- Explicitly state in §17: Pareto cost axis = online + consolidation cost only, excluding methodological re-evaluation cost.

**P1.4 Differentiate from Alqithami (2025) in prose.** *Source: EIC §1; R2 §1 (CRITICAL); DA M3.*
- Add new subsection §1.4 *Positioning vs. prior work* with an explicit table: columns {Alqithami 2025, Xiong 2025, Lindenbauer 2025, Joshi 2025 SWE-Bench-CL, this work} × rows {benchmark, # policies, retrieval held constant?, primary metric, statistical unit, model, N (runs)}.
- Name the delta contribution in one paragraph: SWE-Bench-CL specifically + identical-retrieval-confound control + Pareto framing + pre-committed interpretation rules.
- Without this, novelty rejection at any peer venue is one pass away.

**P1.5 Tighten §19 pre-registered interpretations into commitments, not narratives.** *Source: DA C4; R3 §4; EIC minor.*
- Each §19.x must include: (i) the *exact* effect-size threshold that triggers this framing, (ii) the *primary* contrast it applies to, (iii) what additional analysis is gated on the trigger. Example for §19.2: "*This framing activates only if H1a is rejected in the Type-Aware-vs-Full direction AND r_rb ≥ 0.3 AND the Pareto frontier places Type-Aware Decay strictly above Full Memory.*"
- This converts §19 from "any outcome is fine" to "specific outcome → specific narrative."

### Priority 2 — MAJOR

**P2.1 Statistical reporting hygiene.** *Source: R1 #3, #4, #5, #6, #8, #10; DA C3, C5, M4.*
- §15: report the exact minimum Holm-adjusted p achievable at N=8 numerically; concede Wilcoxon is descriptive; r_rb + BCa CI is primary evidence.
- Pre-register `scipy.stats.wilcoxon(..., method='exact')` and pinned r_rb estimator (Kerby 2014).
- Make `(1|task_id)` PRIMARY GLMM spec, not sensitivity (dropping it INCREASES pseudoreplication). Pre-register Bayesian fallback (`BinomialBayesMixedGLM`) as primary if `glmer` is singular. (R1 #5)
- Family-wise alpha: declare an explicit hierarchy — CL-F1 5 contrasts (primary, Holm); efficiency 5 contrasts per metric (secondary family, gated on CL-F1 contrast surviving); GLMM coefficients and feature-importance reported with CIs only, no NHST claims. (R1 #3)
- Replace 5-fold-stratified-by-sequence CV in §16.5 with leave-one-sequence-out (k=8). (R1 #6, DA m8)
- Pre-register TOST procedure with SESOI for any equivalence claims. (R1 #8, DA M4)
- Pre-register a consistency filter on 3-seed sign agreement; flag sequences with seed disagreement in sensitivity analysis. (R1 #10)
- Classifier audit (§10.3): use Clopper-Pearson lower CI bound as decision boundary, not point estimate. (R1 #7)

**P2.2 De-cosmetic the cognitive-science framing.** *Source: R2 §5, §6; R3 §1, §2.*
- §8 P4: drop "Anderson & Schooler grounding" rhetoric; reframe as "power-law form with one calibrated decay knob per type, motivated by but not derived from A&S." Cite Anderson, Fincham & Douglass (1999) for the frequency exponent or label 0.5 as a fixed design choice.
- §8 P5: rename "CLS Consolidation" to "Cluster-Summarize Consolidation" or "Periodic Abstractive Consolidation." McClelland 1995 as a *distant* inspirational analogy only — the protocol does not implement a dual-store.
- §5.1 / §8 P4: anchor the 5-type taxonomy to at least one peer-reviewed bug-categorization paper (Catolino et al. 2019; Herzig, Just, Zeller 2013) in addition to the Fastpaca blog. Add an "other / mixed" residual category to the §10.2 audit so taxonomy coverage is measurable.

**P2.3 Fix the calibration story for Type-Aware Decay.** *Source: EIC §6; R1 #2; R2 §6; DA M2.*
- 11 free knobs (5 base × 5 decay × 1 exponent) cannot be calibrated from a 12-run pilot. Pick one of:
  - **(a)** Declare base/decay values as a-priori theoretical (Fastpaca-style tiers); the pilot is sanity-check only, not calibration. State this.
  - **(b)** Collapse to a single global `d` scaled by tier rank (`d_tier = d_base × tier_multiplier`) — 1 free parameter, calibrable from 12 runs.
  - **(c)** Drop the calibration step entirely and lock the published values; treat any deviation as future work.
- Pre-register a pass/fail criterion: if Type-Aware Decay does not beat Random Prune on the pilot's 2 sequences, fall back to uniform decay and report this transparently (do not silently re-tune).

**P2.4 Add Anti-Type baseline to separate "type matters" from "this is recency in disguise."** *Source: DA M1.*
- Add one extra condition: Type-Aware Decay with `decay_d` values randomly permuted across types (architectural ↔ config, etc.). 8 seq × 3 seeds = 24 extra runs.
- If Type-Aware beats Anti-Type, the type signal carries weight. If they tie, Type-Aware Decay = Recency Prune + noise.
- Without this, H2 ("WHAT is forgotten matters") is untestable as designed.

**P2.5 Address classifier-as-policy confound.** *Source: DA M8; R1 #7.*
- Pre-register a per-policy sensitivity analysis: re-run analysis with classifier labels replaced by gold (manual audit) labels on the 150 audited items only; report whether Type-Aware Decay's ranking changes.
- Log per-task classifier confidence; report mean confidence as a covariate in the GLMM.

**P2.6 Strengthen H5 operationalization.** *Source: R2 §8.*
- Pre-register a "rare-critical memory" identifier: memories with `architectural` type AND `file_overlap > 0.5` with a later task AND `use_count ≥ 2`. Then test: fraction of failed tasks under each pruning policy in which a rare-critical memory was archived before retrieval.
- Without this, H5 is not falsifiable.

**P2.7 Repair H4.** *Source: R1 #9; R3 §3.*
- Either (a) drop "analysis paralysis" label and reframe as "memory-induced action inflation" with no causal claim, or (b) explicitly note H4 is observable only via *retrieved-content quality changes* under fixed prompt length, not prompt-growth dynamics. The locked retrieval budget makes the "growing context → paralysis" mechanism impossible.
- Acknowledge that `max_steps_per_task=20` may truncate H4's signal; pre-register `timeout=true` rate as the actual H4 indicator if step-cap saturation > 20% in any condition.

**P2.8 Multi-model validation (§12.2): commit or downgrade.** *Source: EIC §4; DA m1.*
- Either expand to 6 conditions × 4 sequences × 2 seeds = 48 runs (so within-condition variance is measurable), or rename "validation" → "exploratory cross-model probe" in the abstract and §1.
- "Including frontier models" in §1.1 is currently unsupported; either restrict the contribution claim to GPT-5.4 or expand the multi-model arm.

**P2.9 Missing references.** *Source: R2 §2.*
- Add to §26 and discuss in text: **MemoryBank (Zhong et al. 2024, AAAI)** — the closest prior art; foundationally important. **A-MEM (Xu/Yu et al. 2024)**. **Reflexion (Shinn et al. 2023, NeurIPS)** in §9. **Generative Agents (Park et al. 2023)** importance/recency/relevance triplet in §7 and §8 P4 prose, not just the reference table. **Catolino et al. 2019** or **Herzig, Just, Zeller 2013** for bug taxonomy in §5.1. **Cohen 1960** for kappa in §10.2.

**P2.10 Ecological validity section.** *Source: R3 §6.*
- Add §20.11: results are bound to (offline, single-thread, frozen-issue, same-repo, clean-repo-every-task, no-user-state, one-record-per-task, top-k=5 retrieval) regime. State explicitly that Mem0/Letta/Zep-style deployment surfaces are out of scope.

**P2.11 Rename or rescope the "continual learning" framing.** *Source: R2 §10; R3 §8.*
- Same-repo retrieval excludes the main CL phenomenon (cross-task / cross-domain transfer). Reframe contribution as "intra-domain sequential learning" or "in-repo episodic memory" in the title or §1, OR elevate cross-repo (Ablation D) to a secondary main experiment with 8 seq × 1 seed = 8 extra runs.

**P2.12 CLS Consolidation — concrete specification.** *Source: R2 §4.*
- Specify the clustering algorithm (HDBSCAN? agglomerative? linkage?). Specify the similarity measure (cosine on embedding? Jaccard on `files_touched`? hybrid?).
- Log the per-task firing rate of CLS; report fraction of consolidation rounds with empty clusters.
- If CLS rarely fires on short sequences, declare in advance which sequences are CLS-informative.

**P2.13 Budget stop-loss.** *Source: R3 §9.*
- Add to §22: explicit stop-loss number (USD), a decision tree if triggered, and which scope reductions are pre-approved.

**P2.14 Sequence-mean i.i.d. violation.** *Source: DA C5.*
- Acknowledge in §15 that within-sequence dependence varies systematically by treatment. Either (a) report sequence-level variance estimates per condition and use them as weights, or (b) frame Wilcoxon as a rank-only test that does not assume equal sequence variance.

### Priority 3 — MINOR

- **P3.1.** Replace embedding ceiling drift (§0.1 #18 says <8K; §5.3 enforces <7500). Pin one value. (EIC minor)
- **P3.2.** Pre-commit "top-3 conditions" selection rule for §12.2 (e.g., "top-3 by Pareto rank on CL-F1 vs cost"). (EIC minor)
- **P3.3.** Specify OpenMem deliverable (§21 Week 10) or downgrade to "Future Work." (EIC minor; R3 §7)
- **P3.4.** Operationally define `syntax_error_rate` in §14.6 — how is a syntax error detected from `run_command` output? (EIC minor)
- **P3.5.** Add to §23: "Thesis is complete and submittable regardless of which condition wins." (EIC minor)
- **P3.6.** Pre-register OSF / AsPredicted timestamp and code/data release plan. (R3 §10)
- **P3.7.** Verify or mark as preprint placeholders the 2026 arXiv references with future IDs (Shen 2026, Zhu 2026). (EIC minor)
- **P3.8.** Embedding payload — either justify omission of reflection `test_summary` empirically (token-budget audit) or add it. (R2 §9)
- **P3.9.** Document per-component seed table (what each seed controls). (R1 reproducibility)
- **P3.10.** Lock the anchor-probe schedule deterministically before Spike Week. (R1 reproducibility)
- **P3.11.** Note carbon/energy cost in §22. (DA stakeholder)
- **P3.12.** Document the single-rater problem for §10.2 (Cohen's κ requires two raters); state plan or accept as limitation. (DA stakeholder)
- **P3.13.** Cite Liu et al. 2024 effect size when invoking "Lost-in-the-Middle" fix in §7.4. (DA m9)

---

## Acceptance criteria for the revision

The revised protocol is ready to lock and start Spike Week when:

1. H1 is reformulated with a pre-specified equivalence margin (P1.1).
2. The retrieval-bottleneck question (P1.2) is resolved by one of the three named options, documented in §1 and §20.
3. `a_{i,j}` cost (P1.3) has a published budget projection, a specified `re_evaluate` implementation, and a stop-loss fallback.
4. Alqithami 2025 differentiation table exists in §1.4 (P1.4).
5. §19 framings are gated on explicit effect-size triggers (P1.5).
6. Type-Aware calibration story is one of the three options in P2.3.
7. Anti-Type baseline (P2.4) is either added or its absence is explicitly documented as limiting H2.
8. Equivalence claims use TOST with declared SESOI (part of P2.1).
9. GLMM has `(1|task_id)` as primary; family-wise alpha hierarchy declared (P2.1).
10. Missing references (P2.9) added.

Items 11–28 in the consensus map are MAJOR/MINOR and should be addressed but do not gate Spike Week start.

---

## Strengths to preserve (do not lose these in revision)

- **Identical retrieval across conditions (§0.1 #19).** This is a real methodological contribution. Foreground it in §1.
- **Estimation-over-NHST (§15.1).** Cite Cumming/Wasserstein with conviction.
- **Orthogonal type × outcome (§5.1).** Conceptually correct.
- **Causal humility (§16, §20.10).** Right side of a frequent over-claim in this literature.
- **Comprehensive logging schema (§11).** Publication-grade.
- **Anti-creep manifesto (§24).** Real commitment device.
- **Pre-committed interpretation framings (§19).** Fix the trigger problem (P1.5) but keep the spirit.
- **Best-item-LAST injection order (§7.4).** Operationally sound, well-cited.
- **3 seeds for all 6 conditions, not just stochastic ones (§0.1 #8).** Better-than-standard practice.

---

## Confidence in this decision

Synthesizer confidence: **4/5.** Three CRITICAL items have ≥3-reviewer consensus; the panel is convergent on H1 falsifiability, prior-art differentiation, the retrieval bottleneck, and `a_{i,j}` cost realism. The two areas of genuine reviewer disagreement (severity of H4 critique; whether ecological validity is a MAJOR or merely a framing issue) are handled by inclusion in the roadmap at honest severity.

The Devil's Advocate raised CRITICAL findings that were independently corroborated, so IRON RULE #4 mandates not-Accept. Major Revision is the correct decision; Reject would be unjust given the methodological maturity of the protocol, and Minor Revision would understate how much the H1 framing and the retrieval-bottleneck observation reshape the contribution.

---

*Panel: EIC (NeurIPS-tier area chair, agents/CL), R1 (applied statistics + CL methodology), R2 (agentic memory systems), R3 (cogsci + production memory deployment), DA (adversarial reader).*
*Synthesized: 2026-05-25 by editorial_synthesizer.*
