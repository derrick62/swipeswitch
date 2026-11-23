"""XFCE/X11 virtual-workspace navigation through libwnck."""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)


class WorkspaceManager:
    def __init__(self, screen, timestamp=0, wrap=False):
        self.screen = screen
        self.timestamp = timestamp
        self.wrap = wrap

    def navigate(self, direction: str) -> bool:
        if direction not in {"left", "right"}:
            log.warning("Ignoring invalid workspace direction: %r", direction)
            return False
        self.screen.force_update()
        workspaces = list(self.screen.get_workspaces() or [])
        current = self.screen.get_active_workspace()
        if not workspaces or current not in workspaces:
            return False
        index = workspaces.index(current)
        # Product mapping: four-finger left = next; right = previous.
        target_index = index + (1 if direction == "left" else -1)
        if self.wrap:
            target_index %= len(workspaces)
        elif not 0 <= target_index < len(workspaces):
            return False
        target = workspaces[target_index]
        if target == current:
            return False
        try:
            target.activate(self.timestamp)
            return True
        except Exception:
            log.exception("Workspace activation failed")
            return False
