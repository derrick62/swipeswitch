from swipeswitch.controller import SwipeSwitchController


class Screen:
    def force_update(self): pass
    def get_windows(self): return []


def test_task_view_selection_skips_window_that_has_closed():
    controller = SwipeSwitchController.__new__(SwipeSwitchController)
    controller.screen = Screen()
    controller.Gdk = None
    assert controller.activate_xid(12345) is False


class FakeSwitcher:
    def __init__(self):
        self.selections = []

    def update_selection(self, index):
        self.selections.append(index)


class FakeWindow:
    pass


def test_right_swipe_advances_to_next_displayed_window():
    controller = SwipeSwitchController.__new__(SwipeSwitchController)
    controller.switch_windows = [FakeWindow() for _ in range(4)]
    controller.selected = 0
    controller.switcher = FakeSwitcher()

    from swipeswitch.recognition.gestures import GestureAction
    controller._dispatch(GestureAction("switch_move", 3, "right", 1))

    assert controller.selected == 1
    assert controller.switcher.selections == [1]


def test_left_swipe_moves_to_previous_displayed_window():
    controller = SwipeSwitchController.__new__(SwipeSwitchController)
    controller.switch_windows = [FakeWindow() for _ in range(4)]
    controller.selected = 2
    controller.switcher = FakeSwitcher()

    from swipeswitch.recognition.gestures import GestureAction
    controller._dispatch(GestureAction("switch_move", 3, "left", 1))

    assert controller.selected == 1
    assert controller.switcher.selections == [1]


class FakeTaskView:
    def __init__(self): self.hidden = 0
    def hide(self): self.hidden += 1


class FakeWorkspaces:
    def __init__(self, outcomes=None):
        self.calls = []
        self.outcomes = list(outcomes or [])
    def navigate(self, direction):
        self.calls.append(direction)
        return self.outcomes.pop(0) if self.outcomes else True


def test_four_finger_workspace_action_applies_each_incremental_step():
    from swipeswitch.recognition.gestures import GestureAction
    controller = SwipeSwitchController.__new__(SwipeSwitchController)
    controller.task_view = FakeTaskView()
    controller.workspaces = FakeWorkspaces()
    controller.switch_windows = [object()]
    controller._dispatch(GestureAction("workspace", 4, "left", 3))
    assert controller.workspaces.calls == ["left", "left", "left"]
    assert controller.task_view.hidden == 1
    assert controller.switch_windows == []


def test_workspace_navigation_stops_when_boundary_is_reached():
    from swipeswitch.recognition.gestures import GestureAction
    controller = SwipeSwitchController.__new__(SwipeSwitchController)
    controller.task_view = FakeTaskView()
    controller.workspaces = FakeWorkspaces([True, False, True])
    controller.switch_windows = []
    controller._dispatch(GestureAction("workspace", 4, "left", 3))
    assert controller.workspaces.calls == ["left", "left"]
