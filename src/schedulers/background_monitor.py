"""
Facade for Background Monitor.
Delegates to modular subpackage in src.schedulers.bg_monitor.
"""
from src.schedulers.bg_monitor import (
    BackgroundMonitor,
    _env_enabled,
)

__all__ = [
    "BackgroundMonitor",
    "_env_enabled",
]
