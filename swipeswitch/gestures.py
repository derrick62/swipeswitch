"""Pure, desktop-independent recognition for SwipeSwitch gestures."""
from __future__ import annotations

from dataclasses import dataclass
import time

from .events import GestureEvent


@dataclass(frozen=True)
class GestureAction:
    name: str
    fingers: int
    direction: str | None = None
    steps: int = 0


class GestureRecognizer:
    """Classify one-finger-count swipe lifecycle into product-level actions.

    libinput reports deltas, not absolute positions. We therefore accumulate
    the full gesture and emit window-selection steps as thresholds are crossed.
    A gesture is classified once; it can never be routed to two features.
    """

    def __init__(self, threshold_px: float = 35, step_px: float = 80,
                 horizontal_dominance: float = 1.25):
        self.threshold_px = float(threshold_px)
        self.step_px = float(step_px)
        self.horizontal_dominance = float(horizontal_dominance)
        self.reset()

    def reset(self):
        self.fingers = 0
        self.dx = 0.0
        self.dy = 0.0
        self.axis = None
        self.direction = None
        self.last_step = 0
        self.cancelled = False
        self.started_at = None
        self.last_activity = None

    def handle(self, event: GestureEvent) -> list[GestureAction]:
        actions: list[GestureAction] = []
        if event.kind == "begin":
            if self.fingers == 3 and self.axis == "horizontal":
                actions.append(GestureAction("switch_cancel", 3, self.direction))
            self.reset()
            self.fingers = event.fingers
            self.started_at = time.monotonic()
            self.last_activity = self.started_at
            return actions

        if event.fingers != self.fingers or self.fingers not in (3, 4):
            if event.kind == "end":
                self.reset()
            return actions

        if event.kind == "update":
            self.last_activity = time.monotonic()
            self.dx += event.dx
            self.dy += event.dy
            if self.axis is None:
                if max(abs(self.dx), abs(self.dy)) < self.threshold_px:
                    return actions
                if abs(self.dx) >= abs(self.dy) * self.horizontal_dominance:
                    self.axis = "horizontal"
                    self.direction = "left" if self.dx < 0 else "right"
                    if self.fingers == 3:
                        actions.append(GestureAction("switch_begin", 3, self.direction))
                elif abs(self.dy) >= abs(self.dx) * self.horizontal_dominance:
                    self.axis = "vertical"
                    self.direction = "up" if self.dy < 0 else "down"
                else:
                    # A diagonal gesture remains undecided until it becomes
                    # sufficiently dominant or ends; ambiguous gestures do nothing.
                    return actions

            if self.axis == "horizontal" and self.fingers in (3, 4):
                # Both horizontal gestures consume distance incrementally.
                # Reversing direction therefore reverses the outstanding
                # movement naturally instead of waiting until finger-up.
                step = int(self.dx / self.step_px)
                delta = step - self.last_step
                if delta:
                    move_direction = "left" if delta < 0 else "right"
                    action_name = "switch_move" if self.fingers == 3 else "workspace"
                    actions.append(GestureAction(
                        action_name, self.fingers, move_direction, abs(delta)
                    ))
                    self.last_step = step
            return actions

        if event.kind == "end":
            if event.cancelled:
                if self.fingers == 3 and self.axis == "horizontal":
                    actions.append(GestureAction("switch_cancel", 3, self.direction))
            elif self.axis == "vertical" and self.fingers == 3:
                actions.append(GestureAction("task_view" if self.direction == "up"
                                             else "show_desktop", 3, self.direction))
            elif self.axis == "horizontal" and self.fingers == 3:
                actions.append(GestureAction("switch_commit", 3, self.direction))
            elif self.axis == "horizontal" and self.fingers == 4:
                # A short, deliberate four-finger flick should still move one
                # workspace even if it did not travel a full repeat interval.
                # Longer swipes have already emitted their crossed steps.
                if self.last_step == 0 and abs(self.dx) >= self.threshold_px:
                    final_direction = "left" if self.dx < 0 else "right"
                    actions.append(GestureAction("workspace", 4, final_direction, 1))
            self.reset()
        return actions

    def check_timeout(self, timeout_seconds: float) -> list[GestureAction]:
        """Cancel an unfinished gesture after inactivity; never commit it."""
        if self.fingers == 0 or self.last_activity is None:
            return []
        if time.monotonic() - self.last_activity <= timeout_seconds:
            return []
        actions = []
        if self.fingers == 3 and self.axis == "horizontal":
            actions.append(GestureAction("switch_cancel", 3, self.direction))
        self.reset()
        return actions
