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

# Switcher overlay — fixed vertical proportions.
# Card width is derived at runtime from monitor width and window count.
_CARD_GAP      = 12          # px between cards
_PREVIEW_ASPECT = 16 / 9     # width / height ratio for preview area
_CARD_PADDING  = 20          # horizontal internal padding (left+right)
_CARD_EXTRA_H  = 69          # height above the preview: title + icon row + padding
_STRIP_PAD_X   = 24          # strip margin left and right inside the frame
_STRIP_PAD_Y   = 14          # strip margin top and bottom
_FRAME_PAD_X   = 48          # frame internal horizontal padding (left+right)

# Card width limits — cards never grow beyond _CARD_MAX_W (looks too wide)
# and never shrink below _CARD_MIN_W (becomes unreadable below this).
_CARD_MAX_W    = 362
_CARD_MIN_W    = 90


class LayoutEngine:
    """Compute monitor-aware card and frame metrics for SwitcherOverlay.

    Returns a ``SimpleNamespace`` with all sizing values so callers never
    guess at magic numbers.  The same namespace is passed to ``CardBuilder``
    so there is a single source of truth for card dimensions.

    Card width is solved from the available frame width and window count so
    that all cards always fit in one row without scrolling — Windows Alt+Tab
    style.  Cards shrink as more windows open, down to ``_CARD_MIN_W``.
    """

    @staticmethod
    def compute(geo, count: int) -> SimpleNamespace:
        """Return layout metrics for *count* cards on a monitor of size *geo*.

        *geo* may be ``None`` (before the first real show); returns safe
        fallback values in that case.
        """
        # ── monitor-aware frame width ──────────────────────────────────────
        if geo is not None:
            frame_w = min(1380, max(620, int(geo.width * 0.86)))
            frame_w = min(frame_w, max(480, geo.width - 40))
            frame_h_cap = max(330, geo.height - 40)
        else:
            frame_w = 1380
            frame_h_cap = 430

        # ── solve card width so all cards fit in one row ───────────────────
        # Available horizontal space inside the strip (inside the frame,
        # minus frame padding and strip margins).
        n = max(1, count)
        inner = frame_w - _FRAME_PAD_X - 2 * _STRIP_PAD_X

        # card_w * n + gap * (n-1) <= inner
        # card_w <= (inner - gap*(n-1)) / n
        card_w = max(
            _CARD_MIN_W,
            min(_CARD_MAX_W, (inner - _CARD_GAP * (n - 1)) // n),
        )

        # ── derive preview and card height from card width ─────────────────
        pv_w   = max(32, card_w - _CARD_PADDING)
        pv_h   = max(28, round(pv_w / _PREVIEW_ASPECT))
        card_h = pv_h + _CARD_EXTRA_H

        strip_h = card_h + 2 * _STRIP_PAD_Y

        return SimpleNamespace(
            pv_w=pv_w,
            pv_h=pv_h,
            card_w=card_w,
            card_h=card_h,
            strip_h=strip_h,
            frame_w=frame_w,
            frame_h=min(strip_h + 160, frame_h_cap),
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