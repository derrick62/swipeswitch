"""Wnck-backed window filtering and application-maintained MRU ordering."""
import logging

log = logging.getLogger(__name__)


class WindowTracker:
    def __init__(self, screen, config):
        import gi
        gi.require_version("Wnck", "3.0")
        from gi.repository import Wnck

        self._wnck = Wnck
        self.screen, self.config = screen, config
        self._mru = []
        self._seed()
        screen.connect("active-window-changed", self._on_active_changed)
        screen.connect("window-opened", self._on_window_opened)
        screen.connect("window-closed", self._on_window_closed)

    def update_config(self, config):
        self.config = config

    def _eligible_type(self, window):
        return window.get_window_type() in (
            self._wnck.WindowType.NORMAL, self._wnck.WindowType.DIALOG
        )

    @staticmethod
    def _xid(window):
        return int(window.get_xid())

    def _move_front(self, window):
        xid = self._xid(window)
        self._mru = [w for w in self._mru if self._xid(w) != xid]
        self._mru.insert(0, window)

    def _seed(self):
        try:
            for window in reversed(list(self.screen.get_windows_stacked() or [])):
                if self._eligible_type(window):
                    self._move_front(window)
        except Exception:
            log.exception("Could not seed initial MRU order")

    def _on_active_changed(self, screen, _previous_window):
        window = screen.get_active_window()
        if window is not None and self._eligible_type(window):
            self._move_front(window)

    def _on_window_opened(self, _screen, window):
        if self._eligible_type(window):
            self._move_front(window)

    def _on_window_closed(self, _screen, window):
        xid = self._xid(window)
        self._mru = [w for w in self._mru if self._xid(w) != xid]

    def _is_on_current_workspace(self, window):
        if not self.config.current_workspace_only:
            return True
        workspace = window.get_workspace()
        return workspace is None or workspace == self.screen.get_active_workspace()

    def get_switchable_windows(self):
        self.screen.force_update()
        live = {self._xid(w): w for w in (self.screen.get_windows() or [])}
        source = self._mru if self.config.order == "mru" else list(self.screen.get_windows_stacked() or [])
        result, seen = [], set()
        for window in source:
            xid = self._xid(window)
            current = live.get(xid)
            if current is None or xid in seen:
                continue
            name = (current.get_name() or "").lower()
            if (not self._eligible_type(current) or not self._is_on_current_workspace(current)
                    or current.is_skip_tasklist()
                    or name.startswith("swipeswitch")):
                continue
            result.append(current)
            seen.add(xid)
        for current in live.values():
            xid = self._xid(current)
            if xid in seen:
                continue
            name = (current.get_name() or "").lower()
            if (self._eligible_type(current) and self._is_on_current_workspace(current)
                    and not current.is_skip_tasklist() and not name.startswith("swipeswitch")):
                result.append(current)
                seen.add(xid)
        return result
