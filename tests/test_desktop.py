from swipeswitch.desktop.desktop import DesktopVisibilityManager


class Window:
    def __init__(self, xid, minimized=False):
        self.xid = xid
        self.minimized = minimized
        self.activated = False
        self.minimize_calls = 0

    def get_xid(self): return self.xid
    def is_minimized(self): return self.minimized
    def minimize(self):
        self.minimized = True
        self.minimize_calls += 1
    def unminimize(self, _timestamp): self.minimized = False
    def activate(self, _timestamp): self.activated = True


class Screen:
    def __init__(self, windows, active):
        self.windows = windows
        self.active = active
    def force_update(self): pass
    def get_active_window(self): return self.active
    def get_windows(self): return self.windows


class Tracker:
    def __init__(self, windows): self.windows = windows
    def get_switchable_windows(self): return self.windows


def test_restore_only_reactivates_previously_visible_snapshot_window():
    visible = Window(1)
    already_minimized = Window(2, minimized=True)
    screen = Screen([visible, already_minimized], already_minimized)
    manager = DesktopVisibilityManager(screen, Tracker([visible, already_minimized]))

    assert manager.show_desktop()
    assert manager.has_snapshot
    assert visible.minimized
    assert already_minimized.minimized
    assert visible.minimize_calls == 1
    assert already_minimized.minimize_calls == 0

    assert manager.restore()
    assert not visible.minimized
    assert already_minimized.minimized
    assert not already_minimized.activated
    assert not manager.has_snapshot


def test_repeated_show_desktop_does_not_replace_snapshot():
    first, second = Window(1), Window(2)
    screen = Screen([first, second], first)
    manager = DesktopVisibilityManager(screen, Tracker([first, second]))
    assert manager.show_desktop()
    original = list(manager._snapshot)
    assert not manager.show_desktop()
    assert manager._snapshot == original
