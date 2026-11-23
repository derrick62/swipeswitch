"""Small GTK control panel for the SwipeSwitch user service."""
from __future__ import annotations

import logging

from .service import SwipeSwitchService

log = logging.getLogger(__name__)


def main() -> int:
    try:
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import GLib, Gtk
    except (ImportError, ValueError) as exc:
        raise SystemExit(
            "SwipeSwitch Control Panel requires GTK 3. Install python3-gi and "
            "gir1.2-gtk-3.0."
        ) from exc

    manager = SwipeSwitchService()

    class ControlPanel(Gtk.Window):
        def __init__(self):
            super().__init__(title="SwipeSwitch")
            self.set_border_width(22)
            self.set_default_size(430, 250)
            self.set_resizable(False)
            self.set_position(Gtk.WindowPosition.CENTER)
            self.connect("destroy", Gtk.main_quit)

            root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
            self.add(root)

            heading = Gtk.Label()
            heading.set_markup('<span size="x-large" weight="bold">SwipeSwitch</span>')
            heading.set_halign(Gtk.Align.START)
            root.pack_start(heading, False, False, 0)

            description = Gtk.Label(label="Manage your touchpad gestures")
            description.set_halign(Gtk.Align.START)
            description.get_style_context().add_class("dim-label")
            root.pack_start(description, False, False, 0)

            status_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            status_row.set_margin_top(5)
            root.pack_start(status_row, False, False, 0)

            self.indicator = Gtk.Label()
            self.indicator.set_use_markup(True)
            status_row.pack_start(self.indicator, False, False, 0)

            self.status_label = Gtk.Label()
            self.status_label.set_halign(Gtk.Align.START)
            self.status_label.set_xalign(0)
            status_row.pack_start(self.status_label, True, True, 0)

            self.toggle_button = Gtk.Button(label="Start SwipeSwitch")
            self.toggle_button.set_size_request(-1, 42)
            self.toggle_button.get_style_context().add_class("suggested-action")
            self.toggle_button.connect("clicked", self.on_toggle)
            root.pack_start(self.toggle_button, False, False, 0)

            self.autostart = Gtk.CheckButton(label="Launch automatically when I log in")
            self.autostart.set_active(manager.is_autostart_enabled())
            self.autostart_handler = self.autostart.connect("toggled", self.on_autostart_toggled)
            root.pack_start(self.autostart, False, False, 0)

            footer = Gtk.Label(
                label="Stopping SwipeSwitch does not disable your touchpad or system libinput."
            )
            footer.set_line_wrap(True)
            footer.set_halign(Gtk.Align.START)
            footer.get_style_context().add_class("dim-label")
            root.pack_start(footer, False, False, 0)

            self.refresh_status()
            GLib.timeout_add_seconds(2, self.refresh_status)

        def show_error(self, message: str) -> None:
            dialog = Gtk.MessageDialog(
                transient_for=self,
                flags=Gtk.DialogFlags.MODAL,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.CLOSE,
                text="SwipeSwitch could not complete that action",
            )
            dialog.format_secondary_text(message)
            dialog.run()
            dialog.destroy()

        def refresh_status(self):
            try:
                running = manager.is_running()
            except Exception as exc:  # status should never crash the panel
                log.warning("Could not query SwipeSwitch service: %s", exc)
                running = False
                self.status_label.set_text("Stopped · service manager unavailable")
                self.indicator.set_markup('<span foreground="#d97706">●</span>')
                self.toggle_button.set_label("Start SwipeSwitch")
                return GLib.SOURCE_CONTINUE

            if running:
                self.indicator.set_markup('<span foreground="#16a34a">●</span>')
                self.status_label.set_text("Running")
                self.toggle_button.set_label("Stop SwipeSwitch")
                self.toggle_button.get_style_context().remove_class("suggested-action")
                self.toggle_button.get_style_context().add_class("destructive-action")
            else:
                self.indicator.set_markup('<span foreground="#9ca3af">●</span>')
                self.status_label.set_text("Stopped")
                self.toggle_button.set_label("Start SwipeSwitch")
                self.toggle_button.get_style_context().remove_class("destructive-action")
                self.toggle_button.get_style_context().add_class("suggested-action")
            return GLib.SOURCE_CONTINUE

        def on_toggle(self, _button):
            try:
                if manager.is_running():
                    manager.stop()
                else:
                    manager.start()
            except Exception as exc:
                self.show_error(str(exc))
            self.refresh_status()

        def on_autostart_toggled(self, button):
            try:
                manager.set_autostart(button.get_active())
            except Exception as exc:
                button.handler_block(self.autostart_handler)
                button.set_active(not button.get_active())
                button.handler_unblock(self.autostart_handler)
                self.show_error(str(exc))

    panel = ControlPanel()
    panel.show_all()
    Gtk.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
