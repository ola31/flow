#!/bin/bash
# Installs Flow's captive-portal config (dnsmasq answer-all + nft redirect
# dispatcher). Run once with root (pkexec). Idempotent.
set -e
SRC_DIR="$(cd "$(dirname "$0")" && pwd)"

install -D -m 644 "$SRC_DIR/flow-captive.conf" \
  /etc/NetworkManager/dnsmasq-shared.d/flow-captive.conf
install -D -m 755 "$SRC_DIR/90-flow-captive" \
  /etc/NetworkManager/dispatcher.d/90-flow-captive

nmcli general reload 2>/dev/null || systemctl reload NetworkManager 2>/dev/null || true
echo "Flow captive portal installed."
