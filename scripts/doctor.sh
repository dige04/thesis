#!/usr/bin/env bash
# Thesis fleet doctor — per-droplet self-healing + heartbeat for unattended running.
# Run by thesis-doctor@<shard>.service (Restart=always, boot-persistent).
#
# Heals: disk (docker-image leak), ollama, the nyc1 sub-tunnel, the matrix shard.
# Reports: doctor_status.json heartbeat (disk, progress, last-result age, 402 count).
# FAIL-CLOSED on go-cap: it does NOT switch the aux model mid-run (that would confound
# the matrix). Repeated 402 = go exhausted -> aux dead fleet-wide -> surfaced in the
# heartbeat (err402) + log for the operator to refill/escalate; the run already
# fail-closes via src/errors.py (no false resolved=0).
set -u
THESIS=/root/thesis
STATUS="$THESIS/doctor_status.json"
SHARD="${1:-0}"
PROXY_KEY="thsmem-kimi-proxy-2f9c4a"
log() { echo "[doctor $(date -u +%FT%TZ) shard=$SHARD] $*"; }

proxy_ok() { curl -s --max-time 6 -H "Authorization: Bearer $PROXY_KEY" http://localhost:8317/v1/models >/dev/null 2>&1; }

while true; do
  # 1. Disk backstop (docker eval images are the leak; cleaner only did /tmp before).
  u=$(df / | awk 'NR==2{gsub("%","",$5);print $5}')
  if [ "${u:-0}" -ge 80 ]; then
    docker container prune -f >/dev/null 2>&1
    docker image prune -af --filter "until=30m" >/dev/null 2>&1
    find /tmp -maxdepth 1 -name 'swebench_*' -mmin +20 -exec rm -rf {} + 2>/dev/null
    log "disk ${u}% -> pruned"
  fi

  # 2. Ollama (embeddings are mandatory).
  if ! pgrep -x ollama >/dev/null 2>&1; then
    systemctl restart ollama 2>/dev/null || (nohup ollama serve >/tmp/ollama.log 2>&1 &)
    log "ollama down -> restarted"
  fi

  # 3. Sub tunnel to nyc1 (agent endpoint). systemd also restarts it; this is a backup.
  if ! proxy_ok; then
    systemctl restart thesis-tunnel 2>/dev/null
    log "sub tunnel (localhost:8317) unreachable -> restarted thesis-tunnel"
  fi

  # 4. Matrix shard alive (systemd Restart=always too; backup).
  if ! systemctl is-active --quiet "thesis-matrix@${SHARD}" 2>/dev/null; then
    systemctl restart "thesis-matrix@${SHARD}" 2>/dev/null
    log "matrix@${SHARD} not active -> restarted"
  fi

  # 5. Heartbeat.
  err402=$(grep -ch "insufficient_balance\|402" "$THESIS/runs_k27/shard_${SHARD}.log" 2>/dev/null | head -1)
  err402=${err402:-0}
  done=$(ls "$THESIS"/results/raw/pilot_*_result.json 2>/dev/null | wc -l | tr -d ' ')
  last=$(ls -t "$THESIS"/runs_k27/*/task_results.jsonl 2>/dev/null | head -1)
  if [ -n "$last" ]; then age=$(( ($(date +%s) - $(stat -c %Y "$last")) / 60 )); else age=-1; fi
  tun=$(proxy_ok && echo up || echo down)
  printf '{"ts":"%s","shard":%s,"disk":"%s%%","done_markers":%s,"last_result_min":%s,"err402":%s,"tunnel":"%s"}\n' \
    "$(date -u +%FT%TZ)" "$SHARD" "${u:-?}" "${done:-0}" "$age" "$err402" "$tun" > "$STATUS" 2>/dev/null
  [ "$err402" -gt 0 ] 2>/dev/null && log "WARNING: $err402 x 402/insufficient_balance in shard log — go may be capped (aux SPOF). Refill/escalate; run fail-closes (no corruption)."

  sleep 180
done
