"""Marketing attribution service.

Demo KPI values are intentionally forbidden: callers must receive an explicit
unavailable response until real Meta Ads and AmoCRM attribution are wired.
"""

from typing import Any, Dict


class MarketingAttributionService:
    def __init__(self, amocrm_sync=None, db=None):
        self.amo = amocrm_sync
        self.db = db

    def get_performance_data(self, start_date: str, end_date: str) -> Dict[str, Any]:
        raise RuntimeError(
            "Marketing attribution real Meta Ads va AmoCRM manbalari ulanmaguncha mavjud emas"
        )
