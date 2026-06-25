# Codex Review Request — LaTeX Thesis Report (progressive draft)

**Date:** 2026-06-25 · **Branch:** `report/latex-progressive` (git worktree) · **Tip:** `750c7dc`
**Ask:** Review the report for structure, academic rigor, **integrity/honesty of framing**, and
**presentation quality benchmarked against the reference thesis** `example_contents/`.

---

## 0. TL;DR for the reviewer
A Bachelor thesis (USTH) written to **master-level scope**: a controlled measurement of memory
forgetting policies for AI coding agents. This is a **progressive draft**: Chapters 1–4 +
instrument-validation + Deviations + Threats are **finished prose**; Chapter 5 (Results), parts of
Discussion, Conclusion, and the appendices are **honest placeholders** because the trustworthy
144-run rerun is **not done yet** (blocked at 15/144, see §6). **No result numbers are fabricated
in the real report.** A separate, **watermarked SIMULATED** build exists only to preview layout.

---

## 1. What to review (paths are absolute)

### The real report (review THIS)
- Source: `/Users/leodinh/Documents/personal/thesis/.claude/worktrees/report-draft/paper/latex/`
- Compiled PDF (37 pp): `…/paper/latex/build/main.pdf`
- Build command (Tectonic; note the bundled script version is **0.2.3**, the README still says 0.2.2):
  ```bash
  python3 /Users/leodinh/.codex/plugins/cache/openai-bundled/latex/0.2.3/scripts/compile_latex.py \
    /Users/leodinh/Documents/personal/thesis/.claude/worktrees/report-draft/paper/latex/main.tex \
    --compiler tectonic \
    --output-directory /Users/leodinh/Documents/personal/thesis/.claude/worktrees/report-draft/paper/latex/build
  ```

### The presentation benchmark (compare AGAINST this — do NOT review its content)
- `/Users/leodinh/Documents/personal/thesis/example_contents/` — a finished sibling thesis
  (Qwen3-VL spatial VLM), **same modular section layout**, default LaTeX/Computer Modern.
  Use it as the bar for "what a finished, figure/table-dense thesis looks like." Note: its
  typography is **default LaTeX, identical to ours** — the gap is content-completeness + figure/
  table craft, not fonts. Compiled abstract: `example_contents/Abstract/Abstract.pdf`.

### The SIMULATED preview (context only — NEVER treat its numbers as real)
- `/Users/leodinh/Documents/personal/thesis/.claude/worktrees/report-draft/paper/latex_sim/build/main.pdf`
  (51 pp). Every page is watermarked **"SIMULATED"** + a red footer. It fills the pending
  placeholders with **illustrative OLD-matrix numbers** (`runs_k27_merged`) to preview the
  finished layout. **It is fabricated and watermarked; do not audit its values as results.**
  It also diverges from the real report (uses `natbib \citet/\citep`; a cosmetic `siunitx`
  trailing-zero issue, e.g. "95.000\%") — both are sim-only.

---

## 2. ⚠️ THE INTEGRITY HINGE (read before flagging "missing numbers")

The placeholder scaffolding in the real report is **deliberate and correct**, not an oversight:
- `[RESULT: pending runs_144_seq_cceb325]` markers, yellow `todobox`es, blue `[PENDING]`
  figure stubs, and `—` table cells mark work that **awaits the 144-run rerun**.
- `GROUNDED_FACTS.md` currently holds **OLD-matrix** numbers from an **instrument-crippled** run
  (broken `read_file`/`edit_file`); the rerun exists *because* that matrix is untrustworthy. So
  the old numbers must **not** be pasted as final results. The honest expectation (the "spine")
  is a *powered null* + a small bounded memory benefit, but it **must be re-derived on the new 144**.
- **Honest line everywhere** (verify the report holds it): the original §5 A/B gate **STOPped** →
  root-cause (path-normalization bug) → hotfix `cceb325` → **amended** (pre-registered, Codex-
  reviewed) gate → **GO** → 144 executed on fixed code. **Never** "the original gate passed."

A prior leak-check confirms **no old-matrix result number appears in the real prose** (grep for
`2986|0.330|0.311|31.5|2.40|1472|4675` over the PDF text returns empty). Please re-confirm.

---

## 3. What is finished vs pending (so you review the right things)

**Finished (review fully):**
- Ch1 Introduction (1.1–1.4); Ch2 Background (2.1–2.4); Ch3 Related Work (3.1–3.3).
- Ch4 Methodology (4.1–4.6 + six policy subsections), incl. **§4.7 Instrument Validation** (new).
- **§5.0/5.1 Instrument-Validation Result** — a *durable* result with REAL verified numbers
  (source `results/ab_gate/amended_cceb325_result.json`): instrument-attributable failures 79→0,
  model-quality 0.152 ≤ 0.183, token inflation 0.986×/0.992×, verdict GO.
- §6.3 Deviations (D1–D8, A1–A7, hotfix + sequence-phased execution) + §6.4 Threats to Validity.
- Abstract (numbers as placeholders), title page, LoF/LoT.

