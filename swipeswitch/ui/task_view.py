"""Monitor-aware GTK3 window overview for the Task View gesture.

Improvements over the original:
- Uses ``ThemeManager`` for consistent light/dark styling.
- Uses ``LayoutEngine.pick_monitor`` to open on the pointer's monitor and
  size the window to that monitor (no hardcoded 1120 × 720).
- Card count per row scales with monitor width.
- GTK is imported once at module level via ``_ensure_gtk()``.
"""
from __future__ import annotations

import logging

from .helpers import LayoutEngine, WindowPropertyHelpers
from .theme import ThemeManager
from ..thumbs import capture_thumbnail

log = logging.getLogger(__name__)

_Gdk = _Gtk = _Pango = None


def _ensure_gtk():
    global _Gdk, _Gtk, _Pango
    if _Gtk is None:
        try:
            import gi
            gi.require_version("Gtk", "3.0")
            gi.require_version("Gdk", "3.0")
            gi.require_version("Pango", "1.0")
            from gi.repository import Gdk, Gtk, Pango
            _Gdk, _Gtk, _Pango = Gdk, Gtk, Pango
        except (ImportError, ValueError) as exc:
            raise RuntimeError(f"GTK3 bindings unavailable: {exc}") from exc


class TaskView:
    """Full-screen window overview opened by a three-finger swipe up."""

    # Cards are scaled to roughly this fraction of monitor width.
    _CARD_WIDTH_FRACTION = 0.18
    _CARD_MIN_W = 200
    _CARD_MAX_W = 320
    _PREVIEW_ASPECT = 9 / 16   # height / width

    def __init__(self, config, activate_callback):
        _ensure_gtk()
        Gtk = _Gtk

        self.config = config
        self.activate_callback = activate_callback
        self._helpers = WindowPropertyHelpers()

        self.window = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
        self.window.set_title("SwipeSwitch Task View")
        self.window.set_name("swipeswitch-task-view")
        self.window.set_decorated(False)
        self.window.set_keep_above(True)
        self.window.set_skip_taskbar_hint(True)

        self._theme = ThemeManager(config)
        self._theme.watch_system_changes()
        self._theme.apply()

        self.root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        self.root.set_border_width(24)

        heading = Gtk.Label(label="Open windows")
        heading.set_halign(Gtk.Align.START)
        heading.get_style_context().add_class("heading")
        self.root.pack_start(heading, False, False, 0)

        self.grid = Gtk.FlowBox()
        self.grid.set_selection_mode(Gtk.SelectionMode.NONE)
        self.grid.set_max_children_per_line(6)
        self.grid.set_min_children_per_line(1)
        self.grid.set_column_spacing(16)
        self.grid.set_row_spacing(16)
        self.grid.set_homogeneous(True)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.add(self.grid)
        self.root.pack_start(scroll, True, True, 0)

        footer = Gtk.Label(label="Select a window  ·  Esc to close")
        footer.set_halign(Gtk.Align.END)
        footer.get_style_context().add_class("footer")
        self.root.pack_start(footer, False, False, 0)

        self.window.add(self.root)

        self.window.connect("key-press-event", self._on_key)
        self.window.connect("delete-event", self._on_delete)
        self.window.connect("focus-out-event", self._on_focus_out)
        self.window.hide()

    # ----------------------------------------------------------------- public

    def update_config(self, config) -> None:
        self.config = config
        self._theme.update_config(config)

    def show(self, windows) -> None:
        # Determine monitor geometry and derive card dimensions from it.
        monitor = LayoutEngine.pick_monitor(_Gdk, self.config)
        geo = monitor.get_geometry()

        card_w = max(
            self._CARD_MIN_W,
            min(self._CARD_MAX_W, int(geo.width * self._CARD_WIDTH_FRACTION)),
        )
        preview_w = card_w - 20
        preview_h = max(80, int(preview_w * self._PREVIEW_ASPECT))
        cols = max(1, (geo.width - 48) // (card_w + 16))

        self.grid.set_max_children_per_line(cols)

        # Fit the window to the monitor
        self.window.set_default_size(geo.width, geo.height)
        self.window.resize(geo.width, geo.height)
        self.window.move(geo.x, geo.y)

        # Rebuild cards
        for child in self.grid.get_children():
            self.grid.remove(child)

        for window in windows:
            self.grid.add(
                self._make_card(window, card_w, preview_w, preview_h)
            )

        self.window.show_all()
        self.window.present()

    def hide(self) -> None:
        self.window.hide()

    # ----------------------------------------------------------------- cards

    def _make_card(self, window, card_w: int, preview_w: int, preview_h: int):
        Gtk = _Gtk
        h = self._helpers

        button = Gtk.Button()
        button.get_style_context().add_class("task-card")

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        content.set_size_request(card_w, -1)

        # Preview or icon
        preview = capture_thumbnail(window, _Gdk, max_width=preview_w, max_height=preview_h)
        if preview is not None:
            image = Gtk.Image.new_from_pixbuf(preview)
            image.set_halign(Gtk.Align.CENTER)
            image.get_style_context().add_class("task-preview")
            content.pack_start(image, True, True, 0)
        else:
            icon = h.safe(window.get_icon)
            if icon is not None:
                image = Gtk.Image.new_from_pixbuf(icon)
                image.set_pixel_size(48)
                image.set_halign(Gtk.Align.CENTER)
                content.pack_start(image, True, True, 0)

        # Title
        name = h.window_title(window)
        title = Gtk.Label(label=name[:90])
        title.set_line_wrap(True)
        title.set_max_width_chars(24)
        title.set_halign(Gtk.Align.CENTER)
        title.get_style_context().add_class("task-title")
        content.pack_start(title, False, False, 0)

        # State badges
        badges = []
        if h.is_minimized(window):
            badges.append("Minimized")
        if h.needs_attention(window):
            badges.append("Needs attention")
        if badges:
            badge_label = Gtk.Label(label="  ·  ".join(badges))
            badge_label.set_opacity(0.6)
            badge_label.get_style_context().add_class("subheading")
            content.pack_start(badge_label, False, False, 0)

        button.add(content)
        button.connect("clicked", self._on_select, int(window.get_xid()))
        return button

    # --------------------------------------------------------------- events

    def _on_select(self, _button, xid: int) -> None:
        self.hide()
        self.activate_callback(xid)

    def _on_key(self, _window, event) -> bool:
        if event.keyval == _Gdk.KEY_Escape:
            self.hide()
            return True
        return False

    def _on_delete(self, *_args) -> bool:
        self.hide()
        return True

    def _on_focus_out(self, *_args) -> bool:
        self.hide()
        return False
