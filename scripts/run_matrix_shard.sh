#!/usr/bin/env bash
# Run a SHARD of the full 3-seed × 144-unit matrix.
#
# Unit list is driven from results/manifest/runs_144.json (its runs[].run_id).
# A unit is DONE iff <RUNS_ROOT>/<run_id>/RUN_COMPLETED.json exists — checked
# via scripts/unit_status.py (delegates to src.benchmark.completion).
# A unit with RUN_FAILED.json (or neither marker) is eligible to re-run; its
# prior dir is archived via archive_prior_attempt before the fresh attempt.
#
# Sharding: each droplet runs units where (global_index % NUM_SHARDS == SHARD),
# giving modulo-interleaved, never-colliding assignment across the fleet.
#
# Env knobs (all optional; safe defaults given):
#   RUNS_ROOT        — where run dirs land  (default: runs)
#   AGENT_TOOL_MODE  — passed through to the runner  (default: fixed)
#   MANIFEST         — path to the manifest JSON
#                      (default: results/manifest/runs_144.json)
#
# Usage:
#   nohup bash scripts/run_matrix_shard.sh <shard_index> <num_shards> [conc] \
#       > "${RUNS_ROOT}/shard_<i>.log" 2>&1 &
set -u
cd "$(dirname "$0")/.."

SHARD="${1:?usage: run_matrix_shard.sh <shard_index> <num_shards> [conc]}"
NUM="${2:?num_shards required}"
CONC="${3:-2}"

export RUNS_ROOT="${RUNS_ROOT:-runs}"
export AGENT_TOOL_MODE="${AGENT_TOOL_MODE:-fixed}"
MANIFEST="${MANIFEST:-results/manifest/runs_144.json}"

if [ ! -f "$MANIFEST" ]; then
  echo "ERROR: manifest not found at $MANIFEST" >&2; exit 1
fi

# Guard: if SHARD >= NUM there is no work for this instance.
# Under Restart=always systemd would restart endlessly on exit 0.
# Instead, park (sleep infinity) so the unit stays active but does nothing,
# avoiding a restart-spin when fleet size is reduced.
if [ "$SHARD" -ge "$NUM" ]; then
  echo "SHARD $SHARD >= NUM $NUM — no units assigned, parking." >&2
  exec sleep infinity
fi

# ---------------------------------------------------------------------------
# Extract this shard's unit list from the manifest using Python
# (avoids jq dependency on VPS droplets).
# Emits one line per unit:  <global_index>|<run_id>|<policy>|<seed>|<seq_name>
# ---------------------------------------------------------------------------
mapfile -t units < <(
  .venv/bin/python - "$MANIFEST" "$SHARD" "$NUM" <<'PYEOF'
import json, sys
manifest_path, shard, num = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
with open(manifest_path) as f:
    data = json.load(f)
for i, r in enumerate(data["runs"]):
    if i % num == shard:
        print(f"{i}|{r['run_id']}|{r['policy']}|{r['seed']}|{r['sequence_name']}")
PYEOF
)

mkdir -p "$RUNS_ROOT"
echo "SHARD $SHARD/$NUM : ${#units[@]} units, conc=$CONC, RUNS_ROOT=$RUNS_ROOT, AGENT_TOOL_MODE=$AGENT_TOOL_MODE $(date -u +%H:%M:%S)"

# ---------------------------------------------------------------------------
# run_unit: execute one (run_id, policy, seed, sequence) unit.
#
# Done-check uses scripts/unit_status.py which keys on RUN_COMPLETED.json
# (not the stale results/raw/*_result.json markers).
# ---------------------------------------------------------------------------
run_unit() {
  local entry="$1"
  IFS='|' read -r _idx run_id pol seed seq <<< "$entry"

  # Done-check: delegate to unit_status.py (RUN_COMPLETED.json sentinel).
  # Fail-closed: if status is not exactly one of complete|failed|incomplete
  # (e.g. empty on a transient import error), skip this pass with a warning
  # rather than falling through to archive/re-run.
  local status
  status=$(.venv/bin/python scripts/unit_status.py "$run_id" "$RUNS_ROOT" 2>/dev/null)

  case "$status" in
    complete)
      echo "SKIP(done) $run_id"
      return 0
      ;;
    failed|incomplete)
      : # fall through to archive + run
      ;;
    *)
      echo "WARN: unit_status.py returned unexpected value $(printf '%q' "$status") for $run_id — skipping this pass" >&2
      return 0
      ;;
  esac

  # Archive any prior failed/partial attempt before starting fresh.
  # archive_prior_attempt is a no-op for a clean empty dir.
  .venv/bin/python - "$run_id" "$RUNS_ROOT" <<'PYEOF'
import sys
from pathlib import Path
from src.benchmark.completion import archive_prior_attempt
archive_prior_attempt(Path(sys.argv[2]) / sys.argv[1])
PYEOF

  echo "START $run_id (status=$status) $(date -u +%H:%M:%S)"
  .venv/bin/python -u -m scripts.run_pilot_policy \
      --policy    "$pol"  \
      --seed      "$seed" \
      --sequences "$seq"  \
      --run-id    "$run_id" \
      > "${RUNS_ROOT}/unit_${run_id}.log" 2>&1
  local exit_code=$?
  echo "DONE  $run_id EXIT=$exit_code $(date -u +%H:%M:%S)"
  return $exit_code
}
export -f run_unit
export RUNS_ROOT AGENT_TOOL_MODE

printf '%s\n' "${units[@]}" | xargs -P "$CONC" -I {} bash -c 'run_unit "$@"' _ {}
echo "SHARD_DONE $SHARD/$NUM $(date -u +%H:%M:%S)"
