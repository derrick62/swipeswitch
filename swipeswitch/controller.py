"""Coordinates recognised gestures with desktop services and GTK views."""
from __future__ import annotations

import logging

from .desktop.activator import activate_window
from .desktop.desktop import DesktopVisibilityManager
from .desktop.workspaces import WorkspaceManager
from .recognition.gestures import GestureAction, GestureRecognizer

log = logging.getLogger(__name__)


class SwipeSwitchController:
    """Wire gesture recogniser output to window switcher, task view and desktop.

    Action dispatch uses a plain dict of bound methods rather than an if/elif
    chain so that adding a new action requires only adding one entry to
    ``_build_handlers`` and one private method — no branching to extend.
    """

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

        self.switch_windows: list = []
        self.selected: int = 0

        self._handlers = self._build_handlers()

    # ----------------------------------------------------------------- public

    def update_config(self, config) -> None:
        self.config = config
        self.recognizer = GestureRecognizer(config.show_threshold_px, config.step_px)
        self.tracker.update_config(config)
        self.switcher.update_config(config)

    def activate_xid(self, xid: int) -> bool:
        """Resolve a Task View selection against live windows before activation."""
        self.screen.force_update()
        target = next(
            (w for w in (self.screen.get_windows() or []) if int(w.get_xid()) == int(xid)),
            None,
        )
        if target is None:
            log.info("Task View selection %s is no longer available", xid)
            return False
        return activate_window(target, self.Gdk, log)

    def handle_event(self, event) -> None:
        for action in self.recognizer.handle(event):
            self._dispatch(action)

    def check_timeout(self) -> None:
        for action in self.recognizer.check_timeout(self.config.gesture_timeout):
            self._dispatch(action)

    # ---------------------------------------------------------------- dispatch

    def _build_handlers(self) -> dict:
        return {
            "switch_begin":  self._on_switch_begin,
            "switch_move":   self._on_switch_move,
            "switch_commit": self._on_switch_commit,
            "switch_cancel": self._on_switch_cancel,
            "workspace":     self._on_workspace,
            "show_desktop":  self._on_show_desktop,
            "task_view":     self._on_task_view,
        }

    def _dispatch(self, action: GestureAction) -> None:
        # _handlers is set in __init__; tests that bypass __init__ via __new__
        # get it built on first dispatch instead.
        if not hasattr(self, "_handlers"):
            self._handlers = self._build_handlers()
        handler = self._handlers.get(action.name)
        if handler is None:
            log.warning("Unhandled gesture action: %r", action.name)
            return
        handler(action)

    # --------------------------------------------------------- action handlers

    def _on_switch_begin(self, action: GestureAction) -> None:
        self.switch_windows = self.tracker.get_switchable_windows()
        self.selected = 0
        if len(self.switch_windows) < 2:
            self.switch_windows = []
            return
        self.switcher.show(self.switch_windows, self.selected)

    def _on_switch_move(self, action: GestureAction) -> None:
        if not self.switch_windows:
            return
        delta = action.steps * (1 if action.direction == "right" else -1)
        self.selected = (self.selected + delta) % len(self.switch_windows)
        self.switcher.update_selection(self.selected)

    def _on_switch_commit(self, action: GestureAction) -> None:
        self.switcher.hide()
        if self.switch_windows:
            target_xid = int(self.switch_windows[self.selected].get_xid())
            self.screen.force_update()
            live = {int(w.get_xid()): w for w in (self.screen.get_windows() or [])}
            target = live.get(target_xid)
            if target is not None:
                activate_window(target, self.Gdk, log)
        self.switch_windows = []

    def _on_switch_cancel(self, action: GestureAction) -> None:
        self.switcher.hide()
        self.switch_windows = []

    def _on_workspace(self, action: GestureAction) -> None:
        self.task_view.hide()
        for _ in range(max(1, action.steps)):
            if not self.workspaces.navigate(action.direction):
                break
        self.switch_windows = []

    def _on_show_desktop(self, action: GestureAction) -> None:
        self.task_view.hide()
        self.desktop.show_desktop()

    def _on_task_view(self, action: GestureAction) -> None:
        if self.desktop.has_snapshot:
            self.desktop.restore()
        else:
            self.switcher.hide()
            windows = self.tracker.get_switchable_windows()
            if windows:
                self.task_view.show(windows)
