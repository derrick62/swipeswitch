"""SwipeSwitch X11 application entry point."""
import argparse
import logging
import os
import signal

from .config import load_config
from .input.listener import LibinputListener, detect_touchpad


def _require_gtk():
    """Import and version-pin GTK3 bindings; raise RuntimeError with install hint."""
    try:
        import gi
        gi.require_version("Gtk", "3.0")
        gi.require_version("Gdk", "3.0")
        gi.require_version("Pango", "1.0")
        gi.require_version("Wnck", "3.0")
        from gi.repository import Gdk, GLib, Gtk, Wnck
        return Gdk, GLib, Gtk, Wnck
    except (ImportError, ValueError) as exc:
        raise RuntimeError(
            "Could not load GTK 3 / libwnck 3 bindings "
            f"({type(exc).__name__}: {exc}). Install them with:\n"
            "  sudo apt install python3-gi gir1.2-gtk-3.0 gir1.2-wnck-3.0"
        ) from exc


def main(argv=None):
    parser = argparse.ArgumentParser(prog="swipeswitch")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--config")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    log = logging.getLogger("swipeswitch")

    try:
        if not os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
            raise RuntimeError(
                "SwipeSwitch requires an X11 session; Wayland is not supported."
            )

        cfg = load_config(args.config)
        device = detect_touchpad(cfg.touchpad_device)
        Gdk, GLib, Gtk, Wnck = _require_gtk()

        if args.check:
            print(f"X11 DISPLAY: {os.environ['DISPLAY']}")
            print(f"Touchpad:    {device}")
            print(f"Config:      {cfg.config_path}")
            print("GTK 3 / libwnck imports: OK")
            return 0

        screen = Wnck.Screen.get_default()
        if screen is None:
            raise RuntimeError("Could not connect to the X11 window manager.")
        screen.force_update()

        # Deferred imports — GTK is verified available above, so these are safe.
        from .desktop.tracker import WindowTracker
        from .controller import SwipeSwitchController
        from .ui.overlay import SwitcherOverlay
        from .ui.task_view import TaskView

        tracker = WindowTracker(screen, cfg)
        switcher = SwitcherOverlay(cfg)                       # no Gtk/Gdk args
        task_view = TaskView(cfg, activate_callback=None)     # callback wired below

        controller = SwipeSwitchController(
            screen, tracker, switcher, task_view, Gdk, cfg
        )
        task_view.activate_callback = controller.activate_xid

        listener = LibinputListener(
            device,
            {3, 4},
            callback=lambda event: GLib.idle_add(controller.handle_event, event),
            debug=args.debug,
            use_unaccelerated=cfg.use_unaccelerated,
        )
        listener.start()
        GLib.timeout_add(
            250,
            lambda: (controller.check_timeout(), GLib.SOURCE_CONTINUE)[1],
        )

        def reload_config(_signum, _frame):
            try:
                new_cfg = load_config(args.config)
                controller.update_config(new_cfg)
                task_view.update_config(new_cfg)
                listener.use_unaccelerated = new_cfg.use_unaccelerated
                log.info("Configuration reloaded")
            except Exception:
                log.exception("Config reload failed; retaining current configuration")

        def shutdown(*_args):
            listener.stop()
            Gtk.main_quit()

        if hasattr(signal, "SIGHUP"):
            signal.signal(signal.SIGHUP, reload_config)
        signal.signal(signal.SIGINT, shutdown)
        signal.signal(signal.SIGTERM, shutdown)

        log.info(
            "SwipeSwitch started; listening to %s (3- and 4-finger gestures)", device
        )
        Gtk.main()
        listener.stop()
        return 0

    except Exception as exc:
        log.error("%s", exc)
        if args.debug:
            log.exception("Startup error")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
