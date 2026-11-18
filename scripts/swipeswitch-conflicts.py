#!/usr/bin/env python3
"""Detect and optionally disable competing Linux touchpad gesture handlers.

This helper is deliberately conservative: it only recognises a small allowlist
of known gesture managers, never uninstalls packages, and changes autostart
state only after an explicit interactive confirmation.
"""
from __future__ import annotations

import argparse
import configparser
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ALIASES = {
    "libinput-gestures", "libinput-gestures-qt", "touchegg",
    "fusuma", "gebaar", "gebaar-libinput",
}
SERVICE_NAMES = {
    "libinput-gestures.service", "touchegg.service", "fusuma.service",
    "gebaar.service",
}


def _command_tokens(pid: str) -> list[str]:
    try:
        raw = Path("/proc", pid, "cmdline").read_bytes()
        return [part.decode(errors="replace") for part in raw.split(b"\0") if part]
    except (OSError, PermissionError):
        return []


def _matches(tokens: list[str]) -> bool:
    return any(Path(token).name in ALIASES for token in tokens)


def running_handlers() -> list[tuple[int, str]]:
    found = []
    proc = Path("/proc")
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        tokens = _command_tokens(entry.name)
        if tokens and _matches(tokens):
            found.append((int(entry.name), " ".join(tokens)))
    return sorted(found)


def autostart_handlers() -> list[Path]:
    directory = Path.home() / ".config" / "autostart"
    found = []
    if not directory.is_dir():
        return found
    for desktop_file in directory.glob("*.desktop"):
        parser = configparser.ConfigParser(interpolation=None)
        try:
            parser.read(desktop_file, encoding="utf-8")
            command = parser.get("Desktop Entry", "Exec", fallback="")
        except (OSError, configparser.Error):
            continue
        # Desktop Exec values may contain field codes; tokenise only the first
        # executable and compare its basename against the explicit allowlist.
        executable = command.strip().split(maxsplit=1)[0] if command.strip() else ""
        if Path(executable).name in ALIASES:
            found.append(desktop_file)
    return sorted(found)


def _systemctl(*args: str, user: bool = True) -> subprocess.CompletedProcess[str]:
    command = ["systemctl"]
    if user:
        command.append("--user")
    command.extend(args)
    return subprocess.run(command, text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.DEVNULL, check=False)


def service_units(user: bool = True) -> list[str]:
    if not shutil_which("systemctl"):
        return []
    result = _systemctl("list-unit-files", "--type=service", "--no-legend", user=user)
    found = []
    for line in result.stdout.splitlines():
        fields = line.split()
        if (len(fields) >= 2 and fields[0] in SERVICE_NAMES
                and fields[1] in {"enabled", "enabled-runtime"}):
            found.append(fields[0])
    return sorted(set(found))


def shutil_which(command: str) -> str | None:
    # Avoid importing shutil solely for one lookup in this small helper.
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        candidate = Path(directory) / command
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def confirm(prompt: str) -> bool:
    if not sys.stdin.isatty():
        print(f"\n{prompt} [not changed: no interactive terminal]")
        return False
    try:
        return input(f"{prompt} [y/N] ").strip().lower() in {"y", "yes"}
    except EOFError:
        return False


def report(*, system_only: bool = False) -> tuple[list[tuple[int, str]], list[Path], list[str], list[str]]:
    processes = running_handlers()
    # Debian maintainer scripts run as root and cannot reliably identify the
    # desktop user's home directory or user systemd manager. Keep that report
    # explicitly system-scoped; the user command performs the full scan.
    autostart = [] if system_only else autostart_handlers()
    user_units = [] if system_only else service_units(user=True)
    system_units = service_units(user=False)
    if not any((processes, autostart, user_units, system_units)):
        print("No known competing touchpad gesture handlers detected.")
        return processes, autostart, user_units, system_units

    print("Potential touchpad gesture conflicts detected:")
    for pid, command in processes:
        print(f"  Running process {pid}: {command}")
    for unit in user_units:
        print(f"  User systemd unit: {unit}")
    for unit in system_units:
        print(f"  System systemd unit: {unit}")
    for path in autostart:
        print(f"  XFCE/user autostart: {path}")
    print("\nThese tools may interpret the same three- or four-finger gestures as SwipeSwitch.")
    return processes, autostart, user_units, system_units


def resolve(items) -> None:
    processes, autostart, user_units, system_units = items
    if user_units and confirm("Disable and stop the detected user systemd gesture service(s)?"):
        for unit in user_units:
            result = _systemctl("disable", "--now", unit, user=True)
            print(f"  {unit}: {'disabled/stopped' if result.returncode == 0 else 'could not change'}")

    if system_units and confirm("Disable and stop the detected system gesture service(s) using sudo?"):
        for unit in system_units:
            if not shutil_which("sudo"):
                print(f"  Cannot manage {unit}: sudo was not found.")
                continue
            result = subprocess.run(["sudo", "systemctl", "disable", "--now", unit], check=False)
            print(f"  {unit}: {'disabled/stopped' if result.returncode == 0 else 'could not change'}")

    if autostart and confirm("Disable the detected user autostart entries? (They will be renamed, not deleted.)"):
        for path in autostart:
            target = path.with_name(path.name + ".disabled-by-swipeswitch")
            try:
                path.rename(target)
                print(f"  Disabled {path.name}; preserved as {target.name}")
            except OSError as exc:
                print(f"  Could not disable {path}: {exc}")

    # Stop only remaining matching processes. Managed services were stopped
    # above where possible; this handles manually launched instances.
    remaining = running_handlers()
    if remaining and confirm("Send SIGTERM to the remaining detected gesture process(es) now?"):
        for pid, command in remaining:
            try:
                os.kill(pid, signal.SIGTERM)
                print(f"  Sent SIGTERM to PID {pid}: {command}")
            except ProcessLookupError:
                pass
            except PermissionError:
                print(f"  No permission to stop PID {pid}; left it running.")
        time.sleep(0.25)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resolve", action="store_true",
                        help="interactively offer to stop/disable detected handlers")
    parser.add_argument("--system-only", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    items = report(system_only=args.system_only)
    if args.resolve and any(items):
        resolve(items)
        print("\nConflict check complete. No packages were uninstalled.")
    elif args.resolve and not sys.stdin.isatty():
        print("Run `swipeswitch-conflicts --resolve` in a terminal to review options.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
