"""Focused tests for the conservative gesture-conflict detector."""
import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "scripts" / "swipeswitch-conflicts.py"
SPEC = importlib.util.spec_from_file_location("swipeswitch_conflicts", MODULE_PATH)
conflicts = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(conflicts)


def test_matches_known_gesture_handlers_only():
    assert conflicts._matches(["/usr/bin/python3", "/usr/bin/fusuma"])
    assert conflicts._matches(["/usr/bin/touchegg", "--daemon"])
    assert not conflicts._matches(["/usr/bin/python3", "swipeswitch"])
    assert not conflicts._matches(["/usr/bin/libinput", "debug-events"])


def test_autostart_detection_only_returns_known_handlers(tmp_path, monkeypatch):
    autostart = tmp_path / ".config" / "autostart"
    autostart.mkdir(parents=True)
    (autostart / "fusuma.desktop").write_text(
        "[Desktop Entry]\nType=Application\nExec=/usr/bin/fusuma -d\n"
    )
    (autostart / "browser.desktop").write_text(
        "[Desktop Entry]\nType=Application\nExec=firefox\n"
    )
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    assert conflicts.autostart_handlers() == [autostart / "fusuma.desktop"]


def test_service_detection_only_reports_enabled_units(monkeypatch):
    class Result:
        returncode = 0
        stdout = (
            "touchegg.service enabled enabled\n"
            "fusuma.service disabled disabled\n"
        )

    monkeypatch.setattr(conflicts, "shutil_which", lambda _name: "/bin/systemctl")
    monkeypatch.setattr(conflicts, "_systemctl", lambda *a, **k: Result())
    assert conflicts.service_units(user=True) == ["touchegg.service"]
