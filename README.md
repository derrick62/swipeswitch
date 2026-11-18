# SwipeSwitch

A touchpad-driven desktop navigation utility for Kali Linux and Debian-based
systems running XFCE on X11. SwipeSwitch combines three-finger window
switching, Task View, Show Desktop/restoration and four-finger workspace
navigation with a horizontal, preview-first window switcher.

**Version:** 0.3.3 — **License:** MIT  
**Status:** First installable Debian package; live acceptance testing on the
target laptop is still required before calling the application stable.

## Core features

- Three-finger right/left: browse the MRU window list and activate the selected window on release.
- Three-finger up: open Task View, or restore a valid Show Desktop snapshot.
- Three-finger down: hide currently visible eligible windows and preserve a snapshot.
- Four-finger left/right: navigate next/previous XFCE virtual workspaces without wrapping.
- Horizontal window cards with large previews, app identity, selected-card outline, animated scrolling and off-screen edge hints.
- Monitor-aware sizing and selection of the monitor beneath the pointer when the GTK display backend supports it.
- Lazy, best-effort X11 thumbnails and a locally captured blurred/dimmed desktop backdrop, with graceful icon/dim fallbacks.
- Optional mouse callbacks in the switcher; they are not connected by default, so gesture-only use remains unchanged.
- TOML configuration, XFCE autostart, and no network or telemetry.

Window previews are static snapshots, not live video. Minimized, protected or
inaccessible windows may show their application icon instead. Wayland is not
supported. Gesture thresholds may need calibration for individual touchpads.

## Requirements

Kali/Debian with Python 3.10+, an X11 session, GTK 3, PyGObject, libwnck 3,
Pillow, libinput-tools and XFCE/xfwm4. These runtime dependencies are declared
in the Debian package and are installed by APT.

## Install the Debian package

Download or build `swipeswitch_0.3.3_all.deb`, then install it with APT:

```bash
sudo apt install ./swipeswitch_0.3.3_all.deb
```

APT installs the required runtime dependencies. The package installs:

- `/usr/bin/swipeswitch` — system-wide launcher
- `/usr/lib/python3/dist-packages/swipeswitch/` — application modules
- `/usr/share/applications/swipeswitch.desktop` — application-menu entry
- `/etc/xdg/autostart/swipeswitch.desktop` — XFCE session autostart

Log out and back in (or start it manually) after installation. Run it as your
normal desktop user; **never use `sudo swipeswitch`**.

```bash
swipeswitch --check
swipeswitch
swipeswitch --debug
```

Remove the application while preserving your personal configuration with:

```bash
sudo apt remove swipeswitch
```

Purge also removes package-managed system files and does not delete your
personal `~/.config/swipeswitch/` settings:

```bash
sudo apt purge swipeswitch
```

## Build the Debian package from source

On a Debian/Kali build machine with `dpkg-deb` installed:

```bash
./build-deb.sh
```

The package is written to `dist/swipeswitch_0.3.3_all.deb`. The package is
architecture-independent; its runtime dependencies are supplied by APT.

## Input-device permissions

The listener runs `libinput debug-events --device /dev/input/eventX` for the
selected touchpad only. Reading `/dev/input/eventX` commonly requires
membership in the `input` group. Inspect permissions before changing them:

```bash
ls -l /dev/input/event*
getent group input
```

If access is denied and you understand the broader implications, an
administrator can add your account to the `input` group:

```bash
sudo usermod -aG input "$USER"
```

Then log out completely and back in. Membership grants access to input
devices more broadly than SwipeSwitch itself needs. The package deliberately
does not change group membership or install a setuid helper.

## Configuration

The first run creates `~/.config/swipeswitch/config.toml` if it does not
already exist. Common settings include:

```toml
touchpad_device = "auto"
step_px = 80
show_threshold_px = 35
use_unaccelerated = false
current_workspace_only = true
order = "mru"
gesture_timeout = 3.0
theme = "dark"
monitor = "primary"
thumbnails = true
```

- `step_px`: horizontal distance per selection/workspace step.
- `show_threshold_px`: distance before classifying a gesture.
- `use_unaccelerated`: use libinput's unaccelerated movement pair when available.
- `current_workspace_only`: active workspace only; sticky windows remain eligible.
- `order`: `mru` or `fixed`.
- `gesture_timeout`: safety timeout in seconds.
- `touchpad_device`: `auto` or a `/dev/input/eventX` path.
- `theme`: `dark`, `light`, or `auto`.
- `monitor`: retained for configuration compatibility; the polished switcher chooses the monitor beneath the pointer when possible and falls back to the primary monitor.
- `thumbnails`: enable best-effort X11 window snapshots.

After editing the config, reload the running process with `kill -HUP <PID>`.

## Avoid gesture conflicts

If `libinput-gestures` handles three-finger horizontal swipes, both programs
may respond. Back up `~/.config/libinput-gestures.conf` and disable only its
three-finger left/right bindings. Keep unrelated gestures if desired. The
package does not edit this file automatically.

## Tests and validation

Run the automated tests from the source tree:

```bash
python3 -m pytest -q
python3 -m compileall -q swipeswitch
```

The automated suite uses fakes for window-manager integration. Actual GTK
rendering, X11 thumbnail/backdrop capture, XFCE workspace timing and physical
touchpad behaviour must be tested in a live desktop session. `swipeswitch
--check` checks X11, touchpad discovery and GTK/libwnck imports; it does not
replace a real gesture test.

## Troubleshooting

- **No touchpad detected:** inspect `libinput list-devices`; set `touchpad_device` to the correct event path if auto-detection is ambiguous.
- **Permission denied:** inspect `/dev/input` access and input-group membership. Never run the app as root.
- **No gesture events:** test `libinput debug-events --device /dev/input/eventX` and confirm the touchpad reports the configured finger count.
- **Double switching:** disable conflicting three-finger horizontal bindings in libinput-gestures.
- **No overlay:** confirm X11 (`echo "$DISPLAY"`) and GTK/libwnck packages; run with `--debug`.
- **Unexpected initial MRU order:** the MRU list is seeded from stacking order and improves as windows receive focus changes.

## Privacy

SwipeSwitch processes local libinput gesture events and local X11 window
metadata/previews. It does not read keyboard devices, record keystrokes, send
telemetry or require a network connection.
