"""Theme management: CSS definitions and system-theme resolution.

Importing this module requires GTK3 gi bindings to already be loaded.
All CSS strings live here so that both SwitcherOverlay and TaskView use the
same colour tokens and both respond to system dark/light preference changes.
"""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CSS — shared design tokens (colours, radii, font sizes)
# ---------------------------------------------------------------------------
# Every visual property that must stay consistent between the overlay and the
# task view is defined once here.  Each theme block is a complete stylesheet;
# the theme manager loads one at a time.

DARK_CSS = """\
window#swipeswitch-overlay,
window#swipeswitch-task-view {
  background-color: rgba(5, 8, 14, 0.52);
}
.frame {
  background-color: rgba(24, 30, 42, 0.94);
  border: 1px solid rgba(255,255,255,0.16);
  border-radius: 24px;
  padding: 24px;
}
.heading  { color: #f7f9fd; font-size: 21px; font-weight: 700; }
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
.card.attention  { border-color: rgba(255,184,76,0.85); }
.card.minimized .preview-area { opacity: 0.55; }
.card.minimized .title        { opacity: 0.70; }
.card.selected {
  background-color: rgba(75,132,224,0.16);
  border-color: #8fc0ff;
  box-shadow: 0 0 14px rgba(96,160,255,0.38);
}
.preview-area { background-color: rgba(8,12,19,0.86); border-radius: 10px; }
.title          { color: #d4dbe8; font-size: 13px; font-weight: 600; }
.card.selected .title { color: #ffffff; font-weight: 700; }
.app-icon       { opacity: 1; }
.footer         { color: #b4bfd0; font-size: 11px; }
.scrollbar      { min-height: 6px; }
.edge-left  { background-image: linear-gradient(to right, rgba(24,30,42,0.94), rgba(24,30,42,0)); }
.edge-right { background-image: linear-gradient(to left,  rgba(24,30,42,0.94), rgba(24,30,42,0)); }
/* Task view */
button.task-card {
  background: #252d3c; color: #f5f7fb;
  border: 1px solid #414c60; border-radius: 14px;
  padding: 10px; min-width: 210px; min-height: 160px;
}
button.task-card:hover { background: #34445e; border-color: #79aaff; }
label.task-title { color: #f5f7fb; font-size: 12px; font-weight: 600; }
.task-preview    { background: #111722; border-radius: 8px; }
"""

LIGHT_CSS = """\
window#swipeswitch-overlay,
window#swipeswitch-task-view {
  background-color: rgba(18, 25, 36, 0.38);
}
.frame {
  background-color: rgba(247,249,253,0.96);
  border: 1px solid rgba(35,48,68,0.18);
  border-radius: 24px; padding: 24px;
}
.heading    { color: #172235; font-size: 21px; font-weight: 700; }
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
.card.attention  { border-color: rgba(222,140,20,0.85); }
.card.minimized .preview-area { opacity: 0.55; }
.card.minimized .title        { opacity: 0.70; }
.card.selected {
  background-color: #eef4ff;
  border-color: #246fce;
  box-shadow: 0 0 14px rgba(52,127,229,0.30);
}
.preview-area { background-color: #e7edf5; border-radius: 10px; }
.title          { color: #3a4960; font-size: 13px; font-weight: 600; }
.card.selected .title { color: #172235; font-weight: 700; }
.app-icon       { opacity: 1; }
.footer         { color: #5a677c; font-size: 11px; }
.scrollbar      { min-height: 6px; }
.edge-left  { background-image: linear-gradient(to right, rgba(247,249,253,0.96), rgba(247,249,253,0)); }
.edge-right { background-image: linear-gradient(to left,  rgba(247,249,253,0.96), rgba(247,249,253,0)); }
/* Task view */
button.task-card {
  background: #f0f4fa; color: #172235;
  border: 1px solid #c8d4e4; border-radius: 14px;
  padding: 10px; min-width: 210px; min-height: 160px;
}
button.task-card:hover { background: #ddeafc; border-color: #246fce; }
label.task-title { color: #172235; font-size: 12px; font-weight: 600; }
.task-preview    { background: #e0e8f4; border-radius: 8px; }
"""


class ThemeManager:
    """Applies and watches the active CSS theme for one GTK screen.

    A single ``ThemeManager`` can be shared between all windows in the
    application; calling ``apply()`` re-loads the CSS for every registered
    subscriber.

    Usage::

        mgr = ThemeManager(config)
        mgr.watch_system_changes()   # react to gtk-theme-name changes
        mgr.apply()                  # first paint

    ``apply()`` is idempotent and safe to call on every config reload.
    """

    def __init__(self, config):
        import gi
        gi.require_version("Gtk", "3.0")
        gi.require_version("Gdk", "3.0")
        from gi.repository import Gdk, Gtk

        self._Gtk = Gtk
        self._screen = Gdk.Screen.get_default()
        self._provider = Gtk.CssProvider()
        self.config = config

    # ----------------------------------------------------------------- public

    def update_config(self, config) -> None:
        self.config = config
        self.apply()

    def apply(self) -> None:
        """Load the correct CSS for the current theme preference."""
        css = LIGHT_CSS if self.resolve() == "light" else DARK_CSS
        try:
            self._provider.load_from_data(css.encode())
            self._Gtk.StyleContext.add_provider_for_screen(
                self._screen,
                self._provider,
                self._Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )
        except Exception:
            log.exception("Could not apply CSS theme")

    def resolve(self) -> str:
        """Return 'dark' or 'light' honouring config and system preference."""
        theme = getattr(self.config, "theme", "dark")
        if theme in ("auto", "system"):
            try:
                settings = self._Gtk.Settings.get_default()
                if settings.get_property("gtk-application-prefer-dark-theme"):
                    return "dark"
                name = (settings.get_property("gtk-theme-name") or "").lower()
                return "dark" if "dark" in name else "light"
            except Exception:
                return "dark"
        return "light" if theme == "light" else "dark"

    def watch_system_changes(self) -> None:
        """Re-apply CSS whenever the system GTK theme changes."""
        try:
            settings = self._Gtk.Settings.get_default()
            for prop in ("gtk-theme-name", "gtk-application-prefer-dark-theme"):
                settings.connect(f"notify::{prop}", lambda *_: self.apply())
        except Exception:
            log.debug("Could not watch system theme changes", exc_info=True)
