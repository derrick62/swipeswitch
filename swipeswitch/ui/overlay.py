"""Polished horizontal GTK3 window switcher for X11.

Design goals, in priority order:

* Open instantly: the desktop backdrop is blurred at reduced resolution and
  window thumbnails are captured lazily, one per idle tick, with the previous
  thumbnail shown immediately while a fresh one is being captured.
* Move predictably: all cards are always visible in one row — no scrolling,
  no panning — matching Windows Alt+Tab behaviour.  Cards shrink to fit as
  more windows open.  The selected card is outlined without changing its size.
* Fit the screen: the overlay opens on the monitor under the pointer and its
  cards scale with that monitor and the current window count.
* Stay optional: mouse interaction is exposed through callbacks, so the
  overlay keeps working exactly as before when none are connected.

GTK is imported once at module level via ``_gtk_imports()``; this module
should only be loaded after the caller has verified that GTK is available.
"""
from __future__ import annotations

import logging

from .animations import AnimationMixer
from .cards import CardBuilder
from .helpers import LayoutEngine, WindowPropertyHelpers
from .theme import ThemeManager
from ..thumbs import capture_thumbnail

log = logging.getLogger(__name__)

POINTER_GRACE_US  = 250_000
BACKDROP_DOWNSCALE = 4


def _gtk_imports():
    """Return (Gdk, GdkPixbuf, GLib, Gtk, Pango) — raises RuntimeError on failure."""
    try:
        import gi
        gi.require_version("Gtk", "3.0")
        gi.require_version("Gdk", "3.0")
        gi.require_version("Pango", "1.0")
        from gi.repository import Gdk, GdkPixbuf, GLib, Gtk, Pango
        return Gdk, GdkPixbuf, GLib, Gtk, Pango
    except (ImportError, ValueError) as exc:
        raise RuntimeError(f"GTK3 bindings unavailable: {exc}") from exc


_Gdk = _GdkPixbuf = _GLib = _Gtk = _Pango = None


def _ensure_gtk():
    global _Gdk, _GdkPixbuf, _GLib, _Gtk, _Pango
    if _Gtk is None:
        _Gdk, _GdkPixbuf, _GLib, _Gtk, _Pango = _gtk_imports()


