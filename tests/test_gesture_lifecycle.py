"""Regression tests for the single runtime gesture recogniser."""
from swipeswitch.events import GestureEvent
from swipeswitch.gestures import GestureRecognizer


def test_event_defaults_are_normalised():
    event = GestureEvent("begin", fingers=3)
    assert event.kind == "begin"
    assert event.dx == event.dy == 0.0
    assert not event.cancelled


def test_recogniser_timeout_cancels_active_switch(monkeypatch):
    recognizer = GestureRecognizer(threshold_px=10, step_px=20)
    recognizer.handle(GestureEvent("begin", fingers=3))
    recognizer.handle(GestureEvent("update", fingers=3, dx=-25))
    recognizer.last_activity = 1.0
    monkeypatch.setattr("swipeswitch.gestures.time.monotonic", lambda: 5.0)
    actions = recognizer.check_timeout(2.0)
    assert [action.name for action in actions] == ["switch_cancel"]
    assert recognizer.fingers == 0


def test_new_begin_cancels_previous_switch_before_reset():
    recognizer = GestureRecognizer(threshold_px=10, step_px=20)
    recognizer.handle(GestureEvent("begin", fingers=3))
    recognizer.handle(GestureEvent("update", fingers=3, dx=-25))
    actions = recognizer.handle(GestureEvent("begin", fingers=4))
    assert [action.name for action in actions] == ["switch_cancel"]
    assert recognizer.fingers == 4
