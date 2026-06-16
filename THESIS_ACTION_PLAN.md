# THESIS_ACTION_PLAN.md — Reconciled Action Plan (control tower)

**Created:** 2026-06-16 · **Bar:** Master's, full rigor (confirmed) · **Target:** audit-valid pilot → full 144-run matrix → thesis report.

This is the **single status board**. It reconciles four sources and de-duplicates them; it does **not** repeat their detail:

| Source | Role | Use it for |
|---|---|---|
| `THESIS_FINAL_v5.md` | design source of truth | what is frozen, formulas, schemas |
| `THESIS_REVIEW.md` (2026-06-11) | authoritative deep **code** review | problem detail (C1–C7, E1–E8, N1, W1–W2, P1), risk register |
| `docs/superpowers/plans/2026-06-16-thesis-pilot-to-report.md` | **execution** manual | step-by-step files/commands per task |
| kimi Review A (inline) + B (`~/Downloads/thesis_review.md`) | reviews of the **simulated** thesis PDF | prose-spec gaps, reporting framing |

**Status legend:** ✅ DONE (landed; may be uncommitted in the parallel gate-3 session) · 🔄 IN-FLIGHT · 🟡 PORT (solved in `scripts/simulate/sim_stats.py`, move into `src/`) · ❓ VERIFY (may be done in recent commits — confirm first) · ⬜ OPEN · 🔒 ADVISOR (frozen-decision touchpoint — decide & disclose, never silently change) · ⛔ REJECTED (a review proposed it; do **not** adopt).

---

## 1. One-screen status

- **Critical path to a valid full run:** ~~E3 (port stats)~~ ✅ DONE → **E2 (anchor-probe: core ✅, live re-eval wiring pending on host)** → E6 (manipulation pilot, in flight) → **E7 (interdependence: core ✅, runs on gate-3 data)** → E8 (reproducible analysis) → W2 (write results).
- **#1 scientific risk (under-addressed everywhere):** does memory even help? Tasks are *chronological*, not proven *interdependent*. Wave-1 pilot hint: full 12/69 vs no_memory 10/69 — inside the noise floor. If Full ≈ NoMemory, forgetting is moot regardless of policy. **This is E7 and it is missing from the 7-task plan and from both kimi reviews.**
- **Disclosure-cleanup item (code-verified):** classifier runs at `temperature=1` — this is **approved** (amendment A2), but the code comments still say `# FROZEN: Always 0` and `CLAUDE.md` D4 still says "temp-0". Doc hygiene, not a bug. See §3.
- **Already closed since the 06-11 review:** the whole Phase-A correctness set (**C1–C8**), E1, C7b, plus a real end-to-end task — verified this session. Don't redo them (§2).

---

## 2. Already closed — do NOT redo (verify-then-trust; uncommitted in gate-3 session)

| Item | Evidence | Note |
|---|---|---|
| **C1** binding cap | `configs/base.yaml:60` `max_records: 10`; plumbed at `experiment_runner.py:193,204–213`; `tests/test_memory_budget_binds.py` | **10 is correct** (below the 19-task shortest → binds on all 8). Logged as amendment A1. |
| **C3–C8** correctness blockers | 866 tests; verified this session: C4 single retrieval (`langgraph_agent.py:701,742–755`), C5 quota fail-closed (`reflection.py:225–232`; `experiment_runner.py:443,617`), C8 errored-task split (`sequence_runner.py:86–87,310–311`) | C3 (20-turn pin), C6 (CLS provenance + `log_consolidate`), C7a (tuple crash) also done. **Only C7-relevance remains** (§4). |
| **E1** complete cost telemetry | `tests/test_cost_telemetry_e1.py`; gate-3 reports `pareto_cost_complete=True` | enables H1b/H3 + two-axis Pareto |
| **C7b** retrieval-overlap producer | `src/analysis/retrieval_overlap.py`; `tests/test_retrieval_overlap.py` | this **is** kimi's "Jaccard gate" recommendation — already built |
| Gate-2 manipulation check | `scripts/gate2_manipulation_check.py` | archive/consolidate events fire under cap=10 |
| One real end-to-end task | NoMemory · `pytest-dev__pytest-5262` · resolved=1 · all mandatory logs | pipeline can complete a real SWE-bench task (was 0/3) |

> ⚠️ These live in a **parallel session and are UNCOMMITTED**. Coordinate before committing/restarting prod (`francaisvn`). Honor read-only until ownership is settled.

---

## 3. REJECTED from the kimi reviews (do not adopt) + new integrity items

