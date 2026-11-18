from swipeswitch.controller import SwipeSwitchController


class Screen:
    def force_update(self): pass
    def get_windows(self): return []


def test_task_view_selection_skips_window_that_has_closed():
    controller = SwipeSwitchController.__new__(SwipeSwitchController)
    controller.screen = Screen()
    controller.Gdk = None
    assert controller.activate_xid(12345) is False
