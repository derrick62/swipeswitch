"""Polished horizontal GTK3 window switcher for X11.

Design goals, in priority order:

* Open instantly: the desktop backdrop is blurred at reduced resolution and
  window thumbnails are captured lazily, one per idle tick, with the previous
  thumbnail shown immediately while a fresh one is being captured.
* Move predictably: the strip scrolls with a short eased animation, the
  selected card is outlined without ever changing the card's size, and edge
  fades hint at windows that are off screen.
* Fit the screen: the overlay opens on the monitor under the pointer and its
  cards scale with that monitor, switching to a compact density when many
  windows are open.
* Stay optional: mouse interaction is exposed through callbacks, so the
  overlay keeps working exactly as before when none are connected.
"""
from __future__ import annotations

import logging
from types import SimpleNamespace

import gi

gi.require_version("Pango", "1.0")
from gi.repository import GdkPixbuf, GLib, Pango

from .thumbs import capture_thumbnail

log = logging.getLogger(__name__)

# Every card carries the same 3px border at all times (muted when idle).
# Selecting a card only changes colours, so the strip never shifts or reflows
# while the user browses. Card sizes are set from code (they scale with the
# monitor), so the CSS deliberately does not fix a min-width or min-height.
DARK_CSS = """
window#swipeswitch-overlay { background-color: rgba(5, 8, 14, 0.48); }
.frame {
  background-color: rgba(24, 30, 42, 0.94);
  border: 1px solid rgba(255,255,255,0.16);
  border-radius: 24px;
  padding: 24px;
}
.heading { color: #f7f9fd; font-size: 21px; font-weight: 700; }
.subheading { color: #bcc6d6; font-size: 12px; }
.counter {
  color: #f4f7ff; background-color: rgba(255,255,255,0.10);
  border: 1px solid rgba(255,255,255,0.15); border-radius: 13px;
  padding: 7px 12px; font-size: 12px; font-weight: 700;
}
.card {
  background-color: rgba(255,255,255,0.055);
  border: 3px solid rgba(255,255,255,0.10);
  border-radius: 18px; padding: 11px;
  transition: border-color 140ms ease-in-out,
              background-color 140ms ease-in-out,
              box-shadow 140ms ease-in-out;
}
.card.attention { border-color: rgba(255,184,76,0.85); }
.card.minimized .preview-area { opacity: 0.55; }
.card.minimized .title { opacity: 0.7; }
.card.selected {
  background-color: rgba(75,132,224,0.16);
  border-color: #8fc0ff;
  box-shadow: 0 0 14px rgba(96,160,255,0.38);
}
.preview-area { background-color: rgba(8,12,19,0.86); border-radius: 10px; }
.title { color: #d4dbe8; font-size: 13px; font-weight: 600; }
.card.selected .title { color: #ffffff; font-weight: 700; }
.app-icon { opacity: 1; }
.footer { color: #b4bfd0; font-size: 11px; }
.scrollbar { min-height: 6px; }
.edge-left {
  background-image: linear-gradient(to right,
      rgba(24,30,42,0.94), rgba(24,30,42,0));
}
.edge-right {
  background-image: linear-gradient(to left,
      rgba(24,30,42,0.94), rgba(24,30,42,0));
}
"""

LIGHT_CSS = """
window#swipeswitch-overlay { background-color: rgba(18, 25, 36, 0.38); }
.frame {
  background-color: rgba(247,249,253,0.96);
  border: 1px solid rgba(35,48,68,0.18);
  border-radius: 24px; padding: 24px;
}
.heading { color: #172235; font-size: 21px; font-weight: 700; }
.subheading { color: #5a677c; font-size: 12px; }
.counter {
  color: #1c2b42; background-color: rgba(35,65,105,0.08);
  border: 1px solid rgba(35,65,105,0.16); border-radius: 13px;
  padding: 7px 12px; font-size: 12px; font-weight: 700;
}
.card {
  background-color: rgba(255,255,255,0.94);
  border: 3px solid #e1e7f0;
  border-radius: 18px; padding: 11px;
  transition: border-color 140ms ease-in-out,
              background-color 140ms ease-in-out,
              box-shadow 140ms ease-in-out;
}
.card.attention { border-color: rgba(222,140,20,0.85); }
.card.minimized .preview-area { opacity: 0.55; }
.card.minimized .title { opacity: 0.7; }
.card.selected {
  background-color: #eef4ff;
  border-color: #246fce;
  box-shadow: 0 0 14px rgba(52,127,229,0.30);
}
.preview-area { background-color: #e7edf5; border-radius: 10px; }
.title { color: #3a4960; font-size: 13px; font-weight: 600; }
.card.selected .title { color: #172235; font-weight: 700; }
.app-icon { opacity: 1; }
.footer { color: #5a677c; font-size: 11px; }
.scrollbar { min-height: 6px; }
.edge-left {
  background-image: linear-gradient(to right,
      rgba(247,249,253,0.96), rgba(247,249,253,0));
}
.edge-right {
  background-image: linear-gradient(to left,
      rgba(247,249,253,0.96), rgba(247,249,253,0));
}
"""


