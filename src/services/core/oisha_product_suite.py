"""
Facade for Oisha Product Suite.
Delegates to modular subpackage in src.services.core.product_suite.
"""
from src.services.core.product_suite.models import (
    DEEPSALES_URL,
    METASELL_URL,
    REPORTAGRAM_URL,
    ProductPillar,
    UnifiedWorkflow,
    CallTagPolicy,
    TaskDecisionRule,
    RnpSignal,
)
from src.services.core.product_suite.definitions import (
    get_product_pillars,
    get_unified_workflows,
    get_call_tag_policy,
    get_task_decision_rules,
    get_rnp_signals,
)
from src.services.core.product_suite.suite import build_oisha_sales_os_suite

__all__ = [
    "DEEPSALES_URL",
    "METASELL_URL",
    "REPORTAGRAM_URL",
    "ProductPillar",
    "UnifiedWorkflow",
    "CallTagPolicy",
    "TaskDecisionRule",
    "RnpSignal",
    "get_product_pillars",
    "get_unified_workflows",
    "get_call_tag_policy",
    "get_task_decision_rules",
    "get_rnp_signals",
    "build_oisha_sales_os_suite",
]
