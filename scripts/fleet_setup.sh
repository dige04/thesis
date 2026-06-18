#!/usr/bin/env bash
# Install + start the thesis sustained-running stack on ONE sfo droplet.
# Usage: bash scripts/fleet_setup.sh <shard-index>   (0..NUM_SHARDS-1)
set -euo pipefail
SHARD="${1:?usage: fleet_setup.sh <shard-index>}"
cd /root/thesis
chmod +x scripts/doctor.sh
[ -f /root/.ssh/thesis_tunnel_key ] && chmod 600 /root/.ssh/thesis_tunnel_key

cp scripts/systemd/thesis-tunnel.service   /etc/systemd/system/
cp scripts/systemd/thesis-matrix@.service  /etc/systemd/system/
cp scripts/systemd/thesis-doctor@.service  /etc/systemd/system/
systemctl daemon-reload

# Tunnel first; verify it before the matrix (else agent calls fail-closed).
systemctl enable --now thesis-tunnel.service
ok=""
for _ in $(seq 1 12); do
  if curl -s --max-time 5 -H "Authorization: Bearer thsmem-kimi-proxy-2f9c4a" http://localhost:8317/v1/models >/dev/null 2>&1; then ok=1; break; fi
  sleep 2
done
[ -n "$ok" ] || { echo "ABORT: sub tunnel (localhost:8317) not up on shard $SHARD"; systemctl status thesis-tunnel --no-pager -l | tail -15; exit 1; }
echo "tunnel UP"

systemctl enable --now "thesis-matrix@${SHARD}.service"
systemctl enable --now "thesis-doctor@${SHARD}.service"
sleep 2
echo "shard=$SHARD active states:"
systemctl is-active thesis-tunnel "thesis-matrix@${SHARD}" "thesis-doctor@${SHARD}" || true
