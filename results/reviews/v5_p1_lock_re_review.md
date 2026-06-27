# Re-Review Verification Report — v5 P1 Lock (D-0.1 through D-0.5)

**Mode:** `academic-paper-reviewer` · `re-review` (lock-before-Spike-Week verification)
**Inputs:**
- Prior re-review: `results/reviews/v5_p1_re_review.md` (Accept with minor revisions; 5 residual gating items)
- Closure tracker: `MASTER_PLAN.md` §0 "Lock-before-Spike-Week"
- Manuscript under verification: `THESIS_FINAL_v5.md` on `main` after commit `4ff56bd` (squash-merge of `revisions/v5-p1`, tagged `p1-locked`), now 2335 lines

**Verifier:** Inline editorial pass (field-analyst → EIC → editorial-synthesizer), independent of the author.
**Date:** 2026-05-26

---

## Verdict: **Accept with minor revisions** — Spike Week may proceed in parallel with three localized text fixes

All four spec edits (D-0.1, D-0.3, D-0.4, D-0.5) land at their claimed anchors and are internally consistent at the *primary* anchor location. D-0.2 (squash-merge) is verified by commit `4ff56bd` and the `p1-locked` tag. However, **three stragglers** still carry pre-D-0.3/D-0.4 wording elsewhere in the document and must be reconciled before they propagate into Chapters 3–5. None of them blocks W1 Monday provisioning, but the §21 Week-4 line in particular will cause a real divergence if it remains.

---

## Role 1 — Field-analyst note

Persona configuration from P1 is unchanged: CS/ML, continual-learning sub-field, methods/protocol paper at NeurIPS/ICML tier, mature pre-registered protocol. The four edits do not shift field classification — D-0.4 narrows a generalization claim (in-field practice), D-0.5 adds three well-known field-canonical references (MemoryBank, A-MEM, Reflexion), D-0.1 strengthens pre-registration discipline, and D-0.3 explicitly de-scopes calibration. If anything, the venue fit *improves*: NeurIPS reviewers reward strict pre-registration and explicit non-generalization disclaimers over hedged "validation" framings.

---

## Role 2 — EIC traceability matrix

| Item | Original concern | Author's claim | Verified? | Evidence | Residual |
|---|---|---|---|---|---|
| **D-0.1** H1 rejection rule | Compound β-rule (cost can save a degraded H1a); P1 verifier flagged as softer than DA C1 | α-strict rule installed in §1.3; row 30 added to §0.1 | **YES** | §1.3 L119: *"H1 is rejected for policy P iff H1a outcome is C (P degraded) — regardless of H1b"*; §0.1 row 30 mirrors. | None on rule text. §19 framings still gate on H1a outcomes — consistent. |
| **D-0.2** Merge to main | Squash-merge `revisions/v5-p1` after D-0.1/0.3/0.4/0.5 land, tag `p1-locked` | Done as `4ff56bd` | **YES** | Repo state: commit on `main`, tag present. | None. |
| **D-0.3** Type-Aware calibration | Week-4 pilot was "Calibrate + lock" — ambiguous whether `decay_d` is re-tuned | Theoretical lock; pilot is sanity check only | **PARTIAL** | §8 P4 L796: *"`decay_d` is not re-tuned after the pilot"*; §20.8 L1721 mirrors. **But §21 Week-4 L1783 still reads:** *"Analyze pilot. Adjust `decay_d` per type if needed."* | **CRITICAL stragger:** §21 Week 4 directly contradicts the D-0.3 lock. Single-line fix. |
| **D-0.4** Multi-model arm | "Validation" claim was overpowered for 12 underpowered runs | Downgrade to exploratory probe everywhere | **PARTIAL** | §0.1 row 3, §1.4 "Scale" row, §12.2 heading + framing L1140, §20.9 L1726, §21 Week 7 L1792–1795 all updated to "exploratory probe" with explicit non-generalization disclaimer. **But three legacy "validation" mentions persist:** §22.1 L1846 heading *"Multi-model validation (12 runs…)"*; §22.2 L1880 risk-table cell *"Lose Week-7 validation"*; §23 acceptance criterion #17 L1905 *"Multi-model validation results"*. | **MAJOR stragger:** internal-consistency drift between §12.2/§20.9 ("exploratory probe") and §22/§23 ("validation"). Mechanical rename. |
| **D-0.5** Missing references | MemoryBank, A-MEM, Reflexion absent — publishability gate | Added to §26 with one-line anchors in §5.1, §8 P4, §9.1 | **YES** | §26 rows 28 (Zhong et al. 2024, MemoryBank), 29 (Xu et al. 2025, A-MEM), 30 (Shinn et al. 2023, Reflexion). Anchor citations: §5.1 L480 ("A-MEM … #29"), §8 P4 L740 ("MemoryBank … #28"), §9.1 L896 ("Reflexion … #30"). Numbering matches refs section. | None. Anchors are accurate and proportionate. |

### Internal-contradiction sweep

