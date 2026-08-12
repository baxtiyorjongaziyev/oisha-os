# src/__init__.py
"""Package initialization.
Provides a fallback global logger via builtins if not already defined.
"""
import builtins
from .common.logger import logger as _fallback_logger
# Expose fallback logger globally if not present
if not hasattr(builtins, "logger"):
    builtins.logger = _fallback_logger

