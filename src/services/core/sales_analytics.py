"""
Facade for Sales Analytics.
Delegates to modular subpackage in src.services.core.sales_analytics.
"""
from src.services.core.sales_analytics.service import SalesAnalytics

__all__ = [
    "SalesAnalytics",
]
