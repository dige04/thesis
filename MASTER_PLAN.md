# MASTER PLAN — Memory Pruning Thesis (from now → submission)

> **Status as of 2026-05-25:** Thesis design `THESIS_FINAL_v5.md` is P1-revised and verified (`results/reviews/v5_p1_re_review.md` — Accept with minor revisions). Implementation scaffolding through TASK_19.2 is in `src/` and tested. Branch `revisions/v5-p1` carries +187/−52 lines vs. main. Cost projection: ~$3K (§22.1). Target submission: **2026-08-17 (Week 12 Mon)**.
>
> **North star.** Ship a master's thesis that produces (a) the first Pareto map of forgetting policies for coding agents on SWE-Bench-CL with identical retrieval scoring, (b) a falsifiable pre-registered analysis whose conclusion is publishable in any direction, (c) reproducible artifacts (code, configs, logged runs). Methodology > novelty; discipline > scope.

---

## 0. Lock-before-Spike-Week (this week, by Fri 2026-05-29)

These five decisions gate Spike Week (W1). One sentence each; resolve in order.

| # | Decision | Resolution (2026-05-25) | Status |
|---|---|---|---|
| **D-0.1** | **H1 rejection rule** | **α (strict)** — H1 rejected iff H1a outcome C; H1b reported as independent secondary claim | ✅ Applied: §1.3, §0.1 row 30 |
| **D-0.2** | Commit `revisions/v5-p1` to main | Squash into single "Apply P1 revisions" commit, after D-0.1/0.3/0.4/0.5 land | ⏳ Pending merge (this session) |
| **D-0.3** | Type-Aware calibration | **(a) Theoretical** — Week-4 pilot is sanity-check, no re-tuning | ✅ Applied: §8 P4, §20.8 |
| **D-0.4** | Multi-model arm | **Downgrade** to "exploratory cross-model probe" (12 runs, no inferential claims) | ✅ Applied: §0.1 row 3, §1.4, §12.2, §20.9, §21 |
| **D-0.5** | Missing-refs (MemoryBank, A-MEM, Reflexion) | Added with 1-line context anchors | ✅ Applied: §26 rows 28–30, §5.1, §8 P4, §9.1 |

D-0.1, 0.3, 0.4, 0.5 landed 2026-05-25 on `revisions/v5-p1`. D-0.2 squash-merge follows. After merge, the protocol is locked and Spike Week (W1) can proceed.

---

## 1. Current state snapshot

| Component | State |
|---|---|
| Thesis design `THESIS_FINAL_v5.md` | P1-revised + re-review verified; awaiting D-0.1 + D-0.5 |
| Code (`src/`) | Agents, memory (store/retriever/classifier/reflection), 6 policies, benchmark loader, sequence runner, eval_v3 wrapper, CL metrics, behavioral metrics, stat tests, GLMM, Pareto, plots, feature importance, failure analysis — **all stubbed and unit-tested** (25 TASK_*.md docs) |
| Tests | 14+ pytest files; coverage TBD; **not run end-to-end on real SWE-Bench-CL task yet** |
| Docker / VPS | Per CLAUDE.md placeholders — **not provisioned** |
| API keys & cost monitoring | **Not verified** (`make verify-env` not run) |
| Logging schemas | Implemented per §11 |
| `eval_v3` integration | Wrapper exists; not validated against real task |
| Memory snapshots | Implemented |
| Jaccard probe (§11.5) | **Not yet implemented** — Spike-Week add (offline post-processing, ~1h) |
| `re_evaluate` for anchor probe | **Not yet implemented** — Week 2 add per §14.2 |
| §22.1 cost telemetry | Hooks exist (`src/metrics/cost_tracker.py`); dashboard not wired |

**Bottom line:** scaffolding is mature; integration is not validated end-to-end. Spike Week is the make-or-break gate.

---

## 2. Twelve-week execution timeline

