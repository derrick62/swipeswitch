"""Window card widget builder for SwitcherOverlay.

Separating card construction from the overlay's layout and animation concerns
keeps each class focused and makes the card lifecycle testable in isolation.
"""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)


class Card:
    """The widgets and cached state belonging to one window card.

    Cards are keyed by window XID and kept between switcher invocations so
    that re-opening the switcher reuses widgets and shows the last thumbnail
    immediately while a fresh capture is queued.
    """

    __slots__ = (
        "key", "window", "size_key",
        "event_box", "box", "preview_area", "preview_kind",
        "thumb", "app_image", "title",
    )

    def __init__(self, key: int, window, size_key: tuple[int, int]):
        self.key = key
        self.window = window
        self.size_key = size_key
        self.event_box = None
        self.box = None
        self.preview_area = None
        self.preview_kind: str | None = None  # "thumb", "icon", or "fallback"
        self.thumb = None
        self.app_image = None
        self.title = None


class CardBuilder:
    """Builds, updates, and applies state to GTK3 window card widgets.

    The builder owns no state between calls; it is a stateless factory that
    takes dependencies (Gtk, Pango, metrics, window-property helpers) at
    construction time and produces Card objects on demand.

    ``on_press`` and ``on_motion`` are callbacks the overlay registers to wire
    up mouse selection/activation without the builder needing to know about
    selection logic.
    """

    def __init__(self, Gtk, Gdk, Pango, metrics, helpers):
        """
        Parameters
        ----------
        Gtk, Gdk, Pango:
            GTK3 gi.repository namespaces (already imported by the caller).
        metrics:
            A SimpleNamespace from ``LayoutEngine.compute``.
        helpers:
            A ``WindowPropertyHelpers`` instance for window attribute access.
        """
        self._Gtk = Gtk
        self._Gdk = Gdk
        self._Pango = Pango
        self.metrics = metrics
        self.helpers = helpers

    def build(self, window, key: int, on_press, on_motion) -> Card:
        """Create a new Card for *window* and wire up event callbacks."""
        Gtk, Pango = self._Gtk, self._Pango
        metrics = self.metrics

        card = Card(key, window, (metrics.card_w, metrics.card_h))

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

        title_label = Gtk.Label()
        title_label.set_ellipsize(Pango.EllipsizeMode.END)
        title_label.set_max_width_chars(36)
        title_label.set_halign(Gtk.Align.START)
        title_label.set_valign(Gtk.Align.CENTER)
        title_label.set_hexpand(True)
        title_label.get_style_context().add_class("title")
        meta.pack_start(title_label, True, True, 0)
        box.pack_start(meta, False, False, 0)

        event_box = Gtk.EventBox()
        event_box.set_visible_window(False)
        event_box.add(box)
        event_box.add_events(
            self._Gdk.EventMask.BUTTON_PRESS_MASK
            | self._Gdk.EventMask.POINTER_MOTION_MASK
        )
        event_box.connect(
            "button-press-event",
            lambda _w, ev, c=card: on_press(c, ev),
        )
        event_box.connect(
            "motion-notify-event",
            lambda _w, ev, c=card: on_motion(c, ev),
        )

        card.event_box = event_box
        card.box = box
        card.preview_area = preview_area
        card.app_image = app_image
        card.title = title_label
        return card

    def refresh_content(self, card: Card, thumbnails_enabled: bool) -> None:
        """Update title, icon, and optionally invalidate the thumbnail slot."""
        Gtk = self._Gtk
        h = self.helpers
        window = card.window

        name = h.window_title(window)
        card.title.set_text(name[:120])
        card.box.set_tooltip_text(name)

        icon = h.safe(window.get_mini_icon) or h.safe(window.get_icon)
        if icon is not None:
            card.app_image.set_from_pixbuf(icon)
            card.app_image.set_no_show_all(False)
            card.app_image.show()
        else:
            card.app_image.set_no_show_all(True)
            card.app_image.hide()

        if not thumbnails_enabled:
            card.thumb = None
        if card.preview_kind != "thumb" or card.thumb is None:
            self.install_preview(card)

    def install_preview(self, card: Card) -> None:
        """Replace the preview-area contents with thumb, icon, or fallback."""
        Gtk = self._Gtk
        for child in card.preview_area.get_children():
            card.preview_area.remove(child)

        if card.thumb is not None:
            widget = Gtk.Image.new_from_pixbuf(card.thumb)
            kind = "thumb"
        else:
            icon = self.helpers.safe(card.window.get_icon)
            if icon is not None:
                widget = Gtk.Image.new_from_pixbuf(icon)
                widget.set_pixel_size(54)
                kind = "icon"
            else:
                widget = Gtk.Label(label="▣")
                kind = "fallback"

        widget.set_halign(Gtk.Align.CENTER)
        widget.set_valign(Gtk.Align.CENTER)
        card.preview_area.pack_start(widget, True, True, 0)
        widget.show()
        card.preview_kind = kind

    def apply_state(self, card: Card, selected: bool) -> None:
        """Toggle CSS classes on the card box to reflect current state."""
        ctx = card.box.get_style_context()
        h = self.helpers
        window = card.window
        for class_name, active in (
            ("selected",  selected),
            ("minimized", h.is_minimized(window)),
            ("attention", h.needs_attention(window)),
        ):
            if active:
                ctx.add_class(class_name)
            else:
                ctx.remove_class(class_name)
