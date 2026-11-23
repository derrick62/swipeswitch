"""Touchpad discovery and a restartable libinput debug-events listener."""
from __future__ import annotations

import logging
import re
import shutil
import subprocess
import threading
from collections.abc import Iterable

from .parser import parse_libinput_line  # parsing logic lives in its own module

log = logging.getLogger(__name__)


def detect_touchpad(configured: str = "auto") -> str:
    """Find a gesture-capable pointer device, preferring named touchpads."""
    if configured != "auto":
        if not re.fullmatch(r"/dev/input/event\d+", configured):
            raise RuntimeError(
                "touchpad_device must be 'auto' or a /dev/input/eventX path"
            )
        return configured

    if not shutil.which("libinput"):
        raise RuntimeError("libinput was not found. Install libinput-tools.")

    try:
        output = subprocess.run(
            ["libinput", "list-devices"],
            check=True,
            capture_output=True,
            text=True,
            timeout=8,
        ).stdout
    except (subprocess.SubprocessError, OSError) as exc:
        raise RuntimeError(f"Could not list input devices: {exc}") from exc

    candidates = []

    for block in re.split(r"\n\s*\n", output):
        capabilities = re.search(r"(?im)^\s*Capabilities:\s*(.+)$", block)
        if not capabilities:
            continue

        capability_names = set(capabilities.group(1).lower().split())

        if not {"pointer", "gesture"}.issubset(capability_names):
            continue

        kernel = re.search(r"(?im)^\s*Kernel:\s*(/dev/input/event\d+)\b", block)
        if not kernel:
            continue

        name_match = re.search(r"(?im)^\s*Device:\s*(.+)$", block)
        name = name_match.group(1).strip() if name_match else kernel.group(1)

        score = 2 if "touchpad" in name.lower() else 1
        candidates.append((score, kernel.group(1), name))

    if not candidates:
        raise RuntimeError(
            "No pointer device with libinput gesture capability was found. "
            "Check `libinput list-devices` and configure touchpad_device manually."
        )

    candidates.sort(key=lambda item: item[0], reverse=True)

    if len(candidates) > 1:
        log.warning(
            "Multiple gesture-capable pointer devices found; selected %s (%s)",
            candidates[0][2],
            candidates[0][1],
        )

    return candidates[0][1]


class LibinputListener:
    """Read swipe events from one device and deliver them to a callback."""

    def __init__(
        self,
        device,
        fingers,
        callback,
        debug=False,
        use_unaccelerated=False,
    ):
        self.device = device

        if isinstance(fingers, int):
            self.fingers = {fingers}
        elif isinstance(fingers, Iterable):
            self.fingers = {int(value) for value in fingers}
        else:
            raise TypeError("fingers must be an integer or an iterable of integers")

        if not self.fingers or any(value < 1 for value in self.fingers):
            raise ValueError(
                "fingers must contain at least one positive finger count"
            )

        self.callback = callback
        self.debug = debug
        self.use_unaccelerated = bool(use_unaccelerated)

        self._stop = threading.Event()
        self._thread = None
        self._process = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="swipeswitch-libinput",
            daemon=True,
        )
        self._thread.start()

    def stop(self):
        self._stop.set()
        process = self._process
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=1)
        if self._thread:
            self._thread.join(timeout=2)

    def _run(self):
        backoff = 1.0

        while not self._stop.is_set():
            try:
                self._process = subprocess.Popen(
                    ["stdbuf", "-oL", "libinput", "debug-events", "--device", self.device],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    bufsize=1,
                )
                assert self._process.stdout is not None
                backoff = 1.0

                while not self._stop.is_set():
                    line = self._process.stdout.readline()
                    if line == "":
                        break

                    event = parse_libinput_line(line, self.use_unaccelerated)
                    if event is None or event.fingers not in self.fingers:
                        continue

                    if self.debug:
                        log.debug(
                            "Gesture %s fingers=%d dx=%.2f dy=%.2f",
                            event.kind, event.fingers, event.dx, event.dy,
                        )

                    try:
                        self.callback(event)
                    except Exception:
                        log.exception("Gesture callback failed")

                if self._process.poll() is None:
                    self._process.terminate()
                    try:
                        self._process.wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        self._process.kill()
                        self._process.wait(timeout=1)

            except FileNotFoundError:
                log.error(
                    "libinput or stdbuf not found; install libinput-tools and coreutils"
                )
                return

            except OSError as exc:
                if "Permission" in str(exc):
                    log.error(
                        "Permission denied reading %s. Review input-group access; see README.md.",
                        self.device,
                    )
                    return
                log.error("libinput listener error: %s", exc)

            if not self._stop.is_set():
                log.warning(
                    "libinput listener stopped; retrying in %.1fs", backoff
                )
                self._stop.wait(backoff)
                backoff = min(backoff * 2, 15.0)
