"""
Facade for ProposalRepository.
Delegates to modular subpackage in src.db.repositories.proposals.
"""
from src.db.repositories.proposals.constants import (
    VALID_STATUSES,
    ALLOWED_TRANSITIONS,
    _LEGACY_AGENT_TABLE_MARKERS,
)
from src.db.repositories.proposals.repository import ProposalRepository

__all__ = [
    "VALID_STATUSES",
    "ALLOWED_TRANSITIONS",
    "_LEGACY_AGENT_TABLE_MARKERS",
    "ProposalRepository",
]
