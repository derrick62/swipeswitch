#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$HOME/.local/bin"
APP_DIR="$HOME/.local/share/swipeswitch"
UNIT_DIR="$HOME/.config/systemd/user"
APP_LAUNCHERS="$HOME/.local/share/applications"

command -v apt-get >/dev/null || { echo "Kali/Debian apt-based installer only." >&2; exit 1; }
echo "Installing system dependencies (sudo may be required)..."
sudo apt-get update
sudo apt-get install -y python3 python3-gi gir1.2-gtk-3.0 gir1.2-wnck-3.0 python3-pil libinput-tools coreutils wmctrl systemd

echo
echo "Checking for other touchpad gesture handlers..."
python3 "$ROOT/scripts/swipeswitch-conflicts.py" --resolve

mkdir -p "$BIN_DIR" "$APP_DIR" "$UNIT_DIR" "$APP_LAUNCHERS"
rm -rf "$APP_DIR/swipeswitch"
cp -R "$ROOT/swipeswitch" "$APP_DIR/"
cp "$ROOT/pyproject.toml" "$ROOT/README.md" "$APP_DIR/"
cp -R "$ROOT/docs" "$APP_DIR/"
install -m 0755 "$ROOT/scripts/swipeswitch-conflicts.py" "$BIN_DIR/swipeswitch-conflicts"
install -m 0755 "$ROOT/scripts/swipeswitch-session-start" "$BIN_DIR/swipeswitch-session-start"

cat > "$BIN_DIR/swipeswitch" <<EOF
#!/usr/bin/env bash
export PYTHONPATH="$APP_DIR\${PYTHONPATH:+:\$PYTHONPATH}"
exec python3 -m swipeswitch "\$@"
EOF
cat > "$BIN_DIR/swipeswitch-control" <<EOF
#!/usr/bin/env bash
export PYTHONPATH="$APP_DIR\${PYTHONPATH:+:\$PYTHONPATH}"
exec python3 -m swipeswitch.control_panel "\$@"
EOF
chmod 0755 "$BIN_DIR/swipeswitch" "$BIN_DIR/swipeswitch-control"
cat > "$UNIT_DIR/swipeswitch.service" <<EOF
[Unit]
Description=SwipeSwitch touchpad gesture service
After=graphical-session.target
PartOf=graphical-session.target

[Service]
Type=simple
ExecStart=$BIN_DIR/swipeswitch
Restart=on-failure
RestartSec=2
KillSignal=SIGTERM
TimeoutStopSec=10
EOF
sed "s|^Exec=.*|Exec=$BIN_DIR/swipeswitch-control|" \
  "$ROOT/packaging/swipeswitch.desktop" > "$APP_LAUNCHERS/swipeswitch.desktop"
chmod 0644 "$APP_LAUNCHERS/swipeswitch.desktop"

if [[ ! -f "$HOME/.config/swipeswitch/config.toml" ]]; then
  mkdir -p "$HOME/.config/swipeswitch"
  cp "$ROOT/config.example.toml" "$HOME/.config/swipeswitch/config.toml"
  chmod 600 "$HOME/.config/swipeswitch/config.toml"
fi
systemctl --user daemon-reload || true

echo "Installed. Open SwipeSwitch Control Panel from your applications menu or run: swipeswitch-control"
echo "The gesture service is initially stopped. Login startup is an explicit control-panel preference."
echo "Existing ~/.config/swipeswitch/config.toml was preserved."