class SwitcherOverlay:
    """Centered glass-style switcher with large cards and no scrolling.

    All cards are always visible in one row.  Card width shrinks to fit
    the available frame width as the window count grows — Windows Alt+Tab
    style.

    Optional callbacks (all default to ``None``) let the owner wire up mouse
    interaction.  Each receives the card index:

    * ``on_select(index)``   – the pointer moved onto a card or clicked it.
    * ``on_activate(index)`` – a card was left-clicked.
    * ``on_close(index)``    – a card was middle-clicked.
    """

    def __init__(self, config):
        _ensure_gtk()
        Gtk, Gdk, Pango = _Gtk, _Gdk, _Pango

        self.config = config
        self.on_select   = None
        self.on_activate = None
        self.on_close    = None

        self._helpers = WindowPropertyHelpers()

        # GTK window
        self.window = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
        self.window.set_name("swipeswitch-overlay")
        self.window.set_title("SwipeSwitch Window Switcher")
        self.window.set_decorated(False)
        self.window.set_keep_above(True)
        self.window.set_skip_taskbar_hint(True)
        self.window.set_skip_pager_hint(True)
        self.window.set_accept_focus(False)
        self.window.set_focus_on_map(False)
        self.window.set_type_hint(Gdk.WindowTypeHint.DOCK)
        self.window.set_app_paintable(True)
        self.window.connect("draw", self._draw_backdrop)

        # RGBA visual for transparency
        screen = Gdk.Screen.get_default()
        try:
            rgba = screen.get_rgba_visual()
            if rgba is not None:
                self.window.set_visual(rgba)
        except Exception:
            log.debug("RGBA visual unavailable; using default visual")

        self._theme = ThemeManager(config)
        self._theme.watch_system_changes()
        self._theme.apply()

        # Root layout
        self.root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.root.set_halign(Gtk.Align.CENTER)
        self.root.set_valign(Gtk.Align.CENTER)
        self.frame = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        self.frame.get_style_context().add_class("frame")
        self.root.pack_start(self.frame, True, True, 0)

        # Header
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=18)
        header.set_valign(Gtk.Align.CENTER)
        heading_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.heading = Gtk.Label(label="Choose a window")
        self.heading.set_halign(Gtk.Align.START)
        self.heading.set_ellipsize(Pango.EllipsizeMode.END)
        self.heading.set_max_width_chars(60)
        self.heading.get_style_context().add_class("heading")
        self.subheading = Gtk.Label(label="Swipe to move between windows")
        self.subheading.set_halign(Gtk.Align.START)
        self.subheading.set_ellipsize(Pango.EllipsizeMode.END)
        self.subheading.set_max_width_chars(72)
        self.subheading.get_style_context().add_class("subheading")
        heading_box.pack_start(self.heading,    False, False, 0)
        heading_box.pack_start(self.subheading, False, False, 0)
        header.pack_start(heading_box, True, True, 0)
        self.counter = Gtk.Label(label="1 / 1")
        self.counter.get_style_context().add_class("counter")
        header.pack_end(self.counter, False, False, 0)
        self.frame.pack_start(header, False, False, 0)

        # Card strip — plain Box, no ScrolledWindow, no edge fades.
        # All cards are always visible; the strip is sized exactly to its
        # content by _fit_to_monitor().
        self.strip = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=LayoutEngine.compute(None, 0).card_gap,
        )
        self.strip.set_halign(Gtk.Align.CENTER)
        self.frame.pack_start(self.strip, False, False, 0)

        # Footer
        self.footer = Gtk.Label(
            label="Three-finger swipe to browse  ·  Release to switch"
        )
        self.footer.set_halign(Gtk.Align.END)
        self.footer.get_style_context().add_class("footer")
        self.frame.pack_start(self.footer, False, False, 0)
        self.window.add(self.root)

        # State
        self.windows: list    = []
        self.selected: int    = 0
        self._card_objs: list = []
        self._card_cache: dict = {}
        self._metrics   = LayoutEngine.compute(None, 0)
        self._geo       = None
        self._backdrop  = None
        self._backdrop_sx = self._backdrop_sy = 1.0
        self._ignore_pointer_until = 0
        self._thumb_gen    = 0
        self._thumb_source = None

        # AnimationMixer: scroll=None because we have no ScrolledWindow.
        # Only fade is used; the mixer guards scroll calls against None.
        self._anim = AnimationMixer(
            self.window, None, _GLib, self._animations_enabled
        )

        self.window.hide()

    # ----------------------------------------------------------------- config

    def update_config(self, config) -> None:
        self.config = config
        self._theme.update_config(config)

    # ----------------------------------------------------------------- public

    def show(self, windows, selected_index: int = 0) -> None:
        self._anim.cancel_all()
        self._cancel_thumbnails()
        self.windows  = list(windows)
        self.selected = max(0, min(int(selected_index), max(0, len(self.windows) - 1)))
        self._geo     = LayoutEngine.pick_monitor(_Gdk, self.config).get_geometry()
        self._metrics = LayoutEngine.compute(self._geo, len(self.windows))
        self._backdrop = self._capture_blurred_backdrop(self._geo)
        self._rebuild()
        self._fit_to_monitor(self._geo)
        self._ignore_pointer_until = _GLib.get_monotonic_time() + POINTER_GRACE_US

        self.window.show_all()
        self.window.present()
        self.window.set_keep_above(True)
        self._schedule_thumbnails()
        self._anim.start_fade_in()

    def hide(self) -> None:
        self._anim.cancel_all()
        self._cancel_thumbnails()
        self.window.hide()
        self.window.set_opacity(1.0)
        self._backdrop = None

    def remove_window(self, index: int) -> None:
        if not 0 <= index < len(self.windows):
            return
        del self.windows[index]
        if not self.windows:
            self.selected = 0
        else:
            if index < self.selected:
                self.selected -= 1
            self.selected = max(0, min(self.selected, len(self.windows) - 1))
        self._metrics = LayoutEngine.compute(self._geo, len(self.windows))
        self._rebuild()
        if self._geo is not None:
            self._fit_to_monitor(self._geo)

    def update_selection(self, selected_index: int, **_kwargs) -> None:
        """Move the selection outline to another card.

        The ``recenter`` keyword accepted by the old scroll-based version is
        silently ignored — there is nothing to scroll.
        """
        if not self._card_objs:
            return
        selected_index %= len(self._card_objs)
        if selected_index == self.selected:
            return
        builder = self._make_builder()
        builder.apply_state(self._card_objs[self.selected], False)
        self.selected = selected_index
        builder.apply_state(self._card_objs[self.selected], True)
        self._refresh_header()

    # ----------------------------------------------------------------- layout

    def _fit_to_monitor(self, geo) -> None:
        try:
            m = self._metrics
            self.window.set_default_size(geo.width, geo.height)
            self.window.resize(geo.width, geo.height)
            self.window.move(geo.x, geo.y)
            self.frame.set_size_request(m.frame_w, m.frame_h)
            self.strip.set_margin_start(m.strip_pad_x)
            self.strip.set_margin_end(m.strip_pad_x)
            self.strip.set_margin_top(m.strip_pad_y)
            self.strip.set_margin_bottom(m.strip_pad_y)
            # Update strip spacing to match current metrics
            self.strip.set_spacing(m.card_gap)
        except Exception:
            self.window.set_position(_Gtk.WindowPosition.CENTER)

    # --------------------------------------------------------------- backdrop

    def _capture_blurred_backdrop(self, geo):
        try:
            from PIL import Image, ImageFilter
            root = _Gdk.get_default_root_window()
            if root is None:
                return None
            pixbuf = _Gdk.pixbuf_get_from_window(
                root, geo.x, geo.y, geo.width, geo.height
            )
            if pixbuf is None:
                return None
            channels = pixbuf.get_n_channels()
            mode = "RGBA" if channels == 4 else "RGB"
            image = Image.frombytes(
                mode, (geo.width, geo.height),
                pixbuf.get_pixels(), "raw", mode, pixbuf.get_rowstride(), 1,
            )
            factor = BACKDROP_DOWNSCALE
            small  = image.reduce(factor).filter(
                ImageFilter.GaussianBlur(radius=13.0 / factor)
            )
            sw, sh = small.size
            data   = _GLib.Bytes.new(small.tobytes())
            backdrop = _GdkPixbuf.Pixbuf.new_from_bytes(
                data, _GdkPixbuf.Colorspace.RGB, channels == 4, 8,
                sw, sh, sw * channels,
            )
            self._backdrop_sx = geo.width  / float(sw)
            self._backdrop_sy = geo.height / float(sh)
            return backdrop
        except Exception as exc:
            log.debug("Blurred backdrop unavailable: %s", exc)
            return None

    def _draw_backdrop(self, _widget, cr) -> bool:
        try:
            if self._backdrop is not None:
                cr.save()
                cr.scale(self._backdrop_sx, self._backdrop_sy)
                _Gdk.cairo_set_source_pixbuf(cr, self._backdrop, 0, 0)
                cr.paint_with_alpha(0.72)
                cr.restore()
            cr.set_source_rgba(0.025, 0.035, 0.055, 0.38)
            cr.paint()
        except Exception:
            log.debug("Could not draw backdrop", exc_info=True)
        return False

    # ------------------------------------------------------------------ cards

    def _make_builder(self) -> CardBuilder:
        return CardBuilder(_Gtk, _Gdk, _Pango, self._metrics, self._helpers)

    def _rebuild(self) -> None:
        previous = self._card_cache
        for child in self.strip.get_children():
            self.strip.remove(child)
        self._card_cache, self._card_objs = {}, []
        builder  = self._make_builder()
        size_key = (self._metrics.card_w, self._metrics.card_h)

        for index, window in enumerate(self.windows):
            key  = self._helpers.window_key(window)
            card = previous.pop(key, None)
            if card is not None and card.size_key != size_key:
                card.event_box.destroy()
                card = None
            if card is None:
                card = builder.build(
                    window, key,
                    on_press=self._on_card_press,
                    on_motion=self._on_card_motion,
                )
            card.window = window
            builder.refresh_content(card, self._thumbnails_enabled())
            builder.apply_state(card, index == self.selected)
            self.strip.pack_start(card.event_box, False, False, 0)
            self._card_cache[key] = card
            self._card_objs.append(card)

        for stale in previous.values():
            stale.event_box.destroy()

        self._refresh_header()
        self.strip.show_all()

    def _refresh_header(self) -> None:
        count = len(self.windows)
        h = self._helpers
        if not count:
            self.heading.set_text("No windows")
            self.subheading.set_text("There is nothing to switch to")
            self.counter.set_text("0 / 0")
            self.footer.set_text("Release to close")
            return
        window = self.windows[self.selected]
        self.heading.set_text(h.window_title(window)[:100])
        parts = [
            h.app_name(window),
            h.workspace_name(window),
            "Minimized"       if h.is_minimized(window)    else None,
            "Needs attention" if h.needs_attention(window)  else None,
        ]
        self.subheading.set_text(
            "  ·  ".join(p for p in parts if p) or "Switching to this window"
        )
        self.counter.set_text(f"{self.selected + 1} / {count}")
        action = "restore" if h.is_minimized(window) else "switch"
        hint   = f"Three-finger swipe to browse  ·  Release to {action}"
        if self.on_close is not None:
            hint += "  ·  Middle-click to close"
        self.footer.set_text(hint)

    # --------------------------------------------------------------- thumbnails

    def _schedule_thumbnails(self) -> None:
        self._cancel_thumbnails()
        if not self._thumbnails_enabled() or not self._card_objs:
            return
        generation = self._thumb_gen
        queue = sorted(
            range(len(self._card_objs)),
            key=lambda i: (abs(i - self.selected), i),
        )

        def step() -> bool:
            if generation != self._thumb_gen:
                return False
            if queue:
                idx = queue.pop(0)
                if idx < len(self._card_objs):
                    self._refresh_thumbnail(self._card_objs[idx])
            if queue:
                return True
            self._thumb_source = None
            return False

        self._thumb_source = _GLib.idle_add(
            step, priority=_GLib.PRIORITY_DEFAULT_IDLE
        )

    def _cancel_thumbnails(self) -> None:
        self._thumb_gen += 1
        if self._thumb_source is not None:
            _GLib.source_remove(self._thumb_source)
            self._thumb_source = None

    def _refresh_thumbnail(self, card) -> None:
        m = self._metrics
        max_w = max(32, m.pv_w - 8)
        max_h = max(32, m.pv_h - 4)
        try:
            pixbuf = capture_thumbnail(card.window, _Gdk, max_width=max_w, max_height=max_h)
        except Exception:
            log.debug("Thumbnail capture failed", exc_info=True)
            return
        if pixbuf is None:
            return
        card.thumb = self._fit_pixbuf(pixbuf, max_w, max_h)
        self._make_builder().install_preview(card)

    @staticmethod
    def _fit_pixbuf(pixbuf, max_w: int, max_h: int):
        w, h = pixbuf.get_width(), pixbuf.get_height()
        if w <= max_w and h <= max_h:
            return pixbuf
        ratio  = min(max_w / float(w), max_h / float(h))
        scaled = pixbuf.scale_simple(
            max(1, int(w * ratio)), max(1, int(h * ratio)),
            _GdkPixbuf.InterpType.BILINEAR,
        )
        return scaled or pixbuf

    # ------------------------------------------------------------------ mouse

    def _card_index(self, card) -> int:
        try:
            return self._card_objs.index(card)
        except ValueError:
            return -1

    def _on_card_motion(self, card, _event) -> bool:
        if self.on_select is None or not getattr(self.config, "hover_select", True):
            return False
        if _GLib.get_monotonic_time() < self._ignore_pointer_until:
            return False
        index = self._card_index(card)
        if index >= 0 and index != self.selected:
            self.update_selection(index)
            self.on_select(index)
        return False

    def _on_card_press(self, card, event) -> bool:
        index = self._card_index(card)
        if index < 0:
            return False
        if event.type != _Gdk.EventType.BUTTON_PRESS:
            return False
        if event.button == 1:
            if self.on_select is not None and index != self.selected:
                self.update_selection(index)
                self.on_select(index)
            if self.on_activate is not None:
                self.on_activate(index)
            return True
        if event.button == 2 and self.on_close is not None:
            self.on_close(index)
            return True
        return False

    # --------------------------------------------------------------- feature flags

    def _animations_enabled(self) -> bool:
        if not getattr(self.config, "animations", True):
            return False
        try:
            return bool(
                _Gtk.Settings.get_default().get_property("gtk-enable-animations")
            )
        except Exception:
            return True

    def _thumbnails_enabled(self) -> bool:
        return bool(getattr(self.config, "thumbnails", True))