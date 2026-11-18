"""Show Desktop snapshots that preserve the user's pre-existing window state."""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)


class DesktopVisibilityManager:
    def __init__(self, screen, tracker, timestamp=0):
        self.screen = screen
        self.tracker = tracker
        self.timestamp = timestamp
        self._snapshot: list[int] | None = None
        self._active_xid: int | None = None

    @property
    def has_snapshot(self) -> bool:
        return self._snapshot is not None

    def show_desktop(self) -> bool:
        # Repeated down gestures must not replace the original snapshot.
        if self._snapshot is not None:
            return False
        self.screen.force_update()
        windows = self.tracker.get_switchable_windows()
        visible = [w for w in windows if not w.is_minimized()]
        if not visible:
            return False
        self._active_xid = None
        active = self.screen.get_active_window()
        if active is not None:
            self._active_xid = int(active.get_xid())
        self._snapshot = [int(w.get_xid()) for w in visible]
        for window in visible:
            try:
                window.minimize()
            except Exception:
                log.exception("Could not minimize window %s", window.get_xid())
        return True

    def restore(self) -> bool:
        if self._snapshot is None:
            return False
        self.screen.force_update()
        live = {int(w.get_xid()): w for w in (self.screen.get_windows() or [])}
        restored = []
        for xid in self._snapshot:
            window = live.get(xid)
            if window is None:
                continue
            try:
                if window.is_minimized():
                    window.unminimize(self.timestamp)
                restored.append(window)
            except Exception:
                log.exception("Could not restore window %s", xid)
        # Reactivate only the previously active window if it was actually
        # visible and therefore part of the original restoration snapshot.
        active = live.get(self._active_xid) if self._active_xid in self._snapshot else None
        if active is not None:
            try:
                active.unminimize(self.timestamp)
                active.activate(self.timestamp)
            except Exception:
                log.exception("Could not reactivate previously active window")
        self._snapshot = None
        self._active_xid = None
        return bool(restored)
