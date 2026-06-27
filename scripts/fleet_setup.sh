#!/usr/bin/env bash
# Install + start the thesis sustained-running stack on ONE sfo droplet.
# Usage: bash scripts/fleet_setup.sh <shard-index>   (0..NUM_SHARDS-1)
set -euo pipefail
SHARD="${1:?usage: fleet_setup.sh <shard-index>}"
cd /root/thesis
chmod +x scripts/doctor.sh
[ -f /root/.ssh/thesis_tunnel_key ] && chmod 600 /root/.ssh/thesis_tunnel_key

cp scripts/systemd/thesis-matrix@.service  /etc/systemd/system/
cp scripts/systemd/thesis-doctor@.service  /etc/systemd/system/
systemctl daemon-reload

systemctl enable --now "thesis-matrix@${SHARD}.service"
systemctl enable --now "thesis-doctor@${SHARD}.service"
sleep 2
echo "shard=$SHARD active states:"
systemctl is-active "thesis-matrix@${SHARD}" "thesis-doctor@${SHARD}" || true
