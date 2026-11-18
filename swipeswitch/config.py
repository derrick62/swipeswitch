from __future__ import annotations

import logging
import os
from dataclasses import dataclass, fields
from pathlib import Path

log = logging.getLogger(__name__)

DEFAULTS = {
    "fingers": 3, "step_px": 80, "show_threshold_px": 35,
    "flick_min_px": 40, "invert_direction": False,
    "current_workspace_only": True, "order": "mru",
    "gesture_timeout": 3.0, "use_unaccelerated": False,
    "touchpad_device": "auto", "thumbnails": False,
    "thumb_budget_ms": 150, "theme": "dark", "monitor": "primary",
}

@dataclass
class Config:
    fingers: int = 3
    step_px: int = 80
    show_threshold_px: int = 35
    flick_min_px: int = 40
    invert_direction: bool = False
    current_workspace_only: bool = True
    order: str = "mru"
    gesture_timeout: float = 3.0
    use_unaccelerated: bool = False
    touchpad_device: str = "auto"
    thumbnails: bool = False
    thumb_budget_ms: int = 150
    theme: str = "dark"
    monitor: str = "primary"
    config_path: Path | None = None

    def validate(self):
        if not 2 <= self.fingers <= 5:
            raise ValueError("fingers must be between 2 and 5")
        for key in ("step_px", "show_threshold_px", "flick_min_px", "thumb_budget_ms"):
            if getattr(self, key) <= 0:
                raise ValueError(f"{key} must be greater than zero")
        if self.gesture_timeout <= 0:
            raise ValueError("gesture_timeout must be greater than zero")
        if self.order not in {"mru", "fixed"}:
            raise ValueError("order must be 'mru' or 'fixed'")
        if self.theme not in {"dark", "light", "auto"}:
            raise ValueError("theme must be 'dark', 'light' or 'auto'")
        if self.monitor != "primary":
            log.warning("Only monitor='primary' is implemented in v1; using primary")
            self.monitor = "primary"
        return self


def default_config_path():
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "swipeswitch" / "config.toml"


def _default_text():
    return """# SwipeSwitch core preview configuration
touchpad_device = "auto"
step_px = 80
show_threshold_px = 35
use_unaccelerated = false
current_workspace_only = true
order = "mru"
gesture_timeout = 3.0
theme = "dark"
monitor = "primary"
"""


def load_config(path=None):
    config_path = Path(path).expanduser() if path else default_config_path()
    if not config_path.exists():
        config_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            config_path.write_text(_default_text(), encoding="utf-8")
            config_path.chmod(0o600)
        except OSError as exc:
            log.warning("Could not create config file: %s", exc)

    raw = {}
    if config_path.exists():
        try:
            import tomllib
        except ImportError:
            try:
                import tomli as tomllib
            except ImportError as exc:
                raise RuntimeError("Python 3.11+ is required for TOML parsing.") from exc
        try:
            raw = tomllib.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            log.warning("Invalid config (%s); using defaults", exc)

    values = {key: raw.get(key, value) for key, value in DEFAULTS.items()}
    cfg = Config(**values, config_path=config_path)
    try:
        return cfg.validate()
    except (TypeError, ValueError) as exc:
        log.warning("Invalid config value (%s); using defaults", exc)
        return Config(config_path=config_path).validate()
