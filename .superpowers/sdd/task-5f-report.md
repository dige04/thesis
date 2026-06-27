# Task 5f Report: Manifest+sentinel fleet runner

## What changed in each file

### `scripts/unit_status.py` (NEW)
Tiny Python helper that implements the single done-decision gate for the shard runner.

- `unit_status(run_id, runs_root) -> "complete" | "failed" | "incomplete"` delegates to
  `src.benchmark.completion.is_run_complete` for the `RUN_COMPLETED.json` check; falls
  through to `RUN_FAILED.json`; returns `"incomplete"` for absent-dir or no-sentinel cases.
- `__main__` entry-point prints the status to stdout so the shell can capture it:
  `status=$(.venv/bin/python scripts/unit_status.py <run_id> <RUNS_ROOT>)`.

### `tests/test_unit_status.py` (NEW)
6 TDD tests covering all four required cases plus two extras (priority + CLI):
1. `RUN_COMPLETED.json` → `"complete"` (skip)
2. `RUN_FAILED.json` (no completed) → `"failed"` (re-queue)
3. Dir exists, neither marker → `"incomplete"` (re-queue)
4. Dir absent → `"incomplete"` (re-queue)
5. Both markers → `"complete"` wins (deterministic priority)
6. CLI subprocess prints the correct status to stdout

Tests ran FAIL before `scripts/unit_status.py` existed, PASS after (all 6 pass).
Combined run of `test_unit_status.py + test_completion.py` = 22 passed.

### `scripts/run_matrix_shard.sh` (REWRITTEN)
Key changes:

| Before | After |
|--------|-------|
| Unit list reconstructed from hardcoded POLICIES/SEEDS/SEQS bash arrays | Unit list driven from `results/manifest/runs_144.json` via inline Python (no jq dependency) |
| Done-check: `if [ -f "results/raw/pilot_${pol}_${seq}_seed${seed}_result.json" ]` | Done-check: `status=$(.venv/bin/python scripts/unit_status.py "$run_id" "$RUNS_ROOT")` — keys on `RUN_COMPLETED.json` |
| `rm -rf ${RUNS_ROOT}/pilot_...` (destructive, no archival) | `archive_prior_attempt` called via Python inline (moves to `.attempt{k}`) |
| `--policy/--seed/--sequences` only passed to runner | `--run-id` also passed so dir name matches manifest exactly (no `pilot_` prefix) |
| `export RUNS_ROOT` only | `export RUNS_ROOT AGENT_TOOL_MODE` (both passed through) |
| Default `RUNS_ROOT=runs_m3` | Default `RUNS_ROOT=runs` |
| Default `CONC=4` | Default `CONC=2` (safer default for VPS) |
| References to Kimi/tunnel/`runs_k27`/`runs_m3` in comments | Stripped |

### `scripts/doctor.sh` (UPDATED)
- Removed `thesis-tunnel` health check comment and the explicit Ollama tunnel comment
- Changed hardcoded `runs_k27` path references to `${RUNS_ROOT:-runs}` variable
- Added `"runs_root"` field to the heartbeat JSON for observability
- No tunnel restart logic (the doctor never started the tunnel — it was a systemd `Wants=` dependency)

### `scripts/fleet_relaunch.sh` (UPDATED)
- Removed hardcoded `mkdir -p runs_m3` → `mkdir -p "$RUNS_ROOT"`
- Removed hardcoded `runs_m3/shard_${SHARD}.log` → `${RUNS_ROOT}/shard_${SHARD}.log`
- Removed hardcoded `runs_m3/` from autoloop log redirect
- Added `export RUNS_ROOT AGENT_TOOL_MODE` and passes both through to the autoloop
- Removed "12 k2.6 done units are pre-seeded" comment (no longer applies)
- Stripped all references to Kimi-sub, `runs_k27`, `runs_m3`

### `scripts/run_pilot_policy.py` (UPDATED)
- Added `--run-id` optional argument: explicit run_id that matches the manifest entry
  (e.g. `no_memory_django_django_sequence_seed1`)
- When `--run-id` supplied: uses it directly (no `pilot_` prefix)
- When omitted: falls back to `pilot_{policy}_{seq}_seed{seed}` for legacy compatibility
- Updated module docstring to document the new flag and the manifest-aligned invocation

### `scripts/systemd/thesis-matrix@.service` (UPDATED)
- Removed `After=thesis-tunnel.service` and `Wants=thesis-tunnel.service` dependencies
- Changed description: removed "kimi-k2.7-code agent + deepseek-v4-flash aux" → "deepseek-v4-flash, all-go"
- Changed `Environment=RUNS_ROOT=runs_k27` → `Environment=RUNS_ROOT=runs`
- Added `Environment=AGENT_TOOL_MODE=fixed`

### `scripts/systemd/thesis-doctor@.service` (UPDATED)
- Updated description: removed "tunnel" from the heal list
- Added `Environment=RUNS_ROOT=runs`

## Critical finding (run_id alignment)
`run_pilot_policy.py` previously constructed `run_id = f"pilot_{policy}_{seq}_seed{seed}"`
but the manifest uses `{policy}_{seq}_seed{seed}` (no `pilot_` prefix). Without `--run-id`,
the done-check would probe `runs/{manifest_run_id}/RUN_COMPLETED.json` while the runner
writes `runs/pilot_{manifest_run_id}/...` — they never match, and every unit would re-run
forever. Fixed by adding `--run-id` to `run_pilot_policy.py` and having the shell pass it.

## Blocking concerns
None. Shell syntax OK (`bash -n` clean on all three scripts). All 22 tests pass.
The `thesis-tunnel.service` file is left in place (it's inert now that nothing depends on it);
the user may delete it at their discretion — not our call to remove it since it's a systemd
unit that may have been installed on the VPS.
