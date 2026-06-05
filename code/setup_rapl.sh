#!/bin/bash
# One-time privileged setup: grant read access to Intel RAPL energy counters so
# CodeCarbon can measure real CPU/RAM energy instead of TDP estimates.
#
# Why a shell script (and not run.py)? The energy_uj files are root-owned (0400);
# only root can chmod them, so this step can't run from the unprivileged Python
# process. This script re-executes itself with sudo, applies the permission, and
# installs a systemd one-shot so it survives reboots.
#
# Usage:  bash setup_rapl.sh           (will prompt for sudo)
#         NO_PERSIST=1 bash setup_rapl.sh   (apply now, don't install the service)
set -e

if [ "$(id -u)" -ne 0 ]; then
    echo "[setup_rapl] elevating with sudo ..."
    exec sudo --preserve-env=NO_PERSIST bash "$0" "$@"
fi

POWERCAP=/sys/devices/virtual/powercap
if [ ! -d "$POWERCAP" ]; then
    echo "[setup_rapl] $POWERCAP not found - no Intel RAPL here (VM / non-Intel). Nothing to do."
    exit 0
fi

echo "[setup_rapl] granting read on energy_uj files ..."
find "$POWERCAP" -name energy_uj -exec chmod a+r {} +

if [ "${NO_PERSIST:-0}" != "1" ] && command -v systemctl >/dev/null 2>&1; then
    echo "[setup_rapl] installing systemd unit for persistence across reboots ..."
    cat > /etc/systemd/system/rapl-readable.service <<'EOF'
[Unit]
Description=Make Intel RAPL energy_uj readable (for CodeCarbon)
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/bin/sh -c 'find /sys/devices/virtual/powercap -name energy_uj -exec chmod a+r {} +'

[Install]
WantedBy=multi-user.target
EOF
    systemctl daemon-reload
    systemctl enable --now rapl-readable.service >/dev/null 2>&1 || true
    echo "[setup_rapl] enabled rapl-readable.service"
fi

echo "[setup_rapl] done. Verify:  cat /sys/class/powercap/intel-rapl:0/energy_uj"
