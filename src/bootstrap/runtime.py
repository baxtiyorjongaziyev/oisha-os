"""
Facade for runtime boot orchestrator.
Delegates to modular subpackage in src.bootstrap.orchestration.
"""
from src.bootstrap.orchestration.boot import boot_application

__all__ = ["boot_application"]
