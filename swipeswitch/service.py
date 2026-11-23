"""User-session lifecycle management for the SwipeSwitch gesture service.

This module manages only ``swipeswitch.service`` through the current user's
systemd manager. It never invokes sudo, changes input groups, modifies device
permissions, or disables system libinput/the touchpad. Stopping the engine
also terminates its own libinput debug-events capture subprocess.
"""
from __future__ import annotations

import os
import shlex
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable

SERVICE_NAME = "swipeswitch.service"


def _config_home() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")).expanduser()


class SwipeSwitchService:
    """Control SwipeSwitch as a per-user systemd service."""

    def __init__(self, runner: Callable = subprocess.run):
        self._run = runner
        autostart_dir = _config_home() / "autostart"
        self.autostart_file = autostart_dir / "swipeswitch-daemon.desktop"
        self.legacy_autostart_file = autostart_dir / "swipeswitch.desktop"
        self.user_unit_file = _config_home() / "systemd" / "user" / SERVICE_NAME
        self._migrate_legacy_autostart()

    def _migrate_legacy_autostart(self) -> None:
        """Disable and preserve the old direct-launch user autostart entry."""
        if self.autostart_file.exists() or not self.legacy_autostart_file.is_file():
            return
        try:
            content = self.legacy_autostart_file.read_text(encoding="utf-8")
        except OSError:
            return
        if not any(line.strip() == "Exec=swipeswitch" for line in content.splitlines()):
            return
        backup = self.legacy_autostart_file.with_name(
            self.legacy_autostart_file.name + ".disabled-by-swipeswitch-control"
        )
        if not backup.exists():
            self.legacy_autostart_file.rename(backup)

    def _system_unit_exists(self) -> bool:
        return any(
            path.is_file()
            for path in (
                Path("/usr/lib/systemd/user") / SERVICE_NAME,
                Path("/lib/systemd/user") / SERVICE_NAME,
            )
        )

    def ensure_unit(self) -> None:
        """Install a user-local unit for editable/source installs if needed.

        Debian packages provide the canonical unit under /usr/lib. A local
        unit is generated only when no packaged unit exists, which makes the
        control panel usable in a normal ``pip install -e .`` development
        checkout without overriding a packaged service definition.
        """
        if self._system_unit_exists() or self.user_unit_file.exists():
            return

        executable = shutil.which("swipeswitch")
        if executable:
            command = shlex.quote(executable)
        else:
            command = f"{shlex.quote(sys.executable)} -m swipeswitch"

        self.user_unit_file.parent.mkdir(parents=True, exist_ok=True)
        content = (
            "[Unit]\n"
            "Description=SwipeSwitch touchpad gesture service\n"
            "After=graphical-session.target\n"
            "PartOf=graphical-session.target\n\n"
            "[Service]\n"
            "Type=simple\n"
            f"ExecStart={command}\n"
            "Restart=on-failure\n"
            "RestartSec=2\n"
            "KillSignal=SIGTERM\n"
            "TimeoutStopSec=10\n"
        )
        temporary = self.user_unit_file.with_suffix(".service.tmp")
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(self.user_unit_file)

    def _systemctl(self, *arguments: str, check: bool = False):
        return self._run(
            ["systemctl", "--user", *arguments],
            check=check,
            capture_output=True,
            text=True,
            timeout=15,
        )

    def _reload(self) -> None:
        self.ensure_unit()
        result = self._systemctl("daemon-reload")
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "systemd user manager unavailable").strip()
            raise RuntimeError(detail)

    @staticmethod
    def _legacy_processes(proc_root: Path = Path("/proc")) -> list[int]:
        """Find manually launched/older SwipeSwitch engines, not this panel.

        This bridge is needed when upgrading from releases that started the
        foreground engine directly through XDG autostart rather than systemd.
        It matches the exact module/script entry point, never broad name
        substrings such as ``python`` or ``libinput``.
        """
        matches: list[int] = []
        try:
            entries = list(proc_root.iterdir())
        except OSError:
            return matches

        for entry in entries:
            if not entry.name.isdigit():
                continue
            try:
                raw = (entry / "cmdline").read_bytes()
            except (OSError, ProcessLookupError):
                continue
            if not raw:
                continue
            arguments = [part.decode(errors="replace") for part in raw.split(b"\0") if part]
            module_match = any(
                arguments[index] == "-m" and arguments[index + 1] == "swipeswitch"
                for index in range(len(arguments) - 1)
            )
            script_match = (
                Path(arguments[0]).name == "swipeswitch"
                or (len(arguments) > 1 and Path(arguments[1]).name == "swipeswitch")
            )
            # Do not treat the control panel or conflict helper as the engine.
            if module_match or script_match:
                matches.append(int(entry.name))
        return matches

    def is_running(self) -> bool:
        try:
            result = self._systemctl("is-active", "--quiet", SERVICE_NAME)
        except (OSError, subprocess.SubprocessError):
            if self._legacy_processes():
                return True
            raise
        return result.returncode == 0 or bool(self._legacy_processes())

    def start(self) -> None:
        self._reload()
        # The user manager may not inherit the graphical session environment
        # when launched outside the desktop's own autostart sequence.
        self._systemctl(
            "import-environment",
            "DISPLAY",
            "XAUTHORITY",
            "DBUS_SESSION_BUS_ADDRESS",
            "XDG_CURRENT_DESKTOP",
        )
        result = self._systemctl("start", SERVICE_NAME)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "could not start SwipeSwitch").strip()
            raise RuntimeError(detail)

    def stop(self) -> None:
        try:
            active = self._systemctl("is-active", "--quiet", SERVICE_NAME).returncode == 0
        except (OSError, subprocess.SubprocessError):
            active = False

        if active:
            self._reload()
            result = self._systemctl("stop", SERVICE_NAME)
            if result.returncode != 0:
                detail = (result.stderr or result.stdout or "could not stop SwipeSwitch").strip()
                raise RuntimeError(detail)

        # Compatibility path for an engine started manually or by an older
        # autostart entry. SIGTERM invokes SwipeSwitch's normal listener cleanup.
        legacy_pids = self._legacy_processes()
        if not legacy_pids:
            # If no service was active and systemd itself is unavailable,
            # surface that rather than pretending that a stop succeeded.
            if not active:
                self._reload()
            return

        for pid in legacy_pids:
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            except PermissionError as exc:
                raise RuntimeError(f"Permission denied stopping SwipeSwitch process {pid}") from exc

        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            remaining = set(legacy_pids).intersection(self._legacy_processes())
            if not remaining:
                return
            time.sleep(0.1)
        remaining = set(legacy_pids).intersection(self._legacy_processes())
        if remaining:
            raise RuntimeError(
                "SwipeSwitch did not exit after SIGTERM (processes: "
                + ", ".join(map(str, sorted(remaining)))
                + "). No force-kill was attempted."
            )

    def is_autostart_enabled(self) -> bool:
        return self.autostart_file.is_file()

    def set_autostart(self, enabled: bool) -> None:
        """Enable/disable login startup without starting or stopping now."""
        if enabled:
            self.ensure_unit()
            self._reload()
            self.autostart_file.parent.mkdir(parents=True, exist_ok=True)
            helper = (
                shutil.which("swipeswitch-session-start")
                or str(Path.home() / ".local" / "bin" / "swipeswitch-session-start")
            )
            if not Path(helper).exists():
                helper = "/usr/bin/swipeswitch-session-start"
            content = (
                "[Desktop Entry]\n"
                "Type=Application\n"
                "Name=SwipeSwitch Gesture Service\n"
                "Comment=Start SwipeSwitch touchpad gestures at login\n"
                f"Exec={helper}\n"
                "Terminal=false\n"
                "X-GNOME-Autostart-enabled=true\n"
            )
            temporary = self.autostart_file.with_suffix(".desktop.tmp")
            temporary.write_text(content, encoding="utf-8")
            temporary.replace(self.autostart_file)
        else:
            try:
                self.autostart_file.unlink()
            except FileNotFoundError:
                pass


def session_start() -> int:
    """Import the current desktop environment and start the user service."""
    subprocess.run(
        [
            "systemctl", "--user", "import-environment", "DISPLAY",
            "XAUTHORITY", "DBUS_SESSION_BUS_ADDRESS", "XDG_CURRENT_DESKTOP",
        ],
        check=False,
    )
    return subprocess.run(["systemctl", "--user", "start", SERVICE_NAME], check=False).returncode
