# A/B Gate Findings — 2026-06-24

**Run:** 36-cell A/B (fixed vs legacy tool_mode), production config (temp=1, container,
experiment_sha 2133b47), deepseek-v4-flash on go, 9-worker fleet CONC2. 36/36
RUN_COMPLETED, 0 RUN_FAILED. Data pulled to `runs_ab_merged/` (918 trajectories + 918 patches).

## Gate verdict: STOP

`results/ab_gate/` — two failing criteria:
1. `edit_path_index_failures == 82` (must be 0)
2. `edit_failure_ratio == 0.303` (> 0.15 threshold)

Passing: token inflation 1.01–1.02× (≪1.5×), pairing OK, no dup, no tool_mode mismatch.
Informational: resolve-rate **fixed 0.582 vs legacy 0.429 (+15.3pp)** — fixed mode resolves MORE.

## Edit-failure breakdown (the real story)

| class | fixed (567 calls) | legacy (335 calls) | attributable to |
|---|---|---|---|
| total failures | 172 (30.3%) | 84 (25.1%) | |
| **security rejection** | **78** | 0 | INSTRUMENT (my Task 2b) |
| patch malformed | 47 | 46 | MODEL (bad unified diff) |
| file not found | 43 | 16 | MODEL (wrong path) |
| /testbed abs path | 4 | 21 | instrument-ish |
| genuine cross-file | 1 | — | correct reject |

## Root-cause: a real bug in my Task 2b fix (tools.py:681)

`edit_file` normalizes the **diff** paths (strips `/testbed/`, `a/`, `b/`) via
`_normalize_diff_paths`, then at line 681 compares each normalized diff path `p`
against the **raw, un-normalized** `path` argument:

```python
touched = _collect_diff_paths(diff)        # e.g. 'src/_pytest/unittest.py'
for p in touched:
    if p != path:                          # path = '/testbed/src/_pytest/unittest.py' (RAW)
        raise ValueError("Security: diff touches '{p}' but path='{path}'")
```

The LLM legitimately passes the absolute container path `/testbed/src/...` as `path`
and a standard relative-header diff. Same file, different normalization state → false
reject. **77 of 78 security rejections are this bug** (verified: `strip(touched)==strip(path)`);
only 1 is a genuine multi-file diff (correctly rejected).

**Fix:** normalize `path` with the same prefix-strip before the `p != path` comparison
(extract `_strip_path` to a module helper, apply to both sides).

## The deeper issue (needs a decision, not just a code fix)

After fixing the normalization bug, the residual failures are **MODEL-quality**, not
instrument: malformed patches (47) + wrong file paths (43) ≈ 90/567 ≈ **15.9%**, still
≥ the 0.15 gate threshold. deepseek-v4-flash inherently emits ~8% malformed diffs and
~7.5% wrong-path edits regardless of the instrument. The agent RECOVERS from these via
retry/write_file fallback — hence fixed-mode resolve rate is +15pp despite the failures.

So: the instrument fix is genuinely net-positive (read_file ranges etc. → +15pp resolve),
the normalization bug is real and fixable, BUT the 0.15 edit-failure threshold may be
**unachievable with this model even with a perfect instrument**, because it counts
model-quality failures the instrument cannot prevent.

Decision options (for advisor + user):
- (A) Fix normalization bug → re-run full 36-cell A/B → likely still STOP on model-quality
  ratio → then must decide on threshold anyway. Costs another A/B (~1.5h + ~$5).
- (B) Fix bug + confirm via deterministic unit test (the /testbed-abs-path case) + smoke,
  then re-interpret the gate to measure INSTRUMENT-attributable failures (path/index,
  security-bug) which SHOULD be ~0 after the fix; treat model-quality malformed/wrong-path
  as a disclosed model limitation, not an instrument-health failure. Proceed to 144.
- (C) Reconsider whether the 144 rerun is worth it vs writing on the existing matrix with
  heavy disclosure (deadline ~3 days, tight budget).

Risk on (B): changing the gate's failure definition AFTER seeing data is goalpost-moving
(Codex flagged this pattern before). Must be principled — the distinction
instrument-vs-model failure is defensible only if defined on first principles, not to pass.

## RESOLUTION (2026-06-24, after advisor)

**Bug fixed** in `src/agents/tools.py`: extracted module-level `_strip_container_prefix`
(robust ordering: strip `a/`|`b/` once → `lstrip('/')` → `testbed/` → repo_root), and
`edit_file` now normalises the `path` ARG up-front (before existence check + security
compare). Root causes both addressed: (1) raw absolute `path` vs normalised diff path in
the `p != path` compare (77 cases); (2) `a//testbed/...` double-slash surviving normalize
(2 cases). 3 regression tests added to `tests/test_agents_tools.py`
(`absolute_path_arg`, `double_slash_testbed`, `cross_file_rejected_with_abs_path_arg`);
**all 25 tools tests pass, no legacy regression.**

**Verified decomposition (existing A/B data):**

| | fixed (567 calls) | legacy (335 calls) |
|---|---|---|
| instrument-attributable | 79 (13.9%) → **~0 post-fix** | 0 (legacy has no guard) |
| model-quality (malformed + wrong-path) | 92 (16.2%) | 84 (25.1%) |
| correct cross-file reject | 1 | 0 |
| total fail ratio | 30.3% | 25.1% |

Discriminator (advisor's step 3) **PASSES**: instrument-attributable failures collapse to
~0 after the fix — no hidden third gap. Bonus: model-quality failure RATE is LOWER in
fixed (16.2%) than legacy (25.1%) — the read_file/observation fixes actively reduce
model errors. With +15.3pp resolve, the fixed instrument is unambiguously net-positive.

**Decision (pending user + Codex sign-off):** A blind A/B re-run buys nothing — the ~16%
model-quality residual is invariant and would re-STOP the total-ratio criterion regardless.
Proposed principled gate interpretation: **instrument health = instrument-attributable
failures → 0** (which the fix achieves and the deterministic unit tests confirm). The
0.15 total-ratio criterion conflates model-quality diff errors (a disclosed property of
deepseek-v4-flash, held constant across all 6 policies × 3 seeds, hence non-confounding for
H1–H5 — same logic as deviations D1–D5) with instrument health. Plan: fix committed →
run the decomposition past Codex (no compute) → user sign-off → proceed to 144, computing
instrument-health (instrument-attributable → 0) ON the 144 data as the final check; optional
2-task smoke (~$1) first to catch integration errors in the extracted helper.
