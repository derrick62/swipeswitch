# SwipeSwitch — Master Product Specification, Architecture & Development Blueprint

**Version:** 1.0  
**Date:** 18 November 2026  
**Status:** Product baseline; implementation is incremental and not all features exist.

## Product vision

SwipeSwitch is a touchpad-driven desktop navigation utility for Kali Linux running XFCE on X11. It translates multi-finger swipe gestures into predictable window and workspace navigation, while providing a visual window switcher, a persistent Task View, and reversible Show Desktop behaviour.

The product is not merely a collection of gesture bindings. It must reliably capture input, recognise intent, route actions, coordinate with the window manager, preserve desktop state, and present a coherent interface.

## Supported environment

- Initial target: Kali Linux, XFCE/xfwm4, X11.
- Language: Python 3.10+; Python 3.11+ recommended.
- UI: GTK 3 / PyGObject.
- Window management: libwnck 3 and X11 facilities where necessary.
- Input: libinput gesture events from the selected touchpad.
- Configuration: TOML.
- License: MIT.
- Wayland is outside the initial release scope.
- Initial visual overlays target the primary monitor.

## Product behaviour

### Three-finger horizontal window switching

| Gesture | Action |
|---|---|
| Three fingers left | Next window |
| Three fingers right | Previous window |

The switcher presents a live selection overlay. Selection follows accumulated horizontal movement and the highlighted window is activated on release. The default ordering is most-recently-used. Eligible windows are on the current workspace, with sticky windows included. Minimized windows remain eligible and must be unminimized before activation. Panels, docks, desktop windows, splash windows, and SwipeSwitch's own overlay are excluded. Selection wraps around. If fewer than two eligible windows exist, the gesture does nothing. Cancellation must never activate a window. Quick-flick switching remains optional and must not compromise normal selection.

### Three-finger vertical navigation

| Gesture | Action |
|---|---|
| Three fingers down | Show Desktop |
| Three fingers up with a valid snapshot | Restore captured windows |
| Three fingers up without a snapshot | Open Task View |

Show Desktop captures the windows that are visible at the time of activation, then hides/minimizes those windows without closing applications. Windows already minimized are not captured and must remain minimized. Repeated down gestures must not replace the original snapshot. Windows closed before restoration are skipped. After restoration, the snapshot is cleared.

Task View is a persistent visual overview, distinct from the horizontal switcher. It displays eligible windows in a grid with application icon and title; thumbnails are used when available but are not a prerequisite. The user selects a window with the pointer. Selection activates the window and dismisses Task View. Escape and clicking outside dismiss it. It must work with one eligible window and must not unnecessarily steal focus before selection.

### Four-finger horizontal workspace navigation

| Gesture | Action |
|---|---|
| Four fingers left | Next workspace |
| Four fingers right | Previous workspace |

Workspace boundaries do not wrap by default. One gesture produces one workspace navigation action, not repeated actions for every update event. Workspace navigation must not accidentally activate a stale window selection.

### Unsupported gestures

Two-finger gestures, pinch, hold, four-finger vertical gestures, and unsupported finger counts are ignored in the initial release.

## Core engineering principles

- Separate raw input, event parsing, gesture recognition, routing, desktop actions, and presentation.
- Keep gesture recognition testable without GTK or a live window manager.
- GTK widgets are owned by the GTK main thread; input workers dispatch normalised events to that thread.
- Treat cancellation and ambiguous input conservatively.
- Never close applications as part of Show Desktop.
- No telemetry, network access, keyboard capture, or unnecessary privilege escalation.
- Do not silently modify another gesture utility's configuration.
- Distinguish implemented, unit-tested, integration-tested, and manually verified behaviour.

## Proposed architecture

