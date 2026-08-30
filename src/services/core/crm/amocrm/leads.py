"""
AmoCRM Leads composite mixin.
"""
from src.services.core.crm.amocrm.leads_create import AmoCRMLeadsCreateMixin
from src.services.core.crm.amocrm.leads_query import AmoCRMLeadsQueryMixin
from src.services.core.crm.amocrm.leads_mutate import AmoCRMLeadsMutateMixin
from src.services.core.crm.amocrm.auth import _plain_secret, retry_with_backoff

__all__ = [
    "AmoCRMLeadsMixin",
    "_plain_secret",
    "retry_with_backoff",
]


class AmoCRMLeadsMixin(
    AmoCRMLeadsCreateMixin,
    AmoCRMLeadsQueryMixin,
    AmoCRMLeadsMutateMixin,
):
    """Combined AmoCRM leads mixin."""
    pass
