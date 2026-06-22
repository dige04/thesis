#!/usr/bin/env bash
# Relaunch ONE matrix shard on a fleet worker (run this ON the worker).
#
# What it does, idempotently:
#   1. Kills stale matrix procs (run_pilot_policy / run_matrix_shard / old autoloops)
#      WITHOUT touching the /tmp cleaner.
#   2. Starts a /tmp clone cleaner — leaked /tmp/swebench_* clones fill disk
#      silently (checkout "No space" → agent never reaches the LLM → 0% usage).
#      The cleaner removes clones older than 20 min every 5 min.
#   3. Auto-loops the shard runner. Each pass skips units with RUN_COMPLETED.json;
#      failed/partial units are archived and re-run.
#
# Env knobs (pass before calling or export first):
#   RUNS_ROOT        — where run dirs land  (default: runs)
#   AGENT_TOOL_MODE  — passed through to run_matrix_shard.sh  (default: fixed)
#
# Usage (on worker):
#   RUNS_ROOT=runs bash /root/thesis/scripts/fleet_relaunch.sh <shard_index> [num_shards] [conc]
set -u
cd /root/thesis || exit 1
SHARD="${1:?shard index required}"; NUM="${2:-5}"; CONC="${3:-2}"
export RUNS_ROOT="${RUNS_ROOT:-runs}"
export AGENT_TOOL_MODE="${AGENT_TOOL_MODE:-fixed}"

# RUNS_ROOT must exist BEFORE the autoloop redirect: the `>> ${RUNS_ROOT}/...`
# redirect is evaluated by the shell before run_matrix_shard.sh's internal
# `mkdir -p` runs, so a missing dir makes every pass fail silently.
mkdir -p "$RUNS_ROOT"

# 1. Kill stale matrix procs + any previous autoloop (leave the cleaner running).
pkill -f 'run_pilot_policy'  2>/dev/null || true
pkill -f 'run_matrix_shard'  2>/dev/null || true
pkill -f 'THESIS_AUTOLOOP'   2>/dev/null || true
sleep 2

# 2. /tmp clone cleaner (idempotent — replace any prior instance).
pkill -f 'THESIS_TMP_CLEANER' 2>/dev/null || true
nohup bash -c ': THESIS_TMP_CLEANER; while true; do find /tmp -maxdepth 1 -name "swebench_*" -mmin +20 -exec rm -rf {} + 2>/dev/null; sleep 300; done' \
  >/tmp/cleaner.log 2>&1 &

# 3. Auto-loop the shard (80 passes; sleep 30 between to back off a capped provider).
rm -f "${RUNS_ROOT}/shard_${SHARD}.log"
nohup bash -c ": THESIS_AUTOLOOP_${SHARD}; cd /root/thesis
for k in \$(seq 1 80); do
  RUNS_ROOT=${RUNS_ROOT} AGENT_TOOL_MODE=${AGENT_TOOL_MODE} \
    bash scripts/run_matrix_shard.sh ${SHARD} ${NUM} ${CONC} \
    >> ${RUNS_ROOT}/shard_${SHARD}.log 2>&1
  sleep 30
done" \
  >"/tmp/autoloop_${SHARD}.log" 2>&1 &

echo "relaunched shard ${SHARD}/${NUM} conc=${CONC} RUNS_ROOT=${RUNS_ROOT} on $(hostname) at $(date -u +%H:%M:%S) (autoloop pid $!)"
