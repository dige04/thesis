#!/usr/bin/env bash
# Run the Spike-Week pilot: 6 policies x pilot sequences x 1 seed, with at most
# 3 policies running concurrently (8GB droplet — avoids OOM from too many
# simultaneous test containers). Each policy is an independent process writing
# results/raw/pilot_<policy>_<seq>_seed<seed>_result.json and pilot_<policy>.log.
#
# Usage:  bash scripts/run_pilot.sh [seed]
set -u
cd "$(dirname "$0")/.."

SEED="${1:-1}"
CONCURRENCY="${PILOT_CONCURRENCY:-3}"
POLICIES="no_memory full_memory random_prune recency_prune type_aware_decay cls_consolidation"

run_one() {
  pol="$1"; seed="$2"
  echo "START $pol $(date -u +%H:%M:%S)"
  .venv/bin/python -u -m scripts.run_pilot_policy --policy "$pol" --seed "$seed" > "pilot_${pol}.log" 2>&1
  echo "POLICY $pol EXIT=$? $(date -u +%H:%M:%S)"
}
export -f run_one

printf '%s\n' $POLICIES \
  | xargs -P "$CONCURRENCY" -I {} bash -c 'run_one "$@"' _ {} "$SEED"

echo "ALL_PILOT_DONE seed=$SEED"