```text
Touchpad / libinput
        |
Input listener and parser
        |  normalised GestureEvent
Gesture recognition engine
        |  recognised gesture
Central gesture router
        |
+----------------------+----------------------+----------------------+-------------------+
| Window switcher      | Workspace manager   | Desktop manager      | Task View         |
+----------------------+----------------------+----------------------+-------------------+
        |
Desktop integration (libwnck / X11) and GTK presentation
```

Supporting services include configuration validation, logging, window tracking, activation, thumbnail capture, and application lifecycle management. The entry point should compose these services rather than contain feature logic.

## Input and device handling

The device is selected through automatic detection or an explicit `/dev/input/eventX` override. Detection must recognise the actual libinput capability pattern reported by the target hardware: `pointer gesture`. Device paths discovered during diagnostics are not permanent constants. The listener must accept libinput update lines both with and without the optional sequence number. Movement is accumulated over the gesture lifecycle.

The application runs as the logged-in desktop user. It must not run as root or setuid. Input-device permission guidance must explain the broader security implications of `input` group membership.

## Configuration direction

The configuration should evolve from the prototype's single `fingers` setting into feature-specific sections. Proposed shape (values are starting defaults and require real-device tuning):

```toml
[device]
touchpad = "auto"

[window_switcher]
enabled = true
fingers = 3
step_px = 80
show_threshold_px = 25
flick_min_px = 40
invert_direction = false
current_workspace_only = true
order = "mru"

[task_view]
enabled = true
fingers = 3
activation_threshold_px = 35
current_workspace_only = true

[show_desktop]
enabled = true
fingers = 3
activation_threshold_px = 35

[workspace_navigation]
enabled = true
fingers = 4
activation_threshold_px = 35
invert_direction = false
wrap = false

[general]
gesture_timeout = 3.0
use_unaccelerated = false
theme = "dark"
monitor = "primary"

[thumbnails]
enabled = false
capture_budget_ms = 150
```

This is a design target, not a claim that the current application supports these sections. Invalid configuration must be reported clearly and must not silently produce surprising behaviour.

## Reliability and edge cases

- Ignore malformed or unsupported input events without terminating the application.
- Reset incomplete gestures after a bounded timeout.
- Do not activate a window after cancellation.
- Skip windows that close during a selection or restoration operation.
- Thumbnail failure must not prevent window selection.
- Workspace navigation failure must not corrupt switcher state.
- Listener failure must be logged and recovered with bounded backoff where appropriate.
- Touchpad disconnect/reconnect and process shutdown must be handled cleanly.
- Overlay failure must leave the desktop usable.

## Verification standards

Unit tests cover parser formats, finger counts, direction, accumulated movement, thresholds, cancellation, timeout, routing, window filtering, workspace boundaries, and snapshot restoration. Integration tests cover GTK, libwnck, xfwm4 and X11. Manual acceptance testing covers normal, minimized, maximized, fullscreen and sticky windows; multiple workspaces; fast, slow, diagonal and cancelled gestures; repeated Show Desktop; and extended daily use.

A feature is not complete merely because code exists. Record separately whether it is implemented, unit-tested, integration-tested, and manually verified on the target laptop.

## Development roadmap

| Milestone | Objective |
|---|---|
| 0 | Project baseline, technical audit, documentation and development workflow |
| 1 | Gesture input and recognition foundation |
| 2 | Three-finger horizontal window switching |
| 3 | Four-finger workspace navigation |
| 4 | Show Desktop and restoration |
| 5 | Three-finger Task View |
| 6 | Visual refinement and thumbnails |
| 7 | Integration and system reliability |
| 8 | Installation, configuration and packaging |
| 9 | Release preparation and maintenance |

Each milestone follows: understand requirements, design the solution, implement incrementally, test and verify, then document and close the milestone.

## Definition of Done

Core completion requires all six agreed gestures, correct routing, state preservation, validated configuration, automated tests, and successful live desktop testing. Release completion additionally requires reproducible installation/uninstallation, privacy and permission guidance, conflict handling, compatibility documentation, versioning, regression tests, and release notes.
