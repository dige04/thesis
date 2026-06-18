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

## A6 — Seeds 3 → 1 (deadline-constrained)
- **Date:** 2026-06-17
- **Change:** main matrix runs **1 seed** (8 sequences × 6 policies = **48 runs**)
  instead of 3 seeds × 144 runs.
- **Reason:** 10-day submission deadline. The full 144-run matrix + anchor-probe
  is multiple days of compute and cannot fit alongside analysis + writing +
  defense prep. 1 seed **preserves** the N=8 sequence-level primary test
  (Invariants #1, #11), CL-F1 (#9), and anchor-probe (#29); it relaxes only the
  within-cell replication.
- **Validity:** the single seed is identical across all conditions/sequences
  (fixed factor); between-policy comparisons remain valid. Robustness to seed
  noise is reduced → the seed dimension is **exploratory**; disclose prominently
  as a limitation. The 2 gate-3 sequences (django, pytest) are reused.
- **Adaptive:** if compute finishes with time to spare, add seed 2.
- **Touches:** v5 Invariant #2 (3 seeds / 144 runs). Disclose prominently.

---

## D1–D5 — Runtime deviations
Provider/model, embedder, cost metric, classifier structured-output path, and
execution host/architecture. Full table + rationale in `CLAUDE.md` (and v5 §0.1
deviations). Summary: D1 model → Kimi "for coding" (kimi-k2.6); D2 embedder →
local Ollama `nomic-embed-text-v2-moe` (768-d); D3 cost metric → token-count
proxy; D4 classifier → JSON-mode + Pydantic (and see A2 re: temperature); D5 host
→ x86_64 DigitalOcean droplet, prebuilt swebench images.

---

## A7 — A6 REVERTED: 3 seeds / 144 runs RESTORED
- **Date:** 2026-06-17
- **Change:** the main matrix runs the full **3 seeds × 8 sequences × 6 policies
  = 144 runs**, restoring v5 Invariant #2. A6's 1-seed reduction is **withdrawn**.
- **Reason:** the move to a **free-unlimited** generative provider (MiniMax M3 via
  the 0G router — see D6) removed the per-call quota/cost pressure that motivated
  A6, and a **5-VPS horizontal fleet** (snapshot-cloned droplets, sharded across
  the 144 policy×seed×sequence units, ~20 concurrent eval slots) brings the full
  matrix inside the deadline (~12–20 h wall-clock).
- **Validity:** Invariant #2 satisfied as pre-registered; 3-seed within-cell
  replication restored, so the seed dimension is **no longer exploratory**. No
  gate-3 reuse — all 144 runs are fresh on M3 (no model mixing).
- **Touches:** restores v5 Invariant #2; supersedes A6.

## D6 — Provider switch: Kimi → MiniMax M3 (supersedes D1's model choice)
- **Date:** 2026-06-17
- **Change:** the frozen generative model is **MiniMax M3** (OpenAI-compatible via
  the 0G `router-api.0g.ai` endpoint), replacing Kimi-k2.6 (D1). Held **constant
  across all 6 conditions × 3 seeds** (agent + reflection + CLS consolidation +
  5-type classifier — one model, all roles). Embeddings unchanged (local Ollama,
  D2).
- **D6a — Reasoning model.** M3 emits `<think>…</think>` CoT (on by default, no
  documented disable). CoT is **stripped** (`src/model_output.strip_reasoning`)
  before JSON parsing, before embedding into memory records (Invariant #4 payload
  stays CoT-free), and before re-sending agent turns; trajectory logging already
  excludes message content (v5 §11.3). **Cost-axis caveat:** M3 completion-token
  counts include reasoning tokens, so the D3 token-cost Pareto axis is inflated vs
  a non-reasoning model — **uniform across all conditions** (between-policy
  comparison valid), but absolute token cost is **not** comparable to a
  Kimi/GPT-5.4 design. (D1 originally chose Kimi to keep this axis clean; the
  free-unlimited access outweighed it under deadline.) Disclose.
- **D6b — No JSON mode.** M3 returns `400 model_not_capable` for
  `response_format={"type":"json_object"}`. All three structured-output sites
  (classifier #7, reflection, CLS consolidation #9) **drop** `response_format` and
  use prompt-instructed JSON + tolerant extraction
  (`src/model_output.extract_json_object`) + Pydantic validation. Extends D4;
  classifier failure rate logged identically across conditions.
- **D6c — Multi-key rotation.** The 0G free tier rate/credit-limits per API key; a
  **16-key pool** (`FREE_LLM_CHAT_API_KEYS`) is rotated per request with failover
  on 402/429/401, **failing closed** only when the whole pool is exhausted — so
  balance depletion can never silently corrupt the matrix as false `resolved=0`
  (402/insufficient_balance now classified fatal in `is_usage_limit_error`).
- **Execution (extends D5):** 5 snapshot-cloned x86_64 droplets (the fleet) in
  addition to the original; matrix sharded across them (`run_matrix_shard.sh`).
- **Reversible:** `.env`-only (drop FREE_LLM_* → back to Kimi/OpenAI).
- **Touches:** supersedes D1 (model); extends D3 (cost axis), D4 (JSON path), D5
  (host/fleet). Matching edits to CLAUDE.md's deviation table proposed separately
  (locked file — not auto-edited).

## D7 — M3 (D6) discarded; reverted to Kimi `kimi-k2.7-code` agent + `deepseek-v4-flash` aux (DRAFT — review)
- **Date:** 2026-06-18
- **Change:** The MiniMax M3 run (D6) is **discarded** (no usable data; provider
  switch ⇒ no model-mixing). The matrix is re-executed on Kimi. **Per-role split:**
  the **coding agent** = `kimi-k2.7-code` (Kimi "For Coding" subscription via the
  CLIProxyAPI sub, plus OpenCode go for the same model id); the **auxiliary LLM
  roles** (5-type classifier, reflection, CLS-consolidation summary) = the much
  cheaper `deepseek-v4-flash` on OpenCode go, routed through a per-role aux client
  (`AUX_LLM_CHAT_*` → `src.config.llm_factory.get_aux_client`). Embeddings unchanged
  (local Ollama, D2).
- **Final matrix composition:** **132 units** = agent `kimi-k2.7-code` + aux
  `deepseek-v4-flash`; **12 reused gate-3 units** (django + pytest, seed-1, all 6
  policies) = agent `kimi-k2.6` + aux `kimi-k2.5`. Within **every (sequence × seed)
  cell all 6 policies use identical models**, so the model never confounds a
  between-policy contrast (H1–H5). **Sensitivity check:** re-run the primary tests
  dropping the 2 gate-3 cells (django-s1, pytest-s1) and confirm conclusions hold.
- **D7a — Auxiliary model on a 2nd vendor (DeepSeek).** Defensible as held constant
  across all conditions; the aux LLM does **not** author the retrieval payload
  (Invariant #4 = raw `[Issue+Final Error+Final Diff]` + nomic embedder), only the
  type label + record metadata. **Classifier failure rate logged**; calibration on
  the real classifier path = **0% failure**, accurate 5-type labels.
- **D7b — Reasoning handled per provider.** Sub `kimi-k2.7-code` emits inline
  `<think>…</think>` → stripped (`strip_reasoning`). go `deepseek-v4-flash` returns
  reasoning in a separate `reasoning_content` field → `message.content` already
  clean. Both paths parsed by `extract_json_object` + Pydantic. The D6a token-cost-
  axis inflation (reasoning tokens counted) **persists** for the k2.7-code agent
  (≈96% of tokens); uniform across conditions.
- **Execution.** 5 sfo3 droplets, **systemd-managed** (`thesis-tunnel` /
  `thesis-matrix@<shard>` / `thesis-doctor@<shard>`, `Restart=always`,
  boot-persistent); agent reaches the sub via an **nyc1-anchored SSH tunnel** (scoped
  forward-only key); a per-droplet **doctor** auto-heals disk/ollama/tunnel/process
  and heartbeats. Sharded `i % 5`, `RUNS_ROOT=runs_k27`. **Fail-closed** on go-cap
  (402) preserved — no false `resolved=0`.
- **Retained:** 3-seed/144 (A7); A1 (cap=10), A2 (temp=1), A3, A4.
- **Reversible:** `.env`/`AUX_LLM_CHAT_*` only.
- **Touches:** supersedes D6 (model) + A7's "all 144 fresh on M3" clause.

## D8 — D7 SUPERSEDED: single model = `deepseek-v4-flash` (OpenCode go) for ALL roles; all-144 fresh
- **Date:** 2026-06-18
- **Change:** the per-role split (D7: agent k2.7-code on the Kimi sub + DeepSeek aux) is **withdrawn**
  because the Kimi For-Coding **subscription's monthly quota cannot carry 144 units** (~5% of the
  monthly burned for ~109 partial tasks / 0 completed units in the pilot fleet). New design: **one
  model, all roles — `deepseek-v4-flash` on OpenCode go** (agent + 5-type classifier + reflection +
  CLS summary), **default thinking**. Embeddings unchanged (local Ollama nomic, D2).
- **Why valid + chosen:** Flash ≈ 79% SWE-bench Verified / smoke ~50% resolve **≈ the k2.6 gate-3
  rate** (not floor); it's another **fixed-factor model deviation** (like D1/D6), held constant across
  all 6 conditions × seeds ⇒ between-policy contrasts valid; absolute rates not leaderboard-comparable.
  **All 144 run FRESH on Flash** — the 12 k2.6 gate-3 units are **dropped** (Flash is cheap to re-run,
  so a single-model 144 is cleaner than a k2.6↔Flash cross-vendor mix). This **removes** the D7
  agent/aux model mix entirely → the matrix is a clean single model.
- **D8a — Thinking level.** Flash on go accepts `reasoning_effort` (low/med/high, modest effect) and
  `thinking.budget_tokens` (stronger). Pilot 2026-06-18: `reasoning_effort=high` gave **no resolve or
  stability gain** vs default (+7% tokens) → **default thinking** (held constant; disclose). Agent has
  an optional config `agent.reasoning_effort` (off by default). Flash is a light reasoning model → the
  D6a token-cost-axis inflation caveat persists (uniform across conditions).
- **D8b — Cost/quota.** go is one $-capped account (~158k DeepSeek-Flash req/mo at $60). Matrix ≈
  ~108k requests ≈ ~68% of one account → fits, but a **multi-key pool** (`FREE_LLM_CHAT_API_KEYS`) +
  `KeyRotatingClient` failover lets additional go accounts' keys be appended on 402 (fail-closed; no
  false `resolved=0`). go allows concurrency ⇒ the 5-VPS fleet parallelizes (unlike the rate-capped sub).
- **Execution:** 5 sfo droplets, systemd `thesis-matrix@`/`thesis-doctor@` (no `thesis-tunnel`); doctor
  is the all-go variant (go-quota gauge). ~1–1.5 d wall-clock.
- **Retained:** 3-seed/144 (A7); A1–A4.
- **Touches:** supersedes D7 (model + per-role split + sub/tunnel) and D6/D1 (model).