| ID | Item | Verdict |
|---|---|---|
| ⛔ | **cap = 25** (kimi A & B) | Wrong: leaves 3/8 sequences (19,22,22) still inert → heterogeneous manipulation, dilutes N=8. You already set **10**. Done correctly. |
| ⛔ | **Reduce to 3 contrasts / Benjamini-Hochberg FDR** (kimi B P3) | Violates invariant #11 (Wilcoxon + Holm on **5** pre-registered contrasts). Changing the contrast set/correction *after seeing results* to chase power is the exact researcher-DoF pre-registration kills. Keep 5; lead with estimation; **disclose** underpowering. |
| ⛔ | kimi B power-analysis numbers ("Fitts 2025", BCa coverage table, `[^1^]`–`[^18^]`) | Unverified; same profile as the citations `THESIS_REVIEW.md` already had to retract. Direction (BCa under-covers at small N) is real; the numbers are not. Do not paste. |
| ⛔ | Treating simulated footprint/Pareto numbers as findings | "CLS 47% smaller", "Pareto-optimal on footprint" are **DGP knobs**, not results. Only real sim assets: corrected stats, pipeline-runs proof, two design lessons. |
| ⬜ **A2-CLS** | **Classifier (+CLS summary) run at `temperature=1`** (`classifier.py:78`) — **approved & known** (amendment A2, 2026-06-14: Kimi reasoning models reject temp=0), *not* a hidden bug. Real gap is **disclosure hygiene**: `classifier.py:216` comment still says `# FROZEN: Always 0`, docstrings still say "temperature=0", `CLAUDE.md` D4 still calls it a "temp-0 task", and the A2 record names only agent/reflection. | **Not** an invariant-#7 violation (that's the taxonomy, unchanged) — it's a *reproducibility* deviation held constant across all conditions, so between-policy contrasts stay valid. **Action:** fix the contradictory comments/docstrings; name the classifier in `AMENDMENTS.md` A2; update `CLAUDE.md` D4; log the classifier failure-rate (matters more now that classification is non-deterministic). |

---

## 4. Critical path — prioritized, de-duplicated (open work)

Grouped by phase. "Detail" = where the step-by-step lives.

