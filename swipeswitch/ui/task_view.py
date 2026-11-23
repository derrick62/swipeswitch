"""Monitor-aware GTK3 window overview for the Task View gesture.

Improvements over the original:
- Uses ``ThemeManager`` for consistent light/dark styling.
- Uses ``LayoutEngine.pick_monitor`` to open on the pointer's monitor and
  size the window to that monitor (no hardcoded 1120 × 720).
- Card count per row and card dimensions are solved from monitor geometry
  and window count so the grid always fills the screen without scrolling —
  matching Windows Task View behaviour.  At most ``_MAX_PREFERRED_ROWS`` rows
  are used; the grid widens (more columns, smaller cards) before it ever
  grows taller.
- GTK is imported once at module level via ``_ensure_gtk()``.
"""
from __future__ import annotations

import logging
import math

from .helpers import LayoutEngine, WindowPropertyHelpers
from .theme import ThemeManager
from ..thumbs import capture_thumbnail

log = logging.getLogger(__name__)

_Gdk = _Gtk = _Pango = None

# Fraction of usable monitor height reserved for the header + footer rows.
_CHROME_H_FRACTION  = 0.18
_CARD_PADDING       = 20       # internal card padding (left+right)
_PREVIEW_ASPECT     = 9 / 16  # height / width
_CARD_MIN_W         = 160
_CARD_MAX_W         = 320
_GRID_PAD           = 24      # grid outer margin
_GRID_GAP           = 16      # gap between cards
_MAX_PREFERRED_ROWS = 3       # widen the grid before adding a 4th row


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


def _solve_grid(count: int, geo_w: int, geo_h: int):
    """Return (cols, card_w, pv_w, pv_h) so *count* cards fill the screen
    without scrolling on either axis.

    Strategy: prefer wide grids (few rows) over tall ones, matching Windows
    Task View.  Start from the minimum column count that keeps rows <=
    ``_MAX_PREFERRED_ROWS`` and increase columns until the row height fits in
    the available vertical space.  Falls back to a single over-wide row at
    minimum card width if nothing else fits.
    """
    usable_w = geo_w - 2 * _GRID_PAD
    usable_h = int(geo_h * (1.0 - _CHROME_H_FRACTION)) - 2 * _GRID_PAD

    # Minimum columns to stay within the preferred row budget.
    min_cols = math.ceil(count / _MAX_PREFERRED_ROWS)

    for cols in range(min_cols, count + 1):
        rows   = math.ceil(count / cols)
        card_w = max(
            _CARD_MIN_W,
            min(_CARD_MAX_W, (usable_w - _GRID_GAP * (cols - 1)) // cols),
        )
        pv_w   = max(32, card_w - _CARD_PADDING)
        pv_h   = max(28, round(pv_w * _PREVIEW_ASPECT))
        card_h = pv_h + 60   # preview + title + badge rows
        total_h = card_h * rows + _GRID_GAP * (rows - 1)
        if total_h <= usable_h:
            return cols, card_w, pv_w, pv_h

    # Fallback: everything in one row at minimum card width.
    card_w = _CARD_MIN_W
    pv_w   = max(32, card_w - _CARD_PADDING)
    pv_h   = max(28, round(pv_w * _PREVIEW_ASPECT))
    return count, card_w, pv_w, pv_h


class TaskView:
    """Full-screen window overview opened by a three-finger swipe up.

    All cards are always visible — no scrolling on either axis.  The grid
    layout is solved from the monitor geometry and window count so that the
    minimum number of rows is used while keeping cards above the minimum
    readable size.
    """

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

        # FlowBox with no scroll — both axes locked to NEVER via plain Box wrap.
        self.grid = Gtk.FlowBox()
        self.grid.set_selection_mode(Gtk.SelectionMode.NONE)
        self.grid.set_max_children_per_line(999)  # overridden per show()
        self.grid.set_min_children_per_line(1)
        self.grid.set_column_spacing(_GRID_GAP)
        self.grid.set_row_spacing(_GRID_GAP)
        self.grid.set_homogeneous(True)

        grid_wrap = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        grid_wrap.pack_start(self.grid, True, True, 0)
        self.root.pack_start(grid_wrap, True, True, 0)

        footer = Gtk.Label(label="Select a window  ·  Esc to close")
        footer.set_halign(Gtk.Align.END)
        footer.get_style_context().add_class("footer")
        self.root.pack_start(footer, False, False, 0)

        self.window.add(self.root)

        self.window.connect("key-press-event",  self._on_key)
        self.window.connect("delete-event",     self._on_delete)
        self.window.connect("focus-out-event",  self._on_focus_out)
        self.window.hide()

    # ----------------------------------------------------------------- public

    def update_config(self, config) -> None:
        self.config = config
        self._theme.update_config(config)

    def show(self, windows) -> None:
        monitor = LayoutEngine.pick_monitor(_Gdk, self.config)
        geo     = monitor.get_geometry()

        count = max(1, len(windows))
        cols, card_w, pv_w, pv_h = _solve_grid(count, geo.width, geo.height)

        self.grid.set_max_children_per_line(cols)
        self.grid.set_min_children_per_line(cols)

        self.window.set_default_size(geo.width, geo.height)
        self.window.resize(geo.width, geo.height)
        self.window.move(geo.x, geo.y)

        for child in self.grid.get_children():
            self.grid.remove(child)

        for window in windows:
            self.grid.add(self._make_card(window, card_w, pv_w, pv_h))

        self.window.show_all()
        self.window.present()

    def hide(self) -> None:
        self.window.hide()

    # ----------------------------------------------------------------- cards

    def _make_card(self, window, card_w: int, pv_w: int, pv_h: int):
        Gtk = _Gtk
        h   = self._helpers

        button = Gtk.Button()
        button.get_style_context().add_class("task-card")

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        content.set_size_request(card_w, -1)

        preview = capture_thumbnail(window, _Gdk, max_width=pv_w, max_height=pv_h)
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

        name  = h.window_title(window)
        title = Gtk.Label(label=name[:90])
        title.set_line_wrap(True)
        title.set_max_width_chars(24)
        title.set_halign(Gtk.Align.CENTER)
        title.get_style_context().add_class("task-title")
        content.pack_start(title, False, False, 0)

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