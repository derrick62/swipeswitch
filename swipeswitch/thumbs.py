"""Best-effort X11 window previews using GDK's foreign-window support.

Previews are local snapshots taken when an overview is opened. A window that is
unmapped, minimized, protected, or otherwise unavailable falls back to its app
icon; thumbnail failure never blocks switching.
"""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def capture_thumbnail(window, Gdk, max_width=420, max_height=236):
    """Return an aspect-preserving GdkPixbuf snapshot for a Wnck window.

    GdkX11 is optional at runtime. The feature degrades cleanly to the window
    icon on systems where the typelib or the foreign-window capture is absent.
    """
    try:
        import gi
        gi.require_version("GdkX11", "3.0")
        from gi.repository import GdkX11, GdkPixbuf

        display = Gdk.Display.get_default()
        if window.is_minimized():
            return None
        xid = int(window.get_xid())
        foreign = GdkX11.X11Window.foreign_new_for_display(display, xid)
        if foreign is None:
            return None

        width, height = int(foreign.get_width()), int(foreign.get_height())
        if width < 48 or height < 36:
            return None

        pixbuf = Gdk.pixbuf_get_from_window(foreign, 0, 0, width, height)
        if pixbuf is None:
            return None

        scale = min(max_width / width, max_height / height)
        target_width = max(1, int(width * scale))
        target_height = max(1, int(height * scale))
        if target_width == width and target_height == height:
            return pixbuf
        return pixbuf.scale_simple(
            target_width, target_height, GdkPixbuf.InterpType.BILINEAR
        )
    except Exception as exc:
        log.debug("Preview unavailable for window %s: %s", _safe_xid(window), exc)
        return None


def _safe_xid(window):
    try:
        return int(window.get_xid())
    except Exception:
        return "unknown"
