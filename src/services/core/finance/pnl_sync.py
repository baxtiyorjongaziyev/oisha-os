"""Airtable Monthly P&L transaction linking engine.

Links every transaction to its month's Oylik P&L record. The P&L table computes
Kirim, Chiqim, soliq, dividend and foyda itself via native rollups and formulas,
so this module only maintains the link that feeds them.
"""
import logging
from typing import Any
import httpx

from src.services.core.airtable_config import (
    airtable_records_page,
    airtable_request_headers,
)
from src.settings import settings

logger = logging.getLogger(__name__)

AIRTABLE_API_BASE = "https://api.airtable.com/v0"
DEFAULT_BASE_ID = "app8xoyx1XCumYFXV"
TRX_TABLE_ID = "tblrqxqIzyrvg7XpQ"
PNL_TABLE_ID = "tblAgVaGlVory2yAW"

# Link field on Tranzaksiyalar pointing at the current Oylik P&L table. Verified
# live in Airtable 2026-09: this is a "Link to another record" field. The legacy
# "[ESKI] Oylik P&L (V1 Link)" text field still holds old values and must not be used.
PNL_LINK_FIELD = "Oylik P&L (Hisobot)"

UZBEK_MONTHS = {
    "01": "Yanvar", "02": "Fevral", "03": "Mart", "04": "Aprel",
    "05": "May", "06": "Iyun", "07": "Iyul", "08": "Avgust",
    "09": "Sentabr", "10": "Oktabr", "11": "Noyabr", "12": "Dekabr"
}


def _get_headers() -> dict[str, str]:
    return airtable_request_headers()


async def sync_monthly_pnl() -> dict[str, Any]:
    """Link every transaction to its month's Oylik P&L record."""
    base_id = getattr(settings, "AIRTABLE_BASE_ID", None) or DEFAULT_BASE_ID
    headers = _get_headers()

    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Map each month code to its P&L record
        pnl_resp = await client.get(f"{AIRTABLE_API_BASE}/{base_id}/{PNL_TABLE_ID}?pageSize=100", headers=headers)
        pnl_records, _ = airtable_records_page(pnl_resp, resource="P&L")
        pnl_map = {}
        for r in pnl_records:
            code = r["fields"].get("Oy nomi", "")[:7]
            if code:
                pnl_map[code] = r["id"]

        # 2. Fetch all transactions
        trx_records = []
        offset = None
        while True:
            url = f"{AIRTABLE_API_BASE}/{base_id}/{TRX_TABLE_ID}?pageSize=100"
            if offset:
                url += f"&offset={offset}"
            resp = await client.get(url, headers=headers)
            page_records, offset = airtable_records_page(
                resp,
                resource="transactions",
            )
            trx_records.extend(page_records)
            if not offset:
                break

        # 3. Collect transactions whose link is missing or points at the wrong month
        trx_to_link = []
        for r in trx_records:
            f = r["fields"]
            sana = f.get("Sana", "")
            if not sana or len(sana) < 7:
                continue

            target_pnl_id = pnl_map.get(sana[:7])
            if not target_pnl_id:
                continue

            current_links = f.get(PNL_LINK_FIELD, [])
            if not current_links or current_links[0] != target_pnl_id:
                trx_to_link.append({"id": r["id"], "fields": {PNL_LINK_FIELD: [target_pnl_id]}})

        # 4. Patch the links in batches of 10
        for i in range(0, len(trx_to_link), 10):
            chunk = trx_to_link[i:i+10]
            response = await client.patch(
                f"{AIRTABLE_API_BASE}/{base_id}/{TRX_TABLE_ID}",
                headers=headers,
                json={"records": chunk}
            )
            response.raise_for_status()

        logger.info(
            "[PNL_SYNC] Linked %d transactions across %d months",
            len(trx_to_link),
            len(pnl_map),
        )
        return {
            "status": "ok",
            "months_available": len(pnl_map),
            "transactions_linked": len(trx_to_link),
        }
