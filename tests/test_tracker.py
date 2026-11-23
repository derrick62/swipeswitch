from swipeswitch.config import Config
from swipeswitch.desktop.tracker import WindowTracker


class FakeScreen:
    def get_active_workspace(self): return 0


class FakeWindow:
    def __init__(self, xid, workspace=0, skip=False):
        self.xid, self.workspace, self.skip = xid, workspace, skip
    def get_xid(self): return self.xid
    def get_workspace(self): return self.workspace
    def is_skip_tasklist(self): return self.skip
    def get_name(self): return "Test"


def test_mru_move_front():
    tracker = WindowTracker.__new__(WindowTracker)
    tracker._mru = []
    a, b = FakeWindow(1), FakeWindow(2)
    tracker._move_front(a)
    tracker._move_front(b)
    tracker._move_front(a)
    assert [w.xid for w in tracker._mru] == [1, 2]


def test_workspace_and_sticky_filter():
    tracker = WindowTracker.__new__(WindowTracker)
    tracker.config = Config(current_workspace_only=True)
    tracker.screen = FakeScreen()
    assert tracker._is_on_current_workspace(FakeWindow(1, 0))
    assert not tracker._is_on_current_workspace(FakeWindow(2, 1))
    assert tracker._is_on_current_workspace(FakeWindow(3, None))


def test_skip_tasklist_flag():
    assert FakeWindow(1, skip=True).is_skip_tasklist()
