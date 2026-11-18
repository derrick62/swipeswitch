"""Polished, horizontally browsable GTK3 window-switcher overlay."""
import logging

import gi

gi.require_version("Pango", "1.0")
from gi.repository import Pango

log = logging.getLogger(__name__)

DARK_CSS = """
window#swipeswitch-overlay { background-color: rgba(8, 12, 20, 0.78); }
.frame {
    background-color: rgba(25, 31, 43, 0.98);
    border: 1px solid rgba(255,255,255,0.13);
    border-radius: 20px;
    padding: 18px;
}
.header-title { color: #f4f6fb; font-size: 15px; font-weight: 700; }
.header-subtitle { color: #9da9bb; font-size: 10px; }
.counter {
    color: #dce8fa; background-color: rgba(255,255,255,0.09);
    border-radius: 10px; padding: 5px 10px; font-size: 11px; font-weight: 700;
}
.hint { color: #8f9bad; font-size: 10px; }
.card {
    background-color: rgba(255,255,255,0.045);
    border: 1px solid rgba(255,255,255,0.09);
    border-radius: 14px;
    padding: 10px;
    min-width: 174px;
}
.card.selected {
    background-color: rgba(64, 124, 224, 0.19);
    border: 2px solid #75aaff;
    padding: 9px;
}
.preview {
    background-color: rgba(7, 11, 19, 0.48);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 9px;
    min-height: 92px;
}
.preview.selected { background-color: rgba(61, 112, 190, 0.20); }
.preview-icon { color: #dce8fa; }
.card-title { color: #e8edf5; font-size: 11px; font-weight: 600; }
.card-index { color: #8795aa; font-size: 9px; }
.card.selected .card-title { color: #ffffff; }
.card.selected .card-index { color: #a9caff; }
scrolledwindow { background: transparent; border: 0; }
viewport { background: transparent; }
scrollbar.horizontal { min-height: 7px; }
scrollbar trough { background-color: rgba(255,255,255,0.07); border-radius: 5px; }
scrollbar slider { background-color: rgba(160,180,210,0.48); border-radius: 5px; min-width: 28px; }
"""

LIGHT_CSS = """
window#swipeswitch-overlay { background-color: rgba(25, 33, 46, 0.42); }
.frame {
    background-color: rgba(249, 251, 254, 0.99);
    border: 1px solid rgba(35, 51, 75, 0.15);
    border-radius: 20px;
    padding: 18px;
}
.header-title { color: #182437; font-size: 15px; font-weight: 700; }
.header-subtitle { color: #718096; font-size: 10px; }
.counter {
    color: #29466e; background-color: #e8eff9;
    border-radius: 10px; padding: 5px 10px; font-size: 11px; font-weight: 700;
}
.hint { color: #78869a; font-size: 10px; }
.card {
    background-color: #ffffff;
    border: 1px solid #e0e6ef;
    border-radius: 14px;
    padding: 10px;
    min-width: 174px;
}
.card.selected {
    background-color: #edf4ff;
    border: 2px solid #347fe8;
    padding: 9px;
}
.preview {
    background-color: #f0f3f8;
    border: 1px solid #e3e8f0;
    border-radius: 9px;
    min-height: 92px;
}
.preview.selected { background-color: #e3edfc; }
.preview-icon { color: #315b91; }
.card-title { color: #253247; font-size: 11px; font-weight: 600; }
.card-index { color: #8793a5; font-size: 9px; }
.card.selected .card-title { color: #173b70; }
.card.selected .card-index { color: #3975c8; }
scrolledwindow { background: transparent; border: 0; }
viewport { background: transparent; }
scrollbar.horizontal { min-height: 7px; }
scrollbar trough { background-color: #e6ebf2; border-radius: 5px; }
scrollbar slider { background-color: #aab8cb; border-radius: 5px; min-width: 28px; }
"""


