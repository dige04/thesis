# Codex Review Request — LaTeX Thesis Report (FULL DRAFT, real 144 data)

**Date:** 2026-06-27 · **Branch:** `report/latex-progressive` (git worktree) · **Tip:** `8c183469`
**Ask:** Review the **now-complete** report for structure, academic rigor, **integrity/honesty of
framing**, **internal numerical consistency**, and **presentation quality benchmarked against the
reference thesis** `example_contents/`.

---

## 0. TL;DR for the reviewer
A Bachelor thesis (USTH) written to **master-level scope**: a controlled measurement of memory
forgetting policies for AI coding agents. **This is no longer a placeholder draft** — the
trustworthy **144-run rerun is COMPLETE** (`runs_144_seq_cceb325`, deep audit **0 flags**) and
**every Results/Discussion/Conclusion section + Abstract + appendices is now filled with the real,
verified numbers.** No placeholders remain in the PDF. The headline (a **powered null that
survives** on trustworthy data) is the scientific payload. A separate **watermarked SIMULATED**
build still exists only as a layout artifact — never audit its numbers.

**The single biggest ask:** verify every number in the prose matches the source of truth
`paper/report/GROUNDED_FACTS.md` (and the underlying `results_seq_cceb325/`), and that the framing
is honest — especially the shift from the *old* spine (which this rerun partly overturned).

---

## 1. What to review (paths are absolute)

### The real report (review THIS)
- Source: `/Users/leodinh/Documents/personal/thesis/.claude/worktrees/report-draft/paper/latex/`
- Compiled PDF (**58 pp**): `…/paper/latex/build/main.pdf`
- Build (Tectonic; bundled script is **0.2.3**):
  ```bash
  python3 /Users/leodinh/.codex/plugins/cache/openai-bundled/latex/0.2.3/scripts/compile_latex.py \
    /Users/leodinh/Documents/personal/thesis/.claude/worktrees/report-draft/paper/latex/main.tex \
    --compiler tectonic \
    --output-directory /Users/leodinh/Documents/personal/thesis/.claude/worktrees/report-draft/paper/latex/build
  ```

### The presentation benchmark (compare AGAINST; do NOT review its content)
- `/Users/leodinh/Documents/personal/thesis/example_contents/` — a finished sibling thesis
  (Qwen3-VL spatial VLM), **same modular layout**, default LaTeX/Computer Modern. The bar for "what
  a finished, figure/table-dense thesis looks like." Typography is identical to ours — judge
  content-completeness + figure/table craft, not fonts.

### The SIMULATED preview (context only — NEVER treat its numbers as real)
- `…/paper/latex_sim/build/main.pdf` — every page watermarked **"SIMULATED"**, fabricated
  OLD-matrix numbers. Layout artifact only.

---

## 2. ⚠️ THE INTEGRITY HINGE (read before flagging anything)

This rerun was run **to replace an instrument-crippled matrix** (broken `read_file`/`edit_file`).
The honest narrative the report must hold everywhere:
- **Original §5 A/B instrument gate STOPped** → root-caused (edit-tool path-normalization bug) →
  **hotfix `cceb325`** → **amended** pre-registered, Codex-reviewed gate → **GO** → 144 executed on
  the frozen-`cceb325` agent. **Never** "the original gate passed."
- **Agent frozen at `cceb325`** (`git diff cceb325..HEAD -- src/agents/` empty) → science identical
  across all 144. Orchestration changes during execution were **disk-management only** (per-task
  `docker rmi`; sequence-phased scheduling) and are disclosed in §6.3.
- **Model = `deepseek-v4-flash`** (D8, single model all roles). The deviation chain in §6.3
  discloses an intermediate **MiniMax M3 (D6) that was discarded with no usable data** — this is a
  *required provenance disclosure*, not a claim that results ran on M3. Confirm the report never
  implies M3 (or any non-deepseek model) produced the 144.
- **CL-F1 is a resolved-rate proxy** (no `anchor_probe.json`); the A5 anchor probe is a **separate
  construct-validity sub-study**. Confirm this caveat is held consistently.
