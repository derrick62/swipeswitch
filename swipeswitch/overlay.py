"""Polished horizontal GTK3 window switcher for X11."""
from __future__ import annotations

import logging

import gi

gi.require_version("Pango", "1.0")
from gi.repository import Pango

from .thumbs import capture_thumbnail

log = logging.getLogger(__name__)

DARK_CSS = """
window#swipeswitch-overlay { background-color: rgba(5, 8, 14, 0.48); }
.frame {
  background-color: rgba(24, 30, 42, 0.94);
  border: 1px solid rgba(255,255,255,0.16);
  border-radius: 24px;
  padding: 24px;
}
.heading { color: #f7f9fd; font-size: 21px; font-weight: 700; }
.subheading { color: #b7c1d1; font-size: 12px; }
.counter {
  color: #f4f7ff; background-color: rgba(255,255,255,0.10);
  border: 1px solid rgba(255,255,255,0.15); border-radius: 13px;
  padding: 7px 12px; font-size: 12px; font-weight: 700;
}
.card {
  background-color: rgba(255,255,255,0.055);
  border: 1px solid rgba(255,255,255,0.13);
  border-radius: 17px; padding: 13px; min-width: 334px; min-height: 224px;
}
.card.selected {
  background-color: rgba(75,132,224,0.22);
  border: 2px solid #83b5ff;
}
.preview-area { background-color: rgba(8,12,19,0.86); border-radius: 10px; }
.title { color: #f4f7fc; font-size: 13px; font-weight: 650; }
.app-icon { opacity: 1; }
.footer { color: #aeb9ca; font-size: 11px; }
.scrollbar { min-height: 6px; }
"""

LIGHT_CSS = """
window#swipeswitch-overlay { background-color: rgba(18, 25, 36, 0.38); }
.frame {
  background-color: rgba(247,249,253,0.96);
  border: 1px solid rgba(35,48,68,0.18);
  border-radius: 24px; padding: 24px;
}
.heading { color: #172235; font-size: 21px; font-weight: 700; }
.subheading { color: #647187; font-size: 12px; }
.counter {
  color: #1c2b42; background-color: rgba(35,65,105,0.08);
  border: 1px solid rgba(35,65,105,0.16); border-radius: 13px;
  padding: 7px 12px; font-size: 12px; font-weight: 700;
}
.card { background-color: rgba(255,255,255,0.94); border: 1px solid #d9e1ed;
  border-radius: 17px; padding: 13px; min-width: 334px; min-height: 224px; }
.card.selected { background-color: #e8f1ff; border: 2px solid #347fe5; }
.preview-area { background-color: #e7edf5; border-radius: 10px; }
.title { color: #172235; font-size: 13px; font-weight: 650; }
.app-icon { opacity: 1; }
.footer { color: #647187; font-size: 11px; }
.scrollbar { min-height: 6px; }
"""


