#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERSION="$(sed -n 's/^version = "\([^"]*\)"/\1/p' "$ROOT/pyproject.toml" | head -n1)"
[[ -n "$VERSION" ]] || { echo "Could not read project version." >&2; exit 1; }
command -v dpkg-deb >/dev/null || { echo "dpkg-deb is required (install dpkg)." >&2; exit 1; }

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
PKG="$WORK/swipeswitch"
install -d "$PKG/usr/lib/python3/dist-packages/swipeswitch" \
  "$PKG/usr/bin" "$PKG/usr/share/applications" \
  "$PKG/usr/share/doc/swipeswitch/examples" \
  "$PKG/usr/share/doc/swipeswitch/docs" \
  "$PKG/usr/lib/systemd/user" "$PKG/DEBIAN"

# Include the complete package tree, not only top-level Python modules.
cp -a "$ROOT/swipeswitch/." "$PKG/usr/lib/python3/dist-packages/swipeswitch/"
find "$PKG/usr/lib/python3/dist-packages/swipeswitch" -type d -name __pycache__ -prune -exec rm -rf {} +
find "$PKG/usr/lib/python3/dist-packages/swipeswitch" -type f -name '*.pyc' -delete

install -m 0644 "$ROOT/packaging/debian/control" "$PKG/DEBIAN/control"
sed -i "s/^Version: .*/Version: $VERSION/" "$PKG/DEBIAN/control"
cat > "$PKG/usr/bin/swipeswitch" <<'LAUNCHER'
#!/bin/sh
exec /usr/bin/python3 -m swipeswitch "$@"
LAUNCHER
cat > "$PKG/usr/bin/swipeswitch-control" <<'LAUNCHER'
#!/bin/sh
exec /usr/bin/python3 -m swipeswitch.control_panel "$@"
LAUNCHER
chmod 0755 "$PKG/usr/bin/swipeswitch" "$PKG/usr/bin/swipeswitch-control"
install -m 0755 "$ROOT/scripts/swipeswitch-conflicts.py" "$PKG/usr/bin/swipeswitch-conflicts"
install -m 0755 "$ROOT/scripts/swipeswitch-session-start" "$PKG/usr/bin/swipeswitch-session-start"
install -m 0644 "$ROOT/packaging/swipeswitch.service" \
  "$PKG/usr/lib/systemd/user/swipeswitch.service"
install -m 0644 "$ROOT/packaging/swipeswitch.desktop" \
  "$PKG/usr/share/applications/swipeswitch.desktop"
install -m 0644 "$ROOT/config.example.toml" \
  "$PKG/usr/share/doc/swipeswitch/examples/config.example.toml"
install -m 0644 "$ROOT/LICENSE" "$PKG/usr/share/doc/swipeswitch/copyright"
install -m 0644 "$ROOT/README.md" "$PKG/usr/share/doc/swipeswitch/README.md"
install -m 0644 "$ROOT"/docs/*.md "$PKG/usr/share/doc/swipeswitch/docs/"

cat > "$PKG/DEBIAN/postinst" <<'POSTINST'
#!/bin/sh
set -e
# Remove the legacy system-wide autostart entry from older packages.
# Login startup is now an explicit per-user control-panel preference.
rm -f /etc/xdg/autostart/swipeswitch.desktop
if [ "$1" = configure ] && [ -x /usr/bin/swipeswitch-conflicts ]; then
    echo "SwipeSwitch: checking for known competing touchpad gesture handlers..."
    /usr/bin/swipeswitch-conflicts --system-only || true
    echo "Open SwipeSwitch Control Panel to start/stop the service and configure login startup."
fi
exit 0
POSTINST
chmod 0755 "$PKG/DEBIAN/postinst"

mkdir -p "$ROOT/dist"
OUTPUT="$ROOT/dist/swipeswitch_${VERSION}_all.deb"
dpkg-deb --build --root-owner-group "$PKG" "$OUTPUT"
echo "Built: $OUTPUT"
echo "Install with: sudo apt install '$OUTPUT'"