- **TOST was pre-registered but NOT computed** — non-inferiority is read from **bounded BCa CIs**,
  and the **Wilcoxon signed-rank is the primary test** (Invariant #11). Confirm TOST is never
  described as performed.

**Leak-check (please re-confirm):** old-matrix fabricated numbers must be ABSENT. Over the PDF
text, `grep -coE "2986|0.330|0.311|31.5|1472|4675|2.40|0.211"` returns **0**. New numbers (44.3,
1,247, per-cell values like 0.677, GLMM variances 3.223) are present.

---

## 3. The headline & the framing SHIFT (review this carefully)

The rerun **confirmed** the powered null but **overturned several old-spine claims**. The report has
been rewritten to the new findings — please verify it does NOT smuggle in the old framing:

| Claim | NEW (in report, correct) | OLD spine (must NOT appear) |
|---|---|---|
| Policy effect | **Powered null survives**: all 5 Wilcoxon contrasts n.s. (Holm 1.000), every BCa CI crosses 0 | same direction, but on crippled data |
| Memory benefit | full 0.445 vs no_mem 0.429 = **+1.6pp**, n.s. (read as a *bound*, underpowered) | — |
| Footprint win | **~½ (≈2×)**: pruners 598–704 vs full 1,247 tok | ~~4×~~ (old matrix) — must be ~½ now |
| TAD | **underperforms even no_memory** (0.427 < 0.429); mechanism: retrieval-freq term freezes store at ~first 10 items | — |
| GLMM | policy-null; **difficulty −2.18, position −1.49 significant** → effectiveness declines along sequence regardless of policy | — |
| Interdependence | memory_lift **does NOT track** dependency fraction (sklearn low-dep/high-lift; xarray high-dep/~0-lift); **two-filter** attrition | ~~three-filter~~ (retrieval 67% / utilization) — NOT re-derived this run |
| Feature analysis | **VIF passed** (1.42/1.40/1.02); **PR-AUC deferred** (Tier-1 all-neutral → needs Tier-2 gold) | ~~PR-AUC reported~~ |

H3 (CLS): reported as **n.s. vs full + gate-3 mechanism** (DBSCAN rarely clusters heterogeneous
same-repo memories at ≥0.70); the report deliberately makes **no hard matrix-wide
consolidation-event count** (the event-type semantics are ambiguous). Confirm 5.4/4.2.6 hold this.

---

## 4. What is finished (everything — review fully)

- Ch1 (1.1–1.4); Ch2 (2.1–2.4); Ch3 (3.1–3.3).
- Ch4 (4.1–4.6 + six policy subsections); **§4.7 Instrument Validation**; `fig:interdependence`
  (structural-dependency bar, real fractions) in §4.5.
- **§5.0/5.1** instrument-validation result (REAL: failures 79→0, model-quality 0.152 ≤ 0.183,
  inflation ≤1×, GO) + descriptives (4,914 rows, 2,175 resolved, 44.3%).
- **§5.2** H1 table + bounded benefit + two-axis Pareto (`fig:pareto-compute`, `fig:pareto-footprint`).
- **§5.3–5.7** H2/H3/H4, H5 + interdependence (`tab:memory-lift`, `fig:memory-lift`, GLMM),
  manipulation checks.
- **§6.1/6.2** Key Findings + Implications; **Ch7** Conclusion + Future Work.
- **Abstract** (real headline numbers).
- **Appendix A** Provenance (real disclosure list); **Appendix B** Extended Results
  (`tab:per-sequence` CL-F1 8×6, footprint 8×6, `tab:glmm-spec` full GLMM) — all from
  `results_seq_cceb325/aggregated/sequence_aggregates.json` + `glmm/glmm_results.json`.

---

## 5. Specific review asks
1. **Numerical consistency:** Does every stated number match `paper/report/GROUNDED_FACTS.md` and the
   appendix per-cell tables? Do the per-policy means in §5.1/§5.2 equal the column means in
   `tab:per-sequence`? Are the H1 W/p/r_rb/CI internally consistent across §5.2, §5.4, §5.6, §6.1
   (the same litany is restated — flag any drift, and note it's somewhat repetitive).
2. **Integrity:** Any passage stating a non-result as fact, an old-matrix number, "original gate
   passed", a performed TOST, or results on a non-deepseek model? Is the CL-F1-proxy / A5-separate
   framing consistent? Is the §6.3 MiniMax M3 hop correctly framed as *discarded, no data*?
3. **Methodology rigor:** Is the single-factor / retrieval-held-constant logic airtight? Are cap=10
   (A1) binding, the metric/stat plan (Holm not Bonferroni; rank-biserial r_rb not Cohen's d; BCa;
   GLMM binomial/logit; VIF) coherent? Statistics are **frozen to the design** — flag mismatches but
   the report is intentionally aligned to the frozen plan, not to any looser registration text.
4. **GLMM honesty:** The fit is approximate (statsmodels variational, not R/lme4). Confirm the
   report reports *signs + the null* and discloses the approximation + sensitivity check, and does
   NOT recompute the full-vs-no-memory contrast off the coefficients (that's the Wilcoxon's job —
   test-switching guard, Invariant #11).
5. **Narrative/structure:** Does it flow (gap → controlled measurement → instrument trustworthiness
   → results → honest threats)? Is the counter-intuitive lead ("more memory does not help; forgetting
   is footprint-free; decline is positional not policy") landed cleanly?
6. **Presentation vs `example_contents`:** Are chapters at parity? Design figures are TikZ
   (`fig:architecture`, `fig:task-lifecycle`); result charts are **pgfplots** (Pareto ×2,
   memory-lift, interdependence). Figures were visually rendered & checked for label collisions
   (5.1 relabelled to two extremes + caption-listed cluster). Any remaining presentation gaps?
7. **Citations:** 20 `\cite` keys, all resolve to `references.bib` (build shows 0 undefined). Flag
   any claim needing a citation it lacks.

---

## 6. Evidence trail / source-of-truth (reference, don't duplicate)
- **Source of truth for every number:** `paper/report/GROUNDED_FACTS.md` (trustworthy-144).
- **Authoritative rerun report:** `docs/RERUN-COMPLETE-2026-06-27.md` (H1–H5, GLMM, journey,
  provenance, caveats).
- **Raw data / analysis:** `runs_144_seq_cceb325/` (144 cells), `results_seq_cceb325/`
  (`tables/`, `glmm/`, `aggregated/sequence_aggregates.json`, `plots/`). Re-derive:
  `python -m scripts.run_analysis --stage all --runs-dir runs_144_seq_cceb325 --out results_seq_cceb325`.
- **Pre-registration & deviations:** `AMENDMENTS.md` (D1–D8, A1–A7), `CLAUDE.md` (deviation table, 16
  invariants), `THESIS_FINAL_v5.md` (pre-reg of record).
- **Instrument-validation:** `results/ab_gate/amended_cceb325_result.json`,
  `docs/amended-gate-2026-06-24.md`.
- **A5 anchor probe:** `docs/a5-anchor-probe-decision.md`.

---

## 7. Known open items (don't re-flag as bugs)
- **Degree = Bachelor** (USTH; student Dinh Thanh Hieu 22BA13132; internal sup. Dr. Nguyen Hoang Ha;
  external sup. Mr. Ho Trong Duc). Scope is master-level, degree is Bachelor. (`CLAUDE.md` still says
  "master's thesis" — scope, not degree.)
- **PR-AUC helpful/harmful classifier deferred** (Tier-1 weak labels all-neutral → Tier-2 manual gold
  needed). VIF ran clean. Not a headline blocker — reported as such.
- **A5 anchor probe** is reported as a separate construct-validity sub-study; the full matrix-scale
  probe was declined (option-c). CL-F1 stays the resolve-rate proxy primary.
- **MCP / Lethe** practical module intentionally deferred — not a contribution here.
- **Do NOT** re-run `scripts/migrate_typst_report_to_latex.py` — it regenerates `.tex` from the Typst
  scaffold and would clobber the written prose.

---

> **One line:** The report is now COMPLETE on trustworthy 144 data (58 pp, 0 placeholders). Review
> `paper/latex/` for numerical consistency vs `paper/report/GROUNDED_FACTS.md`, honest framing of the
> powered-null-that-survives (and the old-spine claims it overturned), and presentation parity with
> `example_contents/`. The `latex_sim` build is a watermarked layout artifact — never audited.