Dates assume Mon-start weeks beginning 2026-05-25. Adjust if user calendar differs.

### W1 — Spike Week (2026-05-25 → 2026-05-29)

**Goal:** Prove the pipeline runs end-to-end on real tasks, on real VPS, with real cost telemetry. **GO/NO-GO Friday.**

| Day | Deliverable | Gate |
|---|---|---|
| Mon | Provision VPS (32GB / 250GB / 8 cores); install Docker; clone agents-never-forget; `make verify-env` passes | API keys live; Docker daemon up; `eval_v3` images pulled |
| Tue | Wire cost telemetry (wandb daily-spend dashboard); implement Jaccard probe (`src/analysis/retrieval_overlap.py`); land D-0.1 / D-0.4 / D-0.5 edits in THESIS_FINAL_v5.md; commit `revisions/v5-p1` to main per D-0.2 | Spend dashboard alive; tests still pass |
| Wed | Smoke: 3-task run on `eval_v3` (No Memory policy) on smallest sequence (likely matplotlib or sympy) | **≥ 15% pass-rate** (per Appendix A) — if < 15%, halt, debug; if 0%, switch backup model |
| Thu | Smoke: 3-task run on Full Memory policy, same sequence. Verify cost ≈ $0.40/task projection (§22.1) | Token + cost telemetry matches; memory snapshots written; per-step trajectories captured |
| Fri | Lock `top_k`, `max_context_tokens`, `max_workers` based on smoke data. Document deviations from defaults. Update §13 YAML. | **FRIDAY GATE: GO** = smoke passes + cost ≈ projection + all schemas land. **NO-GO** = invoke backup (SWE-agent + custom FAISS on SWE-Bench Verified). |

**Stop-loss this week:** if real per-task cost > $1.50, abort and recompute. If `eval_v3` Docker repeatedly OOMs, drop to `max_workers=2`.

### W2 — Infrastructure + simple policies (2026-06-01 → 2026-06-05)

- Full logging schema validated end-to-end (per-task, per-event, trajectory, snapshots, retrieval-overlap)
- Implement anchor-probe `re_evaluate` (§14.2) — agent re-run path with snapshot-loading
- Run 1 sequence × 4 conditions {No Memory, Full Memory, Random Prune, Recency Prune} × 1 seed = 4 runs
- Compute anchor-probed CL-F1 for each; confirm matrix sanity (Plasticity ∈ [0, 1], Stability ∈ [0, 1])
- Type classifier first integration test on 20 records (Structured Outputs)

**Gate:** 4 conditions produce different CL-F1 with sensible spread; cost per condition lands within ±30% of projection.

### W3 — Complex policies + classifier audit (2026-06-08 → 2026-06-12)

- Implement Type-Aware Decay (P4) and CLS Consolidation (P5) with cost tracking
- **Classifier audit (§10.2):** sample 150 stratified records from W2 runs + manual annotation (you alone — single-rater limitation per DA stakeholder finding; mitigation: ≥2 days of annotation, document inter-day reliability spot-check on 20 re-annotated items)
- Apply §10.3 decision rule: if accuracy ≥ 80% → proceed; 70–79% → note as limitation; < 70% → collapse to 3 types
- **Pilot (12 runs):** all 6 conditions × 2 sequences × 1 seed

**Gate (Wed):** classifier accuracy lower-CI ≥ 70% (per P2.1 stat-hygiene update). If not, collapse types and re-run W3 prep.
**Gate (Fri):** Pareto pilot shows visible separation between at least 2 policies; CLS firing rate ≥ 30%.

### W4 — Calibrate + lock (2026-06-15 → 2026-06-19)

- Analyze 12-run pilot. **Per D-0.3 default:** do NOT re-tune Type-Aware Decay parameters; report pilot as sanity-check.
- If Type-Aware does NOT beat Random Prune on the 2 pilot sequences: document, do not adjust formula, flag as a real possibility for the full run.
- **FREEZE all hyperparameters.** YAML in §13 is locked. Begin Methodology chapter writing (Chapter 3).
- Final review of edits since Spike Week; merge any straggler doc changes to main.

