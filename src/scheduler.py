"""
Facade for background scheduler.
Delegates to modular subpackage in src.schedulers.main_loop.
"""
from src.schedulers.main_loop import (
    _env_int,
    _is_due,
    background_monitor_task,
)

__all__ = [
    "_env_int",
    "_is_due",
    "background_monitor_task",
]
