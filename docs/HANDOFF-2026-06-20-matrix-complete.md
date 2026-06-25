# HANDOFF — 144-unit matrix run (2026-06-20)

**Status: runs COMPLETE — 144/144 verified clean (2026-06-22). The cls_astropy_seed1 re-run completed clean on sfo-6 (22 tasks, 5 resolved, 0 FAISS/container errors; FAISS bug did NOT recur) and is now pulled to the Mac (runs_k27_merged + runs_legacy_merged/sfo-6). Re-aggregated: headline SURVIVES — all 5 Wilcoxon contrasts still n.s. after Holm; only cls_consolidation moved (astropy s1 0.0→0.227 → p 0.195→0.3125, r_rb −0.556→−0.444, less significant). cls mean now 0.2915. Droplets STILL HELD pending anchor-probe (A5) decision — do NOT delete until A5 decided. NOTE: a 10th droplet `ubuntu-s-4vcpu-8gb-nyc1` (nyc1, NOT in the 9-node sfo3 fleet) is also active — provenance unknown, exclude from any fleet-delete.**

## TL;DR

The pre-registered matrix — **6 policies × 8 SWE-Bench-CL sequences × 3 seeds = 144 units** — ran on a single uniform model **`deepseek-v4-flash` (OpenCode go; all roles: agent + classifier + reflection + CLS; default thinking)**.

**Headline (on RESOLVE RATE, not full CL-F1 — see caveat 1): no policy differs significantly from full_memory.** Wilcoxon N=8, all 5 contrasts n.s. after Holm. This matches the gate-3 prior. The CL-specific signal (forgetting / backward-transfer / stability) is **NOT measured** in this run — the anchor-probe (A5) is still pending.

## Data locations (all on Mac)

| Artifact | Path | Coverage |
|---|---|---|
| Outcome data: task_results + cost_summary + memory_events + snapshots | `runs_k27_merged/` | 143/144 task_results (1 re-running), 144/144 rest |
| **Trajectories + memory.db/.faiss** (were only in droplet `runs/` due to store.py:99 bug) | `runs_legacy_merged/sfo-{0..8}/` | 144/144 trajectories, 144/144 faiss |
| Aggregated sequence results | `results/aggregated/sequence_aggregates.json` | 6×8 |
| Wilcoxon + effect sizes | `results/tables/{stats,effect_sizes}.csv` | 5 contrasts |
| Interdependence / E7 | `results/tables/{memory_lift,structural_interdependence}.csv` | |
| Pareto plots (two-axis) | `results/plots/{pareto_compute,pareto_footprint}.png` | |

Outcome verification (143 complete units): 4653 task_rows, 1467 resolved (31.5%), **0/4653 container/pull pollution**.
Re-aggregate: `.venv/bin/python -m scripts.run_analysis --stage all --runs-dir runs_k27_merged --out results`

## Key results (resolve-rate basis)

| Policy | resolve rate | Tokens/unit (±std) | mem_tok/task | tool_calls/task |
|---|---|---|---|---|
| recency_prune | 0.330 | 5.96M (±2.30) | 698 | 21.4 |
| full_memory | 0.311 | 5.74M (±2.27) | 2986 | 21.5 |
| type_aware_decay | 0.300 | 6.06M (±1.99) | 682 | 21.4 |
| random_prune | 0.290 | 6.06M (±2.26) | 666 | 21.6 |
| cls_consolidation | 0.290* | 6.26M (±2.11) | 908 | 21.5 |
| no_memory | 0.287 | 5.41M (±2.29) | 0 | 21.6 |

*cls_consolidation will shift slightly after the astropy-seed1 re-run replaces the broken 0-task unit.

**Wilcoxon vs full_memory — ALL n.s.:** no_memory p=0.109 (r_rb −0.667), recency p=0.383 (+0.389), cls p=0.195 (−0.556), type_aware p=0.313 (−0.444), random p=0.945 (−0.056). All BCa CIs cross 0.

**Token cost is agent-loop-dominated, NOT memory-driven.** `prompt_tokens ≈ 151K/task` (20-step ReAct, conversation resent each step); memory ≈ 0.4–1% of that; `tool_calls/task ≈ 21.5` identical across all policies. Per-policy total-token gaps (~0.2–0.5M) are within noise (std ±~2.2M; paired, full_memory used *more* tokens than recency in 16/24 cells). Pruning's real saving is on the **footprint axis** (full 2986 vs prune ~700 tok/task ≈ 4× lighter) → the point of the two-axis Pareto (A4/H1b).

