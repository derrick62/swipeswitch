#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$HOME/.local/bin"
APP_DIR="$HOME/.local/share/swipeswitch"
AUTOSTART_DIR="$HOME/.config/autostart"

command -v apt-get >/dev/null || { echo "Kali/Debian apt-based installer only." >&2; exit 1; }
echo "Installing system dependencies (sudo may be required)..."
sudo apt-get update
sudo apt-get install -y python3 python3-gi gir1.2-gtk-3.0 gir1.2-wnck-3.0 python3-pil libinput-tools coreutils wmctrl

mkdir -p "$BIN_DIR" "$APP_DIR" "$AUTOSTART_DIR"
cp -R "$ROOT/swipeswitch" "$APP_DIR/"
cp "$ROOT/pyproject.toml" "$ROOT/README.md" "$APP_DIR/"
cp -R "$ROOT/docs" "$APP_DIR/"
cat > "$BIN_DIR/swipeswitch" <<EOF
#!/usr/bin/env bash
export PYTHONPATH="$APP_DIR\${PYTHONPATH:+:\$PYTHONPATH}"
exec python3 -m swipeswitch "\$@"
EOF
chmod 755 "$BIN_DIR/swipeswitch"

if [[ ! -f "$HOME/.config/swipeswitch/config.toml" ]]; then
  mkdir -p "$HOME/.config/swipeswitch"
  cp "$ROOT/config.example.toml" "$HOME/.config/swipeswitch/config.toml"
  chmod 600 "$HOME/.config/swipeswitch/config.toml"
fi
cp "$ROOT/packaging/swipeswitch.desktop" "$AUTOSTART_DIR/"
echo "Installed. Run ~/.local/bin/swipeswitch --check, then start with swipeswitch."
echo "See README.md for input-device permissions and troubleshooting."
