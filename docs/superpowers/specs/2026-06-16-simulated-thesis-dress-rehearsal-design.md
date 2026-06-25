# Spec — Simulated Thesis Dress-Rehearsal (full pipeline, synthetic data)

Date: 2026-06-16
Status: APPROVED (user steered 3 decision points on 2026-06-16)
Owner: Leo Dinh / Claude Code swarm

## Purpose

Produce a **complete, watermarked, SIMULATED** master's-thesis report (and an EMSE
paper-length extract) end-to-end from **synthetic data**, to:

1. Validate the raw → aggregate → stats → tables → figures → prose pipeline before
   real data exists.
2. Preview the final artifact shape so the empirical chapters are write-ready.
3. Exercise the pre-committed "triggered framings" (Discussion §6 of the honest draft).

This is a **dress rehearsal**, NOT real findings. Every number is fabricated by a
seeded generator and watermarked `SIMULATED`. It must never be confused with results.

## Hard integrity constraints (non-negotiable)

- All work lives under **new** locations; the honest `paper/thesis_draft.typ` and the
  pre-existing `paper/thesis_report_simulated.typ` are **left untouched**.
- Output dirs: `paper/simulated/`, `scripts/simulate/`, `results/simulated/`.
- Every page of every PDF carries a banner: `SIMULATED — SYNTHETIC DATA — NOT REAL RESULTS`.
- Every results table/figure caption embeds `[SIMULATED]` and names the scenario + seed.
- A `paper/simulated/README.md` documents the DGP, the master seed, the cap assumption,
  and the exact command to regenerate everything.
- `src/` is NOT modified. Statistical fixes (TOST, Holm, r_rb zero-handling, GLMM) live in
  an isolated `scripts/simulate/sim_analysis.py`; wiring them into `src/analysis` is the
  separate real task E3 (out of scope here).

## Decisions (user-confirmed 2026-06-16)

| # | Decision | Value |
|---|---|---|
| D-cap | Memory budget for the simulation | **cap = 100** (as-configured, inert pruning). Disclosed. CLI-parameterized. |
| D-primary | Scenario rendered in the main body | **Null/realistic**; best & worst → Appendix "Scenario sensitivity". |
| D-scope | Deliverables | **Full master's thesis** + **EMSE extract**. |
| D-rigor | Data rigor | **Seeded DGP + real analysis** producing real tables/figures from synthetic data. |
| D-existing | Pre-existing simulated file | Keep `thesis_report_simulated.typ` as-is; new work in `paper/simulated/`. |

## Synthetic data-generating process (DGP)

Deterministic, seeded by `hash(scenario, policy, sequence, seed)`. Matches the real
`TaskResult` schema (34 fields, see `src/logging/task_logger.py`) exactly, plus
`anchor_probe.json`, `memory_events.jsonl`, `retrieval_overlap.jsonl` matching the real
formats (build agents read the source to conform).

Grounding magnitudes (loosely from wave-1 pilot): resolved rate ~10–18%, ~80–120k
total tokens/task. Per-task resolve probability is a logistic function of
`(policy_effect[scenario], sequence_position, task_difficulty, seed_noise)`.

CL-F1 derived from an anchor-probe matrix: plasticity = mean diagonal accuracy;
stability = 1 − mean(forgetting over k=5 anchors at 4 probe points). Cost telemetry:
Full Memory pays most context tokens; No Memory least; CLS adds consolidation LLM cost.

### Policy behavior under cap=100 (inert pruning) — must be reflected honestly

- **Random / Recency / Type-Aware Decay**: never evict (cap 100 > max seq len 50) ⇒
  generated with the SAME latent resolve-prob as Full Memory + independent seed noise ⇒
  paired Δ ≈ 0. H1a equivalence holds *trivially*; report must disclose this is a
  configuration artifact, and that **H2 is not testable** here.
- **CLS Consolidation**: fires every k=5 tasks regardless of cap ⇒ genuinely differs
  (consolidation cost, compressed footprint, scenario-dependent perf).
- **No Memory**: genuine contrast (memory-value axis), magnitude varies by scenario.

### Three scenarios

- **best** — memory clearly helps (No Memory ≪ Full); CLS non-inferior to Full at lower
  footprint but higher token cost (H3: CLS fails Pareto on cost); Full shows behavioral
  bloat (H4). H2 untestable (disclosed).
- **null** — memory barely helps (No Memory ≈ Full); all conditions overlap; H1a Outcome D
  (inconclusive at N=8); H2/H4 null. **(primary in main body)**
- **worst** — CLS consolidation loses information ⇒ degrades (H1a Outcome C for CLS);
  H5 boundary fires (consolidation removed critical memory); Full Memory wins.

## Analysis (sim_analysis.py)

Imports the real, working modules (`aggregate_results`, `plots`, `pareto`,
`result_tables`, `retrieval_overlap`) via a configurable `--runs-root`. Provides
CORRECTED statistics that the real code currently gets wrong:

- **Holm** correction (monotonicity in raw-p order) — golden-tested vs `statsmodels`.
- **TOST** with ±0.03 SESOI + BCa 95% CI on median paired Δ (H1a; currently absent).
- **rank-biserial r_rb** with correct zero-difference handling.
- **GLMM** binomial/logit via a working statsmodels path (or documented fallback).

Emits per scenario: `sequence_aggregates.json`, the four result-table CSVs + Typst
fragments, and PNG figures (Pareto, sequence bars, memory growth, behavioral, failure).

## Deliverables

```
paper/simulated/
  README.md                       # DGP, seed, cap assumption, rebuild command
  _watermark.typ                  # banner + helpers imported by both docs
  thesis_full_simulated.typ       # A) full thesis (design chapters reused + sim empirical)
  emse_extract_simulated.typ      # B) EMSE paper-length extract
  tables/{best,null,worst}/*.typ  # generated table fragments
  figures/{best,null,worst}/*.png # generated figures
  *.pdf                           # compiled outputs
scripts/simulate/
  generate_synthetic_runs.py      # DGP
  sim_analysis.py                 # analysis driver + corrected stats + golden tests
  run_all.py                      # orchestrate gen → analyze → tables → figures
results/simulated/{best,null,worst}/
  runs/<run_id>/task_results.jsonl, anchor_probe.json, memory_events.jsonl, ...
  aggregated/*.csv, sequence_aggregates.json
  plots/*.png
```

## Swarm phases (verify-gates between)

- **P0** scaffold (folder, README, watermark) — done by orchestrator.
- **P1** build (2 parallel agents): DGP script; analysis driver + stat fixes + golden tests.
- **P2** generate + analyze 3 scenarios → tables/figures. **GATE: orchestrator + user
  review the generated numbers before any prose is written.**
- **P3** write (parallel section authors): Results, Discussion, Conclusion/Abstract,
  Scenario-sensitivity appendix; assemble full thesis + EMSE extract (reuse design chapters
  from `thesis_draft.typ`).
- **P4** compile both PDFs (`typst compile`); verify table↔prose number consistency;
  integrity sweep (banner on every page, every number watermarked).

## Out of scope

- Modifying `src/`, `THESIS_FINAL_v5.md`, `CLAUDE.md`, `thesis_draft.typ`,
  `thesis_report_simulated.typ`.
- Running any real experiment or claiming any real result.
- Adding conditions 7/8/9 or changing frozen invariants.
