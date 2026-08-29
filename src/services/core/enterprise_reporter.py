"""
Facade for EnterpriseReporter.
Delegates to modular subpackage in src.services.reporter.
"""
from src.services.reporter import EnterpriseReporter

__all__ = ["EnterpriseReporter"]
