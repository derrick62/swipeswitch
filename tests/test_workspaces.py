from swipeswitch.desktop.workspaces import WorkspaceManager


class Workspace:
    def __init__(self): self.activations = 0
    def activate(self, _timestamp): self.activations += 1


class Screen:
    def __init__(self):
        self.workspaces = [Workspace(), Workspace(), Workspace()]
        self.active = self.workspaces[1]
    def force_update(self): pass
    def get_workspaces(self): return self.workspaces
    def get_active_workspace(self): return self.active


def test_left_moves_to_next_workspace_once():
    screen = Screen()
    assert WorkspaceManager(screen).navigate("left")
    assert screen.workspaces[2].activations == 1


def test_right_moves_to_previous_workspace():
    screen = Screen()
    assert WorkspaceManager(screen).navigate("right")
    assert screen.workspaces[0].activations == 1


def test_invalid_direction_is_ignored():
    screen = Screen()
    assert not WorkspaceManager(screen).navigate("up")
    assert sum(w.activations for w in screen.workspaces) == 0


def test_boundaries_do_not_wrap():
    screen = Screen()
    screen.active = screen.workspaces[0]
    assert not WorkspaceManager(screen).navigate("right")
    assert sum(w.activations for w in screen.workspaces) == 0
