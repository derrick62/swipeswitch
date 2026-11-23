"""Application configuration: load, validate, and expose as a typed dataclass."""
from __future__ import annotations

import dataclasses
import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)


@dataclasses.dataclass
class Config:
    """All runtime-tunable options for SwipeSwitch.

    Field default values are the single source of truth; there is no separate
    DEFAULTS dict.  ``load_config`` merges the TOML file against these
    defaults using ``dataclasses.fields()`` so the two can never drift apart.
    """

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
    thumbnails: bool = True
    thumb_budget_ms: int = 150
    theme: str = "dark"
    monitor: str = "primary"
    # Not serialised; set by load_config after the file is located.
    config_path: Path | None = dataclasses.field(default=None, repr=False)

    def validate(self) -> "Config":
        """Raise ValueError for bad values; warn-and-coerce for fixable ones."""
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


def _default_config_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")
    return Path(base) / "swipeswitch" / "config.toml"


def _default_toml_text() -> str:
    return """\
# SwipeSwitch configuration
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


def load_config(path: str | Path | None = None) -> Config:
    """Return a validated Config from *path*, or XDG default location.

    If the file does not exist it is created with safe defaults.  Values
    present in the file override the dataclass defaults; unknown keys are
    silently ignored so that future config fields remain backward-compatible.
    """
    config_path = Path(path).expanduser() if path else _default_config_path()

    if not config_path.exists():
        config_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            config_path.write_text(_default_toml_text(), encoding="utf-8")
            config_path.chmod(0o600)
        except OSError as exc:
            log.warning("Could not create config file: %s", exc)

    raw: dict = {}
    if config_path.exists():
        try:
            import tomllib  # Python 3.11+
        except ImportError:
            try:
                import tomli as tomllib  # type: ignore[no-redef]
            except ImportError as exc:
                raise RuntimeError(
                    "Python 3.11+ is required for TOML parsing (or install tomli)."
                ) from exc
        try:
            raw = tomllib.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            log.warning("Invalid config (%s); using defaults", exc)

    # Build kwargs from dataclass field defaults, overriding with file values.
    # ``config_path`` is excluded because it is not a serialised option.
    kwargs = {
        f.name: raw.get(f.name, f.default)
        for f in dataclasses.fields(Config)
        if f.name != "config_path"
    }
    cfg = Config(**kwargs, config_path=config_path)

    try:
        return cfg.validate()
    except (TypeError, ValueError) as exc:
        log.warning("Invalid config value (%s); falling back to defaults", exc)
        return Config(config_path=config_path).validate()
