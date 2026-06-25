# Trustworthy Re-run: Agent Tool-Contract Fixes + Seed-Aware Analysis + 144-Run Re-execution — Spec & Plan

> **Revision v4 (2026-06-22)** — addresses Codex 3rd-pass ("gần pass", 6 precision blockers). Changelog §0.
>
> **For the reviewer (Codex):** v4 makes the remaining items executable — exact GO formulas (§5), no-blind-slice read budget (§3.1/Task 1), full completion-artifact contract (§3.7/Task 5b), unified run_dir (§3.8/Task 2c), split baseline/experiment SHA (Task −1/Freeze), and a fully-pinned A/B (Task 6).

**Goal:** Make the agent capable of reading/editing real files, fix seed-aware analysis, log termination + enforce a real completion contract, validate at the production condition, then re-run all 144 in a fresh *unified* namespace — accepting whatever result emerges.

**Tech Stack:** Python 3, pytest, OpenAI-compatible `deepseek-v4-flash` (D8), Docker `linux/amd64` swebench, x86_64 DigitalOcean + systemd.

## 0. v6 Changelog (Codex 5th-pass — APPROVE implementation, conditional; Phase A may start)
- **E1 Fleet + A/B tooling into Phase A:** NEW Task 5e (A/B scheduler `ab_schedule.py` + gate calculator `ab_gate.py`) and Task 5f (manifest+sentinel fleet runner refactor) are coded/tested/committed **before Freeze**; Tasks 6/7 are pure execution.
- **E2 A/B requires 36/36:** §5 gate now requires **36 `RUN_COMPLETED`, 0 failed, 0 interrupted, exact legacy↔fixed pairing** before ANY metric is computed; `RUN_FAILED` blocks the gate (not "observable").
- **E3 Retry lifecycle:** §3.7 — re-running archives the prior attempt to `{run_dir}.attempt{k}/`; exactly one terminal marker per live run dir; no evidence deletion.
- **E4 Unique A/B run_id:** `run_id` includes `tool_mode` (Task 5e) so legacy/fixed cells of the same `(seq,policy,seed)` never collide.
- **Gate:** Codex APPROVED implementation — **Task −1 + Phase A may begin**; Freeze / A/B / droplets remain blocked behind their gates.

## 0. v5 Changelog (Codex 4th-pass — "after these I can approve implementation")
- **D1 Baseline branch:** Task −1 baselines from **current HEAD `8f0fe3b`** (feat/analysis-e3-e2-e7), NOT `main` (`a205791`); audits tracked + untracked.
- **D2 Freeze ordering:** §6 split into **PHASE A (all code+tests, incl. `AGENT_TOOL_MODE` flag = Task 5c and orchestrator gating = Task 5d, committed) → FREEZE → PHASE B (execution-only)**. No code commits post-Freeze.
- **D3 Uniform completion contract:** §3.7 drops the `no_memory` exemption (runner builds store/snapshots/db/faiss for all 6 — verified) and adds `patches/{task_id}.patch` (`save_patches: true`).
- **D4 Durable failed state:** §3.7 adds atomic **`RUN_FAILED.json`** at the orchestration exception boundary (incl. `UsageLimitError` before re-raise); completed/failed/interrupted are distinguishable after restart.
- **D5 Orchestrator counters:** Task 5d gates `completed_runs += 1` + success `{run_id}_result.json` on the validated sentinel (`experiment_runner.py:433,607,353`, `run_pilot_policy.py:81`).
- **Precision:** `total_edit_file == 0` ⇒ gate FAILS; token gate now covers `total_tokens/task` too; `tool_mode` persisted in sentinels + task rows.