class SwitcherOverlay:
    """A compact carousel that remains usable with many open windows."""

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
        self.window.connect("draw", self._draw_fallback)

        self.css = Gtk.CssProvider()
        self.screen = Gdk.Screen.get_default()
        self._apply_css()

        self.outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.outer.set_halign(Gtk.Align.CENTER)
        self.outer.set_valign(Gtk.Align.CENTER)
        self.frame = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.frame.get_style_context().add_class("frame")
        self.outer.pack_start(self.frame, True, True, 0)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        heading = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.heading_title = Gtk.Label(label="Open windows")
        self.heading_title.set_xalign(0)
        self.heading_title.get_style_context().add_class("header-title")
        self.heading_subtitle = Gtk.Label(label="Swipe to move between your windows")
        self.heading_subtitle.set_xalign(0)
        self.heading_subtitle.get_style_context().add_class("header-subtitle")
        heading.pack_start(self.heading_title, False, False, 0)
        heading.pack_start(self.heading_subtitle, False, False, 0)
        header.pack_start(heading, True, True, 0)
        self.counter = Gtk.Label(label="0 / 0")
        self.counter.get_style_context().add_class("counter")
        header.pack_end(self.counter, False, False, 0)
        self.frame.pack_start(header, False, False, 0)

        self.scroller = Gtk.ScrolledWindow()
        self.scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        self.scroller.set_shadow_type(Gtk.ShadowType.NONE)
        self.scroller.set_overlay_scrolling(False)
        self.scroller.set_min_content_height(142)
        self.cards_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.scroller.add(self.cards_box)
        self.frame.pack_start(self.scroller, True, True, 0)

        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.hint = Gtk.Label(label="Keep swiping to browse  ·  Release to switch")
        self.hint.set_xalign(0)
        self.hint.get_style_context().add_class("hint")
        footer.pack_start(self.hint, True, True, 0)
        self.frame.pack_start(footer, False, False, 0)

        self.window.add(self.outer)
        self.cards, self.preview_boxes, self.windows = [], [], []
        self.selected = 0
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

    def _draw_fallback(self, widget, cr):
        try:
            if not self.Gdk.Screen.get_default().is_composited():
                cr.set_source_rgb(0.055, 0.065, 0.09)
                cr.paint()
        except Exception:
            pass
        return False

    def show(self, windows, selected_index=0):
        self.windows = list(windows)
        self.selected = selected_index % len(self.windows) if self.windows else 0
        self._rebuild()
        self._center_on_primary()
        self.window.show_all()
        self.window.present()
        self.window.set_keep_above(True)
        self._scroll_selected_into_view()

    def _center_on_primary(self):
        try:
            display = self.Gdk.Display.get_default()
            monitor = display.get_primary_monitor() or display.get_monitor(0)
            geo = monitor.get_geometry()
            width = min(1120, max(520, int(geo.width * 0.84)))
            width = min(width, geo.width - 40)
            height = min(285, geo.height - 48)
            self.window.set_default_size(width, height)
            self.window.resize(width, height)
            self.window.move(geo.x + (geo.width - width) // 2,
                             geo.y + (geo.height - height) // 2)
        except Exception:
            self.window.set_position(self.Gtk.WindowPosition.CENTER)

    def _rebuild(self):
        for child in self.cards_box.get_children():
            self.cards_box.remove(child)
        self.cards, self.preview_boxes = [], []
        total = len(self.windows)
        self.counter.set_text(f"{self.selected + 1} / {total}" if total else "0 / 0")
        self.heading_subtitle.set_text(
            f"{total} open windows  ·  Swipe to browse" if total else "No open windows"
        )

        for index, window in enumerate(self.windows):
            card = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=8)
            card.set_halign(self.Gtk.Align.FILL)
            card.set_valign(self.Gtk.Align.FILL)
            card.set_size_request(196, 132)
            card.get_style_context().add_class("card")

            preview = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=5)
            preview.set_halign(self.Gtk.Align.FILL)
            preview.set_valign(self.Gtk.Align.FILL)
            preview.get_style_context().add_class("preview")
            preview.set_hexpand(True)
            preview.set_vexpand(True)

            icon = window.get_icon()
            if icon is not None:
                image = self.Gtk.Image.new_from_pixbuf(icon)
                image.set_pixel_size(48)
                image.get_style_context().add_class("preview-icon")
                preview.pack_start(image, True, True, 0)
            else:
                fallback = self.Gtk.Label(label="▣")
                fallback.set_name("preview-fallback")
                fallback.set_markup('<span size="42000">▣</span>')
                fallback.get_style_context().add_class("preview-icon")
                preview.pack_start(fallback, True, True, 0)

            title_text = (window.get_name() or "Untitled window").strip()
            title = self.Gtk.Label(label=title_text)
            title.set_xalign(0)
            title.set_ellipsize(Pango.EllipsizeMode.END)
            title.set_max_width_chars(25)
            title.get_style_context().add_class("card-title")
            card.pack_start(preview, True, True, 0)
            card.pack_start(title, False, False, 0)

            index_label = self.Gtk.Label(label=f"WINDOW  {index + 1:02d}")
            index_label.set_xalign(0)
            index_label.get_style_context().add_class("card-index")
            card.pack_start(index_label, False, False, 0)

            self.cards_box.pack_start(card, False, False, 0)
            self.cards.append(card)
            self.preview_boxes.append(preview)

        self._apply_selection_style()
        self.cards_box.show_all()

    def _apply_selection_style(self):
        for index, card in enumerate(self.cards):
            context = card.get_style_context()
            preview_context = self.preview_boxes[index].get_style_context()
            if index == self.selected:
                context.add_class("selected")
                preview_context.add_class("selected")
            else:
                context.remove_class("selected")
                preview_context.remove_class("selected")

    def update_selection(self, selected_index):
        if not self.cards:
            return
        selected_index %= len(self.cards)
        if selected_index == self.selected:
            return
        self.selected = selected_index
        self._apply_selection_style()
        self.counter.set_text(f"{self.selected + 1} / {len(self.cards)}")
        self._scroll_selected_into_view()

    def _scroll_selected_into_view(self):
        if not self.cards or self.selected >= len(self.cards):
            return
        adjustment = self.scroller.get_hadjustment()
        card = self.cards[self.selected]
        allocation = card.get_allocation()
        current = adjustment.get_value()
        page = adjustment.get_page_size()
        left, right = allocation.x, allocation.x + allocation.width
        if left < current:
            target = left
        elif right > current + page:
            target = right - page
        else:
            return
        adjustment.set_value(max(adjustment.get_lower(),
                                 min(target, adjustment.get_upper() - page)))

    def hide(self):
        self.window.hide()
