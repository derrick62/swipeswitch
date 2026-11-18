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
  "$PKG/etc/xdg/autostart" "$PKG/DEBIAN"

install -m 0644 "$ROOT"/swipeswitch/*.py "$PKG/usr/lib/python3/dist-packages/swipeswitch/"
install -m 0644 "$ROOT/packaging/debian/control" "$PKG/DEBIAN/control"
sed -i "s/^Version: .*/Version: $VERSION/" "$PKG/DEBIAN/control"
cat > "$PKG/usr/bin/swipeswitch" <<'LAUNCHER'
#!/bin/sh
exec /usr/bin/python3 -m swipeswitch "$@"
LAUNCHER
chmod 0755 "$PKG/usr/bin/swipeswitch"
install -m 0644 "$ROOT/packaging/swipeswitch.desktop" \
  "$PKG/usr/share/applications/swipeswitch.desktop"
install -m 0644 "$ROOT/packaging/swipeswitch-autostart.desktop" \
  "$PKG/etc/xdg/autostart/swipeswitch.desktop"
install -m 0644 "$ROOT/config.example.toml" \
  "$PKG/usr/share/doc/swipeswitch/examples/config.example.toml"
install -m 0644 "$ROOT/LICENSE" "$PKG/usr/share/doc/swipeswitch/copyright"
install -m 0644 "$ROOT/README.md" "$PKG/usr/share/doc/swipeswitch/README.md"
install -m 0644 "$ROOT"/docs/*.md "$PKG/usr/share/doc/swipeswitch/docs/"

mkdir -p "$ROOT/dist"
OUTPUT="$ROOT/dist/swipeswitch_${VERSION}_all.deb"
dpkg-deb --build --root-owner-group "$PKG" "$OUTPUT"
echo "Built: $OUTPUT"
echo "Install with: sudo apt install '$OUTPUT'"
