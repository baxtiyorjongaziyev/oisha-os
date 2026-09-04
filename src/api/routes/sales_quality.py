"""
Facade for sales quality routes.
Delegates to modular subpackage in src.services.sales_quality.
"""
from src.services.sales_quality.helpers import (
    _safe_json_list,
    _row_to_dict,
    _score_to_risk,
    _format_duration,
    _avatar,
    _build_empty_sales_quality,
    _fetch_call_analysis_rows,
    _build_sales_quality_payload,
    _build_manager_cards_payload,
    _fetch_manager_card_rows,
    RADAR_AXES,
)
from src.services.sales_quality.schemas import SalesQualityAnalysisRequest
from src.services.sales_quality.router import (
    router,
    get_sales_quality_overview,
    get_sales_quality_manager_cards,
    ingest_sales_quality_analysis,
    sales_quality_conversion_overview,
    sales_quality_dashboard_html,
)

__all__ = [
    "_safe_json_list",
    "_row_to_dict",
    "_score_to_risk",
    "_format_duration",
    "_avatar",
    "_build_empty_sales_quality",
    "_fetch_call_analysis_rows",
    "_build_sales_quality_payload",
    "_build_manager_cards_payload",
    "_fetch_manager_card_rows",
    "RADAR_AXES",
    "SalesQualityAnalysisRequest",
    "router",
    "get_sales_quality_overview",
    "get_sales_quality_manager_cards",
    "ingest_sales_quality_analysis",
    "sales_quality_conversion_overview",
    "sales_quality_dashboard_html",
]
