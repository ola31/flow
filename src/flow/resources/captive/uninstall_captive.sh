#!/bin/bash
# Removes Flow's captive-portal config. Run with root (pkexec).
set -e
rm -f /etc/NetworkManager/dnsmasq-shared.d/flow-captive.conf
rm -f /etc/NetworkManager/dispatcher.d/90-flow-captive
nft delete table ip flow_captive 2>/dev/null || true
nmcli general reload 2>/dev/null || systemctl reload NetworkManager 2>/dev/null || true
echo "Flow captive portal removed."