## 0b. v4 Changelog (Codex 3rd-pass)
- **C1 RUNS_ROOT split (P1):** NEW §3.8 + Task 2c — `MemoryStore` hardcodes `Path("runs")/run_id` (`store.py:99`, ignores `RUNS_ROOT`); inject one `run_dir` into `MemoryStore` + `TrajectoryLogger`; test all artifacts land under the fresh namespace.
- **C2 SHA split (P1):** Task −1 records `baseline_sha`; a **Freeze gate** records `experiment_sha` + config/manifest hashes **after** all impl/test commits; A/B + 144-run use `experiment_sha` only.
- **C3 A/B placeholders (P1):** Task 6 pins exact sequences, seeds, schedule seed; `legacy` flag toggles **schema + prompt + implementation**; mode recorded per run; full matrix fails closed unless `fixed`.
- **C4 Read budget (P1):** §3.1/Task 1 — **shrink-to-consistency** loop; the header's claimed `last` always equals the rows included → continuation `last+1` never skips lines; no blind final slice.
- **C5 Completion contract (P1):** §3.7/Task 5b — exact artifact list (incl. snapshots, memory.db/faiss, provenance), writer integration point, completed/failed/interrupted states, per-artifact rejection tests.
- **C6 Gate thresholds (P1):** §5 — exact denominators/cutoffs; range-correctness defined for fitting vs bounded ranges; **edit failure > 15% = mandatory STOP**.
- **Task −1 (P1):** isolated worktree + diff audit + **STOP for user confirmation**; no auto-stash/commit of WIP.

