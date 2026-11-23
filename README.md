# SwipeSwitch

SwipeSwitch provides touchpad-driven window and workspace navigation for X11 desktops. Three-finger gestures switch windows, open Task View and show/restore the desktop; four-finger horizontal gestures navigate virtual workspaces.

The application consists of a foreground gesture engine and a separate GTK control panel. The control panel manages the engine as a **per-user systemd service**, so it can be started or stopped without logging out, rebooting, reinstalling the package, or changing touchpad configuration.

> **Platform support:** X11 sessions on Debian-based Linux distributions (including Kali Linux) with GTK 3, libwnck 3, libinput and a compatible touchpad. Wayland is not supported.

## Features

- Three-finger horizontal window switcher with MRU ordering.
- Three-finger up Task View and three-finger down Show Desktop/restore.
- Four-finger horizontal virtual-workspace navigation.
- GTK control panel with a live Running/Stopped indicator.
- Start/Stop control for the gesture service.
- Explicit Launch at Login preference, disabled by default on a fresh installation.
- User-level service management; no `sudo` is used by the control panel.
- Existing user configuration is preserved during package upgrades.

## Requirements

| Component | Debian/Kali package | Purpose |
|---|---|---|
| Python 3.10+ | `python3` | Runtime |
| GTK 3 bindings | `python3-gi`, `gir1.2-gtk-3.0` | Control panel and switcher UI |
| libwnck 3 bindings | `gir1.2-wnck-3.0` | Window/workspace integration |
| GdkPixbuf introspection | `gir1.2-gdkpixbuf-2.0` | Window preview support |
| Pillow | `python3-pil` | Image processing |
| libinput tools | `libinput-tools` | Touchpad gesture event stream |
| Core utilities | `coreutils` | `stdbuf` and standard utilities |
| Window manager tools | `wmctrl` | Window activation fallback |
| Service manager | `systemd` | Per-user service lifecycle |
| Session | X11 | Wayland is currently unsupported |

The Debian package declares these dependencies and APT installs them automatically.

## Installation

### Install a built Debian package

Download the current `swipeswitch_0.3.6_all.deb` package and install it with:

```bash
sudo apt install ./swipeswitch_VERSION_all.deb
```

APT installs the application, the user service unit, the control-panel launcher and required dependencies. The package does **not** automatically start the gesture engine. This lets you decide when it should run.

Open **SwipeSwitch Control Panel** from the desktop applications menu, or run:

```bash
swipeswitch-control
```

### Install from a source checkout

On Kali/Debian, install runtime dependencies and clone the repository:

```bash
sudo apt update
sudo apt install python3 python3-gi gir1.2-gtk-3.0 gir1.2-wnck-3.0 \
  gir1.2-gdkpixbuf-2.0 python3-pil libinput-tools coreutils wmctrl systemd

git clone https://github.com/derrick62/swipeswitch.git
cd swipeswitch
```

For development, use a virtual environment if desired, then install the project in editable mode:

```bash
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install -e .
```

The editable install provides both `swipeswitch` and `swipeswitch-control` commands. Open the control panel with:

```bash
swipeswitch-control
```

If no packaged systemd unit is present, the control panel creates a user-local development unit under `~/.config/systemd/user/swipeswitch.service`, pointing to the `swipeswitch` executable found in the current environment. This keeps development builds separate from the system package files.

For a non-editable source installation, the repository also provides:

```bash
./install.sh
```

The installer copies the application into `~/.local/share/swipeswitch`, creates user launchers and a user service, and preserves an existing `~/.config/swipeswitch/config.toml`.

## Using the control panel

The control panel is the recommended way to manage SwipeSwitch.

### Running / Stopped

The status row shows a coloured indicator and the current service state:

- **Green indicator — Running:** the gesture service is active.
- **Grey indicator — Stopped:** the gesture service is inactive.
- **Amber indicator — service manager unavailable:** the panel cannot query the user systemd manager.

The status refreshes automatically while the panel is open.

### Start / Stop

Select **Start SwipeSwitch** to start the gesture service. Select **Stop SwipeSwitch** to stop it. Stopping sends the normal termination signal to the SwipeSwitch process; its listener shuts down through the application's existing cleanup path.

The control panel manages only `swipeswitch.service` through `systemctl --user`. It does not disable system libinput, alter `/dev/input` permissions, change input groups, disable the touchpad, or manage other gesture applications. It terminates only the libinput `debug-events` capture subprocess that belongs to the SwipeSwitch engine. No root privileges are requested for Start/Stop.

### Launch automatically when I log in

Enable **Launch automatically when I log in** to create a per-user desktop autostart entry at:

```text
~/.config/autostart/swipeswitch-daemon.desktop
```

At login, the entry imports the graphical session environment and starts the user service. Disable the preference to remove that autostart entry. Changing this preference does not start or stop the currently running service; use the Start/Stop button for the current session.

A fresh installation leaves this preference disabled. Existing system-wide SwipeSwitch autostart entries from older packages are removed during upgrade. If an older source installation left `~/.config/autostart/swipeswitch.desktop`, the control panel renames that exact legacy entry to `swipeswitch.desktop.disabled-by-swipeswitch-control` rather than deleting it. An older engine that is still running outside systemd is detected as Running and can be stopped from the panel with SIGTERM; unrelated processes are not targeted.

## Manual service commands

The control panel is preferred, but the underlying user service can also be inspected manually:

```bash
systemctl --user status swipeswitch.service
systemctl --user start swipeswitch.service
systemctl --user stop swipeswitch.service
journalctl --user -u swipeswitch.service -f
```

These commands manage SwipeSwitch only. Do not use `sudo systemctl` for this user service.

## Configuration