def _ease_out_cubic(t: float) -> float:
    return 1.0 - (1.0 - t) ** 3


class _Card:
    """The widgets and cached state belonging to one window card.

    Cards are kept between invocations (keyed by window id) so that reopening
    the switcher reuses widgets and shows the last thumbnail immediately.
    """

    def __init__(self, key, window, size_key):
        self.key = key
        self.window = window
        self.size_key = size_key
        self.event_box = None
        self.box = None
        self.preview_area = None
        self.preview_kind = None  # "thumb", "icon" or "fallback"
        self.thumb = None
        self.app_image = None
        self.title = None


class SwitcherOverlay:
    """Centered glass-style switcher with large cards and horizontal browsing.

    Optional callbacks (all default to ``None``) let the owner wire up mouse
    interaction. Each receives the card index:

    * ``on_select(index)``   - the pointer moved onto a card or clicked it.
      Hover and click selection are only active when this is set, so the
      owner's own notion of the selected window never goes out of sync.
    * ``on_activate(index)`` - a card was left-clicked.
    * ``on_close(index)``    - a card was middle-clicked. After closing the
      window, the owner can call ``remove_window(index)`` to drop its card.
    """

    CARD_WIDTH = 362  # includes card padding and borders
    CARD_GAP = 16
    PREVIEW_W = 308
    PREVIEW_H = 173
    CARD_EXTRA_W = 54   # card width minus preview width (padding, borders)
    CARD_EXTRA_H = 69   # card height minus preview height (meta row, padding)
    STRIP_PAD_X = 18    # room for the selection glow at the strip's ends
    STRIP_PAD_Y = 14    # room for the selection glow above and below cards
    COMPACT_MIN_COUNT = 4
    COMPACT_SCALE = 0.75
    BACKDROP_DOWNSCALE = 4
    FADE_MS = 130
    SCROLL_MS = 170
    POINTER_GRACE_US = 250_000

    def __init__(self, Gtk, Gdk, config):
        self.Gtk, self.Gdk, self.config = Gtk, Gdk, config
        self.on_select = None
        self.on_activate = None
        self.on_close = None

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

        self.css = Gtk.CssProvider()
        self.screen = Gdk.Screen.get_default()
        try:
            rgba = self.screen.get_rgba_visual()
            if rgba is not None:
                self.window.set_visual(rgba)
        except Exception:
            log.debug("RGBA visual is unavailable; using the default visual")
        self._apply_css()
        self._watch_system_theme()

        self.root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.root.set_halign(Gtk.Align.CENTER)
        self.root.set_valign(Gtk.Align.CENTER)
        self.frame = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        self.frame.get_style_context().add_class("frame")
        self.root.pack_start(self.frame, True, True, 0)

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
        heading_box.pack_start(self.heading, False, False, 0)
        heading_box.pack_start(self.subheading, False, False, 0)
        header.pack_start(heading_box, True, True, 0)
        self.counter = Gtk.Label(label="1 / 1")
        self.counter.get_style_context().add_class("counter")
        header.pack_end(self.counter, False, False, 0)
        self.frame.pack_start(header, False, False, 0)

        self.strip = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=self.CARD_GAP)
        self.strip.set_halign(Gtk.Align.START)
        self.strip.set_margin_start(self.STRIP_PAD_X)
        self.strip.set_margin_end(self.STRIP_PAD_X)
        self.strip.set_margin_top(self.STRIP_PAD_Y)
        self.strip.set_margin_bottom(self.STRIP_PAD_Y)
        self.scroll = Gtk.ScrolledWindow()
        self.scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        self.scroll.set_shadow_type(Gtk.ShadowType.NONE)
        self.scroll.add(self.strip)

        # Edge fades sit above the scroller and hint at off-screen windows.
        self.edge_left = Gtk.Box()
        self.edge_left.get_style_context().add_class("edge-left")
        self.edge_left.set_halign(Gtk.Align.START)
        self.edge_left.set_valign(Gtk.Align.FILL)
        self.edge_right = Gtk.Box()
        self.edge_right.get_style_context().add_class("edge-right")
        self.edge_right.set_halign(Gtk.Align.END)
        self.edge_right.set_valign(Gtk.Align.FILL)
        self.scroll_overlay = Gtk.Overlay()
        self.scroll_overlay.add(self.scroll)
        for edge in (self.edge_left, self.edge_right):
            self.scroll_overlay.add_overlay(edge)
            try:
                self.scroll_overlay.set_overlay_pass_through(edge, True)
            except Exception:
                log.debug("Overlay pass-through unavailable", exc_info=True)
            edge.set_opacity(0.0)
        self.frame.pack_start(self.scroll_overlay, False, False, 0)

        adjustment = self.scroll.get_hadjustment()
        if adjustment is not None:
            adjustment.connect("value-changed", lambda *_: self._update_edges())
            adjustment.connect("changed", lambda *_: self._update_edges())

        self.footer = Gtk.Label(label="Three-finger swipe to browse  ·  Release to switch")
        self.footer.set_halign(Gtk.Align.END)
        self.footer.get_style_context().add_class("footer")
        self.frame.pack_start(self.footer, False, False, 0)
        self.window.add(self.root)

        self.cards, self.windows, self.selected = [], [], 0
        self._card_objs = []
        self._card_cache = {}
        self._metrics = self._compute_metrics(None, 0)
        self._geo = None
        self._backdrop = None
        self._backdrop_sx = self._backdrop_sy = 1.0
        self._ignore_pointer_until = 0

        self._fade_tick = None
        self._fade_t0 = None
        self._fade_guard = None
        self._scroll_tick = None
        self._scroll_t0 = None
        self._scroll_from = 0.0
        self._scroll_to = 0.0
        self._thumb_gen = 0
        self._thumb_source = None

        self.window.hide()

    # ------------------------------------------------------------------ theme

    def _resolve_theme(self):
        """Return "light" or "dark", following the system in "auto" mode."""
        theme = getattr(self.config, "theme", "dark")
        if theme in ("auto", "system"):
            try:
                settings = self.Gtk.Settings.get_default()
                if settings.get_property("gtk-application-prefer-dark-theme"):
                    return "dark"
                name = (settings.get_property("gtk-theme-name") or "").lower()
                return "dark" if "dark" in name else "light"
            except Exception:
                return "dark"
        return "light" if theme == "light" else "dark"

    def _watch_system_theme(self):
        try:
            settings = self.Gtk.Settings.get_default()
            for prop in ("gtk-theme-name", "gtk-application-prefer-dark-theme"):
                settings.connect(f"notify::{prop}", lambda *_: self._apply_css())
        except Exception:
            log.debug("Could not watch the system theme", exc_info=True)

    def _apply_css(self):
        css = LIGHT_CSS if self._resolve_theme() == "light" else DARK_CSS
        try:
            self.css.load_from_data(css.encode())
            self.Gtk.StyleContext.add_provider_for_screen(
                self.screen, self.css, self.Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )
        except Exception:
            log.exception("Could not apply overlay CSS")

    def update_config(self, config):
        self.config = config
        self._apply_css()

    # ----------------------------------------------------------------- helpers

    @staticmethod
    def _safe(call, default=None):
        """Call a window accessor, tolerating windows that lack or fail it."""
        try:
            return call()
        except Exception:
            return default

    @staticmethod
    def _window_key(window):
        try:
            return int(window.get_xid())
        except Exception:
            return id(window)

    @staticmethod
    def _fit_pixbuf(pixbuf, max_w, max_h):
        """Shrink a pixbuf to fit a box, preserving its aspect ratio."""
        width, height = pixbuf.get_width(), pixbuf.get_height()
        if width <= max_w and height <= max_h:
            return pixbuf
        ratio = min(max_w / float(width), max_h / float(height))
        scaled = pixbuf.scale_simple(
            max(1, int(width * ratio)), max(1, int(height * ratio)),
            GdkPixbuf.InterpType.BILINEAR,
        )
        return scaled or pixbuf

    def _animations_enabled(self):
        if not getattr(self.config, "animations", True):
            return False
        try:
            settings = self.Gtk.Settings.get_default()
            return bool(settings.get_property("gtk-enable-animations"))
        except Exception:
            return True

    def _thumbnails_enabled(self):
        return bool(getattr(self.config, "thumbnails", True))

    def _window_title(self, window):
        return self._safe(window.get_name) or "Untitled window"

    def _is_minimized(self, window):
        return bool(self._safe(window.is_minimized, False))

    def _needs_attention(self, window):
        return bool(self._safe(window.needs_attention, False))

    def _app_name(self, window):
        getters = (
            lambda: window.get_application().get_name(),
            lambda: window.get_class_group().get_name(),
        )
        for getter in getters:
            name = self._safe(getter)
            if name:
                return name
        return None

    def _workspace_name(self, window):
        """Workspace label, only when there is more than one workspace."""
        count = self._safe(lambda: window.get_screen().get_workspace_count(), 1)
        if not count or count < 2:
            return None
        if self._safe(window.is_pinned, False):
            return "All workspaces"
        return self._safe(lambda: window.get_workspace().get_name())

    # ------------------------------------------------------------------ layout

    def _pick_monitor(self):
        display = self.Gdk.Display.get_default()
        if getattr(self.config, "follow_pointer_monitor", True):
            try:
                pointer = display.get_default_seat().get_pointer()
                _screen, px, py = pointer.get_position()
                monitor = display.get_monitor_at_point(px, py)
                if monitor is not None:
                    return monitor
            except Exception:
                log.debug("Could not find the monitor under the pointer", exc_info=True)
        return display.get_primary_monitor() or display.get_monitor(0)

    def _compute_metrics(self, geo, count):
        """Derive every size from the monitor and the number of windows."""
        scale, compact = 1.0, False
        frame_w, frame_h_cap = 1380, 430
        if geo is not None:
            scale = max(0.8, min(1.25, geo.width / 1920.0))
            frame_w = min(1380, max(620, int(geo.width * 0.86)))
            frame_w = min(frame_w, max(480, geo.width - 40))
            frame_h_cap = max(330, geo.height - 40)
            inner = frame_w - 48 - 2 * self.STRIP_PAD_X
            card_w = round(self.PREVIEW_W * scale) + self.CARD_EXTRA_W
            visible = max(1, (inner + self.CARD_GAP) // (card_w + self.CARD_GAP))
            if count > max(visible, self.COMPACT_MIN_COUNT):
                scale *= self.COMPACT_SCALE
                compact = True
        pv_w = round(self.PREVIEW_W * scale)
        pv_h = round(self.PREVIEW_H * scale)
        card_w = pv_w + self.CARD_EXTRA_W
        card_h = pv_h + self.CARD_EXTRA_H
        scroll_h = card_h + 2 * self.STRIP_PAD_Y
        return SimpleNamespace(
            scale=scale, compact=compact, pv_w=pv_w, pv_h=pv_h,
            card_w=card_w, card_h=card_h, scroll_h=scroll_h,
            frame_w=frame_w, frame_h=min(scroll_h + 160, frame_h_cap),
            edge_w=round(56 * scale),
        )

    def _fit_to_monitor(self, geo):
        try:
            metrics = self._metrics
            self.window.set_default_size(geo.width, geo.height)
            self.window.resize(geo.width, geo.height)
            self.window.move(geo.x, geo.y)
            self.scroll.set_min_content_height(metrics.scroll_h)
            self.scroll.set_max_content_height(metrics.scroll_h)
            self.edge_left.set_size_request(metrics.edge_w, -1)
            self.edge_right.set_size_request(metrics.edge_w, -1)
            self.frame.set_size_request(metrics.frame_w, metrics.frame_h)
        except Exception:
            self.window.set_position(self.Gtk.WindowPosition.CENTER)

    # ---------------------------------------------------------------- backdrop

    def _capture_blurred_backdrop(self, geo):
        """Capture and blur the composed X11 desktop before showing the overlay.

        The blur runs on a reduced-resolution copy, which is both much faster
        and visually near-identical, then is stretched back up at draw time.
        Pillow is installed by the Debian/Kali installer. If screen capture or
        Pillow is unavailable, the translucent dim layer remains the fallback.
        """
        try:
            from PIL import Image, ImageFilter

            root = self.Gdk.get_default_root_window()
            if root is None:
                return None
            x, y = geo.x, geo.y
            width, height = geo.width, geo.height
            pixbuf = self.Gdk.pixbuf_get_from_window(root, x, y, width, height)
            if pixbuf is None:
                return None
            channels = pixbuf.get_n_channels()
            mode = "RGBA" if channels == 4 else "RGB"
            raw = pixbuf.get_pixels()
            image = Image.frombytes(
                mode, (width, height), raw, "raw", mode,
                pixbuf.get_rowstride(), 1,
            )
            factor = self.BACKDROP_DOWNSCALE
            small = image.reduce(factor)
            small = small.filter(ImageFilter.GaussianBlur(radius=13.0 / factor))
            small_w, small_h = small.size
            data = GLib.Bytes.new(small.tobytes())
            backdrop = GdkPixbuf.Pixbuf.new_from_bytes(
                data, GdkPixbuf.Colorspace.RGB, channels == 4, 8,
                small_w, small_h, small_w * channels,
            )
            self._backdrop_sx = width / float(small_w)
            self._backdrop_sy = height / float(small_h)
            return backdrop
        except Exception as exc:
            log.debug("Blurred desktop backdrop unavailable: %s", exc)
            return None

    def _draw_backdrop(self, _widget, cr):
        try:
            if self._backdrop is not None:
                cr.save()
                cr.scale(self._backdrop_sx, self._backdrop_sy)
                self.Gdk.cairo_set_source_pixbuf(cr, self._backdrop, 0, 0)
                cr.paint_with_alpha(0.72)
                cr.restore()
            cr.set_source_rgba(0.025, 0.035, 0.055, 0.38)
            cr.paint()
        except Exception:
            log.debug("Could not draw desktop backdrop", exc_info=True)
        return False

    # -------------------------------------------------------------- show/hide

    def show(self, windows, selected_index=0):
        self._cancel_animations()
        self.windows = list(windows)
        self.selected = max(0, min(int(selected_index), max(0, len(self.windows) - 1)))
        geo = self._geo = self._pick_monitor().get_geometry()
        self._metrics = self._compute_metrics(geo, len(self.windows))
        self._backdrop = self._capture_blurred_backdrop(geo)
        self._rebuild()
        self._fit_to_monitor(geo)
        self._ignore_pointer_until = GLib.get_monotonic_time() + self.POINTER_GRACE_US

        animate = self._animations_enabled()
        if animate:
            self.window.set_opacity(0.0)
        self.window.show_all()
        self.window.present()
        self.window.set_keep_above(True)
        self._scroll_selected_into_view(instant=True)
        self._update_edges()
        GLib.idle_add(self._post_show_layout)
        self._schedule_thumbnails()
        if animate:
            self._start_fade_in()
        else:
            self.window.set_opacity(1.0)

    def _post_show_layout(self):
        """Re-centre once GTK has allocated the cards (not known earlier)."""
        self._scroll_selected_into_view(instant=True)
        self._update_edges()
        return False

    def hide(self):
        self._cancel_animations()
        self.window.hide()
        self.window.set_opacity(1.0)
        self._backdrop = None

    def remove_window(self, index):
        """Drop one card, e.g. after the owner closed that window."""
        if not 0 <= index < len(self.windows):
            return
        del self.windows[index]
        if not self.windows:
            self.selected = 0
        else:
            if index < self.selected:
                self.selected -= 1
            self.selected = max(0, min(self.selected, len(self.windows) - 1))
        self._metrics = self._compute_metrics(self._geo, len(self.windows))
        self._rebuild()
        if self._geo is not None:
            self._fit_to_monitor(self._geo)
        self._scroll_selected_into_view()
        self._schedule_thumbnails()

    # ------------------------------------------------------------------- cards

    def _make_card(self, window, key):
        Gtk, metrics = self.Gtk, self._metrics
        cobj = _Card(key, window, (metrics.card_w, metrics.card_h))

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=11)
        box.set_size_request(metrics.card_w, metrics.card_h)
        box.get_style_context().add_class("card")

        preview_area = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        preview_area.set_size_request(metrics.pv_w, metrics.pv_h)
        preview_area.set_halign(Gtk.Align.CENTER)
        preview_area.set_valign(Gtk.Align.CENTER)
        preview_area.get_style_context().add_class("preview-area")
        box.pack_start(preview_area, False, False, 0)

        meta = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        meta.set_valign(Gtk.Align.CENTER)
        app_image = Gtk.Image()
        app_image.set_pixel_size(28)
        app_image.get_style_context().add_class("app-icon")
        meta.pack_start(app_image, False, False, 0)
        title = Gtk.Label()
        title.set_ellipsize(Pango.EllipsizeMode.END)
        title.set_max_width_chars(36)
        title.set_halign(Gtk.Align.START)
        title.set_valign(Gtk.Align.CENTER)
        title.set_hexpand(True)
        title.get_style_context().add_class("title")
        meta.pack_start(title, True, True, 0)
        box.pack_start(meta, False, False, 0)

        # The event box has no window of its own; it only receives the pointer.
        event_box = Gtk.EventBox()
        event_box.set_visible_window(False)
        event_box.add(box)
        event_box.add_events(
            self.Gdk.EventMask.BUTTON_PRESS_MASK | self.Gdk.EventMask.POINTER_MOTION_MASK
        )
        event_box.connect("button-press-event", lambda _w, ev, c=cobj: self._on_card_press(c, ev))
        event_box.connect("motion-notify-event", lambda _w, ev, c=cobj: self._on_card_motion(c, ev))

        cobj.event_box, cobj.box = event_box, box
        cobj.preview_area, cobj.app_image, cobj.title = preview_area, app_image, title
        return cobj

    def _update_card_content(self, cobj):
        """Refresh title, icon and preview of a (possibly reused) card."""
        window = cobj.window
        name = self._window_title(window)
        cobj.title.set_text(name[:120])
        cobj.box.set_tooltip_text(name)
        icon = self._safe(window.get_mini_icon) or self._safe(window.get_icon)
        if icon is not None:
            cobj.app_image.set_from_pixbuf(icon)
            cobj.app_image.set_no_show_all(False)
            cobj.app_image.show()
        else:
            cobj.app_image.set_no_show_all(True)
            cobj.app_image.hide()
        if not self._thumbnails_enabled():
            cobj.thumb = None
        if cobj.preview_kind != "thumb" or cobj.thumb is None:
            self._install_preview(cobj)

    def _install_preview(self, cobj):
        """Put the thumbnail, or else an icon or glyph, into the preview area."""
        Gtk = self.Gtk
        for child in cobj.preview_area.get_children():
            cobj.preview_area.remove(child)
        if cobj.thumb is not None:
            widget, kind = Gtk.Image.new_from_pixbuf(cobj.thumb), "thumb"
        else:
            icon = self._safe(cobj.window.get_icon)
            if icon is not None:
                widget, kind = Gtk.Image.new_from_pixbuf(icon), "icon"
                widget.set_pixel_size(54)
            else:
                widget, kind = Gtk.Label(label="▣"), "fallback"
        widget.set_halign(Gtk.Align.CENTER)
        widget.set_valign(Gtk.Align.CENTER)
        cobj.preview_area.pack_start(widget, True, True, 0)
        widget.show()
        cobj.preview_kind = kind

    def _apply_card_state(self, cobj, selected):
        context = cobj.box.get_style_context()
        window = cobj.window
        for name, active in (
            ("selected", selected),
            ("minimized", self._is_minimized(window)),
            ("attention", self._needs_attention(window)),
        ):
            if active:
                context.add_class(name)
            else:
                context.remove_class(name)

    def _rebuild(self):
        """Lay the strip out again, reusing cached cards wherever possible."""
        previous = self._card_cache
        for child in self.strip.get_children():
            self.strip.remove(child)  # cached cards keep their own references
        self._card_cache, self._card_objs, self.cards = {}, [], []
        size_key = (self._metrics.card_w, self._metrics.card_h)

        for index, window in enumerate(self.windows):
            key = self._window_key(window)
            cobj = previous.pop(key, None)
            if cobj is not None and cobj.size_key != size_key:
                cobj.event_box.destroy()
                cobj = None
            if cobj is None:
                cobj = self._make_card(window, key)
            cobj.window = window
            self._update_card_content(cobj)
            self._apply_card_state(cobj, index == self.selected)
            self.strip.pack_start(cobj.event_box, False, False, 0)
            self._card_cache[key] = cobj
            self._card_objs.append(cobj)
            self.cards.append(cobj.box)
        for stale in previous.values():
            stale.event_box.destroy()

        self._refresh_header()
        self.strip.show_all()

    def _refresh_header(self):
        count = len(self.windows)
        if not count:
            self.heading.set_text("No windows")
            self.subheading.set_text("There is nothing to switch to")
            self.counter.set_text("0 / 0")
            self.footer.set_text("Release to close")
            return
        window = self.windows[self.selected]
        self.heading.set_text(self._window_title(window)[:100])
        parts = [
            self._app_name(window),
            self._workspace_name(window),
            "Minimized" if self._is_minimized(window) else None,
            "Needs attention" if self._needs_attention(window) else None,
        ]
        self.subheading.set_text("  ·  ".join(p for p in parts if p) or "Switching to this window")
        self.counter.set_text(f"{self.selected + 1} / {count}")
        action = "restore" if self._is_minimized(window) else "switch"
        hint = f"Three-finger swipe to browse  ·  Release to {action}"
        if self.on_close is not None:
            hint += "  ·  Middle-click to close"
        self.footer.set_text(hint)

    # --------------------------------------------------------------- thumbnails

    def _schedule_thumbnails(self):
        """Capture thumbnails lazily, nearest the selection first."""
        self._cancel_thumbnails()
        if not self._thumbnails_enabled() or not self._card_objs:
            return
        generation = self._thumb_gen
        queue = sorted(range(len(self._card_objs)), key=lambda i: (abs(i - self.selected), i))

        def step():
            if generation != self._thumb_gen:
                return False
            if queue:
                index = queue.pop(0)
                if index < len(self._card_objs):
                    self._refresh_thumbnail(self._card_objs[index])
            if queue:
                return True
            self._thumb_source = None
            return False

        self._thumb_source = GLib.idle_add(step, priority=GLib.PRIORITY_DEFAULT_IDLE)

    def _cancel_thumbnails(self):
        self._thumb_gen += 1
        if self._thumb_source is not None:
            GLib.source_remove(self._thumb_source)
            self._thumb_source = None

    def _refresh_thumbnail(self, cobj):
        metrics = self._metrics
        max_w, max_h = max(32, metrics.pv_w - 8), max(32, metrics.pv_h - 4)
        try:
            pixbuf = capture_thumbnail(cobj.window, self.Gdk, max_width=max_w, max_height=max_h)
        except Exception:
            log.debug("Thumbnail capture failed", exc_info=True)
            return
        if pixbuf is None:
            return  # keep the previous thumbnail, or the icon
        cobj.thumb = self._fit_pixbuf(pixbuf, max_w, max_h)
        self._install_preview(cobj)

    # ------------------------------------------------------------------ mouse

    def _card_index(self, cobj):
        try:
            return self._card_objs.index(cobj)
        except ValueError:
            return -1

    def _on_card_motion(self, cobj, _event):
        if self.on_select is None or not getattr(self.config, "hover_select", True):
            return False
        if GLib.get_monotonic_time() < self._ignore_pointer_until:
            return False  # a pointer resting under the overlay is not a choice
        index = self._card_index(cobj)
        if index >= 0 and index != self.selected:
            self.update_selection(index, recenter=False)
            self.on_select(index)
        return False

    def _on_card_press(self, cobj, event):
        index = self._card_index(cobj)
        if index < 0:
            return False
        if event.type != self.Gdk.EventType.BUTTON_PRESS:
            return False
        if event.button == 1:
            if self.on_select is not None and index != self.selected:
                self.update_selection(index, recenter=False)
                self.on_select(index)
            if self.on_activate is not None:
                self.on_activate(index)
            return True
        if event.button == 2 and self.on_close is not None:
            self.on_close(index)
            return True
        return False

    # ---------------------------------------------------------------- scrolling

    def _centered_target(self):
        adjustment = self.scroll.get_hadjustment()
        allocation = self._card_objs[self.selected].event_box.get_allocation()
        page = adjustment.get_page_size()
        target = allocation.x + allocation.width / 2.0 - page / 2.0
        maximum = max(adjustment.get_lower(), adjustment.get_upper() - page)
        return max(adjustment.get_lower(), min(target, maximum))

    def _visible_target(self):
        """Smallest scroll that brings the selected card fully into view."""
        adjustment = self.scroll.get_hadjustment()
        allocation = self._card_objs[self.selected].event_box.get_allocation()
        value, page = adjustment.get_value(), adjustment.get_page_size()
        pad = self.STRIP_PAD_X
        if allocation.x - pad < value:
            target = allocation.x - pad
        elif allocation.x + allocation.width + pad > value + page:
            target = allocation.x + allocation.width + pad - page
        else:
            return None
        maximum = max(adjustment.get_lower(), adjustment.get_upper() - page)
        return max(adjustment.get_lower(), min(target, maximum))

    def _scroll_selected_into_view(self, instant=False, centered=True):
        if not self._card_objs or not self.scroll.get_hadjustment():
            return
        try:
            target = self._centered_target() if centered else self._visible_target()
            if target is not None:
                self._scroll_to_value(target, instant)
        except Exception:
            log.debug("Could not scroll selected window into view", exc_info=True)

    def _scroll_to_value(self, target, instant=False):
        adjustment = self.scroll.get_hadjustment()
        current = adjustment.get_value()
        if (
            instant or abs(target - current) < 1.0
            or not self._animations_enabled()
            or self.scroll.get_frame_clock() is None
        ):
            self._cancel_scroll_animation()
            adjustment.set_value(target)
            return
        self._scroll_from, self._scroll_to, self._scroll_t0 = current, target, None
        if self._scroll_tick is None:
            self._scroll_tick = self.scroll.add_tick_callback(self._scroll_step)

    def _scroll_step(self, widget, clock):
        now = clock.get_frame_time()
        if self._scroll_t0 is None:
            self._scroll_t0 = now
        progress = min(1.0, (now - self._scroll_t0) / (self.SCROLL_MS * 1000.0))
        eased = _ease_out_cubic(progress)
        adjustment = widget.get_hadjustment()
        adjustment.set_value(self._scroll_from + (self._scroll_to - self._scroll_from) * eased)
        if progress >= 1.0:
            self._scroll_tick = None
            return False
        return True

    def _cancel_scroll_animation(self):
        if self._scroll_tick is not None:
            self.scroll.remove_tick_callback(self._scroll_tick)
            self._scroll_tick = None

    def _update_edges(self):
        adjustment = self.scroll.get_hadjustment()
        if adjustment is None:
            return
        value, lower = adjustment.get_value(), adjustment.get_lower()
        upper, page = adjustment.get_upper(), adjustment.get_page_size()
        self.edge_left.set_opacity(1.0 if value > lower + 2 else 0.0)
        self.edge_right.set_opacity(1.0 if value < upper - page - 2 else 0.0)

    # ------------------------------------------------------------------ fading

    def _start_fade_in(self):
        if self.window.get_frame_clock() is None:
            self.window.set_opacity(1.0)
            return
        self._fade_t0 = None
        self._fade_tick = self.window.add_tick_callback(self._fade_step)
        # Never leave the overlay invisible if the frame clock stalls.
        self._fade_guard = GLib.timeout_add(self.FADE_MS * 4, self._fade_guard_expired)

    def _fade_step(self, widget, clock):
        now = clock.get_frame_time()
        if self._fade_t0 is None:
            self._fade_t0 = now
        progress = min(1.0, (now - self._fade_t0) / (self.FADE_MS * 1000.0))
        widget.set_opacity(_ease_out_cubic(progress))
        if progress >= 1.0:
            self._fade_tick = None
            return False
        return True

    def _fade_guard_expired(self):
        self._fade_guard = None
        self._cancel_fade()
        self.window.set_opacity(1.0)
        return False

    def _cancel_fade(self):
        if self._fade_tick is not None:
            self.window.remove_tick_callback(self._fade_tick)
            self._fade_tick = None

    def _cancel_animations(self):
        self._cancel_fade()
        if self._fade_guard is not None:
            GLib.source_remove(self._fade_guard)
            self._fade_guard = None
        self._cancel_scroll_animation()
        self._cancel_thumbnails()

    # --------------------------------------------------------------- selection

    def update_selection(self, selected_index, *, recenter=True):
        """Move the selection outline to another card.

        ``recenter=False`` only scrolls as far as needed to keep the card in
        view, which is what pointer-driven selection wants.
        """
        if not self.cards:
            return
        selected_index %= len(self.cards)
        if selected_index == self.selected:
            return
        self._apply_card_state(self._card_objs[self.selected], False)
        self.selected = selected_index
        self._apply_card_state(self._card_objs[self.selected], True)
        self._refresh_header()
        self._scroll_selected_into_view(centered=recenter)