# Report-Writing Handoff — LaTeX thesis (`paper/latex/`)

**Purpose:** write the thesis report *progressively* while the trustworthy 144 rerun runs
(~22–24h). Lock in everything that does NOT depend on the new 144 data now; leave the 144
results as honest placeholders until `runs_144_seq_cceb325` lands.

**Build:** see `paper/latex/README.md` (Tectonic via the bundled compile script). Section `.tex`
files are migrated from `paper/report/**/*.typ` — content source-of-truth is the Typst tree +
the two control files below. **Do NOT fabricate numbers or citations.**

> **Read first:** `paper/report/THESIS_SPINE.md` (narrative) · `paper/report/GROUNDED_FACTS.md`
> (numbers) · `paper/report/README.md` (storytelling contract).

---

## ⚠️ THE INTEGRITY HINGE (read before writing a single number)

`GROUNDED_FACTS.md` currently holds numbers from the **OLD matrix `runs_k27_merged`** — the
**instrument-CRIPPLED** run (read_file no-range/94.6% truncated, edit_file 30.2% fail). **The
rerun exists precisely because that matrix is untrustworthy.** Therefore:

- **Chapters 1–4 + the instrument-validation story + deviations = writable NOW** (design and
  methodology don't depend on which matrix produced the final numbers).
- **Chapter 5 (Results: H1–H5 on the 144) = PLACEHOLDERS** until the new
  `runs_144_seq_cceb325` completes and `run_analysis` re-derives the numbers. **Do NOT paste the
  old `runs_k27_merged` H1–H5 values as final results.** They may change materially — the edit_file
  hotfix raises edit-success, so resolve rates and possibly the policy contrasts will differ.
- When the new 144 lands, `GROUNDED_FACTS.md` gets re-derived (`scripts/run_analysis --stage all
  --runs-dir runs_144_seq_cceb325 --out results_seq_cceb325`) and Ch5 is filled from THAT.

**Never write "the A/B gate passed" about the original gate.** The honest line (everywhere):
*the original pre-registered §5 A/B gate **STOPped**; root-cause analysis found an instrument bug;
it was fixed (commit `cceb325`); the gate was **amended** (pre-registered criteria) and re-run →
**GO**; the full 144 was then executed on the fixed code under a sequence-phased scheduler.*

---

## ✅ Writable NOW (verified + durable)

### A. The instrument-validation sub-study — a NEW, real methodological contribution
This is new since the spine was written and is **strong, durable, and central to the
trustworthiness story.** Put it in **Methodology** (a §4.x "Instrument validation" subsection) +
a **Results** subsection + **Discussion/Threats**. Verified numbers (source:
`results/ab_gate/amended_cceb325_result.json`, `docs/ab-gate-findings-2026-06-24.md`,
`docs/amended-gate-2026-06-24.md`):
- Defect: the agent's `read_file` (no line ranges, 4k-char truncation) and `edit_file` (path
  normalization) tools were broken → the original 144 was unreliable. Caught via trajectory audit.
- A/B design: 36 cells = {pytest, scikit-learn} × {no_memory, full_memory, recency_prune} × 3
  seeds × {legacy (pre-fix), fixed (post-fix)} tool modes; held-constant everything else.
- Original §5 gate → **STOP** (edit_failure_ratio 0.303, 82 path/index failures). Root cause: the
  fix compared the normalized diff path to the RAW absolute `path` arg → **77/78 "security
  rejections" were false** (same file); + 2 `a//testbed` normalize-gaps. Hotfix `cceb325`.