**Gate:** §13 YAML signed off; chapter 3 outline drafted.

### W5 → W6 — Full matrix execution (2026-06-22 → 2026-07-03)

- **Run all 144 runs:** 6 conditions × 8 sequences × 3 seeds, GPT-5.4, parallelized at `max_workers` from W1
- Daily cost telemetry; tmux + wandb dashboard
- **Resume support:** if a run crashes, resume from last successful task per `task_results.jsonl`
- Anchor-probe re-evaluations triggered at sequence end (§14.2: 4 probe points × up to 5 anchors per probe)
- **Stop-loss checkpoints:**
  - End of W5: projected total < $5K → continue. ≥ $5K → invoke §22.1 fallback (2): drop 1 seed → 96 runs
  - End of W6: ≥ $7K → fallback (3) drop 2 hardest sequences; ≥ $10K → fallback (4) drop CLS
- Begin Chapter 1 (Introduction) writing in parallel

**Gate (end W6):** 144 (or post-fallback N) runs complete with full logs + anchor-probe entries + retrieval-overlap data.

### W7 — Multi-model probe + write Chapters 2–3 (2026-07-06 → 2026-07-10)

- Top-3 conditions × 4 sequences × 1 seed = 12 multi-model runs on Haiku / 4o-mini (per D-0.4 default: framed as exploratory probe, not validation)
- If §22.1 budget supplement allows: 4 supplementary full-`a_{i,j}` cells (§14.3) for the top-2 conditions × 2 sequences
- Chapter 2 (Related Work — anchor on §1.4 differentiation + the missing-refs additions from D-0.5)
- Chapter 3 (Methodology — anchor on §4–13 of THESIS_FINAL_v5.md)

**Gate:** multi-model probe complete; Chapter 2–3 drafts complete.

### W8 — Analysis (strict order) (2026-07-13 → 2026-07-17)

Run in this order; each step gates the next:

