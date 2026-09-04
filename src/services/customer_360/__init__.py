"""
Customer 360 Ecosystem Package.

Provides omnichannel client data aggregation, Obsidian Second Brain synchronization,
and AI-driven 360-degree client briefings.
"""
from src.services.customer_360.models import CallInteraction, Customer360Profile
from src.services.customer_360.collector import Customer360Collector
from src.services.customer_360.obsidian_syncer import Customer360ObsidianSyncer
from src.services.customer_360.query_engine import Customer360QueryEngine

__all__ = [
    "CallInteraction",
    "Customer360Profile",
    "Customer360Collector",
    "Customer360ObsidianSyncer",
    "Customer360QueryEngine",
]
