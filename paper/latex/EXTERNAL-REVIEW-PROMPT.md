# Portable prompt — deep review + deep research of the thesis PDF

> Paste the block below into another model **together with the attached thesis PDF**.
> It is self-contained (assumes the reviewer has only the PDF, not the codebase).
> Works for ChatGPT, Gemini, Claude, Grok, etc.

---

You are a senior reviewer for a top-tier ML/SE venue (think NeurIPS/ICML/ICSE/EMSE
program committee) **and** a research advisor. I am giving you a complete thesis PDF. I want
two things, in this order: (1) a **deep, adversarial review** of what is in the document, and
(2) **deep research** that positions the work against the literature and tells me what would
make it stronger. Be rigorous, specific, and honest. I would rather hear the hardest, fairest
criticism now than from my examiners.

## Context you need (everything else, read from the PDF)
- This is a **Bachelor thesis written to master-level scope**: a *controlled measurement* of
  memory **forgetting / pruning policies** for LLM coding agents on a sequential
  (continual-learning) coding benchmark. It compares six memory policies (No Memory, Full
  Memory, Random Prune, Recency Prune, Type-Aware Decay, CLS Consolidation) under **identical,
  retrieval-held-constant** search, on one frozen model, across 8 task sequences × 3 seeds =
  **144 runs**.
- **The headline is a (powered) NULL result**: no forgetting policy differs significantly from
  full-memory accumulation, with a small bounded memory benefit, and "forgetting is
  footprint-free." **This null is the intended scientific contribution, not a failure** — judge
  whether it is *established and framed honestly*, not whether it is "positive."
- The author has **deliberately declared** several things; do **not** simply flag their
  existence — instead **critique whether the mitigation/disclosure is adequate**:
  - a **single model** was used (a declared deviation from the pre-registration; absolute rates
    are stated as not leaderboard-comparable);
  - the value axis **CL-F1 is a resolved-rate proxy**, not a direct forgetting curve (a separate
    "anchor-probe" sub-study probes this);
  - the statistical plan is **pre-registered and frozen** (Wilcoxon signed-rank on N=8 sequence
    means + Holm correction; rank-biserial effect size; BCa bootstrap CIs; a task-level
    binomial/logit GLMM);
  - an **instrument-validation sub-study** caught and fixed a tooling bug before the main runs.

## Part 1 — Deep adversarial review
Work through these axes. For each finding, give a **severity** (Critical / Major / Minor /
Nitpick), **quote or cite the exact section/figure/table** it concerns, state **why it matters**,
and give a **concrete fix**. Do not pad; prioritize the few things that most threaten the thesis.

1. **Validity of the headline null.** Is the null *established* or merely *not rejected*? With
   N=8 sequences, is the study powered enough to claim non-inferiority? Is the "+1.6pp bounded
   benefit" characterized honestly (as a bound, not a proven null)? Is the absence of a TOST /
   equivalence test (noted as pre-registered-but-not-computed) a real hole, and how damaging?
2. **Statistical rigor.** Are Wilcoxon-on-sequence-means, Holm, rank-biserial, and BCa applied
   and interpreted correctly? Is pooling 144 runs into 8 sequence means defensible (vs.
   pseudo-replication the other way)? Is the GLMM — reported as an *approximate variational fit*
   with signs-only inference because the canonical R/lme4 fit was not run — a credible basis for
   its claims, or must lme4 be run? Any multiple-comparison or effect-size-reporting concerns?
3. **Causal & construct validity.** Are claims appropriately limited to *association*? Does the
   resolved-rate proxy actually capture "continual-learning forgetting," and is the gap handled
   convincingly? Is the GLMM "performance declines with sequence position regardless of policy"
   finding sound, or could it be an artifact (task ordering, difficulty confound, context-window
   effects)?
4. **Methodology / internal validity.** Is the retrieval-held-constant, single-independent-
   variable design genuinely airtight? Is the memory-cap argument (small cap so pruning actually
   binds) sound? Are the six policies faithful, fair operationalizations — especially the
   negative finding that Type-Aware Decay underperforms even No Memory (is the proposed
   mechanism — a retrieval-frequency term freezing the store — convincing)?
5. **Generalizability.** How much does the single-model, single-benchmark, same-repository-only,
   arm/x86 + token-proxy-cost setup limit the conclusions? Which claims survive these limits and
   which should be softened?
6. **Internal consistency.** Do numbers agree across Abstract, Results, Discussion, and the
   appendix per-cell tables? Do the per-policy means equal the sequence-table column means? Flag
   any drift, contradiction, or figure/text mismatch.
7. **Narrative & framing.** Does a null result land compellingly without overclaiming? Is the
   "footprint-free forgetting" framing (the main positive) over- or under-sold? Is anything
   phrased as a stronger result than the statistics support?
8. **Presentation.** Figures, tables, captions, equations, structure, length — judged against a
   strong sibling thesis. What specifically reads as unfinished or below par?
9. **Threats to validity.** Is the threats section complete and honest, or are there unstated
   threats a hostile examiner would raise?

## Part 2 — Deep research (positioning & strengthening)
Use your own knowledge of the literature (2023–2026). Be concrete; name papers/authors where you
can, and clearly separate **what you're confident about** from **what I should verify**.

1. **Related-work completeness.** Given the topic — memory/forgetting for LLM agents, continual
   learning, retrieval-augmented coding agents, context dilution / "lost in the middle,"
   experience-following risk, cognitive theories of adaptive forgetting — what important recent
   work is likely **missing or under-cited**? List candidate citations with one line each on why.
2. **Novelty & gap.** Is the claimed gap (a *retrieval-held-constant* isolation of the storage
   policy for coding agents) genuinely novel and defensible, or has something close been done?
   Where exactly does this sit relative to the closest prior work?
3. **Strengthening experiments/analyses** that are realistic for a thesis revision: rank 3–5 by
   *impact-to-effort*. (E.g., a second model to test robustness, an equivalence test, an lme4
   refit, a power analysis, the interdependent-subset lift, completing the deferred
   helpful/harmful classifier, etc.) For each: what it would add and what it risks.
4. **Examiner Q&A.** Predict the **8–10 hardest questions** a defense committee will ask, and
   sketch the strongest honest answer to each. Flag any question the current draft cannot
   answer well.
5. **Verdict.** Give an overall assessment: is this a credible, defensible contribution at
   Bachelor level (and how far toward master-level)? One paragraph, plus a 1–10 score with
   the single most important thing to fix before submission.

## Output format
Start with a 5–8 line **executive summary** (top strengths, top risks, verdict). Then Part 1 as a
prioritized findings list (Critical → Nitpick). Then Part 2 by its sub-headings. End with a short
**"if you fix only three things"** list. Ground every criticism in the PDF; when you speculate or
rely on outside knowledge, say so explicitly. Do not invent results or numbers that are not in the
document.
