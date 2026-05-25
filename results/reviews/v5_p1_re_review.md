# Re-Review Verification Report — v5 P1 Revisions

**Mode:** `academic-paper-reviewer` · `re-review`
**Inputs:**
- Original Editorial Decision: `results/reviews/v5_editorial_decision.md` (Major Revision verdict)
- Author's Claimed-Revision Report: `results/reviews/v5_p1_revision_applied.md` (15 edits claimed)
- Revised Manuscript: `THESIS_FINAL_v5.md` on branch `revisions/v5-p1` (2322 lines, +187/−52 vs main)

**Verifier:** Independent subagent (did not author either the original review or the revisions).
**Date:** 2026-05-25

---

## Verdict: **Accept with minor revisions** (for the P1 scope)

All five Priority 1 (CRITICAL) items are substantively addressed at the claimed section anchors. The verifier directly inspected §1.1, §1.3, §1.4, §11.5, §14.2–14.3, §17, §19.1–19.8, §20.11–20.12, §22.1, §0.1, and §23. Three internal-consistency contradictions were identified (now fixed). One structural choice about the H1 rejection rule is flagged for your decision.

---

## R&R Traceability Matrix — Priority 1

| Item | Original concern | Verified location | Verdict | Notes |
|---|---|---|---|---|
| **P1.1** | H1 unfalsifiable "win-win" | §1.1 line 99, §1.3 lines 109–119, §0.1 row 27 | **✓** | TOST procedure, SESOI ±0.03 locked, outcomes A/B/C/D explicit, "win-win" removed. **Caveat:** softer rejection rule than DA C1 directive — see "Open question" below. |
| **P1.2** | Retrieval bottleneck (top-5 funnels all storage policies) | §11.5 (probe schema), §20.11 (three-band decision rule), §19.7 (co-firing framing), §0.1 row 28, §23 #18 | **✓** | Option A (Jaccard probe) implemented cleanly; reporting mandatory regardless of outcome; §19.7 conditionally qualifies the contribution claim. Option C (rename contribution) is conditional, not unconditional — fine given §19.7 gating. |
| **P1.3** | a_{i,j} matrix cost (~$32K) unrealistic | §14.2 (anchor primary, k=5 × 4 probes ≤20 re-evals/cell), §14.3 (full matrix supplementary, 4 cells), §22.1 ($3K budget), §17 (cost-axis lock), §0.1 row 29 | **✓** | `re_evaluate` semantics explicit (re-run agent, n=1 with 3-seed pooling, n=3 upgrade path). Stop-loss table with $5K/$7K/$10K triggers and 4-step fallback ladder. Pareto cost-axis excludes methodological overhead. |
| **P1.4** | Alqithami 2025 differentiation missing | §1.4 lines 125–142 | **✓** | 10-axis differentiation table; delta-contribution paragraph names the four-fold novelty (SWE-Bench-CL + identical retrieval + boundary baselines + pre-committed framings) and explicitly disclaims policy-invention novelty. |
| **P1.5** | §19 framings ungated (hedge net) | §19.1–§19.8 lines 1620–1668 | **✓** | Each framing has quantitative trigger (e.g., §19.2: H1a outcome A/B AND r_rb ≥ 0.3 AND Pareto-dominance AND Δ vs Random ≥ +0.02). §19.8 multi-framing rule explicitly prohibits HARKing. Gated analyses tied to specific triggers. |

---

## Priority 2 spot-checks

| P2 item | Status | Evidence |
|---|---|---|
| P2.1 (stat hygiene: TOST + GLMM `(1\|task_id)` primary + family-wise α hierarchy + leave-one-seq-out CV) | **Partial** | TOST present (§15.5 reporting template, §1.3 H1a). GLMM elevation NOT done. Family-wise hierarchy NOT declared. LOSO CV NOT done. Deferred per author's report. |
| P2.3 (Type-Aware calibration story) | **Not done** | §8 P4 still describes 5 base + 5 decay + 1 exponent. §20.8 mentions Fastpaca-theoretical. Deferred to Week 3–4. |
| P2.9 (missing refs: MemoryBank, A-MEM, Reflexion, Catolino, Cohen 1960) | **Not done** | None added to §26. Explicitly deferred. |
| P2.10 (§20.13 ecological validity) | **Not done** | One-sentence caveat in §1.4 only; no dedicated subsection. Deferred. |
| P2.11 (rename CL framing) | **Not done** | §1.1 / §1.4 still claim "Pareto map of forgetting policies for coding agents" — qualified conditionally via §19.7 only. Deferred. |

