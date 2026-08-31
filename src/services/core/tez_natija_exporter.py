"""
Facade for TezNatijaExporter.
Delegates to modular subpackage in src.services.core.tez_natija.
"""
from src.services.core.tez_natija.sheets_exporter import (
    TEZ_NATIJA_GROUPS,
    SHEET_NAME,
    SHEET_HEADERS,
)
from src.services.core.tez_natija.amocrm_exporter import (
    _AMO_PIPELINE_ID,
    _AMO_STATUS_ID,
    _AMO_DELAY,
)
from src.services.core.tez_natija.exporter import TezNatijaExporter

__all__ = [
    "TezNatijaExporter",
    "TEZ_NATIJA_GROUPS",
    "SHEET_NAME",
    "SHEET_HEADERS",
    "_AMO_PIPELINE_ID",
    "_AMO_STATUS_ID",
    "_AMO_DELAY",
]
