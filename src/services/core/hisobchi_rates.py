"""Hisobchi Rates — fetch daily currency rates from bank.uz."""

from __future__ import annotations

import logging
from typing import Optional
import httpx

logger = logging.getLogger(__name__)

_BANK_UZ_URL = "https://bank.uz/uz/currency/conversion-rates"


async def fetch_bank_uz_rates(timeout: int = 15) -> Optional[dict]:
    """Fetch USD/UZS rates from bank.uz (CB rate)."""
    try:
        async with httpx.AsyncClient(timeout=timeout, verify=False) as c:
            r = await c.get("https://cbu.uz/uz/arkhiv-kursov-valyut/json/")
            if r.status_code == 200:
                data = r.json()
                for item in data:
                    if item.get("Ccy") == "USD":
                        return {
                            "USD": {
                                "buy": float(item.get("Rate", 0)) * 0.995,
                                "sell": float(item.get("Rate", 0)) * 1.005,
                                "cb": float(item.get("Rate", 0)),
                                "date": item.get("Date", ""),
                            }
                        }
    except Exception as exc:
        logger.warning("[RATES] CBU uz failed: %s", exc)

    try:
        async with httpx.AsyncClient(timeout=timeout, verify=False) as c:
            r = await c.get("https://nbu.uz/uz/exchange-rates/json/")
            if r.status_code == 200:
                data = r.json()
                for item in data:
                    if item.get("code") == "USD":
                        rate = float(item.get("nbu_cell_price", 0))
                        return {
                            "USD": {
                                "buy": rate * 0.995,
                                "sell": rate * 1.005,
                                "cb": rate,
                                "date": item.get("date", ""),
                            }
                        }
    except Exception as exc:
        logger.warning("[RATES] NBU uz failed: %s", exc)

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as c:
            r = await c.get(
                "https://api.exchangerate-api.com/v4/latest/USD",
                headers={"User-Agent": "Mozilla/5.0"},
            )
            if r.status_code == 200:
                data = r.json()
                uzs = data.get("rates", {}).get("UZS", 0)
                if uzs:
                    return {
                        "USD": {
                            "buy": float(uzs) * 0.995,
                            "sell": float(uzs) * 1.005,
                            "cb": float(uzs),
                            "date": data.get("date", ""),
                        }
                    }
    except Exception as exc:
        logger.warning("[RATES] exchangerate-api failed: %s", exc)

    return None