### Phase A — correctness (essentially DONE — see §2)
C1–C8 are landed and test-backed (verified this session). Only two items remain:
| ID | Item | Status | Detail |
|---|---|---|---|
| C7-rel | Replace vacuous same-repo relevance in `retrieval_quality.py` (default `same_repo=True` + Invariant #16 ⇒ relevant set == candidate pool ⇒ precision/recall trivial) | 🔒 ADVISOR | needs a pre-declared structural criterion (e.g. touched-file overlap) or a blinded labeled set — `THESIS_REVIEW.md` #7 |
| #2 | Confirm `max_storage_tokens` enforcement, or formally declare the record-cap (10) the sole binding budget | ❓ VERIFY | lower-stakes now the record-cap binds; just disclose which budget is authoritative |

### Phase B — measurement (the primary outcome + correct stats)
| ID | Item | Status | Detail |
|---|---|---|---|
| **E2** | Anchor-probe CL-F1 producer `src/benchmark/anchor_probe.py` | 🟡 CORE DONE | schedule math (§14.2: 5 anchors × 4 probes) + orchestration + schema + round-trip through the real loader/metric, all tested (`tests/test_anchor_probe.py`, 10). **Live wiring pending on run host:** real `restore_memory_fn` (snapshot + `memory.db`), `solve_and_eval_fn` (agent + evaluator), top-level `produce_anchor_probe`. Reject proxy CL-F1 in final analysis. |
| **E3** | TOST + Holm fix + r_rb zero-handling in `statistical_tests.py` | ✅ DONE | golden-tested vs statsmodels; `tests/test_statistical_tests.py` (14). Closes #11–#13; public API preserved. |
| **E3-GLMM** | R `lme4::glmer` canonical (Invariant #14 crossed effects) + working `BinomialBayesMixedGLM` fallback | ✅ DONE | advisor decision 2026-06-16; dead `glmer` import removed; `tests/test_glmm.py` (6). Closes #14. |
| E4 | Rebuild feature analysis (leakage-free; the weak-label rule currently emits **no positive class**) | ⬜ OPEN | `THESIS_REVIEW.md` #16; LOSO CV, fold-local scaling, held-out PR-AUC |

### Phase C — gates (each gates the next; don't skip)
| ID | Item | Status | Detail |
|---|---|---|---|
| C2 | Confirm x86_64 host, sync docs, run/retire build-probe gate | 🔄 PARTIAL | de facto x86_64 droplet; CLAUDE.md D5/AGENTS/README still narrate arm64 |
| E6 | Smoke → manipulation-check → 12-run pilot, with go/no-go | 🔄 IN-FLIGHT | gate-3 pilot ~near done; gate-2 script exists |
| E5 | Provenance (config/git/model-id/embedder hashes) + resume/skip-completed | ⬜ OPEN | protects the multi-day matrix |

### Phase D — the scientific de-risk (ELEVATED — missing elsewhere)
| ID | Item | Status | Detail |
|---|---|---|---|
| **E7** | **Quantify interdependence + contamination.** NoMemory–Full Δ by position (early/late split); structural file-overlap with earlier tasks (gold-patch files); contamination/cutoff disclosure. | 🟡 CORE DONE | machinery `src/analysis/interdependence.py` (`memory_lift_by_position`, `structural_interdependence`, `parse_patch_files`) + `tests/test_interdependence.py` (13). **Runs on gate-3 / full-run data** — the does-memory-help verdict. `THESIS_REVIEW.md` #19/E7; missed by both kimi reviews; the linchpin. Contamination/cutoff disclosure prose still to write. |

### Phase E — analysis reproducibility + write-up
| ID | Item | Status | Detail |
|---|---|---|---|
| E8 | `make aggregate/stats/plots` real targets + lockfile + `make lint` runs mypy | ⬜ OPEN | 7-task plan Task 5 Step 5 |
| N1 | Replace "first Pareto map" claim; **verify every `refs.yml` entry verbatim**; add layer taxonomy (app-memory vs prompt-compaction vs KV-eviction) | ⬜ OPEN | citation-hallucination history makes this mandatory |
| W1 | Manuscript implementation-accuracy (provider, host, 19–50 task counts, amendments A1/A2, cost construct) | ⬜ OPEN | after C1/C2/A2 settle |
| W2 | Results **only** from generated tables; two-axis Pareto as primary (kimi A/B, correct); fold in kimi B §2.3 prose-spec gaps¹ | ⬜ OPEN | after E2/E8 |
| P1 | Repo doc sync (README/AGENTS/.env.example) | ⬜ OPEN | after C2/W1 |

¹ kimi B §2.3 genuinely-useful prose gaps to specify in the write-up: Jaccard formula + threshold, stability `f̄` formula, exact Holm ordering, **CLS trigger semantics** (verified: rolling counter, fires every 5th task since last fire; trailing <5 tasks at sequence end are *not* consolidated — `cls_consolidation.py:293–303`), classifier validation/failure-rate, embedding-truncation example.

---

## 5. Advisor decision queue (frozen touchpoints — bring evidence, don't pre-decide)

1. **Degree/deadline** — master's confirmed; is `MASTER_PLAN.md` 2026-08-17 still the deadline? (sets whether the full matrix fits)
2. **A2-CLS classifier temperature** — accept temp=1 (disclose) or move classifier to a temp-0 model? (invariant #7)
3. **GLMM backend** — statsmodels Bayesian mixed GLM vs R `lme4::glmer`? (invariant #14 wording)
4. **H1b construct** — keep "20% fewer tokens" or revise to storage-footprint/retrieval-latency *before* data? (mechanism doesn't support token savings under fixed top_k=5 — `THESIS_REVIEW.md` #17; kimi A agrees)
5. **Provider budget** — full matrix ≈ 20× one pilot; OpenCode go weekly quota wall. Paid balance vs model switch vs staged runs?
6. **Contrast set** — confirm all 5 stay (recommended). Any change is a pre-registration amendment with a *theoretical* (not power-chasing) justification, decided before real data.

---

## 6. Sequencing

Execute via `docs/superpowers/plans/2026-06-16-thesis-pilot-to-report.md`, with two amendments from this reconciliation:
1. **Insert E7** as a first-class step inside the pilot phase (between its Task 4 and Task 6), not after the full run.
2. **E3 is a PORT, not a build** — start from `sim_stats.py`; the hard work is done and golden-tested.

**Done 2026-06-16:** E3 (✅), GLMM (✅), E2 core (✅), E7 core (✅) — all TDD, full suite 935, ruff clean, uncommitted. **E2 live-wiring** handoff spec for the run host: `docs/superpowers/specs/2026-06-16-e2-anchor-probe-live-wiring.md`.

**Next:** run the E2 + E7 machinery on gate-3 output (real CL-F1 + the does-memory-help/interdependence verdict — the linchpin). Still locally-buildable: **E4** (feature-analysis leakage rebuild) and **E8** (`make aggregate/stats/plots` + lockfile). On the host: E2 live wiring (per the spec).
