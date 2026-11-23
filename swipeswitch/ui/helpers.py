"""Shared utilities used by both SwitcherOverlay and TaskView.

``WindowPropertyHelpers`` centralises safe access to Wnck window attributes.
``LayoutEngine`` handles monitor-aware geometry and compact-mode scaling.
Both are pure (no GTK widget creation), making them easy to unit-test.
"""
from __future__ import annotations

import logging
from types import SimpleNamespace

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Window property helpers
# ---------------------------------------------------------------------------

class WindowPropertyHelpers:
    """Safe accessors for Wnck window properties.

    Every method catches exceptions and returns a sensible default so callers
    never have to wrap individual attribute lookups in try/except.
    """

    @staticmethod
    def safe(call, default=None):
        """Call *call()* and return *default* on any exception."""
        try:
            return call()
        except Exception:
            return default

    @classmethod
    def window_title(cls, window) -> str:
        return cls.safe(window.get_name) or "Untitled window"

    @classmethod
    def is_minimized(cls, window) -> bool:
        return bool(cls.safe(window.is_minimized, False))

    @classmethod
    def needs_attention(cls, window) -> bool:
        return bool(cls.safe(window.needs_attention, False))

    @classmethod
    def app_name(cls, window) -> str | None:
        for getter in (
            lambda: window.get_application().get_name(),
            lambda: window.get_class_group().get_name(),
        ):
            name = cls.safe(getter)
            if name:
                return name
        return None

    @classmethod
    def workspace_name(cls, window) -> str | None:
        count = cls.safe(lambda: window.get_screen().get_workspace_count(), 1)
        if not count or count < 2:
            return None
        if cls.safe(window.is_pinned, False):
            return "All workspaces"
        return cls.safe(lambda: window.get_workspace().get_name())

    @staticmethod
    def window_key(window) -> int:
        try:
            return int(window.get_xid())
        except Exception:
            return id(window)


# ---------------------------------------------------------------------------
# Layout engine
# ---------------------------------------------------------------------------

# Switcher overlay card constants (design baseline at 1920 px wide).
_CARD_WIDTH   = 362
_CARD_GAP     = 16
_PREVIEW_W    = 308
_PREVIEW_H    = 173
_CARD_EXTRA_W = 54
_CARD_EXTRA_H = 69
_STRIP_PAD_X  = 18
_STRIP_PAD_Y  = 14
_COMPACT_MIN_COUNT = 4
_COMPACT_SCALE     = 0.75


class LayoutEngine:
    """Compute monitor-aware card and frame metrics for SwitcherOverlay.

    Returns a ``SimpleNamespace`` with all sizing values so callers never
    guess at magic numbers.  The same namespace is passed to ``CardBuilder``
    so there is a single source of truth for card dimensions.
    """

    @staticmethod
    def compute(geo, count: int) -> SimpleNamespace:
        """Return layout metrics for *count* cards on a monitor of size *geo*.

        *geo* may be ``None`` (before the first real show); returns safe
        fallback values in that case.
        """
        scale = 1.0
        compact = False
        frame_w = 1380
        frame_h_cap = 430

        if geo is not None:
            scale = max(0.8, min(1.25, geo.width / 1920.0))
            frame_w = min(1380, max(620, int(geo.width * 0.86)))
            frame_w = min(frame_w, max(480, geo.width - 40))
            frame_h_cap = max(330, geo.height - 40)

            inner = frame_w - 48 - 2 * _STRIP_PAD_X
            card_w = round(_PREVIEW_W * scale) + _CARD_EXTRA_W
            visible = max(1, (inner + _CARD_GAP) // (card_w + _CARD_GAP))
            if count > max(visible, _COMPACT_MIN_COUNT):
                scale *= _COMPACT_SCALE
                compact = True

        pv_w   = round(_PREVIEW_W * scale)
        pv_h   = round(_PREVIEW_H * scale)
        card_w = pv_w + _CARD_EXTRA_W
        card_h = pv_h + _CARD_EXTRA_H
        scroll_h = card_h + 2 * _STRIP_PAD_Y
        edge_w = round(56 * scale)

        return SimpleNamespace(
            scale=scale,
            compact=compact,
            pv_w=pv_w,
            pv_h=pv_h,
            card_w=card_w,
            card_h=card_h,
            scroll_h=scroll_h,
            edge_w=edge_w,
            frame_w=frame_w,
            frame_h=min(scroll_h + 160, frame_h_cap),
            strip_pad_x=_STRIP_PAD_X,
            strip_pad_y=_STRIP_PAD_Y,
            card_gap=_CARD_GAP,
        )

    @staticmethod
    def pick_monitor(Gdk, config):
        """Return the GDK monitor the pointer is on (or the primary monitor)."""
        display = Gdk.Display.get_default()
        if getattr(config, "follow_pointer_monitor", True):
            try:
                pointer = display.get_default_seat().get_pointer()
                _screen, px, py = pointer.get_position()
                monitor = display.get_monitor_at_point(px, py)
                if monitor is not None:
                    return monitor
            except Exception:
                log.debug("Could not find the monitor under the pointer", exc_info=True)
        return display.get_primary_monitor() or display.get_monitor(0)
