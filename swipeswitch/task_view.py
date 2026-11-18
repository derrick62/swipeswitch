"""Simple persistent GTK3 window overview used by the Task View gesture."""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)


class TaskView:
    def __init__(self, Gtk, Gdk, Pango, activate_callback):
        self.Gtk, self.Gdk, self.Pango = Gtk, Gdk, Pango
        self.activate_callback = activate_callback
        self.windows = []
        self.window = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
        self.window.set_title("SwipeSwitch Task View")
        self.window.set_name("swipeswitch-task-view")
        self.window.set_decorated(False)
        self.window.set_keep_above(True)
        self.window.set_skip_taskbar_hint(True)
        self.window.set_default_size(820, 520)
        self.window.set_position(Gtk.WindowPosition.CENTER)
        self.window.connect("key-press-event", self._on_key)
        self.window.connect("delete-event", self._on_delete)
        self.window.connect("focus-out-event", self._on_focus_out)
        self.provider = Gtk.CssProvider()
        self.provider.load_from_data(b"""
            window { background: rgba(15, 19, 28, 0.97); }
            .heading { color: #f5f7fb; font-size: 22px; font-weight: 600; }
            button.task-card { background: #252d3c; color: #f5f7fb; border: 1px solid #414c60; border-radius: 12px; padding: 14px; }
            button.task-card:hover { background: #34445e; border-color: #79aaff; }
            label.task-title { color: #f5f7fb; }
        """)
        self.window.get_style_context().add_provider(
            self.provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        self.root.set_border_width(24)
        heading = Gtk.Label(label="Open windows")
        heading.set_halign(Gtk.Align.START)
        heading.get_style_context().add_class("heading")
        self.root.pack_start(heading, False, False, 0)
        self.grid = Gtk.FlowBox()
        self.grid.set_selection_mode(Gtk.SelectionMode.NONE)
        self.grid.set_max_children_per_line(4)
        self.grid.set_min_children_per_line(1)
        self.grid.set_column_spacing(14)
        self.grid.set_row_spacing(14)
        self.grid.set_homogeneous(True)
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.add(self.grid)
        self.root.pack_start(scroll, True, True, 0)
        footer = Gtk.Label(label="Select a window · Esc to close")
        footer.set_halign(Gtk.Align.END)
        footer.set_opacity(0.7)
        self.root.pack_start(footer, False, False, 0)
        self.window.add(self.root)
        self.window.hide()

    def show(self, windows):
        self.windows = list(windows)
        for child in self.grid.get_children():
            self.grid.remove(child)
        for window in self.windows:
            button = self.Gtk.Button()
            button.get_style_context().add_class("task-card")
            content = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=10)
            icon = window.get_icon()
            if icon is not None:
                image = self.Gtk.Image.new_from_pixbuf(icon)
                image.set_pixel_size(48)
                content.pack_start(image, False, False, 0)
            title = self.Gtk.Label(label=(window.get_name() or "Untitled window")[:90])
            title.set_line_wrap(True)
            title.set_max_width_chars(24)
            title.get_style_context().add_class("task-title")
            content.pack_start(title, False, False, 0)
            button.add(content)
            button.connect("clicked", self._on_select, int(window.get_xid()))
            self.grid.add(button)
        self.window.show_all()
        self.window.present()

    def _on_select(self, _button, xid):
        self.hide()
        self.activate_callback(xid)

    def _on_key(self, _window, event):
        if event.keyval == self.Gdk.KEY_Escape:
            self.hide()
            return True
        return False

    def _on_delete(self, *_args):
        self.hide()
        return True

    def _on_focus_out(self, *_args):
        # Clicking elsewhere dismisses the overview without activating a card.
        self.hide()
        return False

    def hide(self):
        self.window.hide()
