# swipeswitch

A touchpad-driven desktop navigation utility for Kali Linux running XFCE on X11.
The 0.2.0 core preview implements three-finger window switching, Task View,
Show Desktop/restoration and four-finger workspace navigation.

**Version:** 0.2.0 — **License:** MIT  
**Status:** Core-feature preview; live desktop acceptance testing and refinement remain outstanding.

## Core features in this preview

- Three-finger left/right: continuous MRU window selection and activation.
- Three-finger up: open Task View, or restore a valid Show Desktop snapshot.
- Three-finger down: hide currently visible eligible windows and preserve a snapshot.
- Four-finger left/right: navigate next/previous XFCE virtual workspaces.
- Gesture recognition is separated from desktop actions and GTK presentation.
- libinput listener accepts both three- and four-finger swipe events.
- Touchpad auto-detection recognises pointer + gesture capabilities.
- Window tracking includes eligible minimized windows and sticky windows.
- Task View provides a persistent clickable overview with Escape dismissal.
- TOML configuration, XFCE autostart and module-based launcher are included.

These features are implemented in the source but are not yet verified on the
target laptop. Treat this as a functional preview, not a stable release.

## Requirements and limits

Kali/Debian, Python 3.10+ (3.11+ recommended), X11, GTK 3, PyGObject,
libwnck 3, libinput-tools and XFCE/xfwm4 recommended. Wayland and VMs that
swallow touchpad gestures are not supported. The switcher overlay targets the
primary monitor. Window thumbnails, animation, advanced focus restoration,
multiple touchpads and Wayland support are not yet implemented. Gesture thresholds may need calibration on the target hardware.

## Install

From the extracted directory:

```bash
chmod +x install.sh
./install.sh
```

The installer uses apt to install runtime dependencies, places the app in
`~/.local/share/swipeswitch`, installs a module-based launcher in
`~/.local/bin`, creates the first config and adds an XFCE autostart entry.
The included systemd user-service file is a template and is not enabled by the
installer; use the XFCE autostart entry as the single default startup method.
Ensure `~/.local/bin` is on your PATH.

```bash
~/.local/bin/swipeswitch --check
~/.local/bin/swipeswitch
~/.local/bin/swipeswitch --debug
```

`--debug` logs parsed gesture information, not raw event streams.

## Input permissions and privacy

The listener runs `stdbuf -oL libinput debug-events --device /dev/input/eventX`.
The `--device` option restricts input to the selected touchpad. The program
parses only swipe BEGIN, UPDATE and END events; it does not read keyboard
devices, record keystrokes, collect pointer motion, use the network or send
telemetry.

Reading `/dev/input/eventX` commonly requires membership in the `input` group.
Inspect permissions first:

```bash
ls -l /dev/input/event*
getent group input
```

If appropriate for your machine, add your user with
`sudo usermod -aG input "$USER"`, then log out completely and back in.
Membership grants broader access to input devices than this app itself needs;
understand that trade-off before changing group membership. The app does not
need root or setuid and should never be launched with `sudo`.

## Configuration

Created on first run at `~/.config/swipeswitch/config.toml`:

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

- `step_px`: horizontal distance per selection step.
- `show_threshold_px`: distance before classifying a gesture.
- `use_unaccelerated`: use libinput's unaccelerated movement pair when available.
- `current_workspace_only`: active workspace only; sticky windows remain eligible.
- `order`: `mru` or `fixed`.
- `gesture_timeout`: safety timeout in seconds.
- `touchpad_device`: `auto` or a `/dev/input/eventX` path.
- `theme`: `dark`, `light`, or `auto` (auto currently uses dark fallback).
- `monitor`: `primary` in v1.

Reload after editing with `kill -HUP <PID>`.

## libinput-gestures conflict

If `libinput-gestures` handles three-finger horizontal swipes, both programs
may respond. Back up `~/.config/libinput-gestures.conf` and disable only its
three-finger left/right bindings. Keep unrelated gestures such as four-finger
workspace changes and three-finger up/down. The installer does not edit this
file automatically.

## Tests

Runtime uses distro-provided libraries; tests use pytest:

```bash
python3 -m venv --system-site-packages .venv
. .venv/bin/activate
pip install pytest
python -m pytest -q
```

Tracker tests use Wnck-like fakes. Real GTK/xfwm and touchpad behavior requires
a live X11 session.

## Troubleshooting

- **No touchpad detected:** inspect `libinput list-devices`; set
  `touchpad_device` to the correct event path if auto-detection is ambiguous.
- **Permission denied:** inspect `/dev/input` access and input-group membership.
  Log out/in after changing groups. Never run the app as root.
- **No gesture events:** test `libinput debug-events --device /dev/input/eventX`
  and confirm the touchpad reports the configured finger count.
- **Double switching:** disable the conflicting three-finger horizontal
  bindings in libinput-gestures.
- **No overlay:** confirm X11 (`echo "$DISPLAY"`) and GTK/libwnck packages;
  run with `--debug`.
- **Unexpected initial MRU order:** the MRU list is seeded from stacking order
  and improves as windows receive focus changes.
- **Fullscreen/decoration quirks:** GTK overlay hints may need tuning against
  the target xfwm4 version.

## Architecture

```text
touchpad -> libinput debug-events --device <touchpad>
         -> listener/parser worker -> GLib.idle_add
         -> gesture recognizer -> gesture controller
         -> Wnck window/workspace services -> GTK switcher and Task View
```

## Roadmap and validation status

- **Stage 0:** capture real BEGIN/UPDATE/END lines from the target Dell touchpad.
  The included fixture is illustrative and must be replaced with captured data.
- **Core preview:** gesture recognition, switching, workspaces, Show Desktop and Task View implemented; desktop acceptance testing remains outstanding.
- **Next:** verify all gesture paths on the target laptop, fix integration defects and tune thresholds.
- **Polish:** thumbnails, animation, monitor support, configuration UX and release hardening.
- **Phase B/C:** validate another laptop, refine installer, add Debian package
  and release workflow.

This archive is a core-feature preview, not a claim that the target hardware
has already been validated.


## Project documentation

The product and engineering source of truth is maintained in `docs/`:

- `docs/MASTER_PROJECT_DOCUMENT.md` — product behaviour, architecture direction and definition of done.
- `docs/DEVELOPMENT_ROADMAP.md` — milestone scope and exit conditions.
- `docs/ARCHITECTURE.md` — component boundaries, event flow and threading model.
- `docs/GESTURE_DESIGN.md` — gesture mapping and recognition rules.
- `docs/AUDIT.md` — current implementation assessment and outstanding verification.
- `docs/TESTING_STRATEGY.md` — unit, integration and manual acceptance strategy.
- `docs/GIT_WORKFLOW.md` — repository, branching and commit conventions.
- `docs/CHANGELOG.md` — project change history.

The 0.2.0 archive contains the first integrated implementation of the agreed core gestures. It has not yet been validated on the target laptop; consult `docs/AUDIT.md` and the changelog for verification status.
