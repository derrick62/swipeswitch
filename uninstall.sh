#!/usr/bin/env bash
set -euo pipefail
systemctl --user disable --now swipeswitch.service 2>/dev/null || true
rm -f "$HOME/.local/bin/swipeswitch" \
      "$HOME/.local/bin/swipeswitch-control" \
      "$HOME/.local/bin/swipeswitch-conflicts" \
      "$HOME/.local/bin/swipeswitch-session-start" \
      "$HOME/.config/autostart/swipeswitch-daemon.desktop" \
      "$HOME/.config/autostart/swipeswitch.desktop" \
      "$HOME/.config/systemd/user/swipeswitch.service" \
      "$HOME/.local/share/applications/swipeswitch.desktop"
rm -rf "$HOME/.local/share/swipeswitch"
systemctl --user daemon-reload 2>/dev/null || true
echo "Application removed; ~/.config/swipeswitch was preserved."
