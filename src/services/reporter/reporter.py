"""
EnterpriseReporter class composed of modular mixins.
"""
from typing import Any, Dict, List, Optional, Set
import structlog

from src.database import Database
from src.services.core.crm.crm_service import CRMService
from src.services.core.crm.amocrm_pipeline_config import (
    LEGACY_CLOSER_PIPELINE_ID,
    SALES_PIPELINE_ID,
)
from src.services.reporter.efficiency import EfficiencyMixin
from src.services.reporter.audit import AuditMixin
from src.services.reporter.plans import PlansMixin

logger = structlog.get_logger()


class EnterpriseReporter(EfficiencyMixin, AuditMixin, PlansMixin):
    """
    Jamoa samaradorligi va Plan-Fakt hisobotlarini tayyorlash xizmati.
    """

    def __init__(
        self,
        db: Optional[Database] = None,
        crm: Optional[CRMService] = None,
        airtable: Any = None,
        amocrm: Any = None,
        hisobchi: Any = None,
        gsheets: Any = None,
    ):
        self.db = db
        self.crm = crm or amocrm
        self.airtable = airtable
        self.amocrm = self.crm
        self.hisobchi = hisobchi
        self.gsheets = gsheets

        # Standart statuslar (AmoCRM defaults)
        self.WON_STATUS = 142
        self.LOST_STATUS = 143
        self.HUNTER_PIPELINE_ID = SALES_PIPELINE_ID
        self.CLOSER_PIPELINE_ID = LEGACY_CLOSER_PIPELINE_ID
