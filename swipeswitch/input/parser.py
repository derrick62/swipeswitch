"""Parse raw libinput debug-events output into normalised GestureEvents.

This module has no I/O dependency — it is a pure text-to-dataclass
transformation and can be unit-tested without a running X11 session or
a libinput subprocess.
"""
from __future__ import annotations

import re

from .events import GestureEvent

# libinput versions/builds may include an optional sequence number between the
# event name and timestamp.  Accept both:
#   GESTURE_SWIPE_UPDATE +2.203s 3 ...
#   GESTURE_SWIPE_UPDATE 2 +2.209s 3 ...
_EVENT_RE = re.compile(r"\bGESTURE_SWIPE_(BEGIN|UPDATE|END)\b")
_HEADER_RE = re.compile(
    r"\bGESTURE_SWIPE_(?:BEGIN|UPDATE|END)\b"
    r"(?:\s+\d+)?\s+[+\-]?\d+(?:\.\d+)?s\s+(\d+)\b"
)
_PAIR_RE = re.compile(
    r"([+\-]?\d+(?:\.\d+)?)\s*/\s*([+\-]?\d+(?:\.\d+)?)"
)
_DX_RE = re.compile(r"\bdx\s*[=:]?\s*([+\-]?\d+(?:\.\d+)?)", re.I)
_DY_RE = re.compile(r"\bdy\s*[=:]?\s*([+\-]?\d+(?:\.\d+)?)", re.I)

_KIND_MAP = {"BEGIN": "begin", "UPDATE": "update", "END": "end"}


def parse_libinput_line(
    line: str, use_unaccelerated: bool = False
) -> GestureEvent | None:
    """Parse one libinput swipe line, tolerating optional sequence numbers.

    Returns ``None`` for lines that do not contain a recognised swipe event.
    """
    event_match = _EVENT_RE.search(line)
    header_match = _HEADER_RE.search(line)

    if not event_match or not header_match:
        return None

    kind_raw = event_match.group(1)
    fingers = int(header_match.group(1))
    dx = dy = 0.0

    if kind_raw == "UPDATE":
        tail = line[header_match.end():]
        pairs = list(_PAIR_RE.finditer(tail))

        if pairs:
            # libinput prints accelerated movement first; an optional
            # unaccelerated pair follows in parentheses.
            selected = (
                pairs[-1]
                if use_unaccelerated and len(pairs) > 1
                else pairs[0]
            )
            dx = float(selected.group(1))
            dy = float(selected.group(2))
        else:
            xm = _DX_RE.search(tail)
            ym = _DY_RE.search(tail)
            if xm:
                dx = float(xm.group(1))
            if ym:
                dy = float(ym.group(1))

    return GestureEvent(
        kind=_KIND_MAP[kind_raw],
        fingers=fingers,
        dx=dx,
        dy=dy,
        cancelled=(kind_raw == "END" and "cancelled" in line.lower()),
    )