1. **Aggregate `task_results.jsonl` → sequence-level means per condition** (`make aggregate`)
2. **Jaccard probe analysis (§11.5)** — compute median overlap per pruning-vs-Full pair. **If median > 0.9 → §19.7 fires** and the rest of analysis carries the qualifier
3. **Primary statistical tests (§15.2):** Wilcoxon + Holm + r_rb + BCa for 5 planned contrasts; **TOST per H1a** (SESOI=±0.03); H1b cost-reduction tests
4. **Pareto plots (§17):** 4 frontiers (CL-F1 vs cost / vs resolved-rate / vs memory size / vs tool calls); identify non-dominated conditions
5. **Trajectory plots:** resolved-rate, memory-size, tokens, tool-calls per sequence position
6. **Behavioral analysis (H4):** tool-calls + syntax-errors over sequence; address P2.7 H4 rewording in the Discussion (don't say "analysis paralysis"; use "memory-induced action inflation")
7. **GLMM (§15.3) with `(1|task_id)` as PRIMARY** (per P2.1) — `BinomialBayesMixedGLM` if `glmer` is singular; report random-effect SDs + `emmeans` contrasts
8. **Feature importance (§16):** LogReg + GBM, PR-AUC, **leave-one-sequence-out CV** (per P2.1); compute VIF; use `retrieval_rate` derived feature if collinear
9. **Failure analysis (§18):** 5 cases per policy hand-coded against §18 template
10. **Survival analysis per memory type** (if data supports — i.e., classifier accuracy ≥ 70%); **dose-response** (CL-F1 vs final memory size)

**Determine which §19 framing(s) fire** based on the trigger conditions in §19.1–§19.8.

### W9 — Synthesize results + draft Chapter 4 (2026-07-20 → 2026-07-24)

- Chapter 4 (Results) drafted around triggered §19 framings, in §19.8 order
- Pareto envelope is the headline figure; CL-F1 ± BCa CI table is the headline table
- Failure-analysis case-studies in §4 / §5 boundary
- **Classifier-as-policy sensitivity (§20.12):** rerun Type-Aware Decay maintain step with manual gold labels on the 150 audited items; report Jaccard of archived sets vs original

**Gate:** Chapter 4 draft complete; all primary figures and tables generated and named per a stable convention (`results/plots/fig_N_*.png`, `results/tables/tab_N_*.tex`).

### W10 — Chapter 5 + OpenMem packaging (2026-07-27 → 2026-07-31)

- Chapter 5 (Discussion): triggered §19 framings as the spine; H4 interpretation; ecological-validity statement (P2.10 belongs here, not §20.13 — promote to a Discussion subsection); future work
- **OpenMem packaging** (§21 W10): translate validated policies into a stand-alone module at `src/openmem/`. **Scope decision (per re-review residual):** keep this honest — design spec in thesis, code skeleton in repo, no production claim. If a single policy doesn't compile against a non-SWE workload, drop the code claim and keep only the spec
- Begin Chapter 1 final pass

**Gate:** Chapter 5 draft complete; OpenMem decision documented; Chapter 1 final pass started.

### W11 — Full chapter pass + revision (2026-08-03 → 2026-08-07)

- Chapter 1 final pass + Abstract (bilingual per ARS academic-paper standards)
- Internal consistency check: §1.4 differentiation claim ↔ §19.7 conditional qualifier; H1a/b ↔ Pareto findings ↔ Discussion claims
- Self-review using `/academic-research-skills:academic-paper-reviewer` in `re-review` mode against the full thesis (not just the protocol)
- Address re-review residuals on a 24h turn

**Gate:** All 5 chapters draft-complete; self re-review clears at "Accept with minor revisions" or better.

### W12 — Finalize + submit (2026-08-10 → 2026-08-17)

- Mon–Wed: Final language pass, figure quality pass, citation check (`ars-citation-check`), AI-usage disclosure (`ars-disclosure`)
- Thu: Format conversion to required submission format (`ars-format-convert` — LaTeX or DOCX per institution)
- Fri: Pre-flight checklist (Section 5 below); package supplementary materials
- **Mon 2026-08-17:** Submit

---

## 3. Parallel workstreams

These run *across* the timeline, not sequential. Each has its own owner-cadence.

### 3.a Writing stream (W4 → W12)

| Chapter | Anchor sections of v5 spec | Target draft date |
|---|---|---|
| 1. Introduction | §1, §1.4 | W6 |
| 2. Related Work | §1.4 + §26 + D-0.5 additions | W7 |
| 3. Methodology | §3–§13 | W7 |
| 4. Results | §14–§17, §19 (triggered), §16 features | W9 |
| 5. Discussion | §19 (triggered) + §20 (incl. ecological validity) + §22 (cost realization) | W10 |

Write *anchored on the v5 spec*. If you find yourself contradicting the spec, stop and update the spec first; the spec is the contract.

### 3.b Code / implementation stream (W1 → W7)

| Component | Status | Target |
|---|---|---|
| Jaccard probe (§11.5, P1.2) | Not started | W1 Tue |
| Anchor-probe `re_evaluate` (§14.2, P1.3) | Not started | W2 |
| Cost-telemetry dashboard (§22.1) | Hooks exist | W1 Tue |
| TOST procedure (§15.5, P1.1) | Need to add `src/analysis/equivalence.py` | W8 |
| Classifier-as-policy sensitivity (§20.12) | Not started | W9 |
| Leave-one-sequence-out CV (§16.5, P2.1) | Need to modify `feature_importance.py` | W8 |
| GLMM with `(1|task_id)` primary + Bayesian fallback | `glmm.py` exists; verify spec | W8 |
| OpenMem packaging (§21 W10) | Not started | W10 |

Implementation discipline: each component lands with a pytest test. No code without a test.

### 3.c Experiments stream (W1 → W7)

| Phase | Runs | When |
|---|---|---|
| Spike smoke | 6 runs (3 tasks × 2 conditions) | W1 |
| Pilot | 12 runs (2 sequences × 6 cond × 1 seed) | W3 |
| Full matrix | 144 (or post-fallback) runs | W5–W6 |
| Multi-model probe | 12 runs | W7 |
| Supplementary `a_{i,j}` (§14.3) | up to 4 cells × full T²/2 re-evals | W7 (budget-permitting) |

### 3.d Open-science stream (W1 → W12)

- **Pre-registration timestamp** — file an OSF or AsPredicted pre-registration **before** W5 starts, with §1.3 H1a/H1b SESOI + §15.2 planned contrasts + §19 triggered framings. Reference number goes in §15 and on the submitted thesis.
- **Code & data release plan** — by W11: code at `github.com/<you>/memory-pruning-thesis` (MIT); raw results at `runs/` (zipped, no PII concerns); pre-registered protocol artifact in the repo
- **Reproducibility container** — by W12: `docker/Dockerfile` pinning Python, FAISS, model API versions; `make reproduce` runs the smoke test on a fresh clone

### 3.e Risk monitoring stream (continuous)

| Metric | Threshold | Action |
|---|---|---|
| Daily spend | > $400 | Pause; investigate; do not auto-restart |
| Week-N cumulative spend | per §22.1 ladder ($5K/$7K/$10K) | Invoke corresponding fallback |
| `timeout=true` rate | > 20% in any condition | Per P2.7: pre-register as H4 indicator; consider raising step cap or accept it |
| Smoke-Day-1 pass rate | < 15% | Halt; backup model |
| Classifier audit accuracy LCL | < 70% | Collapse to 3 types |
| Schema drift | any change to §11 schemas after W2 | STOP; mid-experiment schema changes invalidate prior runs |

---

## 4. Critical path

```
D-0.1 + D-0.5 → Spike Week GO/NO-GO → W2 anchor-probe re_evaluate → W3 classifier audit → W4 hyperparameter lock → W5–W6 full matrix → W8 analysis → W9–W10 chapters 4–5 → W11–W12 finalize
```

**Single biggest critical-path risk:** W1 Friday gate. If the smoke run fails, the backup (SWE-agent on Verified) costs ~1 week of replanning. Build in slack: schedule W1 Mon–Wed for everything *except* the smoke run, so a Thu–Fri delay is absorbable.

**Second:** W3 classifier audit. If accuracy < 70%, the 3-type collapse forces a redesign of Type-Aware Decay (P4) — re-pilot, re-lock. Mitigation: stratify the 150-item sample carefully; if you only have one annotator (single-rater κ ≈ unfundable), commit to two annotation passes 3 days apart and report intra-rater agreement.

---

## 5. Top-5 risks (compressed from §22.2)

| Risk | Likelihood | Impact | Trigger / mitigation |
|---|---|---|---|
| Spike Friday gate fails | Med | 1-week delay | Reserve W1 Thu/Fri for the smoke; backup is SWE-agent on Verified |
| Cost overrun (Week-5 projection > $5K) | Med | Scope cut | §22.1 fallback ladder; daily spend telemetry; the §23 minimum-acceptable-scope is pre-registered, not invented under pressure |
| Classifier accuracy < 70% | Med | Type-Aware redesign | Audit Week 3; collapse to 3 types per §10.3; document |
| Jaccard probe shows > 0.9 overlap | Low–Med | §19.7 fires, contribution qualifier required | Already pre-registered as a finding — not a failure mode |
| Single base model deprecates mid-experiment | Low | Reproducibility hit | Pin model name + version; back up raw outputs; multi-model probe (W7) provides a partial hedge |

---

## 6. Submission checklist (W12 Fri)

Before submitting on 2026-08-17:

- [ ] All §23 acceptance criteria (now 19 items) met or explicit limitation documented
- [ ] §22.1 budget realization table populated and reported (criterion #19)
- [ ] §11.5 Jaccard probe report attached as appendix (criterion #18)
- [ ] Pre-registration artifact (OSF/AsPredicted) referenced in §15 with timestamp
- [ ] Code repo public + DOI'd (Zenodo)
- [ ] Reproducibility container builds clean on a fresh machine
- [ ] AI-usage disclosure statement included (per ARS `ars-disclosure`)
- [ ] Citation pass clean (per `ars-citation-check`)
- [ ] Bilingual abstract + keywords (Vietnamese + English)
- [ ] Format conversion verified visually (PDF render matches LaTeX source)
- [ ] Defense slides drafted (separate deliverable, target 30 min talk)

---

## 7. Things this plan deliberately does NOT do

Per the spirit of §24 (anti-creep manifesto), and to be honest about scope:

- No new policies beyond the locked 6 (and the Anti-Type baseline remains a P2 nice-to-have, not promised)
- No cross-repo retrieval as main experiment (Ablation D only if W7 budget supplements allow)
- No production deployment claims for OpenMem (design spec + skeleton only)
- No re-tuning of Type-Aware Decay parameters after W4 lock
- No formal causal claims beyond Tier-3 matched-contrast case studies
- No mid-experiment schema changes (any change after W2 invalidates prior runs)
- No grid search over hyperparameters
- No additional benchmarks (MEMTRACK / SWE-ContextBench remain "Future Work" unless an unforeseen window opens)

If any of these tempt you mid-execution, surface it explicitly and weigh against the calendar before acting.

---

## 8. Where to look when stuck

| Situation | First place to look |
|---|---|
| "Does the spec say X?" | `THESIS_FINAL_v5.md` (search by section) |
| "What did the review say?" | `results/reviews/v5_editorial_decision.md` |
| "Are my P1 revisions intact?" | `results/reviews/v5_p1_re_review.md` |
| "What was deferred and to when?" | `results/reviews/v5_p1_revision_applied.md` and this MASTER_PLAN.md §3 |
| "How much have I spent?" | `results/aggregated/cost_realization.csv` (W1 onward) |
| "Did Spike Week pass?" | `runs/spike_w1/task_results.jsonl` + smoke-test report |
| "Is the contribution still valid?" | `runs/aggregated/jaccard_overlap_report.json` → if median > 0.9, §19.7 framing applies |
| "Am I creep-violating?" | `THESIS_FINAL_v5.md` §24 anti-creep manifesto |

---

## 9. Version control hygiene

- Branch policy: feature branches off `main`, named `revisions/<topic>` for spec edits, `feat/<topic>` for code, `runs/<phase>` for experiment artifacts
- **Never commit to `main` directly.** Even for typos. Always via branch + PR (even solo).
- **Don't commit** `runs/`, `*.faiss`, `*.sqlite`, wandb cache, large logs. Per `.gitignore`.
- Tag at each major gate: `spike-pass`, `pilot-pass`, `freeze`, `matrix-complete`, `analysis-done`, `submitted`
- The `revisions/v5-p1` branch (current) needs to land on `main` per D-0.2 before W2 starts.

---

## 10. One-line summary

> Lock 5 decisions this week → smoke-test Friday → 144 runs over W5–W6 → analyze in strict order W8 → write W9–W11 → submit W12 Mon 2026-08-17. Cost target $3K, stop-loss $10K with pre-registered fallbacks. Methodology beats novelty; pre-registration beats hedging; Pareto beats winner-takes-all.

---

*Last updated: 2026-05-25. Update at each gate (W1 Fri, W4 Fri, W6 Fri, W8 Fri, W11 Fri).*