**E7 interdependence (memory_lift):** heterogeneous — helps pytest (+0.21), matplotlib (+0.09); hurts pydata (−0.14), django (−0.06), astropy (−0.05). Memory's value depends on intra-sequence task interdependence.

## Caveats / known issues

1. **CL-F1 reported = RESOLVE RATE proxy.** Aggregate warns `no anchor_probe.json present`; `mean_cl_f1 == mean_resolved_rate` exactly. The thesis's CL-specific metric (forgetting/backward-transfer/stability) is **unmeasured**. Do NOT claim the headline holds for true CL-F1 — that is untested. Resolve the anchor-probe (A5) first (see pending #2).
2. **FAISS bug in cls_consolidation** (1 occurrence): `IndexFlat::reconstruct ... 'key < ntotal' failed` aborted `cls_consolidation_astropy_seed1` at 0 tasks. Isolated (only FAISS error fleet-wide; only 0-row unit). Re-running on sfo-6 (24.144.92.6) — exercises the same path; if it recurs it is a real code bug (out-of-range reconstruct in the consolidation step) needing a fix, not just a re-run.
3. **Result-marker is written even on catastrophic failure** AND cost_summary can exist with 0 task_results — so "has cost_summary" ≠ complete. Reconcile by task_results row count + `error_message`, not marker/cost_summary presence.
4. **store.py:99 bug** routes memory.db/.faiss + trajectories to `runs/` not `RUNS_ROOT` — that's why a second pull (`runs_legacy_merged/`) was needed. Fix before the next run.
5. **Model not stamped per row.** Provenance = dir separation + `configs/base.yaml`@b495e6e + `MODEL_PROVENANCE.json` per droplet + AMENDMENTS.md **D8**. Stamp model into rows next time.

## Why 7 OTHER units were re-run earlier (resolved)

Verified root cause = **Docker Hub unauthenticated pull rate limit** (`swebench/sweb.eval...` images; "You have reached your unauthenticated pull rate limit" → tools.py:364 "Failed to start container"). NOT LLM quota (402/429 = 0). Fail-loud-aborts the whole unit (never a false resolved=0): 0/4653 pollution. Re-ran clean on healthy hosts. Mitigation: `docker login` (→200/6h) or pre-pull. (`timeout_tasks` ≠ failures — it's "agent used all 20 steps", counted even when resolved=1.)

## Pending (need user / next session)

1. ~~Finish the cls_astropy_s1 re-run, pull + re-aggregate.~~ **DONE 2026-06-22** — pulled from sfo-6 (overwrote broken 0-task copy), re-aggregated, headline survived. Now truly 144/144.
2. **Anchor-probe (A5) decision** — `docs/a5-anchor-probe-decision.md` recommends running **option (b)**: a cheap targeted discrimination test (tens of re-evals) on *interdependent* anchors (django/pytest + a high-overlap seq), Full Memory vs aggressive prune, ≥3× each — to decide whether the stability instrument can discriminate at all (stability=1.000 may be measurement-blindness, same phenomenon as E7) before committing the full ~1,900-re-eval probe. This needs the eval images (droplets or local) → another reason to HOLD droplets until decided.
3. ~~DELETE droplets~~ **MOSTLY DONE 2026-06-22**: data confirmed fully pulled (144/144 outcome + every unit's legacy trajectories/faiss), then deleted **9 droplets** — 8 idle sfo + the nyc1 box (`ubuntu-s-4vcpu-8gb-nyc1` = original kimi-k2.6 dev box, all runs 06-17 pre-D8, NOT in the 144). **Only m3-sfo-4 (143.198.230.28) kept**, running the A5 discrimination probe; delete it once the probe completes + results pulled. NOTE: matrix data is now **Mac-only** (runs_k27_merged 87M + runs_legacy_merged 255M) — consider a backup before deleting sfo-4 if you want cloud redundancy (though sfo-4 only has its shard, not all 144).
4. **Write-up** — feed resolve-rate results + two-axis Pareto + E7 into `paper/report/` Results-by-hypothesis. Frame CL-F1 honestly as resolve-rate unless the anchor-probe is run.

## Droplet fleet reference

DigitalOcean x86_64, `/root/thesis`, all-go-Flash `.env`, local ollama embeddings:
`0=209.38.73.215 1=164.92.103.21 2=209.38.66.73 3=146.190.38.23 4=143.198.230.28 5=143.244.186.89 6=24.144.92.6 7=144.126.209.63 8=143.198.136.147`
Old sfo-0..4 = NUM=5 shards; new sfo-5..8 = NUM=9. systemd `thesis-matrix@N` / `thesis-doctor@N`. SSH must be **foreground** (background fails Keychain); multi-SSH loops stay foreground only with per-host incremental echo.
