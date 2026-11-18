# SwipeSwitch Gesture Design

## Gesture mapping

| Fingers | Direction | Intent |
|---|---|---|
| 3 | Left | Next window |
| 3 | Right | Previous window |
| 3 | Up | Restore Show Desktop snapshot, or Task View if none exists |
| 3 | Down | Show Desktop |
| 4 | Left | Next workspace |
| 4 | Right | Previous workspace |

All other finger counts and gesture types are ignored in the initial release.

## Recognition principles

- Treat BEGIN, UPDATE and END as one gesture lifecycle.
- Accumulate deltas across all UPDATE events; do not classify from a single update.
- Use the finger count from the lifecycle and reject unsupported counts.
- Apply activation thresholds before dispatching an action.
- Resolve horizontal versus vertical intent from accumulated movement, with an ambiguity policy for diagonals.
- Dispatch each completed gesture at most once.
- A cancelled or timed-out gesture must not activate a window or trigger a desktop action.
- Do not let a workspace transition complete a stale window-switching operation.

## Window-switching lifecycle

A three-finger horizontal gesture obtains an eligible-window snapshot at BEGIN. Once the horizontal threshold is crossed, the overlay appears. Continued movement changes the selected index in MRU order. The selected item is activated on a non-cancelled END. Selection wraps. The implementation must revalidate the selected XID before activation because a window may close during the gesture.

## Vertical gesture context

Three-finger down captures the set of currently visible eligible windows and hides them. If a snapshot already exists, another down gesture must not replace it. Three-finger up restores only surviving captured windows and clears the snapshot. If no valid snapshot exists, three-finger up opens Task View.

## Workspace lifecycle

Four-finger horizontal gestures navigate one workspace per completed gesture. The initial policy is non-wrapping. Repeated UPDATE events contribute to direction/threshold recognition but must not cause repeated workspace changes.

## Calibration

Thresholds in the example configuration are provisional. Tune them on the actual touchpad after the recogniser is implemented. Prefer unaccelerated movement only if testing demonstrates more predictable behaviour.