class SwitcherOverlay:
    """Centered glass-style switcher with large cards and horizontal browsing."""

    CARD_WIDTH = 362  # includes card padding and borders
    CARD_GAP = 16

    def __init__(self, Gtk, Gdk, config):
        self.Gtk, self.Gdk, self.config = Gtk, Gdk, config
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
        self.heading.get_style_context().add_class("heading")
        self.subheading = Gtk.Label(label="Swipe to move between windows")
        self.subheading.set_halign(Gtk.Align.START)
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
        self.scroll = Gtk.ScrolledWindow()
        self.scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        self.scroll.set_shadow_type(Gtk.ShadowType.NONE)
        self.scroll.set_min_content_height(270)
        self.scroll.set_max_content_height(270)
        self.scroll.add(self.strip)
        self.frame.pack_start(self.scroll, False, False, 0)

        self.footer = Gtk.Label(label="Three-finger swipe to browse  ·  Release to switch")
        self.footer.set_halign(Gtk.Align.END)
        self.footer.get_style_context().add_class("footer")
        self.frame.pack_start(self.footer, False, False, 0)
        self.window.add(self.root)

        self.cards, self.windows, self.selected = [], [], 0
        self._backdrop = None
        self.window.hide()

    def _apply_css(self):
        css = LIGHT_CSS if self.config.theme == "light" else DARK_CSS
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

    def _capture_blurred_backdrop(self):
        """Capture and blur the composed X11 desktop before showing the overlay.

        Pillow is installed by the Debian/Kali installer. If screen capture or
        Pillow is unavailable, the translucent dim layer remains the fallback.
        """
        try:
            import gi
            from gi.repository import GdkPixbuf, GLib
            from PIL import Image, ImageFilter

            root = self.Gdk.get_default_root_window()
            if root is None:
                return None
            display = self.Gdk.Display.get_default()
            monitor = display.get_primary_monitor() or display.get_monitor(0)
            geometry = monitor.get_geometry()
            x, y = geometry.x, geometry.y
            width, height = geometry.width, geometry.height
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
            image = image.filter(ImageFilter.GaussianBlur(radius=13))
            pixels = image.tobytes()
            data = GLib.Bytes.new(pixels)
            return GdkPixbuf.Pixbuf.new_from_bytes(
                data, GdkPixbuf.Colorspace.RGB, channels == 4, 8,
                width, height, width * channels,
            )
        except Exception as exc:
            log.debug("Blurred desktop backdrop unavailable: %s", exc)
            return None

    def _draw_backdrop(self, _widget, cr):
        try:
            if self._backdrop is not None:
                self.Gdk.cairo_set_source_pixbuf(cr, self._backdrop, 0, 0)
                cr.paint_with_alpha(0.72)
            cr.set_source_rgba(0.025, 0.035, 0.055, 0.38)
            cr.paint()
        except Exception:
            log.debug("Could not draw desktop backdrop", exc_info=True)
        return False

    def show(self, windows, selected_index=0):
        self.windows = list(windows)
        self.selected = max(0, min(int(selected_index), max(0, len(self.windows) - 1)))
        self._backdrop = self._capture_blurred_backdrop()
        self._rebuild()
        self._fit_to_primary()
        self.window.show_all()
        self.window.present()
        self.window.set_keep_above(True)
        self._scroll_selected_into_view()

    def _fit_to_primary(self):
        try:
            display = self.Gdk.Display.get_default()
            monitor = display.get_primary_monitor() or display.get_monitor(0)
            geo = monitor.get_geometry()
            self.window.set_default_size(geo.width, geo.height)
            self.window.move(geo.x, geo.y)
            # Keep a comfortable margin while avoiding the previous oversized
            # near-full-screen panel. Card browsing is horizontal, not squeezed.
            frame_width = min(1380, max(620, int(geo.width * 0.86)))
            frame_height = 430
            frame_width = min(frame_width, max(480, geo.width - 40))
            frame_height = min(frame_height, max(330, geo.height - 40))
            self.frame.set_size_request(frame_width, frame_height)
        except Exception:
            self.window.set_position(self.Gtk.WindowPosition.CENTER)

    def _make_card(self, window, index):
        card = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=11)
        card.set_size_request(self.CARD_WIDTH, 242)
        card.get_style_context().add_class("card")
        if index == self.selected:
            card.get_style_context().add_class("selected")

        preview_area = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=0)
        preview_area.set_size_request(308, 173)
        preview_area.set_halign(self.Gtk.Align.CENTER)
        preview_area.set_valign(self.Gtk.Align.CENTER)
        preview_area.get_style_context().add_class("preview-area")
        preview = (
            capture_thumbnail(window, self.Gdk, max_width=300, max_height=169)
            if getattr(self.config, "thumbnails", True) else None
        )
        if preview is not None:
            image = self.Gtk.Image.new_from_pixbuf(preview)
            image.set_halign(self.Gtk.Align.CENTER)
            image.set_valign(self.Gtk.Align.CENTER)
            preview_area.pack_start(image, True, True, 0)
        else:
            icon = window.get_icon()
            if icon is not None:
                image = self.Gtk.Image.new_from_pixbuf(icon)
                image.set_pixel_size(54)
                image.set_halign(self.Gtk.Align.CENTER)
                image.set_valign(self.Gtk.Align.CENTER)
                preview_area.pack_start(image, True, True, 0)
            else:
                fallback = self.Gtk.Label(label="▣")
                fallback.set_halign(self.Gtk.Align.CENTER)
                fallback.set_valign(self.Gtk.Align.CENTER)
                preview_area.pack_start(fallback, True, True, 0)
        card.pack_start(preview_area, False, False, 0)

        meta = self.Gtk.Box(orientation=self.Gtk.Orientation.HORIZONTAL, spacing=10)
        meta.set_valign(self.Gtk.Align.CENTER)
        app_icon = window.get_mini_icon() or window.get_icon()
        if app_icon is not None:
            app_image = self.Gtk.Image.new_from_pixbuf(app_icon)
            app_image.set_pixel_size(28)
            app_image.get_style_context().add_class("app-icon")
            meta.pack_start(app_image, False, False, 0)
        title = self.Gtk.Label(label=(window.get_name() or "Untitled window")[:120])
        title.set_ellipsize(Pango.EllipsizeMode.END)
        title.set_max_width_chars(36)
        title.set_halign(self.Gtk.Align.START)
        title.set_valign(self.Gtk.Align.CENTER)
        title.set_hexpand(True)
        title.get_style_context().add_class("title")
        meta.pack_start(title, True, True, 0)
        card.pack_start(meta, False, False, 0)
        card.set_tooltip_text(window.get_name() or "Untitled window")
        return card

    def _rebuild(self):
        for child in self.strip.get_children():
            self.strip.remove(child)
        self.cards = []
        for index, window in enumerate(self.windows):
            card = self._make_card(window, index)
            self.strip.pack_start(card, False, False, 0)
            self.cards.append(card)
        count = len(self.windows)
        self.subheading.set_text(
            f"{count} open windows  ·  Swipe horizontally to browse"
        )
        self.counter.set_text(f"{self.selected + 1} / {count}" if count else "0 / 0")
        self.strip.show_all()

    def _scroll_selected_into_view(self):
        if not self.cards or not self.scroll.get_hadjustment():
            return
        try:
            allocation = self.cards[self.selected].get_allocation()
            adjustment = self.scroll.get_hadjustment()
            page = adjustment.get_page_size()
            target = allocation.x + allocation.width / 2.0 - page / 2.0
            maximum = max(adjustment.get_lower(), adjustment.get_upper() - page)
            adjustment.set_value(max(adjustment.get_lower(), min(target, maximum)))
        except Exception:
            log.debug("Could not scroll selected window into view", exc_info=True)

    def update_selection(self, selected_index):
        if not self.cards:
            return
        selected_index %= len(self.cards)
        if selected_index == self.selected:
            return
        self.cards[self.selected].get_style_context().remove_class("selected")
        self.selected = selected_index
        self.cards[self.selected].get_style_context().add_class("selected")
        self.counter.set_text(f"{self.selected + 1} / {len(self.windows)}")
        self._scroll_selected_into_view()

    def hide(self):
        self.window.hide()
        self._backdrop = None
