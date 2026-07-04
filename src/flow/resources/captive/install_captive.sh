#!/bin/bash
# Installs Flow's captive-portal config (dnsmasq answer-all + nft redirect
# dispatcher). Run once with root (pkexec). Idempotent.
set -e
SRC_DIR="$(cd "$(dirname "$0")" && pwd)"

install -D -m 644 "$SRC_DIR/flow-captive.conf" \
  /etc/NetworkManager/dnsmasq-shared.d/flow-captive.conf
install -D -m 755 "$SRC_DIR/90-flow-captive" \
  /etc/NetworkManager/dispatcher.d/90-flow-captive

# firewalld puts the hotspot interface in the nm-shared zone, which only
# allows dhcp/dns/ssh and rejects everything else — so phones get an IP and
# DNS but can't reach the web server or the WebSocket slide feed. Open the
# broadcast port (8777), the WebSocket port (8778), and 80 for the captive
# redirect on that zone.
if command -v firewall-cmd >/dev/null 2>&1; then
  firewall-cmd --permanent --zone=nm-shared --add-port=8777/tcp 2>/dev/null || true
  firewall-cmd --permanent --zone=nm-shared --add-port=8778/tcp 2>/dev/null || true
  firewall-cmd --permanent --zone=nm-shared --add-port=80/tcp 2>/dev/null || true
  # firewalld blocks inter-zone forwarding by default. Without this, phones
  # get an IP and can resolve DNS (answered locally by dnsmasq) but every
  # real packet to the internet is dropped when the hotspot is sharing real
  # upstream connectivity (e.g. Ethernet plugged into the laptop) — DNS
  # works while actual browsing silently fails.
  firewall-cmd --permanent --zone=nm-shared --add-forward 2>/dev/null || true
  firewall-cmd --reload 2>/dev/null || true
fi

nmcli general reload 2>/dev/null || systemctl reload NetworkManager 2>/dev/null || true
echo "Flow captive portal installed."
