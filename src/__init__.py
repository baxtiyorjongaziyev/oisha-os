# src/__init__.py
"""Package initialization.
Provides a fallback global logger via builtins if not already defined.
"""
import builtins
from .common.logger import logger as _fallback_logger
from typing import Optional

# Expose fallback logger globally if not present
if not hasattr(builtins, "logger"):
    builtins.logger = _fallback_logger

# Make Optional globally available
builtins.Optional = Optional

# Prod userbot session faqat Hetzner prod hostida, bitta jarayonda ulanadi
# (AuthKeyDuplicatedError himoyasi). Telethon connect global oʼraladi.
try:
    from .services.core.telegram.userbot_host_guard import install as _install_userbot_guard

    _install_userbot_guard()
except Exception as _guard_exc:  # pragma: no cover - import muammosi bootni toʼxtatmasin
    _fallback_logger.warning("[USERBOT GUARD] install failed: %s", _guard_exc)
