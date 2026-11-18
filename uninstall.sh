#!/usr/bin/env bash
set -euo pipefail
rm -f "$HOME/.local/bin/swipeswitch" "$HOME/.local/bin/swipeswitch-conflicts"
rm -rf "$HOME/.local/share/swipeswitch"
rm -f "$HOME/.config/autostart/swipeswitch.desktop"
echo "Application removed; ~/.config/swipeswitch was preserved."