- **Amended gate (pre-registered, Codex-reviewed) → GO**, on fresh post-hotfix data:
  **instrument-attributable failures 79 → 0**; model-quality edit-error rate **fixed 0.152 ≤
  legacy 0.183** (fix doesn't regress); token inflation **prompt 0.986 / total 0.992 (≤1.0×)**;
  complete + paired + provenance (sha/config/row-level tool_mode) all pass.
- Informational A/B delta (NOT the 144 headline — pytest+sklearn only): fixed resolve 0.582 vs
  legacy 0.429 (+15.3pp). Frame as "the fixed instrument is net-positive," not as a thesis result.
- Decomposition (defensible, not goalpost-moving): edit failures split into INSTRUMENT-attributable
  (→0 after fix) vs MODEL-quality (malformed diffs / wrong paths — a fixed property of the frozen
  model, present in both arms ⇒ non-confounding for between-policy contrasts, same logic as
  deviations D1–D8). The 0.15 total-ratio criterion was retired *for this model* and replaced by
  instrument-attributable→0 + model-rate non-regression.

### B. Chapters 1–4 (design, not results)
Write from `THESIS_SPINE.md` + the existing scaffold stubs:
- Ch1 Introduction, Ch2 Background, Ch3 Related Work — narrative + citations (`references.bib`).
- Ch4 Methodology — 6 policies, memory architecture, retrieval-fixed invariant, agent/benchmark/
  model, metrics + statistical plan (Wilcoxon N=8 Holm / r_rb / GLMM / Pareto / PR-AUC+VIF).
  **Add the §4.x instrument-validation subsection (A above).**

### C. Deviations & Threats (writable now)
- Deviations D1–D8 (model = deepseek-v4-flash single-model D8; embedder D2; cost=tokens D3;
  classifier JSON-mode D4; arm64→x86_64 host D5; etc. — see `CLAUDE.md` + `AMENDMENTS.md`) **plus
  the new instrument-hotfix amendment** (cceb325 + sequence-phased execution due to disk capacity).
- Threats to validity: the instrument defect (caught + fixed + validated); the CL-F1 =
  resolved-rate-proxy caveat + the A5 anchor-probe construct-validity sub-study
  (`docs/a5-anchor-probe-decision.md`); single-model scope; held-constant-model ⇒ between-policy
  only (absolute rates not leaderboard-comparable).

## ⏳ PENDING the new 144 (placeholders only — no fabrication)
- Ch5 Results: H1 (Wilcoxon vs full_memory + Holm + r_rb + BCa), H1b (two-axis Pareto:
  compute vs footprint), H2/H3/H4, E7 (memory-lift × interdependence). Mark each `[RESULT: pending
  runs_144_seq_cceb325]`.
- Abstract headline numbers, Discussion's quantitative claims, Conclusion.
- The spine's "powered null + bounded +2.4pp + footprint win + interdependence ceiling" is from the
  OLD matrix — treat as the *expected* shape but **re-verify on the new 144**; the headline may shift.

## Pointers (evidence trail — reference, don't duplicate)
- Spine/facts/contract: `paper/report/{THESIS_SPINE.md, GROUNDED_FACTS.md, README.md}`
- A/B + instrument story: `results/ab_gate/amended_cceb325_result.json`,
  `docs/ab-gate-findings-2026-06-24.md`, `docs/amended-gate-2026-06-24.md`,
  `docs/codex-review-request-2026-06-24.md`, `docs/codex-preflight-proof-2026-06-24.md`
- Run state / decisions (survives compaction): `.superpowers/sdd/progress.md`,
  `docs/MORNING-REPORT-2026-06-25.md`
- The 144-rerun ops handoff: `/tmp/HANDOFF-144-seq-phased-2026-06-25.md`
- Provenance: `results/manifest/freeze.json` (experiment_sha cceb325, agent freeze)

## Suggested skills
- `superpowers:using-superpowers` at session start.
- Academic writing: the **ARS plugin** commands — `/ars-outline`, `/ars-revision`,
  `/ars-revision-coach`, `/ars-abstract`, `/ars-lit-review`, `/ars-citation-check`,
  `/ars-disclosure` (deviations), `/ars-reviewer`. Use `/ars-disclosure` for the Deviations
  section and `/ars-citation-check` against `references.bib`.
- Consult **`advisor`** before finalizing the instrument-validation framing (it must read as
  honest root-cause + amendment, never "the original gate passed").
