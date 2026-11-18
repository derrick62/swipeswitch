from swipeswitch.listener import parse_libinput_line


def test_begin():
    event = parse_libinput_line("event4 GESTURE_SWIPE_BEGIN +0.123s 3")
    assert event.kind == "begin" and event.fingers == 3


def test_update_pair():
    event = parse_libinput_line("GESTURE_SWIPE_UPDATE +0.1s 3 -12.5/+1.25")
    assert (event.dx, event.dy) == (-12.5, 1.25)


def test_update_labelled():
    event = parse_libinput_line("GESTURE_SWIPE_UPDATE +0.1s 3 dx -2.5 dy 0.75")
    assert (event.dx, event.dy) == (-2.5, 0.75)


def test_cancelled_end():
    event = parse_libinput_line("GESTURE_SWIPE_END +0.1s 3 cancelled")
    assert event.kind == "end" and event.cancelled


def test_ignore_non_gesture_and_malformed():
    assert parse_libinput_line("POINTER_MOTION +0.01s 1/2") is None
    assert parse_libinput_line("GESTURE_SWIPE_BEGIN +0.1s") is None


def test_update_with_optional_sequence_number():
    event = parse_libinput_line(
        "event6 GESTURE_SWIPE_UPDATE      2  +2.209s  3  4.69/0.00 (4.80/0.00 unaccelerated)"
    )
    assert event is not None
    assert event.kind == "update" and event.fingers == 3
    assert (event.dx, event.dy) == (4.69, 0.0)


def test_update_without_sequence_number_still_parses():
    event = parse_libinput_line(
        "event6 GESTURE_SWIPE_UPDATE +2.203s 3 -3.88/0.55 (-4.10/0.59 unaccelerated)"
    )
    assert event is not None
    assert (event.dx, event.dy) == (-3.88, 0.55)


def test_update_can_select_unaccelerated_movement():
    line = (
        "GESTURE_SWIPE_UPDATE +0.1s 3 "
        "4.69/0.00 (4.80/0.25 unaccelerated)"
    )
    accelerated = parse_libinput_line(line)
    unaccelerated = parse_libinput_line(line, use_unaccelerated=True)
    assert (accelerated.dx, accelerated.dy) == (4.69, 0.0)
    assert (unaccelerated.dx, unaccelerated.dy) == (4.80, 0.25)
