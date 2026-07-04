#!/bin/bash
# Removes Flow's captive-portal config. Run with root (pkexec).
set -e
rm -f /etc/NetworkManager/dnsmasq-shared.d/flow-captive.conf
rm -f /etc/NetworkManager/dispatcher.d/90-flow-captive
nft delete table ip flow_captive 2>/dev/null || true
if command -v firewall-cmd >/dev/null 2>&1; then
  firewall-cmd --permanent --zone=nm-shared --remove-port=8777/tcp 2>/dev/null || true
  firewall-cmd --permanent --zone=nm-shared --remove-port=8778/tcp 2>/dev/null || true
  firewall-cmd --permanent --zone=nm-shared --remove-port=80/tcp 2>/dev/null || true
  firewall-cmd --permanent --zone=nm-shared --remove-forward 2>/dev/null || true
  firewall-cmd --reload 2>/dev/null || true
fi
nmcli general reload 2>/dev/null || systemctl reload NetworkManager 2>/dev/null || true
echo "Flow captive portal removed."
