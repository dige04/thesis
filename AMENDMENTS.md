# Pre-registration Amendments & Runtime Deviations

Authoritative record of every change to the frozen pre-registration
(`THESIS_FINAL_v5.md`) and every runtime deviation. **Each must be disclosed in
the thesis Methods → "Deviations from pre-registration."** This file is the paper
trail that protects the study against "you moved the goalposts after seeing data."

Principle applied to every entry: a change is defensible only if it is (a) a
mechanical fix to an inconsistency a deviation introduced, OR a construct
correction the mechanism demands; (b) decided and dated before the affected data
is collected; (c) held **constant across all conditions × seeds**; (d) disclosed.

---

## A1 — Binding memory budget (record cap 100 → 10)
- **Date:** 2026-06-14
- **Change:** `memory.max_records` 100 → **10** (`configs/base.yaml`).
- **Reason:** all 8 official sequences are 19–50 tasks with one record/task, so a
  cap of 100 never binds → Random/Recency/Type-Aware/CLS were operationally
  identical to Full Memory (pruning never fired). Confirmed in the simulated
  dress-rehearsal and the live wave-1 pilot.
- **Validity:** the cap is applied identically to all four pruning policies (and
  CLS fallback); Full Memory remains the boundary baseline and ignores the cap by
  design. 10 < the shortest sequence (19) → pruning binds on all 8.
- **Disclosure:** Methods → Deviations. (Sanctioned under v5 §0.1 #6 "documented
  compute/scope trade-off"; this is the budget that makes H2 testable.)

## A2 — Temperature 0 → 1 (agent, reflection, **classifier**, CLS summary)
- **Date:** 2026-06-14
- **Change:** temperature 0 → **1** for the agent (`base.yaml`), reflection
  (`base.yaml`), the **type classifier** (`classifier.py` `TEMPERATURE`), and the
  CLS summary LLM.
- **Reason:** the Kimi "for coding" reasoning endpoint rejects `temperature=0`
  (only 1 accepted).
- **Validity:** temperature is held constant across all policies, sequences, and
  seeds, so it is a fixed factor — between-policy comparisons stay valid.
- **⚠ Disclosure-hygiene (open cleanup):** this amendment touches the **classifier**,
  which v5 deviation D4 / Invariant #7's *task* described as "temp-0 deterministic."
  The change does NOT alter the 5-type taxonomy (Invariant #7 proper); it makes
  classification non-deterministic → **log + report the classifier failure rate.**
  Code comments in `classifier.py` still read "FROZEN: Always 0" and `CLAUDE.md`
  D4 still says "temp-0 task" — these must be corrected to reference this
  amendment. (Tracked; not yet applied to the locked files pending user edit.)

## A3 — CLS old-memory threshold 10 → 5 (= cap/2)
- **Date:** 2026-06-17
- **Change:** `cls_consolidation.OLD_MEMORY_THRESHOLD` 10 → **5**.
- **Reason:** **derived consequence of A1.** At `cap=10` the active set spans ~10
  consecutive sequence indices, so the oldest active record is only ~9 tasks old
  and never reaches the v5 threshold of 10 → CLS could never select candidates and
  ran as its Type-Aware fallback (gate-3: 0 consolidation events, H3 untestable).
  Lowering to cap/2 = 5 lets the oldest ~5 records qualify so consolidation can
  fire. This restores the consistency the A1 cap amendment broke; it is **not** a
  result-chasing tweak (decided before the corrected CLS data is collected).
- **Validity:** identical across all CLS runs; `MIN_CLUSTER_SIZE=3`, k=5 interval,
  architectural-exclusion all unchanged.
- **VALIDATION (2026-06-17), on real gate-3 CLS records:** A3 makes candidates
  available (5–10 per probe vs 0 before) — but **CLS still consolidates 0× at
  every probe on both django and pytest.** The binding constraint is the
  *clustering* (#23: DBSCAN needs ≥3 memories at ≥0.70 cosine), not the age.
  Diverse same-repo coding memories (each a different issue) do not form
  ≥3-clusters at 0.70. **Conclusion:** CLS is structurally inert on SWE-Bench-CL
  for a reason A3 cannot fix. **We will NOT lower `SIMILARITY_THRESHOLD`** to
  force it — that is frozen #23, would merge dissimilar memories into garbage
  summaries, and would be result-chasing. **H3 (compressive forgetting) is
  therefore reported as a negative / not-applicable result on this benchmark:
  CLS degenerates to its Type-Aware-Decay fallback.** CLS stays in the matrix
  (preserve the locked 6 conditions, Invariant #2) and is expected to ≡
  Type-Aware empirically; the negative H3 is itself a finding.
- **Touches:** v5 Invariants #23 (CLS params) and #30/H3. Disclose.

## A4 — H1b construct: token-savings → storage footprint / retrieval latency
- **Date:** 2026-06-17
- **Change:** H1b reframed from "≥20% fewer total tokens" to **memory storage
  footprint + retrieval latency** (operational efficiency), reported on the
  two-axis Pareto (compute-token vs footprint-token).
- **Reason:** the mechanism cannot deliver token savings — retrieval is fixed at
  `top_k=5` / `max_context_tokens`, so storage pruning does not reduce the prompt
  budget, and every task still pays reflection/classifier/embedding cost. Gate-3
  E1 telemetry showed CLS *adds* ~10% tokens. "20% fewer tokens" would be
  trivially falsified; footprint/latency is the honest, mechanism-aligned axis.
- **Validity:** decided before the full-matrix cost analysis. H1a (CL-F1
  non-inferiority, the load-bearing claim) is unchanged. Disclose; report H1b
  separately under §19.
- **Touches:** v5 §0.1 #30 (H1b lock). Disclose.

## A5 — Anchor-probe scope (PENDING — advisor decision before the matrix)
- **Date raised:** 2026-06-17 (not yet decided)
- **Context:** the gate-3 linchpin E2 run found **anchor-probe stability saturated
  at 1.000** (zero detected forgetting on the 5-anchor sample) → CL-F1 reduces to
  a function of plasticity. At full-matrix scale the anchor-probe is ~1,900 live
  re-evaluations (~days of compute) to measure a dimension that, in the pilot, was
  uninformative. **Options:** (a) keep full anchor-probe; (b) run it on a subset of
  runs to check it ever discriminates; (c) accept plasticity-driven CL-F1 and
  demote anchor-probe stability. Touches v5 Invariant #29 (anchor-probe = PRIMARY
  CL-Stability). **Decide before committing the matrix's anchor-probe budget.**

---

## D1–D5 — Runtime deviations
Provider/model, embedder, cost metric, classifier structured-output path, and
execution host/architecture. Full table + rationale in `CLAUDE.md` (and v5 §0.1
deviations). Summary: D1 model → Kimi "for coding" (kimi-k2.6); D2 embedder →
local Ollama `nomic-embed-text-v2-moe` (768-d); D3 cost metric → token-count
proxy; D4 classifier → JSON-mode + Pydantic (and see A2 re: temperature); D5 host
→ x86_64 DigitalOcean droplet, prebuilt swebench images.