**Pending the 144 (placeholders only — do NOT expect numbers):**
- §5.2–5.7 (H1 Wilcoxon, two-axis Pareto, H2/H3/H4, E7 interdependence, manipulation checks).
- §6.1 Key Findings, §6.2 Implications, Ch7 Conclusion/Future Work, Appendices A/B.
- Result figures `fig:pareto-compute/footprint`, `fig:interdependence` (figure stubs).

---

## 4. Specific review asks
1. **Integrity:** Does any passage state a pending result as fact, paste an old-matrix number, or
   imply the original gate passed? Is the resolve-rate-proxy caveat for CL-F1 consistently held?
   Is the A5 framing correct (instrument **not** measurement-blind; 1.000 is **regime-driven**;
   backward-retention only; **no** p-value)? Is TOST described as *pre-registered but not computed*
   (Wilcoxon is the primary test, Invariant #11), never as performed?
2. **Methodology rigor:** Is the single-factor / retrieval-held-constant logic airtight? Are the
   six policies, the cap=10 (A1) binding argument, and the metric/statistical plan (Holm, $r_{rb}$,
   BCa, GLMM, PR-AUC+VIF) coherent and correctly motivated? **Note:** statistics are *frozen*
   (Holm not Bonferroni; rank-biserial $r_{rb}$ not Cohen's d) — flag mismatches, but the report is
   intentionally aligned to the frozen design, not to any looser registration text.
3. **Narrative/structure:** Does the argument flow (gap → controlled measurement → instrument
   trustworthiness → pending results → honest threats)? Is the "powered null + bounded benefit +
   three-filter attrition + footprint-free forgetting" spine legible without the numbers?
4. **Deviations defense:** Are D1–D8 + A1–A7 + the hotfix/seq-phased amendments defensible as
   *principled* (dated-before-data, held-constant, disclosed) rather than goalpost-moving?
5. **Presentation vs `example_contents`:** Are the finished chapters at parity? The two design
   figures are now **TikZ** (fig:architecture, fig:task-lifecycle); tables use booktabs; equations
   are numbered (4.1–4.3). What presentation gaps remain *that don't require the 144 data*?
6. **Citations:** All `\cite` keys resolve to `references.bib` (19 used, all present); several
   scaffold `[VERIFY+ADD]` works were dropped as uncited (noted in file comments). Flag any
   claim that needs a citation it doesn't have.

---

## 5. Evidence trail / source-of-truth (reference, don't duplicate)
- **Narrative spine + grounded numbers (UNTRACKED — main checkout only, not in this worktree):**
  `/Users/leodinh/Documents/personal/thesis/paper/report/THESIS_SPINE.md`,
  `/Users/leodinh/Documents/personal/thesis/paper/report/GROUNDED_FACTS.md`
- **Pre-registration & deviations:** `AMENDMENTS.md` (D1–D8, A1–A7), `CLAUDE.md` (deviation table,
  16 frozen invariants). Pre-registration of record: `THESIS_FINAL_v5.md`.
- **Instrument-validation evidence:** `results/ab_gate/amended_cceb325_result.json`,
  `docs/ab-gate-findings-2026-06-24.md`, `docs/amended-gate-2026-06-24.md`.
- **A5 anchor-probe construct-validity:** `docs/a5-anchor-probe-decision.md`.
- **Threats prose source:** `docs/threats-to-validity.md` (NOTE: its construct-validity paragraph
  is *superseded* by the A5 resolution — the report carries A5 through; the doc does not).
- **Run state / why 144 is pending:** `docs/MORNING-REPORT-2026-06-25.md`,
  `/tmp/HANDOFF-144-seq-phased-2026-06-25.md`.
- **This session's presentation work:** `paper/latex/PRESENTATION-UPGRADE.md` (playbook),
  `paper/latex/OURS-AUDIT.md` (placeholder inventory), `paper/latex/REPORT-HANDOFF.md` (original).

---

## 6. Known open items (don't re-flag as bugs)
- **144 rerun is blocked at 15/144** (Docker image disk-capacity wall), awaiting an infra decision
  (bigger disk / sequence-phased + docker login / harness image-cleanup). This is *why* Ch5 is
  pending; it is not a writing gap.
- **Degree = Bachelor** (USTH, student Dinh Thanh Hieu 22BA13132, internal sup. Dr. Nguyen Hoang
  Ha, external sup. Mr. Ho Trong Duc). NB: `CLAUDE.md` still calls the project a "master's thesis"
  — the *scope* is master-level, the *degree* is Bachelor.
- **MCP / practical forgetting module (Lethe)** is intentionally **deferred** — not a current
  contribution; to be considered only after the 144 completes.
- **Do NOT** re-run `scripts/migrate_typst_report_to_latex.py` — it regenerates the `.tex` from the
  Typst scaffold and would clobber the written prose.

---

> **One line:** Review the *real* report (`paper/latex/`, 37 pp) for rigor + honest framing, and its
> finished chapters' presentation against `example_contents/`; the `latex_sim` 51-pp build is a
> watermarked layout preview with fabricated numbers — context only, never audited as results.