All P2 deferrals are *explicit* in the author's applied report, not silent omissions. Acceptable as a P1-only revision pass.

---

## New issues introduced by the revisions (caught and fixed during re-review)

| # | Issue | Status |
|---|---|---|
| R1 | §24 anti-creep manifesto still listed "Anchor probe as primary stability measure — supplementary only" under *Rejected*, contradicting new §0.1 row 29 and §14.2 | **Fixed:** row replaced with "Calibrating all 11 Type-Aware knobs from the 12-run pilot" (a real anti-creep boundary) |
| R2 | §0.1 row 9 (Primary metric) still said "computed from full `a_{i,j}` matrix" | **Fixed:** now reads "computed from anchor-probe `a_{i,j}` entries per §14.2; full matrix is supplementary (§14.3)" |
| R3 | §23 acceptance criterion #8 still referenced "Per-sequence `a_{i,j}` matrices" | **Fixed:** now references "anchor-probe `a_{i,j}` entries (§14.2: k=5 anchors × 4 probe points)" |

Cumulative diff vs `main`: **+187 / −52 lines**. (Was +183 / −48 after the initial P1 application; the +4 / −4 here are the three consistency fixes.)

---

## Open question for the author — H1 rejection rule

The DA directive (Critical issue C1) said: *"H1 is rejected if H1a fails."* (Strict performance gate.)

The applied edit reads: *"H1 as a whole is rejected for policy P iff H1a outcome is C (P degraded) AND H1b is not satisfied. Otherwise H1 stands for P."* (Compound rule — H1 can stand if cost criterion succeeds even when performance degrades.)

This is logically consistent with the H1 umbrella ("at least one of H1a or H1b"), but **softer than the DA directive**. The trade-off:

| Choice | Pro | Con |
|---|---|---|
| **(α) Strict H1a gate** — replace current rule with "H1 rejected for P iff H1a outcome is C" | Matches DA C1 directive exactly. Pre-registration cleaner — no "we won on cost, so the hypothesis survives" loophole. | Loses information when a policy genuinely trades performance for cost — common in production memory systems. |
| **(β) Current compound rule** | Reflects real-world Pareto thinking — cost-quality trade-offs are legitimate. | Reintroduces partial hedge: H1 can stand even when performance degrades, if cost saves are large enough. The DA's "heads-I-win-tails-you-lose" critique still applies, just at a higher bar. |

**Verifier's recommendation:** (α) for pre-registration discipline. The cost-quality Pareto story belongs in §17 (Pareto analysis) and §19 (interpretation framings), not in H1 itself. H1 should test one thing cleanly.

**Decision needed.** One-sentence edit in §1.3 either way. I have *not* applied this change; awaiting your call.

---

## Remaining items for next revision round

1. **Decide H1 rejection rule (α or β).** One-sentence edit.
2. **P2.1 — GLMM primacy and family-wise α hierarchy** (per editorial acceptance criteria, items 8–9). Pre-Spike-Week.
3. **P2.9 — at least three missing refs (MemoryBank, A-MEM, Reflexion)** — these are foundational; their absence is a publishability gate, not a P2 nicety.
4. **P2.3 — Type-Aware calibration story** locked in §8 P4 prose before Week 3 pilot starts.
5. **P2.10 — §20.13 ecological-validity scope statement** (one paragraph). Removes a common reviewer objection.

Items 2–5 are explicitly deferred and tracked.

---

## Final status

| Question | Answer |
|---|---|
| Did P1 revisions substantively address the Major-Revision verdict? | **Yes** — all 5 CRITICAL items verified. |
| Did the revisions introduce new contradictions? | Yes (3), all fixed during re-review. |
| Are deferred P2 items silently lost? | No — explicitly listed in `v5_p1_revision_applied.md` "Items deferred." |
| Is the protocol ready to lock for Spike Week? | **Conditional yes** — pending resolution of H1 rejection rule + 4 deferred items (GLMM primacy, missing refs, Type-Aware calibration choice, ecological-validity §20.13). |
| New verdict for the P1 pass alone? | **Accept with minor revisions** (the 3 contradiction fixes + 1 open H1 question). |

---

## Confidence

**4/5.** Direct text verification of all 5 P1 items + 3 contradiction fixes. The one judgment call (H1 strict vs compound rejection rule) is surfaced as an open question, not adjudicated.

---

*Re-reviewed: 2026-05-25 by independent subagent verifier. Synthesized and contradiction fixes applied by editorial_synthesizer.*
