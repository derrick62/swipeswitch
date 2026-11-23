# SwipeSwitch

Touchpad-driven window and workspace navigation for X11 desktops.  
Swipe with three or four fingers to switch windows, change workspaces, open a task overview, or show the desktop — no mouse required.

---

## Requirements

| Requirement | Minimum version | Notes |
|-------------|----------------|-------|
| Python | 3.10 | 3.11+ recommended (built-in TOML parser) |
| GTK 3 | 3.0 | `gir1.2-gtk-3.0` |
| libwnck 3 | 3.0 | `gir1.2-wnck-3.0` |
| libinput | any | `libinput-tools` package |
| stdbuf | any | part of `coreutils` |
| X11 session | — | Wayland is **not** supported |

---

## Installation

### 1 — System dependencies

```bash
sudo apt install python3-gi gir1.2-gtk-3.0 gir1.2-wnck-3.0 \
                 libinput-tools coreutils
```

> **Fedora / RHEL**
> ```bash
> sudo dnf install python3-gobject gtk3 libwnck3 libinput
> ```

### 2 — Input-device access

`libinput debug-events` requires read access to `/dev/input/event*`.  
The safest way is to add your user to the `input` group:

```bash
sudo usermod -aG input "$USER"
```

Log out and back in (or run `newgrp input`) for the change to take effect.  
Verify with:

```bash
libinput debug-events --list-devices
```

If you see your touchpad listed, access is working.

### 3 — Clone and install

```bash
git clone https://github.com/your-username/swipeswitch.git
cd swipeswitch
pip install --break-system-packages -e .
```

The `-e` flag installs in *editable* mode so changes you make to the source are reflected immediately without reinstalling.

If you prefer an isolated environment:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

---

## Running

### Quick sanity check

Before starting the daemon, confirm that SwipeSwitch can find your touchpad and load GTK:

```bash
swipeswitch --check
```

Expected output:
```
X11 DISPLAY: :0
Touchpad:    /dev/input/event5
Config:      /home/you/.config/swipeswitch/config.toml
GTK 3 / libwnck imports: OK
```

### Start the daemon

```bash
swipeswitch
```

For verbose logging while you test your gestures:

```bash
swipeswitch --debug
```

Press **Ctrl-C** to stop.

### Autostart on login

#### XFCE / GNOME / KDE — using the desktop autostart folder

```bash
mkdir -p ~/.config/autostart
cat > ~/.config/autostart/swipeswitch.desktop << 'EOF'
[Desktop Entry]
Type=Application
Name=SwipeSwitch
Exec=swipeswitch
X-GNOME-Autostart-enabled=true
EOF
```

#### Systemd user service

```bash
mkdir -p ~/.config/systemd/user
cat > ~/.config/systemd/user/swipeswitch.service << 'EOF'
[Unit]
Description=SwipeSwitch touchpad gesture daemon
After=graphical-session.target
PartOf=graphical-session.target

[Service]
ExecStart=%h/.local/bin/swipeswitch
Restart=on-failure
Environment=DISPLAY=:0

[Install]
WantedBy=graphical-session.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now swipeswitch
```

Check service status:
```bash
systemctl --user status swipeswitch
journalctl --user -u swipeswitch -f
```

---

## Configuration

The config file is created automatically on first run at:

```
~/.config/swipeswitch/config.toml
```

You can point to a different file with `--config /path/to/file.toml`.

### Available options

```toml
# Which touchpad to listen on. "auto" detects the first gesture-capable device.
touchpad_device = "auto"

# Pixels of travel before the gesture is classified as horizontal or vertical.
show_threshold_px = 35

# Pixels between consecutive window-selection steps during a swipe.
step_px = 80

# Use unaccelerated touchpad movement (matches raw finger travel more closely).
use_unaccelerated = false

# Only show windows from the current virtual workspace.
current_workspace_only = true

# Window order in the switcher: "mru" (most-recently-used) or "fixed" (stack order).
order = "mru"

# Cancel an unfinished gesture after this many seconds of inactivity.
gesture_timeout = 3.0

# Colour scheme: "dark", "light", or "auto" (follows system preference).
theme = "dark"

# Which monitor to show the switcher on (only "primary" is implemented in v1).
monitor = "primary"
```

### Reloading config without restarting

Send `SIGHUP` to pick up changes immediately:

```bash
pkill -HUP swipeswitch
```

---

## Gestures

| Fingers | Direction | Action |
|---------|-----------|--------|
| 3 | Left / Right | Switch between open windows (swipe to scroll, release to activate) |
| 3 | Up | Open task overview |
| 3 | Down | Show desktop (swipe up again to restore windows) |
| 4 | Left / Right | Move to next / previous virtual workspace |

---

## Project structure

```
swipeswitch/
├── input/
│   ├── __init__.py
│   ├── listener.py      # libinput subprocess + restartable thread
│   ├── parser.py        # pure text→dataclass parser (no I/O)
│   └── events.py        # GestureEvent dataclass
├── recognition/
│   ├── __init__.py
│   └── gestures.py      # GestureRecognizer + GestureAction
├── desktop/
│   ├── __init__.py
│   ├── tracker.py       # MRU window list (Wnck-backed)
│   ├── workspaces.py    # virtual workspace navigation
│   ├── desktop.py       # show-desktop snapshot/restore
│   └── activator.py     # window activation + wmctrl fallback
├── ui/
│   ├── __init__.py
│   ├── overlay.py       # switcher overlay window
│   ├── task_view.py     # monitor-aware task overview grid
│   ├── theme.py         # CSS strings + ThemeManager
│   ├── cards.py         # CardBuilder — individual card widgets
│   ├── animations.py    # AnimationMixer — fade + scroll
│   └── helpers.py       # LayoutEngine + WindowPropertyHelpers
├── config.py            # Config dataclass + TOML loader
├── controller.py        # gesture→action wiring
└── __main__.py          # entry point
```

Flat shims at the top level (`swipeswitch/events.py`, `swipeswitch/gestures.py`, etc.) forward imports for backward compatibility with any code that used the old structure.

---

## Running the tests

```bash
pip install --break-system-packages pytest
python -m pytest
```

Tests that require a live X11/GTK session are skipped automatically; the pure-Python suite (parser, gestures, controller, config, tracker, workspaces) runs anywhere.

---

## Troubleshooting

**"No pointer device with libinput gesture capability was found"**  
Run `libinput list-devices` and check that your touchpad has `gesture` in its capabilities. If it does not, your kernel or libinput version may not support it.

**"Permission denied reading /dev/input/eventX"**  
Your user is not in the `input` group. Run `sudo usermod -aG input "$USER"` and log out/in.

**"libinput was not found"**  
Install `libinput-tools` (`sudo apt install libinput-tools`).

**"SwipeSwitch requires an X11 session"**  
You are on a Wayland session. SwipeSwitch requires X11; on a mixed session set `DISPLAY=:0 swipeswitch`.

**Gestures are detected but windows do not switch**  
Check that `wmctrl` is installed (`sudo apt install wmctrl`) as the activation fallback; some window managers also require compositing to be enabled.
