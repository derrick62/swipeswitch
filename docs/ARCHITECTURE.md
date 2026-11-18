# SwipeSwitch Architecture

## Architectural objective

Keep input capture, gesture interpretation, desktop operations and presentation independent enough to test and evolve separately. Avoid abstractions that do not have a concrete responsibility.

## Target component boundaries

| Component | Responsibility |
|---|---|
| `listener.py` | Discover the selected device, run libinput and emit parsed events |
| Parser (`listener.py`) | Convert libinput text into normalised `GestureEvent` values |
| Gesture recogniser | Track lifecycle, finger count, accumulated movement, direction, thresholds, cancellation and timeout |
| `gestures.py` / `controller.py` | Classify gestures and dispatch recognised actions to the correct desktop feature |
| `tracker.py` / window service | Discover eligible windows, maintain MRU order and expose current desktop state |
| Window switcher controller | Manage selection lifecycle and activation request |
| Workspace manager | Discover and navigate virtual workspaces |
| Desktop manager | Capture visible-window snapshot and restore surviving windows |
| Task View controller | Present persistent overview and manage pointer selection/dismissal |
| `activator.py` | Activate and unminimise a selected window |
| `overlay.py` and future views | GTK presentation only; no raw input parsing |
| `thumbs.py` | Optional thumbnail acquisition with bounded work and graceful failure |
| `config.py` | Load, validate and expose typed configuration |
| `__main__.py` | Compose dependencies, own process lifecycle and start the GTK loop |

## Threading model

The libinput subprocess is read by a background worker. Parsing may occur in that worker, but callbacks that affect desktop state or GTK must be dispatched to the GTK main loop using `GLib.idle_add` or an equivalent main-context mechanism. GTK widgets must never be created, mutated or destroyed from the input worker.

## Event flow

```text
libinput text line
  -> parser
  -> GestureEvent(kind, fingers, dx, dy, cancelled)
  -> recogniser lifecycle and accumulated movement
  -> recognised gesture intent
  -> router
  -> feature controller
  -> desktop service / GTK view
```

## State ownership

- The recogniser owns the in-progress gesture lifecycle.
- The window tracker owns the live eligible-window view and MRU order.
- The window switcher controller owns a selection snapshot only for the duration of a switch gesture.
- The desktop manager owns the Show Desktop snapshot until restoration or explicit invalidation.
- Task View owns its presentation lifecycle and selected item while open.
- The GTK main thread owns all UI state.

## Failure boundaries

Malformed input must not terminate the application. A failed thumbnail must not prevent selection. A closed window must be revalidated before activation or restoration. A workspace operation must not leave an active window-switcher gesture eligible for later activation. If the overlay cannot be displayed, the desktop remains usable and the action fails safely.

## Current implementation note

The 0.2.0 core preview implements the primary gesture, controller, workspace, desktop-visibility and Task View boundaries. Some responsibilities may still be consolidated or refined after integration testing.
