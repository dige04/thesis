#!/usr/bin/env bash
# Thesis fleet doctor — per-droplet self-healing + heartbeat + quota awareness.
# Run by thesis-doctor@<shard>.service (Restart=always, boot-persistent).
#
# Heals: disk (docker-image leak), ollama (embeddings), the matrix shard.
# Reports doctor_status.json: disk, task_rows, est_go_requests (quota gauge),
# last-result age, err402.
#
# QUOTA: go is one $-capped account (~158k DeepSeek-Flash req/mo). On cap it
# 402s. The run fail-closes (no false resolved=0). When err402>0, ADD a fresh
# go key to the FREE_LLM_CHAT_API_KEYS pool in .env (KeyRotatingClient fails
# over) — it NEVER switches model.
set -u
THESIS=/root/thesis
STATUS="$THESIS/doctor_status.json"
SHARD="${1:-0}"
RUNS_ROOT="${RUNS_ROOT:-runs}"
log() { echo "[doctor $(date -u +%FT%TZ) shard=$SHARD] $*"; }

while true; do
  # 1. Disk backstop (swebench docker eval images are the leak).
  u=$(df / | awk 'NR==2{gsub("%","",$5);print $5}')
  if [ "${u:-0}" -ge 80 ]; then
    docker container prune -f >/dev/null 2>&1
    docker image prune -af --filter "until=30m" >/dev/null 2>&1
    find /tmp -maxdepth 1 -name 'swebench_*' -mmin +20 -exec rm -rf {} + 2>/dev/null
    log "disk ${u}% -> pruned"
  fi

  # 2. Ollama (embeddings are mandatory; agent is on go over the internet).
  if ! pgrep -x ollama >/dev/null 2>&1; then
    systemctl restart ollama 2>/dev/null || (nohup ollama serve >/tmp/ollama.log 2>&1 &)
    log "ollama down -> restarted"
  fi

  # 3. Matrix shard alive (systemd Restart=always too; backup).
  if ! systemctl is-active --quiet "thesis-matrix@${SHARD}" 2>/dev/null; then
    systemctl restart "thesis-matrix@${SHARD}" 2>/dev/null
    log "matrix@${SHARD} not active -> restarted"
  fi

  # 4. Heartbeat + go-quota gauge.
  err402=$(grep -ch "insufficient_balance\|402\|GoUsageLimit\|usage limit" \
    "$THESIS/${RUNS_ROOT}/shard_${SHARD}.log" 2>/dev/null | head -1)
  err402=${err402:-0}
  rows=$(find "$THESIS/${RUNS_ROOT}" -name task_results.jsonl -exec cat {} + 2>/dev/null | wc -l | tr -d ' ')
  reqs=$(( ${rows:-0} * 22 ))   # ~22 go requests/task (agent ~20 + classifier + reflection)
  last=$(ls -t "$THESIS/${RUNS_ROOT}"/*/task_results.jsonl 2>/dev/null | head -1)
  if [ -n "$last" ]; then age=$(( ($(date +%s) - $(stat -c %Y "$last")) / 60 )); else age=-1; fi
  printf '{"ts":"%s","shard":%s,"runs_root":"%s","disk":"%s%%","task_rows":%s,"est_go_requests_this_shard":%s,"last_result_min":%s,"err402":%s}\n' \
    "$(date -u +%FT%TZ)" "$SHARD" "$RUNS_ROOT" "${u:-?}" "${rows:-0}" "$reqs" "$age" "$err402" > "$STATUS" 2>/dev/null
  [ "$err402" -gt 0 ] 2>/dev/null && \
    log "WARNING: $err402x 402/usage-limit in shard log — a go key likely capped. Add a fresh go key to FREE_LLM_CHAT_API_KEYS in .env; KeyRotatingClient fails over. (fail-closed, no corruption)"

  sleep 180
done
