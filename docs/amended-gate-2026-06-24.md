# Amended A/B Instrument-Health Gate (declared BEFORE re-run)

**Status:** PRE-RUN declaration. Written and committed BEFORE any re-run data exists,
so the criteria are pre-registered, not fitted to observed results.

**Provenance / honesty clause (binding on thesis wording):**
The ORIGINAL §5 gate (spec `2026-06-22-trustworthy-rerun.md`) returned **STOP** on the
36-cell A/B at experiment_sha `2133b47` (artifact: `results/manifest/ab_gate_STOP_2133b47.json`;
root cause: `docs/ab-gate-findings-2026-06-24.md`). That STOP stands and is preserved. The
thesis Methods MUST state: *the original pre-registered A/B gate STOPped; root-cause analysis
attributed 79/172 fixed-mode edit failures to an instrument bug (path normalization), which was
fixed as a post-gate hotfix; the gate was then amended (criteria below) and re-validated at a
new SHA.* Do NOT state the original gate passed.

## Why amend (root cause, in brief)

The original gate's two failing criteria — `edit_path_index_failures > 0` and
`edit_failure_ratio > 0.15` — were both driven by a bug in the Task-2b fix: `edit_file`
compared the normalized diff path against the RAW absolute `path` argument, yielding 77 false
"security" rejections (same file, `/testbed` prefix), plus 2 `a//testbed` normalize gaps.
After the hotfix, instrument-attributable failures → ~0 (deterministic unit tests confirm).
The residual ~16% edit-failure rate is **model-quality** (deepseek-v4-flash emits malformed
diffs / wrong paths), present in BOTH arms, recovered from via retry (fixed resolve +15.3pp,
and fixed model-error rate 16.2% < legacy 25.1%). The original 0.15 *total*-ratio criterion
conflates model-quality errors — a property of the frozen model held constant across all 6
policies × 3 seeds (cf. deviations D1–D5) — with instrument health.

## Amended GO criteria (ALL must hold) — Codex 2026-06-24

Computed on FRESH re-run data at the new (post-hotfix) experiment SHA:

1. **Instrument-attributable edit failures == 0** — zero false security rejections (a security
   rejection is "false" iff `strip(touched) == strip(path_arg)`), zero `/testbed`/`a//testbed`
   normalize-gap failures, zero path/index failures of instrument origin.
2. **No false security/path-index rejects** (the operational form of #1, checked per-trajectory).
3. **Token inflation ≤ 1.5×** — fixed median ≤ 1.5× legacy median on prompt_tokens AND total_tokens.
4. **Complete pairing** — every (sequence, policy, seed, task_id) present in BOTH legacy and fixed.
5. **Model-quality sanity lower-bound:** model-quality edit-error RATE (fixed) ≤ rate (legacy).
   (Guards against the hotfix silently making the agent worse; the fix must not regress diff quality.)

The original `edit_failure_ratio ≤ 0.15` is **retired** for this model and **replaced** by #1+#5:
instrument health is measured by instrument-attributable failures (→0) and a non-regression
sanity bound on model-quality, NOT by an absolute total-ratio the instrument cannot control.

## Decision rule

- **All 5 pass on the re-run → GO → scale to 144.** Instrument-health is then re-confirmed ON
  the 144 data itself (instrument-attributable → 0) as the final check.
- **Any fail → STOP.** Re-diagnose; do not proceed.

## Minimum-acceptable fallback (if re-running 36 is infeasible on time/budget)

Per Codex: commit + refreeze + a 2-task production smoke + an explicit "protocol exception"
signed by user + advisor. Same honesty clause applies (original gate STOPped, amended after
root-cause). This is strictly weaker than the re-run and must be labeled as such.
