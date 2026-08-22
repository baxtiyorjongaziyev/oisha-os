"""Central Bank of Uzbekistan (CBU) currency exchange rate service."""
from __future__ import annotations

import json
import logging
import urllib.request
from typing import Optional

logger = logging.getLogger(__name__)

_CBU_USD_URL = "https://cbu.uz/uz/arkhiv-kursov-valyut/json/USD/"
_cached_rate: Optional[float] = None


def get_live_usd_rate() -> float:
    """Fetch current official USD/UZS rate from Central Bank of Uzbekistan."""
    global _cached_rate
    try:
        req = urllib.request.Request(
            _CBU_USD_URL,
            headers={"User-Agent": "JonBranding-ERP/2.0"}
        )
        with urllib.request.urlopen(req, timeout=5.0) as resp:  # nosec B310
            data = json.loads(resp.read().decode())
            if data and isinstance(data, list):
                rate_str = data[0].get("Rate")
                if rate_str:
                    rate = float(rate_str)
                    _cached_rate = rate
                    logger.info("[CBU] Live USD rate fetched: %s UZS (%s)", rate, data[0].get("Date"))
                    return rate
    except Exception as exc:
        logger.warning("[CBU] Failed to fetch live rate from CBU: %s", exc)

    # Fallback to cached or standard default
    return _cached_rate or 11850.0
