from swipeswitch.gestures import GestureRecognizer
from swipeswitch.events import GestureEvent


def event(kind, fingers, dx=0, dy=0, cancelled=False):
    return GestureEvent(kind, fingers, dx, dy, cancelled)


def test_three_finger_left_starts_switch_and_advances_steps():
    recognizer = GestureRecognizer(threshold_px=30, step_px=50)
    assert recognizer.handle(event("begin", 3)) == []
    actions = recognizer.handle(event("update", 3, dx=-110))
    assert [action.name for action in actions] == ["switch_begin", "switch_move"]
    assert actions[0].direction == "left"
    assert actions[1].steps == 2
    assert recognizer.handle(event("end", 3))[0].name == "switch_commit"


def test_three_finger_up_routes_to_task_view():
    recognizer = GestureRecognizer(threshold_px=25)
    recognizer.handle(event("begin", 3))
    recognizer.handle(event("update", 3, dy=-40))
    actions = recognizer.handle(event("end", 3))
    assert [(a.name, a.direction) for a in actions] == [("task_view", "up")]


def test_three_finger_down_routes_to_show_desktop():
    recognizer = GestureRecognizer(threshold_px=25)
    recognizer.handle(event("begin", 3))
    recognizer.handle(event("update", 3, dy=40))
    actions = recognizer.handle(event("end", 3))
    assert [a.name for a in actions] == ["show_desktop"]


def test_four_finger_left_navigates_next_workspace():
    recognizer = GestureRecognizer(threshold_px=25)
    recognizer.handle(event("begin", 4))
    recognizer.handle(event("update", 4, dx=-40))
    actions = recognizer.handle(event("end", 4))
    assert [(a.name, a.direction) for a in actions] == [("workspace", "left")]


def test_cancelled_horizontal_switch_never_commits():
    recognizer = GestureRecognizer(threshold_px=25)
    recognizer.handle(event("begin", 3))
    recognizer.handle(event("update", 3, dx=-40))
    actions = recognizer.handle(event("end", 3, cancelled=True))
    assert [a.name for a in actions] == ["switch_cancel"]


def test_ambiguous_diagonal_gesture_is_ignored():
    recognizer = GestureRecognizer(threshold_px=25)
    recognizer.handle(event("begin", 3))
    recognizer.handle(event("update", 3, dx=35, dy=30))
    assert recognizer.handle(event("end", 3)) == []


def test_horizontal_reversal_changes_selection_direction():
    recognizer = GestureRecognizer(threshold_px=20, step_px=40)
    recognizer.handle(event("begin", 3))
    recognizer.handle(event("update", 3, dx=-50))
    actions = recognizer.handle(event("update", 3, dx=100))
    movement = [a for a in actions if a.name == "switch_move"]
    assert movement
    assert movement[-1].direction == "right"
    # The first update moved one item left. The net displacement is now
    # one item right of the origin, so two rightward steps undo and reverse it.
    assert movement[-1].steps == 2