1. **§1.3 H1 rule ↔ §0.1 row 30 ↔ §19 framings.** Consistent. §19.1–§19.8 trigger conditions still reference H1a outcomes (A/B/C/D) without invoking the old compound rule. ✓
2. **§8 P4 / §20.8 (no re-tune) ↔ §21 Week 4 ("Adjust `decay_d` per type if needed").** **Contradiction.** §21 Week 4 was not updated when D-0.3 landed. This is a load-bearing inconsistency: Week 4 is the gate where the decision actually executes. ✗
3. **§12.2 / §20.9 (exploratory probe) ↔ §22.1 / §22.2 / §23 #17 (validation).** **Contradiction × 3.** The cost section heading, the risk-table cell, and the §23 acceptance-criterion line still say "validation." This contradicts D-0.4 row 3 of §0.1. ✗
4. **§26 ref numbering.** Anchors `#28`, `#29`, `#30` in §5.1, §8 P4, §9.1 correctly match rows 28/29/30 in §26. ✓
5. **§1.4 differentiation table "Scale" row** now reads `144 runs + 12-run exploratory cross-model probe` — matches D-0.4. ✓
6. **§0.1 row 30** is the canonical lock for H1 rejection; §1.3 quotes it back. ✓

### Quote evidence for the three stragglers (so the fix is unambiguous)

- L1783 (§21 Week 4): `- Analyze pilot. Adjust \`decay_d\` per type if needed.`
- L1846 (§22.1): `**Multi-model validation (12 runs, Haiku/4o-mini at lower per-token cost):**`
- L1880 (§22.2 risk row): `| Multi-model run blows budget | Med | Lose Week-7 validation | …`
- L1905 (§23 #17): `17. ✅ Multi-model validation results (12 runs, top-3 conditions)`

---

## Role 3 — Editorial synthesis

### 1. Decision

**Accept with minor revisions.** All five gating decisions are substantively landed at their primary anchors; D-0.5 references are correctly numbered and anchored; D-0.1 is the cleanest of the four (matches the P1 verifier's recommendation exactly). The four stragglers are localized text drift, not design drift — total fix surface is ~4 lines. Spike Week W1 Monday provisioning can begin in parallel.

### 2. Closure status per D-0.x

| ID | Status |
|---|---|
| D-0.1 H1 α-strict | **Closed** |
| D-0.2 Merge to main | **Closed** (commit `4ff56bd`, tag `p1-locked`) |
| D-0.3 Calibration theoretical | **Closed with caveat** — §21 Week 4 still says "adjust if needed" (1-line straggler) |
| D-0.4 Multi-model exploratory | **Closed with caveat** — §22.1 / §22.2 / §23 #17 still say "validation" (3-line straggler) |
| D-0.5 Missing refs | **Closed** |

### 3. New residuals (introduced or surviving)

| Severity | Item | Where | Recommended fix |
|---|---|---|---|
| **CRITICAL** | §21 Week 4 contradicts §8 P4 + §20.8 D-0.3 lock | L1783 | Replace `Adjust \`decay_d\` per type if needed.` with `Per D-0.3: do NOT re-tune \`decay_d\`. Pilot is sanity check only; underperformance is carried into the main run as a real signal.` |
| **MAJOR** | §22.1 cost heading retains "Multi-model validation" | L1846 | Rename to `Multi-model exploratory probe (12 runs, Haiku/4o-mini at lower per-token cost):` |
| **MAJOR** | §22.2 risk-table cell retains "Lose Week-7 validation" | L1880 | Replace with `Lose Week-7 exploratory probe` |
| **MAJOR** | §23 acceptance criterion #17 retains "Multi-model validation results" | L1905 | Rename to `Multi-model exploratory probe results (12 runs, top-3 conditions)` |
| MINOR | §22.2 row L1881 mentions "Lose validation" re SWE-ContextBench | L1881 | Optional: clarify "Lose secondary validation surface" or leave (SWE-ContextBench is a separate object than D-0.4). Defer. |

No new design issues introduced. No new contradictions outside the four stragglers above.

### 4. Spike Week unblock

- **VPS provisioning, Docker, `make verify-env`, API keys**: not blocked. Proceed Monday.
- **Smoke (Wed/Thu)**: not blocked.
- **§22.1 cost telemetry wiring (Tue)**: not blocked. Cost dashboard does not depend on the "validation/exploratory" wording in the heading.
- **§21 Week-4 contradiction (D-0.3 straggler)**: not blocked for W1, but **must be fixed before W4 Monday 2026-06-15**, or the author may execute the wrong rule under time pressure. Recommended to fix this session.
- **§22 / §23 wording (D-0.4 straggler)**: fix opportunistically; will surface again when drafting Chapter 5 Discussion in W10 and the §23 checklist in W12 — fixing now is cheaper.

### 5. Recommendation for the user (this session, before W1 Monday)

Apply the four single-line edits in the residuals table above on a small commit on `main` (or a tiny `revisions/p1-stragglers` branch if you want a paper trail). Total surface ≈ 4 lines; no need for another full re-review pass — these are mechanical reconciliations of already-locked decisions, not new design choices. After that:

1. Tag `p1-locked-final` (or amend `p1-locked` if you prefer one tag — your call; non-destructive to amend a local annotated tag if not yet pushed shared).
2. Begin W1 Monday VPS provisioning per `MASTER_PLAN.md` §2 W1.
3. The `MemoryBank` / `A-MEM` / `Reflexion` anchors are accurate; no further citation work needed before W7's Chapter 2 draft.

The protocol is locked in substance. The remaining work is hygiene.

---

## Confidence

**4.5/5.** Direct line-level verification of all five D-0.x items at all claimed anchors. The three "validation" stragglers and the §21 Week-4 line are unambiguous and quoted verbatim above. The only judgment call (whether the §22/§23 stragglers are MAJOR or MINOR) is mechanical — the underlying lock is unambiguous; only the surface text drifted.

---

*Re-reviewed: 2026-05-26. Inline three-role pass (field-analyst → EIC → editorial-synthesizer). No subagent dispatch; no spec edits applied. File: `results/reviews/v5_p1_lock_re_review.md`.*
