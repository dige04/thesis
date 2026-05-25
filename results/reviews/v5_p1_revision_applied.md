# P1 Revision — Application Report

**Branch:** `revisions/v5-p1`
**Base:** `main` (commit `445021e`)
**File:** `THESIS_FINAL_v5.md`
**Stat:** 183 insertions, 48 deletions; line count 2187 → 2322
**Status:** Applied locally on branch, **not committed**. Awaiting user review.

---

## Edits applied (15)

| # | Edit | Section | Verification |
|---|---|---|---|
| 1 | §1.1 central-question rewording (drop "win-win", "including frontier models") | §1.1 | ✓ |
| 2 | H1 → falsifiable two-part hypothesis with TOST/SESOI=±0.03 + H1b ≥20% cost cut | §1.3 | ✓ |
| 3 | New §1.4 *Positioning vs. prior work* with differentiation table | §1.4 | ✓ |
| 4 | §19 rewritten with 8 trigger-gated framings (+§19.7 Jaccard outcome, +§19.8 multi-framing rule) | §19 | ✓ |
| 5 | New §11.5 *Cross-condition retrieval comparison* (Jaccard probe spec) | §11.5 | ✓ |
| 6 | New §20.11 *Retrieval-bottleneck confound* | §20.11 | ✓ |
| 7 | New §20.12 *Classifier-as-policy confound* (added for §19.3 coherence) | §20.12 | ✓ |
| 8 | §14.2 rewritten — anchor probe (k=5, 4 probe points) becomes PRIMARY | §14.2 | ✓ |
| 9 | §14.3 rewritten — full `a_{i,j}` matrix demoted to SUPPLEMENTARY | §14.3 | ✓ |
| 10 | §17 Pareto cost-axis clarification (excludes methodological re-eval) | §17 | ✓ |
| 11 | §23 acceptance criteria #18 (Jaccard report) + #19 (budget realization) | §23 | ✓ |
| 12 | §23 minimum-acceptable-scope rewritten as 4-step fallback ladder | §23 | ✓ |
| 13 | New §22.1 budget projection (~$3K) + stop-loss decision tree; §22 restructured (§22.2 risk registry) | §22 | ✓ |
| 14 | §0.1 frozen decisions: rows 27 (SESOI), 28 (Jaccard rule), 29 (anchor primacy) | §0.1 | ✓ |
| 15 | §15.5 reporting template updated with TOST line; §26 reference #13 expanded | §15.5, §26 | ✓ |

## Deltas vs. proposal

- **§20.12 added** beyond the proposal: §19.3 references the classifier-as-policy confound and needs an anchor in §20. Kept scope minimal (one paragraph + one mitigation).
- All other edits match the proposal verbatim.

## Frozen-invariant changes summary

| Locked decision | Status |
|---|---|
| #9 (Primary metric CL-F1) | Unchanged (still primary) |
| #19 (Pure cosine retrieval, identical across conditions) | Unchanged; reinforced by §20.11 |
| #16 (5-type taxonomy) | Unchanged; classifier-quality confound now explicit in §20.12 |
| **NEW #27** | SESOI = ±0.03 CL-F1 for H1a TOST |
| **NEW #28** | Jaccard overlap probe decision rule |
| **NEW #29** | Anchor probe as PRIMARY Stability estimator (was: full a_{i,j} matrix per old #9 sub-clause) |
| Old §14.2 (full matrix primary) | **Demoted** — now §14.3 supplementary |

## What this changes about the protocol's commitments

- **H1 now has a falsifier** — H1 is rejected for policy P iff H1a outcome is C *and* H1b is not satisfied. Earlier framing had no rejection condition.
- **a_{i,j} budget is bounded** — anchor probe caps re-evaluation at 20 per cell; total ≈ $1.2K instead of an open-ended $32K bill.
- **Pareto cost is well-defined** — measurement overhead explicitly excluded.
- **§19 narratives are gated** — each framing has a specific trigger; HARKing is now operationally restricted.
- **Retrieval-bottleneck is empirically testable** — Jaccard probe is offline, free, mandatory.
- **Stop-loss has numbers** — $5K / $7K / $10K with fallback ladder.
- **Budget realization is a deliverable** — acceptance criterion #19 commits to publishing actual cost numbers regardless of outcome.

## What is NOT changed

- Locked decisions #1–#26 are intact.
- Implementation (`src/`) is untouched.
- Tests are untouched.
- No commits made.

## Items deferred to later weeks (per the user's ladder)

- **Spike Week (step 4):** implement Jaccard probe as offline post-processing on `task_results.jsonl`. Spec in §11.5; ~1 hour of work.
- **Week 3–4 pilot (step 5):** pick Type-Aware Decay calibration option (default option (a) — declare theoretical, pilot is sanity-check).
- **P2 items:** Anti-Type baseline (+24 runs), H4 rewording, ecological-validity §20.13, CLS clustering algo spec, missing refs (MemoryBank/A-MEM/Reflexion/Park-et-al-triplet/Catolino), multi-model expansion decision.
- **P3 items:** OSF pre-reg artifact, OpenMem scope, syntax-error definition, embedding-payload audit, per-component seed table, anchor-probe-set determinism note.

---

## Next-step options (from `superpowers:finishing-a-development-branch`)

I have **not** committed. Per CLAUDE.md ("Do not auto-modify locked files") and the original branch-policy concern, the commit decision is yours. Options:

1. **Inspect and commit on this branch.** Review `git diff THESIS_FINAL_v5.md`; if good, commit. Example: `git add THESIS_FINAL_v5.md results/reviews/ && git commit -m "Apply P1 revisions: H1 TOST, §1.4 differentiation, §19 gated framings, anchor probe primary, §22.1 budget"`. Then either merge to main (`git checkout main && git merge --no-ff revisions/v5-p1`) or open a PR.
2. **Inspect and edit further.** Mark issues; I'll apply additional edits on this branch.
3. **Discard.** `git checkout main && git branch -D revisions/v5-p1`. Edits are lost (still recoverable as the proposal file in `results/reviews/`).

Branch tip is `main` + the in-place changes only. No commits to roll back.
