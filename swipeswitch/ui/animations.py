"""Fade-in and smooth-scroll animation helpers for GTK3 tick callbacks.

Each animation is self-contained: it registers a tick callback when started
and removes it when finished or cancelled.  The caller keeps the returned
``AnimationMixer`` instance and calls its cancel methods on hide/destroy.
"""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)

FADE_MS = 130
SCROLL_MS = 170


def _ease_out_cubic(t: float) -> float:
    return 1.0 - (1.0 - t) ** 3


class AnimationMixer:
    """Manages fade and scroll tick-callback animations for one GTK window.

    Parameters
    ----------
    window:
        The GTK3 ``Window`` whose opacity the fade animation controls.
    scroll:
        The ``ScrolledWindow`` whose horizontal adjustment the scroll
        animation drives.
    GLib:
        ``gi.repository.GLib`` — passed in so this module stays import-free.
    animations_enabled_fn:
        Zero-argument callable that returns ``True`` when animations should
        run; typically checks the config flag and
        ``gtk-enable-animations`` setting.
    """

    def __init__(self, window, scroll, GLib, animations_enabled_fn):
        self._window = window
        self._scroll = scroll
        self._GLib = GLib
        self._animations_enabled = animations_enabled_fn

        self._fade_tick = None
        self._fade_t0 = None
        self._fade_guard = None

        self._scroll_tick = None
        self._scroll_t0: float | None = None
        self._scroll_from = 0.0
        self._scroll_to = 0.0

    # ------------------------------------------------------------------ fade

    def start_fade_in(self) -> None:
        """Fade the window from opacity 0 to 1 over ``FADE_MS`` ms."""
        if not self._animations_enabled():
            self._window.set_opacity(1.0)
            return
        if self._window.get_frame_clock() is None:
            self._window.set_opacity(1.0)
            return
        self._window.set_opacity(0.0)
        self._fade_t0 = None
        self._fade_tick = self._window.add_tick_callback(self._fade_step)
        self._fade_guard = self._GLib.timeout_add(
            FADE_MS * 4, self._fade_guard_expired
        )

    def cancel_fade(self) -> None:
        if self._fade_tick is not None:
            self._window.remove_tick_callback(self._fade_tick)
            self._fade_tick = None
        if self._fade_guard is not None:
            self._GLib.source_remove(self._fade_guard)
            self._fade_guard = None

    def _fade_step(self, widget, clock) -> bool:
        now = clock.get_frame_time()
        if self._fade_t0 is None:
            self._fade_t0 = now
        progress = min(1.0, (now - self._fade_t0) / (FADE_MS * 1000.0))
        widget.set_opacity(_ease_out_cubic(progress))
        if progress >= 1.0:
            self._fade_tick = None
            return False
        return True

    def _fade_guard_expired(self) -> bool:
        self._fade_guard = None
        self.cancel_fade()
        self._window.set_opacity(1.0)
        return False

    # --------------------------------------------------------------- scroll

    def scroll_to(self, target: float, instant: bool = False) -> None:
        """Animate the horizontal scroll position to *target*.

        Passes through immediately when *instant* is True, the delta is tiny,
        animations are disabled, or no frame clock is available.
        """
        adjustment = self._scroll.get_hadjustment()
        if adjustment is None:
            return
        current = adjustment.get_value()
        if (
            instant
            or abs(target - current) < 1.0
            or not self._animations_enabled()
            or self._scroll.get_frame_clock() is None
        ):
            self._cancel_scroll()
            adjustment.set_value(target)
            return

        self._scroll_from = current
        self._scroll_to = target
        self._scroll_t0 = None
        if self._scroll_tick is None:
            self._scroll_tick = self._scroll.add_tick_callback(self._scroll_step)

    def cancel_scroll(self) -> None:
        self._cancel_scroll()

    def _cancel_scroll(self) -> None:
        if self._scroll_tick is not None:
            self._scroll.remove_tick_callback(self._scroll_tick)
            self._scroll_tick = None

    def _scroll_step(self, widget, clock) -> bool:
        now = clock.get_frame_time()
        if self._scroll_t0 is None:
            self._scroll_t0 = now
        progress = min(1.0, (now - self._scroll_t0) / (SCROLL_MS * 1000.0))
        eased = _ease_out_cubic(progress)
        adj = widget.get_hadjustment()
        adj.set_value(self._scroll_from + (self._scroll_to - self._scroll_from) * eased)
        if progress >= 1.0:
            self._scroll_tick = None
            return False
        return True

    # ----------------------------------------------------------------- combined

    def cancel_all(self) -> None:
        """Cancel every running animation; call before hide() or rebuild."""
        self.cancel_fade()
        self._cancel_scroll()
