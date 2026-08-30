"""
Facade for Oisha-OS ERP Telegram command handlers.
Delegates to modular subpackage in src.services.core.finance.erp.
"""
from src.services.core.finance.erp.helpers import (
    _reply,
    _sender_id,
    _check_permission,
    _current_period,
)
from src.services.core.finance.erp.reports import (
    cmd_erp_holat,
    cmd_moliya,
    cmd_jamoa,
    cmd_loyihalar,
    cmd_erp_salomatlik,
)
from src.services.core.finance.erp.mutations import (
    cmd_qo_shish_loyiha,
    cmd_xarajat_qosh,
)
from src.services.core.finance.erp.registry import (
    COMMAND_REGISTRY,
    ERP_HELP_TEXT,
)

__all__ = [
    "_reply",
    "_sender_id",
    "_check_permission",
    "_current_period",
    "cmd_erp_holat",
    "cmd_moliya",
    "cmd_jamoa",
    "cmd_loyihalar",
    "cmd_erp_salomatlik",
    "cmd_qo_shish_loyiha",
    "cmd_xarajat_qosh",
    "COMMAND_REGISTRY",
    "ERP_HELP_TEXT",
]
