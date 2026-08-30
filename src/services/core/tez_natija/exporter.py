"""
Tez Natija Exporter composition class.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from src.services.core.tez_natija.sheets_exporter import TezNatijaSheetsMixin
from src.services.core.tez_natija.amocrm_exporter import TezNatijaAmoCRMMixin

if TYPE_CHECKING:
    from src.services.core.gsheets import GoogleSheetsSync
    from src.services.core.crm.amocrm_sync import AmoCRMSync
    from src.database import Database


class TezNatijaExporter(TezNatijaSheetsMixin, TezNatijaAmoCRMMixin):
    """Tez Natija guruhlaridan a'zolarni CRM formatida export qiladi."""

    def __init__(
        self,
        sheets: Optional["GoogleSheetsSync"] = None,
        amocrm: Optional["AmoCRMSync"] = None,
        db: Optional["Database"] = None,
    ):
        self.sheets = sheets
        self.amocrm = amocrm
        self.db = db
        self._worksheet = None
