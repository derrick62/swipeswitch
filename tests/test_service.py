"""Lifecycle management tests; no real system services are touched."""
from pathlib import Path
from types import SimpleNamespace

from swipeswitch.service import SERVICE_NAME, SwipeSwitchService


def test_start_imports_session_environment_then_starts_only_swipeswitch(tmp_path, monkeypatch):
    calls = []

    def runner(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    manager = SwipeSwitchService(runner=runner)
    manager.user_unit_file = tmp_path / "systemd" / "user" / SERVICE_NAME
    monkeypatch.setattr(manager, "_system_unit_exists", lambda: False)
    manager.start()

    assert calls[0] == ["systemctl", "--user", "daemon-reload"]
    assert calls[1][:3] == ["systemctl", "--user", "import-environment"]
    assert calls[2] == ["systemctl", "--user", "start", SERVICE_NAME]
    assert manager.user_unit_file.is_file()
    assert "ExecStart=" in manager.user_unit_file.read_text()


def test_stop_only_stops_swipeswitch_user_service():
    calls = []

    def runner(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    manager = SwipeSwitchService(runner=runner)
    manager._system_unit_exists = lambda: True
    manager.stop()

    assert calls[-1] == ["systemctl", "--user", "stop", SERVICE_NAME]
    assert all("libinput" not in " ".join(command) for command in calls)
    assert all("touchpad" not in " ".join(command) for command in calls)
    assert all("sudo" not in command for command in calls)


def test_running_status_uses_only_service_state():
    def runner(command, **kwargs):
        assert command == ["systemctl", "--user", "is-active", "--quiet", SERVICE_NAME]
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    manager = SwipeSwitchService(runner=runner)
    assert manager.is_running() is True


def test_autostart_preference_writes_and_removes_only_its_entry(tmp_path, monkeypatch):
    manager = SwipeSwitchService(runner=lambda *_a, **_k: SimpleNamespace(returncode=0))
    manager.autostart_file = tmp_path / "autostart" / "swipeswitch-daemon.desktop"
    manager.ensure_unit = lambda: None
    helper = tmp_path / "bin" / "swipeswitch-session-start"
    helper.parent.mkdir()
    helper.write_text("#!/bin/sh\nexit 0\n")
    monkeypatch.setattr("swipeswitch.service.shutil.which", lambda _name: str(helper))

    manager.set_autostart(True)
    assert manager.is_autostart_enabled()
    entry = manager.autostart_file.read_text()
    assert f"Exec={helper}" in entry
    assert "swipeswitch.service" not in entry or "Exec=" in entry

    manager.set_autostart(False)
    assert not manager.is_autostart_enabled()
    assert manager.autostart_file.parent.is_dir()


def test_legacy_process_detection_matches_engine_not_control_panel(tmp_path):
    engine = tmp_path / "101"
    engine.mkdir()
    (engine / "cmdline").write_bytes(b"/usr/bin/python3\0-m\0swipeswitch\0")

    panel = tmp_path / "102"
    panel.mkdir()
    (panel / "cmdline").write_bytes(b"/usr/bin/python3\0-m\0swipeswitch.control_panel\0")

    other = tmp_path / "103"
    other.mkdir()
    (other / "cmdline").write_bytes(b"/usr/bin/python3\0-m\0unrelated_app\0")

    direct = tmp_path / "104"
    direct.mkdir()
    (direct / "cmdline").write_bytes(b"/usr/bin/swipeswitch\0--debug\0")

    assert SwipeSwitchService._legacy_processes(tmp_path) == [101, 104]


def test_stop_sends_sigterm_to_legacy_engine_only(monkeypatch):
    import signal

    manager = SwipeSwitchService(runner=lambda *_a, **_k: SimpleNamespace(returncode=3))
    manager._legacy_processes = lambda: [4242]
    killed = []
    monkeypatch.setattr("swipeswitch.service.os.kill", lambda pid, sig: killed.append((pid, sig)))
    manager._legacy_processes = lambda: [4242]
    # The process disappears after the initial SIGTERM.
    sequence = iter(([4242], []))
    manager._legacy_processes = lambda: next(sequence, [])

    manager.stop()
    assert killed == [(4242, signal.SIGTERM)]


def test_legacy_user_autostart_is_preserved_but_disabled(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    autostart = tmp_path / "config" / "autostart"
    autostart.mkdir(parents=True)
    old_entry = autostart / "swipeswitch.desktop"
    old_entry.write_text("[Desktop Entry]\nType=Application\nExec=swipeswitch\n")

    manager = SwipeSwitchService(runner=lambda *_a, **_k: SimpleNamespace(returncode=0))

    assert not old_entry.exists()
    backup = autostart / "swipeswitch.desktop.disabled-by-swipeswitch-control"
    assert backup.is_file()
    assert "Exec=swipeswitch" in backup.read_text()
    assert not manager.is_autostart_enabled()
