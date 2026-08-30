"""
Facade for AmoCRMSync.
Delegates to modular implementations in src.services.core.crm.amocrm.
"""

from src.services.core.crm.amocrm.auth import retry_with_backoff, _plain_secret
from src.services.core.crm.amocrm.sync import AmoCRMSync

__all__ = ["AmoCRMSync", "retry_with_backoff", "_plain_secret"]