## Global Constraints
- Frozen invariants untouched: 6 policies, 8 sequences, 3 seeds = 144; max 20 turns (#3, `langgraph_agent.py:852`); pure-cosine retrieval (#5); best-LAST (#6); payload < 7500 tok (#4).
- **Temperature = 1, held constant** (A2, `limit_tracker.py:238`).
- Single frozen model `deepseek-v4-flash` (D8); fix identical across conditions.
- Fresh **unified** `RUNS_ROOT` + fresh marker namespace; never mix old/new.
- Suite green (**baseline 981**); new tests additive.

---

## 1. Why this spec exists
Prior validation was unit-level on tiny fixtures, and the prior "completion" check was a `cost_summary` written in a `finally` (present even for partial runs). v4 reproduces the production condition (large files, real failing tests, `/testbed` diffs, multi-seed fixtures) and enforces manifest-exact completion. Detail §4.

## 2. Confirmed defects + evidence
> Indicative; **Task 0 recomputes canonically** (outcomes `runs_k27_merged`; trajectories joined from `runs_legacy_merged`).

| # | Defect | Location | Impact |
|---|---|---|---|
| D-1 | `read_file` no range; args dropped | `tools.py:423`; schema `langgraph_agent.py:75` | 74% reads pass ignored range args; 94.6% hit the 4000-cap; 63% re-read |
| D-2 | `_MAX_OBS=4000` head-truncation | `langgraph_agent.py:48,923,925` | agent sees only file head |
| D-3 | tail failures hidden | `:986,:990-991` | run_command 10% / run_tests 3.1% truncated |
| D-4 | `get_patch` unregistered; shell grep/sed | `prompts.py:39` vs `:74-90` | 471 hallucinated calls |
| D-5 | E7 seed mix + silent partial | `run_analysis.py:107-123` | corrupts GROUNDED_FACTS §5 |
| D-6 | `edit_file` no path-norm/security | `tools.py:455-499` | 30.2% fail (912/3,024): 42% bad-diff, 24% stale, 23% path |
| D-7 | no `termination_reason` | loop exits | finish/timeout unobservable |
| D-8 | artifacts split off `RUNS_ROOT` | `store.py:99` (`Path("runs")/run_id`) | FAISS/db/snapshots ignore RUNS_ROOT |

**Existing matrix is INCOMPLETE:** `runs_k27_merged` = 144 dirs / **4,675 rows / 239 missing** (expected 4,914), ~28 incomplete units; `cost_summary.json` in a `finally` (`sequence_runner.py:349`) made "144/144 clean" false at the completeness level; `runs_legacy_merged` has 0 task rows, 296 extra files, 103 unresolvable dup trajectories.

**Verified-FALSE (excluded):** step-cap violation — 20-turn cap enforced at `:852`. **Hypothesis (not asserted):** finish≈0/high-timeout *may* be D-1/D-6 non-convergence — test with D-7.

## 3. Design

### 3.1 `read_file` ranges + numbering + **exact** budget (D-1, C4)
- `read_file(path, start_line=None, end_line=None)`, 1-indexed inclusive, numbered. Validate `start≥1`, `end≥start`, `start≤n`.
- `MAX_READ_LINES=400`, `MAX_READ_CHARS=12000`. **Shrink-to-consistency:** greedily collect rows, then while `header(last)+body > MAX_READ_CHARS` pop the last row (so `last` and the continuation `read_file(path, last+1, e)` always match the rows actually returned). A single oversized line is truncated in place with `last=s` (continuation → `s+1`). **No blind slice.** Full code in Task 1; output is provably ≤ MAX_READ_CHARS with zero skipped lines between calls.

### 3.2 Tail-preserving truncation (D-2, D-3) — code in Task 2.
### 3.3 Schema + prompt (D-1, D-4) — code in Task 3.
### 3.4 Seed-aware E7 + completeness (D-5) — key `(policy,repo,seed,index)`; paired-per-seed lift; drop+report incomplete cells; float diff.
### 3.5 `edit_file` path-norm + container-root security (D-6, B5) — `path` is authority; strip `/testbed/`, backend-resolved repo root, `a/`,`b/`; reject cross-file/multi-file/`..`; `-p0` retry.
### 3.6 `termination_reason` (D-7) — enum {`finished_tool`,`model_no_tool_calls`,`step_limit`,`wall_time`,`tool_call_limit`,`test_run_limit`,`llm_error`}; **no `usage_limit`** (run-level abort, no TaskResult; recorded at run level).

### 3.7 Completion contract — uniform across all 6 policies (C5, B8, D2)
`validate_run_complete(run_dir, manifest_entry) -> (ok: bool, missing: list[str])` applies **one contract to every policy including `no_memory`** (the runner creates `MemoryStore`/snapshots/db/faiss for all six — `sequence_runner.py:151,177,419,504`). Checks:
- `task_results.jsonl` task-id set **==** `manifest_entry["task_ids"]` (no missing, no duplicate);
- per task: `trajectories/{task_id}.json` AND `patches/{task_id}.patch` present (`save_patches: true`, base.yaml:139, written at `:450-452`);
- per task index k: `memory/snapshots/before_task_{k}.json` + `after_task_{k}.json`;
- run-level: `memory/memory.db`, `memory/memory.faiss`, `memory_events.jsonl`, `cost_summary.json`;
- no recorded run-level fatal error.

**Tri-state markers (all atomic temp+rename), distinguishable after a process restart:**
- **completed** → `RUN_COMPLETED.json`, written in the SequenceRunner **success path after the task loop returns cleanly (NOT in `finally`)**, only if `ok`. Contents `{experiment_sha, config_hash, manifest_hash, tool_mode, task_count, validated_at}`.
- **failed** → `RUN_FAILED.json`, written at the **orchestration exception boundary** (catches `UsageLimitError` and any run-level exception *before* it re-raises — currently it re-raises with no durable record). Contents `{error_type, error_message, experiment_sha, tool_mode, failed_at}`.
- **interrupted/killed** → neither marker present → reconcile re-runs.

**Retry lifecycle (exclusive transitions, no evidence loss):** re-running a unit that has a `RUN_FAILED.json` (or is interrupted) first **moves the prior attempt directory to `{run_dir}.attempt{k}/`** (archived, not deleted), then starts a clean `{run_dir}`. Invariant: a live `{run_dir}` carries **exactly one** terminal marker (`RUN_COMPLETED.json` XOR `RUN_FAILED.json`) or none (in-flight/interrupted) — never both. `cost_summary` is a log, never a completion signal.

### 3.8 Unified run_dir (D-8, C1)
`MemoryStore` and `TrajectoryLogger` take an explicit `run_dir` (default RUNS_ROOT-aware) instead of hardcoding `Path("runs")/run_id`; `SequenceRunner` passes `self.run_dir` to both, so task rows, trajectories, snapshots, `memory.db`, `memory.faiss`, and `memory_events.jsonl` all land under the one fresh `run_dir`.

## 4. Validation Strategy
1. **Unit:** read budget (exact len + no-skip + oversized progress + invalid range); `_truncate_obs` ≤ limit + tail; edit normalize/reject incl. container-root; seed paired+drop; termination per exit; `validate_run_complete` accept + reject-per-artifact; unified run_dir.
2. **Realistic integration:** >400-line/>12000-char fixture; 30KB pytest tail survives; `/testbed` diff applies; cross-file rejected; **all artifacts under one run_dir**.
3. **Mandatory real-task smoke:** ≥3 task IDs (gold patch in >4000-char file past line 200) at `experiment_sha`; assert ranged read, no repeat loop, edit success, termination + sentinel.
4. **Multi-seed analysis regression** (drops incomplete cell; FAILS on current code).
5. **Contemporaneous A/B** (Task 6): one `experiment_sha`, `AGENT_TOOL_MODE` flag toggling schema+prompt+impl, pinned task set + randomized schedule, same provider window.

## 5. Acceptance criteria — INSTRUMENT HEALTH ONLY (exact, executable)
> Gated on the instrument, never the result. resolve/gap deltas reported as context only.

**Freeze gates:**
- [ ] **Task −1:** isolated worktree from baseline; diff-audit report; **STOP for user confirmation** of baseline membership (no auto-commit); record `baseline_sha` + `results/manifest/runs_144.json` (assert 144 runs, Σtasks=4,914).
- [ ] **Post-impl Freeze:** after ALL Phase-A tasks green (1, 2, 2b, 2c, 3, 5, 5b, 5c, 5d, **5e, 5f**, 4a — incl. all fleet + A/B tooling), record `experiment_sha`, `config_hash`, `manifest_hash`. Phase B (4b, 6, 7) uses `experiment_sha` ONLY — no code commits.

**Code gates:** suite ≥ 981 + the 5 new test groups; `termination_reason` on 100% of task rows; `validate_run_complete` unit-tested (accept + reject per artifact); unified run_dir test green.

**Instrument-health GO gate (all hold on the A/B `fixed`-mode runs; exact):**
- [ ] **Range correctness = 100%**: over a deterministic harness, every ranged read is either (a) *exact* — output line set == requested [s,e] — when [s,e] fits the budget, or (b) *contiguous-prefix-with-valid-continuation* — output == [s,last], `last<e`, and the hint requests exactly `last+1..e` (no gap, no overlap) — when it does not. Failures = 0.
- [ ] **Edit path/index failures = 0**: `count(edit_file obs matching "/testbed"-path OR "does not match index") == 0`.
- [ ] **Overall edit failure ≤ 15%**: requires `total_edit_file > 0` (else **gate FAILS** — no edit activity to validate, ratio undefined); then `failed_edit_file / total_edit_file ≤ 0.15`. **If > 0.15 → MANDATORY STOP for user decision** (escalate the §7 search/replace tool), not a silent proceed.
- [ ] **Token inflation (both axes):** `median(prompt_tokens_per_task | fixed) ≤ 1.5 × median(prompt_tokens_per_task | legacy)` AND `median(total_tokens_per_task | fixed) ≤ 1.5 × median(total_tokens_per_task | legacy)` on the A/B set.
- [ ] **Provenance:** every run records its `tool_mode` (in the sentinel + task rows); legacy and fixed outputs are never mixed in any aggregate.
- [ ] **No duplicate rows:** `count(distinct (policy,seed,task_id)) == count(rows)`.
- [ ] **A/B is complete + paired (precondition for ALL metrics above):** **36/36 runs have `RUN_COMPLETED.json`, 0 `RUN_FAILED`, 0 interrupted**, and every `(sequence, policy, seed, task_id)` is present in BOTH `legacy` and `fixed` (exact pairing). The edit-rate / token / range-correctness metrics are computed **only** on this complete paired set — a `RUN_FAILED` does NOT count as "observable"; it blocks the gate until re-run completes (retry lifecycle §3.7).

**Full re-run DoD:** 144/144 manifest units have `RUN_COMPLETED.json` (validator passed); aggregates from the NEW namespace only; `dropped_incomplete` empty.

## 6. Tasks

### Task −1: Isolated baseline worktree + manifest (C2, D1)
- [ ] **Step 1:** Create an isolated git worktree from **the current HEAD `8f0fe3b` on `feat/analysis-e3-e2-e7`** (superpowers:using-git-worktrees) — **NOT `main` (`a205791`)**, which lacks the D8 provider/fleet/runtime commits. Inventory **both** tracked-uncommitted changes (`git diff`, `git diff --staged`) **and** untracked files (`git status --porcelain`) into a categorized audit report (`results/manifest/diff_audit.md`).
- [ ] **Step 2: STOP — ask the user** which tracked + untracked changes belong to the intended runtime baseline. Do NOT auto-stash or auto-commit user WIP.
- [ ] **Step 3:** On the confirmed baseline, record `baseline_sha`; generate `results/manifest/runs_144.json` (policy×sequence×seed×task_id from the curriculum; assert 144 runs, Σtasks=4,914). Commit the manifest.

### Task 0: Canonical diagnostic + smoke-task selection (B2)
- [ ] Outcomes ← `runs_k27_merged/*/task_results.jsonl` (assert 144 dirs/4,675 rows; report complete/incomplete/missing vs manifest). Trajectories ← join `runs_legacy_merged` by `(run_id,task_id)`; **exclude+list** the ~103 unresolvable dups → `results/preflight/ambiguous_trajectories.json`. Compute defect rates → `runner_defects.json`. Emit `smoke_tasks.json` (≥3 IDs, gold patch in >4000-char file past line 200). Commit.

### Task 1: `read_file` ranges + numbering + budget (D-1, C4)
**Files:** `src/agents/tools.py:423`; `tests/test_agents_tools.py`.
- [ ] **Step 1: Failing tests**
```python
def test_read_file_range_exact_when_fits(tmp_path):
    f = tmp_path/"b.py"; f.write_text("\n".join(f"line{i}" for i in range(1,501)))
    out = AgentTools(working_dir=str(tmp_path)).read_file("b.py", 180, 182)
    assert "180\tline180" in out and "182\tline182" in out and "183\t" not in out and "179\t" not in out

def test_read_file_budget_and_no_skip(tmp_path):
    from src.agents.tools import MAX_READ_CHARS
    f = tmp_path/"b.py"; f.write_text("\n".join(f"line{i}" for i in range(1,5001)))
    out = AgentTools(working_dir=str(tmp_path)).read_file("b.py", 1, 5000)
    assert len(out) <= MAX_READ_CHARS
    import re
    last = max(int(x) for x in re.findall(r"(?m)^(\d+)\t", out))   # highest line shown
    assert f"read_file(path, {last+1}," in out                    # continuation == last+1 (no skip)

def test_read_file_oversized_line_progresses(tmp_path):
    from src.agents.tools import MAX_READ_CHARS
    f = tmp_path/"b.py"; f.write_text("x"*(MAX_READ_CHARS*2)+"\nnext")
    out = AgentTools(working_dir=str(tmp_path)).read_file("b.py", 1, 2)
    assert len(out) <= MAX_READ_CHARS and "truncated" in out and "read_file(path, 2," in out

def test_read_file_invalid_and_oob(tmp_path):
    f = tmp_path/"s.py"; f.write_text("a\nb\nc"); t=AgentTools(working_dir=str(tmp_path))
    assert "invalid range" in t.read_file("s.py",3,1).lower()
    assert "past end" in t.read_file("s.py",99).lower()
```
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3: Implement** (consts `MAX_READ_LINES=400`, `MAX_READ_CHARS=12000`):
```python
def read_file(self, path: str, start_line: int | None = None,
              end_line: int | None = None) -> str:
    args = {"path": path, "start_line": start_line, "end_line": end_line}
    if not self.backend.exists(path):
        error = f"File not found: {path}"; self.tracker.record_call("read_file", args, None, error)
        raise FileNotFoundError(error)
    if not self.backend.is_file(path):
        error = f"Path is not a file: {path}"; self.tracker.record_call("read_file", args, None, error)
        raise ValueError(error)
    try:
        content = self.backend.read_text(path)
    except Exception as ex:
        self.tracker.record_call("read_file", args, None, str(ex)); raise
    lines = content.splitlines(); n = len(lines)
    self.tracker.record_call("read_file", args, len(content))
    s = max(1, int(start_line)) if start_line else 1
    e = n if end_line is None else int(end_line)
    if e < s:
        return f"# {path} ({n} lines): invalid range start_line={s} > end_line={e}."
    if s > n:
        return f"# {path} ({n} lines): requested start_line {s} is past end of file."
    e = min(n, e)
    def header(last):
        if last < e:
            return (f"# {path} (lines {s}-{last} of {n}; showing through {last} of requested "
                    f"{s}-{e}. Call read_file(path, {last + 1}, {e}) to continue.)\n")
        return f"# {path} (lines {s}-{last} of {n})\n"
    rows = [f"{i}\t{lines[i-1]}" for i in range(s, min(e, s + MAX_READ_LINES - 1) + 1)]
    while rows:
        last = s + len(rows) - 1
        out = header(last) + "\n".join(rows)
        if len(out) <= MAX_READ_CHARS:
            return out
        if len(rows) == 1:
            hdr = header(s); suffix = f" …[line {s} truncated]"
            avail = max(0, MAX_READ_CHARS - len(hdr) - len(f"{s}\t") - len(suffix))
            return hdr + f"{s}\t{lines[s - 1][:avail]}{suffix}"
        rows.pop()
    return header(s)
```
- [ ] **Step 4:** Run → PASS.  - [ ] **Step 5:** Commit.

### Task 2: Tail-preserving, length-correct truncation (D-2, D-3)
- [ ] Failing test (`len(out) <= _MAX_OBS`, head + tail "FAIL:" survive) → implement `_MAX_OBS=12000` + marker-reserving `_truncate_obs` (final `[:limit]` guard) → apply `:923,:925`; `_execute_tool` forwards `start_line`/`end_line` → PASS → commit.

### Task 2b: `edit_file` normalization + container-root security (D-6, B5)
- [ ] Failing tests (`/testbed/m.py` applies; backend-resolved repo-root prefix stripped; cross-file `other.py` rejected; `../escape.py` rejected) → implement `_normalize_diff_paths(diff, repo_root)` + cross-file/traversal guard + `-p0` → PASS → commit.

### Task 2c: Unified run_dir across MemoryStore + TrajectoryLogger (D-8, C1)
**Files:** `src/memory/store.py:99`, `TrajectoryLogger`, `src/benchmark/sequence_runner.py:151,854`; Test `tests/test_run_dir_unified.py`.
- [ ] **Step 1: Failing test** — run a tiny 2-task sequence under `RUNS_ROOT=tmp/runs_x`; assert `task_results.jsonl`, `trajectories/*.json`, `memory/snapshots/*`, `memory/memory.db`, `memory/memory.faiss`, `memory_events.jsonl` **all** exist under `tmp/runs_x/{run_id}/` and **nothing** is written to `./runs/`.
- [ ] **Step 2:** Run → FAIL (artifacts split into `runs/`).
- [ ] **Step 3:** Add `run_dir: Path` param to `MemoryStore.__init__` (replace `Path("runs")/run_id`) and to `TrajectoryLogger`; `SequenceRunner` passes `self.run_dir`.
- [ ] **Step 4:** Run → PASS.  - [ ] **Step 5:** Commit `fix: unify all run artifacts under run_dir (D-8)`.

### Task 3: Schema + prompt (D-1, D-4, D-6)
- [ ] Failing test (`start_line`/`end_line` in schema; `get_patch` absent) → schema + `SYSTEM_PROMPT` edits (ranges; no `N\t` prefix in diffs; re-read before edit; prefer write_file; no shell grep/sed/get_patch) → PASS → commit.

### Task 5: Seed-aware E7 + completeness (D-5)
- [ ] Failing 3-seed test (paired-avg; missing-seed cell dropped+reported) → implement §3.4 → PASS → commit.

### Task 5b: termination_reason + completion contract (D-7, C5, B8)
**Files:** `langgraph_agent.py` (loop exits), `sequence_runner.py` (writer), new `src/benchmark/completion.py`; Tests.
- [ ] **Step 1: Failing tests** — drive loop to each exit → assert `termination_reason` (no `usage_limit`); `validate_run_complete` ACCEPTS a complete fixture and REJECTS, with the right `missing[]`, runs that drop ANY mandatory artifact: a task row, a duplicate row, a `trajectories/{id}.json`, a `patches/{id}.patch`, a `before/after` snapshot, `memory.db`, `memory.faiss`, or `memory_events.jsonl` — **applied uniformly to all 6 policies including `no_memory`** (§3.7). Separately, an `UsageLimitError` path writes a `RUN_FAILED.json` and no `RUN_COMPLETED.json`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** set `state.termination_reason` at each break + write to task row; implement `validate_run_complete` (uniform contract, §3.7) + atomic `RUN_COMPLETED.json` writer in the SequenceRunner success path (after the loop, not `finally`) + atomic `RUN_FAILED.json` at the exception boundary (incl. `UsageLimitError`, before re-raise); include `tool_mode` in both sentinels.
- [ ] **Step 4:** Run → PASS.  - [ ] **Step 5:** Commit.

### Task 5c: `AGENT_TOOL_MODE` variant flag (C3, PHASE A — code)
**Files:** `langgraph_agent.py` (schema + `_MAX_OBS`), `tools.py` (read_file/edit), `prompts.py`; Test.
- [ ] **Step 1: Failing test** — `AGENT_TOOL_MODE=legacy` → read_file schema has **no** `start_line`/`end_line`, prompt shows `read_file(path)`, `_MAX_OBS == 4000`, edit normalization OFF; default/`fixed` → all §3 fixes ON.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement env `AGENT_TOOL_MODE` (default `fixed`) toggling **schema + prompt + implementation together**; record the resolved mode into each task row + both sentinels.
- [ ] **Step 4:** Run → PASS.  - [ ] **Step 5:** Commit.

### Task 5d: Orchestrator gates completion on the sentinel (D5, PHASE A — code)
**Files:** `experiment_runner.py:433,607,353`, `scripts/run_pilot_policy.py:81`; Test.
- [ ] **Step 1: Failing test** — give the orchestrator a returned-but-INCOMPLETE run dir (missing a task row) → assert it is NOT counted in `completed_runs`, a failure is recorded (`RUN_FAILED.json`/failure result), and the unit stays eligible for reconcile.
- [ ] **Step 2:** Run → FAIL (current code increments `completed_runs` + writes `{run_id}_result.json` right after `run_sequence()` returns, regardless of completeness).
- [ ] **Step 3:** Gate `completed_runs += 1` and the success `{run_id}_result.json` write on `validate_run_complete` + `RUN_COMPLETED.json`; on failure write the failure marker, do not increment.
- [ ] **Step 4:** Run → PASS.  - [ ] **Step 5:** Commit.

### Task 5e: A/B scheduler + gate calculator (PHASE A — code, E1)
**Files:** Create `scripts/ab_schedule.py`, `scripts/ab_gate.py`; Tests.
- [ ] **Step 1: Failing tests** — `ab_schedule(seed=20260622)` yields the exact 36-cell list `{2 seq}×{3 policy}×{3 seed}×{legacy,fixed}` in a deterministic randomized order; each cell's **`run_id` includes `tool_mode`** (e.g. `pilot_{policy}_{seq}_seed{n}_{mode}`) so legacy/fixed never collide. `ab_gate(results_dir)` returns FAIL unless 36/36 `RUN_COMPLETED` + 0 failed/interrupted + exact `(seq,policy,seed,task_id)` legacy↔fixed pairing, then computes the §5 metrics (range correctness, edit path/index==0, edit-fail≤0.15 with total>0, prompt & total token ≤1.5×).
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement both; `run_id` carries `tool_mode`; gate refuses to compute metrics on an incomplete/unpaired set.
- [ ] **Step 4:** Run → PASS.  - [ ] **Step 5:** Commit.

### Task 5f: Manifest+sentinel fleet runner (PHASE A — code, E1)
**Files:** Refactor `run_matrix_shard.sh`, `doctor.sh`, systemd units `thesis-matrix@`/`thesis-doctor@`, fleet setup; Test (dry-run/unit).
- [ ] **Step 1: Failing test** — a shard runner over a fixture manifest treats a unit "done" **iff `RUN_COMPLETED.json`** (NOT `results/raw` markers, NOT `cost_summary`); a unit with `RUN_FAILED.json` is re-queued (after archive per §3.7); no Kimi/tunnel assumptions remain.
- [ ] **Step 2:** Run → FAIL (current skip logic keys on stale `results/raw` markers).
- [ ] **Step 3:** Rewrite skip/reconcile to manifest + sentinel; archive-on-retry; strip Kimi/tunnel; `RUNS_ROOT`/`AGENT_TOOL_MODE` honored.
- [ ] **Step 4:** Run → PASS.  - [ ] **Step 5:** Commit. *(All fleet + A/B code is now committed before Freeze; Phase B only executes it.)*

### Task 4a: Integration + smoke TEST code (§4.2/4.3, PHASE A — code)
- [ ] Commit the realistic-input integration tests (§4.2, pass offline now) and the mandatory real-task smoke **harness** (§4.3) reading `smoke_tasks.json`. The network smoke RUN is Task 4b. Commit.

---
### FREEZE GATE — after ALL Phase-A code + tests are green
Record `experiment_sha`, `config_hash`, `manifest_hash`. **No code commits past this point.** Phase B executes the pinned `experiment_sha` only.

---
### Task 4b: Run mandatory real-task smoke (PHASE B — execution-only)
- [ ] At `experiment_sha`, run the smoke harness over `smoke_tasks.json`; assert ranged read of the target region, no identical-repeat loop, edit success, `termination_reason` + sentinel. Required before the A/B.

### Task 6: Contemporaneous A/B + instrument-health gate (C3, PHASE B — execution-only)
- [ ] **Step 1:** Execute the 36-cell schedule from `ab_schedule.py` (Task 5e; sequences {pytest(19), scikit-learn(32)} × {no_memory, full_memory, recency_prune} × seeds {1,2,3} × {legacy, fixed}, seed 20260622) on `m3-sfo-4` at `experiment_sha`, `AGENT_TOOL_MODE` per cell, same provider window. **No code commits.** Re-run any `RUN_FAILED`/interrupted via the §3.7 retry lifecycle until **36/36 `RUN_COMPLETED`**.
- [ ] **Step 2:** Run `ab_gate.py` (Task 5e) — it refuses unless 36/36 complete + paired, then computes the §5 GO gate (exact). Report (NOT gate) resolve/timeout/gap deltas. Write `results/pilot/decision.md`. **Stop for user sign-off.**

### Task 7: Full 144 re-run — fresh unified namespace + real completion (B8, PHASE B — execution-only)
- [ ] Run the **Task-5f** manifest+sentinel fleet runner against `runs_144.json` in fresh `RUNS_ROOT=runs_v2/` (unified, Task 2c) at `experiment_sha`, `AGENT_TOOL_MODE=fixed`; "done" iff `RUN_COMPLETED.json`. 10 droplets; pre-pull/`docker login`; key-pool + 402 failover; systemd `Restart=always` + doctor. Reconcile by missing sentinel; re-run incomplete via §3.7 retry (archive prior attempt). **No code commits** — execution-only. Pull → `run_analysis --stage all --runs-dir runs_v2 --out results_v2`; `dropped_incomplete` empty. Verify §5 DoD; commit aggregates + provenance + Methods "Deviations" (D-1..D-8, temp=1/A2, x86_64 fleet/D5, prior-matrix incompleteness).

## 7. Risks & open decisions
- **No guaranteed "better" headline** — interdependence ceiling (~30%) is tool-independent; the rerun buys *trustworthiness*. A clean capable-agent null is defensible.
- **Edit failure > 15% on A/B = MANDATORY STOP** → decide the `replace_in_file(path, old, new)` tool (adds a v5 §4.3 tool, needs approval). Below 15% → ship numbered-reads + write_file steering.
- **Disclosure:** instrument correction (not p-hacking); archive the old (incomplete) matrix + this spec; disclose D-1..D-8, temp=1 (A2), x86_64 fleet (D5), prior-matrix incompleteness + flawed completion check.

## 8. Self-review
- Coverage: D-1→T1/T3; D-2/3→T2; D-4→T3; D-5→T5; D-6→T2b/T3; D-7→T5b; D-8→T2c; completion→§3.7/T5b/T7; freeze→T−1+Freeze; gate→§5/T6; rerun→T7. Codex 3rd-pass: C1→§3.8/T2c; C2→T−1/Freeze; C3→T5c/T6; C4→§3.1/T1; C5→§3.7/T5b; C6→§5. Codex 4th-pass: D1→T−1 (HEAD `8f0fe3b`); D2→PHASE A/Freeze/PHASE B; D3→§3.7 uniform + patches; D4→`RUN_FAILED.json` §3.7/T5b; D5→T5d; precision (total_edit==0 fail, total_tokens, tool_mode)→§5. Codex 5th-pass (approve): E1→T5e/T5f (fleet+A/B tooling in Phase A); E2→§5 (36/36 paired); E3→§3.7 retry/archive; E4→T5e (`tool_mode` in run_id).
- Gate state: **implementation APPROVED**; Task −1 (user-confirm baseline) + Phase A may start; Freeze/A-B/droplets blocked behind their gates.
- Type consistency: `read_file(path,start_line,end_line)` T1/T2/T3; `_truncate_obs(text,limit)` T2; `termination_reason` enum §3.6/T5b/§5; `validate_run_complete(run_dir, manifest_entry)` + `RUN_COMPLETED.json` §3.7/T5b/T7; `run_dir` param §3.8/T2c.
- Placeholders: code tasks (1,2,2b,2c,5,5b) full code/tests; A/B (T6) fully pinned; T−1/0/4/7 are contracts gated on the manifest + a user STOP.
