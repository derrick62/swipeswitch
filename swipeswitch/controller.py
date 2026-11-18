"""Coordinates recognised gestures with desktop services and GTK views."""
from __future__ import annotations

import logging

from .desktop import DesktopVisibilityManager
from .gestures import GestureRecognizer
from .workspaces import WorkspaceManager
from .activator import activate_window

log = logging.getLogger(__name__)


class SwipeSwitchController:
    def __init__(self, screen, tracker, switcher, task_view, Gdk, config):
        self.screen = screen
        self.tracker = tracker
        self.switcher = switcher
        self.task_view = task_view
        self.Gdk = Gdk
        self.config = config
        self.recognizer = GestureRecognizer(config.show_threshold_px, config.step_px)
        self.desktop = DesktopVisibilityManager(screen, tracker)
        self.workspaces = WorkspaceManager(screen, wrap=False)
        self.switch_windows = []
        self.selected = 0

    def update_config(self, config):
        self.config = config
        self.recognizer = GestureRecognizer(config.show_threshold_px, config.step_px)
        self.tracker.update_config(config)
        self.switcher.update_config(config)

    def activate_xid(self, xid):
        """Resolve a Task View selection against live windows before activation."""
        self.screen.force_update()
        target = next(
            (window for window in (self.screen.get_windows() or [])
             if int(window.get_xid()) == int(xid)),
            None,
        )
        if target is None:
            log.info("Task View selection %s is no longer available", xid)
            return False
        return activate_window(target, self.Gdk, log)

    def handle_event(self, event):
        for action in self.recognizer.handle(event):
            self._dispatch(action)

    def check_timeout(self):
        for action in self.recognizer.check_timeout(self.config.gesture_timeout):
            self._dispatch(action)

    def _dispatch(self, action):
        if action.name == "switch_begin":
            self.switch_windows = self.tracker.get_switchable_windows()
            self.selected = 0
            if len(self.switch_windows) < 2:
                self.switch_windows = []
                return
            self.switcher.show(self.switch_windows, self.selected)
        elif action.name == "switch_move":
            if not self.switch_windows:
                return
            # Follow the physical swipe: right advances to the next item,
            # left moves to the previous item in the displayed MRU sequence.
            delta = action.steps * (1 if action.direction == "right" else -1)
            self.selected = (self.selected + delta) % len(self.switch_windows)
            self.switcher.update_selection(self.selected)
        elif action.name == "switch_commit":
            self.switcher.hide()
            if self.switch_windows:
                target_xid = int(self.switch_windows[self.selected].get_xid())
                self.screen.force_update()
                live = {int(w.get_xid()): w for w in (self.screen.get_windows() or [])}
                target = live.get(target_xid)
                if target is not None:
                    activate_window(target, self.Gdk, log)
            self.switch_windows = []
        elif action.name == "switch_cancel":
            self.switcher.hide()
            self.switch_windows = []
        elif action.name == "workspace":
            self.task_view.hide()
            # A four-finger swipe moves one workspace per crossed distance
            # threshold. Reversals are emitted as opposite-direction steps.
            for _ in range(max(1, action.steps)):
                if not self.workspaces.navigate(action.direction):
                    break
            self.switch_windows = []
        elif action.name == "show_desktop":
            self.task_view.hide()
            self.desktop.show_desktop()
        elif action.name == "task_view":
            if self.desktop.has_snapshot:
                self.desktop.restore()
            else:
                self.switcher.hide()
                windows = self.tracker.get_switchable_windows()
                if windows:
                    self.task_view.show(windows)