The user configuration is stored at:

```text
~/.config/swipeswitch/config.toml
```

The application creates it with defaults on first run. Package upgrades do not replace it. A sample configuration is included as `config.example.toml` in the source tree and under `/usr/share/doc/swipeswitch/examples/` in the Debian package.

Common options:

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
```

To reload configuration in a manually running development instance, send `SIGHUP` to that process. When managed by systemd, restart the service after editing:

```bash
systemctl --user restart swipeswitch.service
```

## Gestures

| Fingers | Direction | Action |
|---|---|---|
| 3 | Left / Right | Switch between open windows |
| 3 | Up | Open Task View |
| 3 | Down | Show Desktop; swipe up to restore the captured windows |
| 4 | Left / Right | Move to previous / next virtual workspace |

## Input-device permissions

`libinput debug-events` must be able to read the touchpad event device. Check device discovery with:

```bash
libinput list-devices
swipeswitch --check
```

If the current user does not have permission to read the relevant `/dev/input/event*` device, follow your distribution's device-access policy. On some Debian-derived desktop installations, membership in the `input` group is used:

```bash
sudo usermod -aG input "$USER"
```

Log out and back in for group membership changes to take effect. Membership in the `input` group grants broad access to input devices, so use the least-privileged device-access mechanism supported by your system where possible.

## Development

### Project layout

```text
swipeswitch/
├── swipeswitch/
│   ├── input/                 # libinput subprocess, event parsing and event model
│   ├── recognition/           # gesture lifecycle and action recognition
│   ├── desktop/               # window tracking, workspace and desktop operations
│   ├── ui/                    # switcher overlay, Task View, cards and theme
│   ├── __main__.py            # gesture-engine entry point
│   ├── controller.py          # gesture actions wired to desktop/UI operations
│   ├── config.py              # typed configuration and TOML loading
│   ├── service.py             # per-user systemd and login-autostart management
│   └── control_panel.py       # GTK Running/Stopped and Start/Stop panel
├── scripts/
│   ├── swipeswitch-conflicts.py
│   └── swipeswitch-session-start
├── packaging/
│   ├── debian/control
│   ├── swipeswitch.desktop    # applications-menu entry for the control panel
│   └── swipeswitch.service    # packaged user service unit
├── tests/                     # automated regression tests
├── docs/                      # architecture, gesture and testing documentation
├── build-deb.sh               # builds the Debian package
├── install.sh                 # user-local source installer
├── uninstall.sh               # removes app files but preserves user config
└── pyproject.toml              # package metadata and command entry points
```

### Lifecycle architecture

- `swipeswitch.__main__` owns the gesture engine and its `LibinputListener` lifecycle. SIGTERM triggers the existing listener cleanup and exits GTK.
- `swipeswitch.service` is the control-plane boundary. It invokes only `systemctl --user` for `swipeswitch.service` and manages one user autostart file.
- `swipeswitch.control_panel` is a GTK client of that service manager. It polls service status, issues Start/Stop requests and stores the login preference.
- `packaging/swipeswitch.service` is installed as a systemd **user** unit. It is not enabled automatically.
- The desktop autostart helper imports the active X11/DBus environment before asking the user service manager to start SwipeSwitch.

The control panel does not import or manipulate the input listener directly. This keeps UI state and process lifecycle separate from gesture recognition and desktop integration.

### Tests

Install pytest in the development environment and run:

```bash
python -m pytest -q
python -m compileall -q swipeswitch
bash -n install.sh build-deb.sh uninstall.sh scripts/swipeswitch-session-start
```

The service-manager tests use a fake command runner and temporary configuration paths; they do not start or stop the host's real services. GTK rendering and physical touchpad gestures require a live X11 desktop and compatible hardware.

### Build a Debian package

On a Debian/Kali build host with `dpkg-deb` installed:

```bash
./build-deb.sh
```

The package is written to `dist/swipeswitch_VERSION_all.deb`. Inspect it before installing:

```bash
dpkg-deb --info dist/swipeswitch_*_all.deb
dpkg-deb --contents dist/swipeswitch_*_all.deb
```

## Troubleshooting

**The control panel says the service manager is unavailable**

Confirm that the desktop session has a running user systemd manager and DBus session:

```bash
systemctl --user status
printf 'DISPLAY=%s\n' "$DISPLAY"
printf 'DBUS_SESSION_BUS_ADDRESS=%s\n' "$DBUS_SESSION_BUS_ADDRESS"
```

**The service starts and immediately stops**

Inspect its logs:

```bash
journalctl --user -u swipeswitch.service -b --no-pager
```

Confirm the session is X11 (`echo "$XDG_SESSION_TYPE"`), then run `swipeswitch --check` from a terminal in that same session.

**No gesture-capable touchpad is found**

Run `libinput list-devices` and confirm that the touchpad advertises gesture capability. Hardware, kernel and libinput support vary by device.

**Permission denied reading `/dev/input/eventX`**

Check the device's access policy and the current user's group membership. Restart the login session after any permission-group change.

**Gestures are detected but windows do not switch**

Check that the session is X11 and that the window manager exposes windows through libwnck. `wmctrl` is used as an activation fallback on supported setups.

## Uninstall

For a source installation:

```bash
./uninstall.sh
```

For the Debian package:

```bash
sudo apt remove swipeswitch
```

The user's `~/.config/swipeswitch/` configuration is intentionally preserved. If you also want to remove that configuration, remove it separately after uninstalling.

## Security and privacy

SwipeSwitch is a local desktop utility. The control panel does not require root for service management. It never disables libinput or the touchpad, changes device permissions, or stops unrelated services. No telemetry or network connection is required for normal operation.

## License

See [LICENSE](LICENSE).
