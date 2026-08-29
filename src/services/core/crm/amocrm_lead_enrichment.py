"""
Facade for AmoCRM Lead Enrichment.
Delegates to modular subpackage in src.services.core.crm.enrichment.
"""
from src.services.core.crm.enrichment import (
    AmoCRMLeadEnricher,
    LeadEnrichmentResult,
    _clip,
    _extract_role_from_history_item,
    _extract_text_from_history_item,
    _secret_to_text,
    maybe_await,
    normalize_phone,
)

__all__ = [
    "AmoCRMLeadEnricher",
    "LeadEnrichmentResult",
    "_clip",
    "_extract_role_from_history_item",
    "_extract_text_from_history_item",
    "_secret_to_text",
    "maybe_await",
    "normalize_phone",
]
