"""Normalised input events shared by the listener and gesture recogniser."""
from dataclasses import dataclass


@dataclass(frozen=True)
class GestureEvent:
    kind: str
    fingers: int = 0
    dx: float = 0.0
    dy: float = 0.0
    cancelled: bool = False
    timestamp: float | None = None
