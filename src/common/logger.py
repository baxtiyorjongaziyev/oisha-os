# src/common/logger.py
"""Central logger module.
Provides a fallback logger that can be imported anywhere.
If a module already defines its own ``logger`` (e.g., via ``structlog``), that definition takes precedence.
"""
import importlib
import sys
# Ensure we import the standard library logging, not the project stub
if '' in sys.path:
    sys.path.remove('')
logging = importlib.import_module('logging')

# Basic configuration – can be overridden by the application if needed.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

# Export a module‑level logger instance.
logger = logging.getLogger("oisha")
