"""
Facade for CRMArchiver.
Delegates to modular subpackage in src.services.core.crm.archiver.
"""
from src.services.core.crm.archiver.archiver import CRMArchiver
from src.services.core.crm.archiver.campaign import generate_outreach_campaign
from src.services.core.crm.archiver.schema import (
    init_archiver_tables,
    save_archived_lead_and_campaign,
)

__all__ = [
    "CRMArchiver",
    "generate_outreach_campaign",
    "init_archiver_tables",
    "save_archived_lead_and_campaign",
]
