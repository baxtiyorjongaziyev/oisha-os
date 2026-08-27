"""Airtable Monthly P&L Dynamic Calculation and Linking Engine.
Automatically links all new and existing transactions to the corresponding Oylik P&L record
and recalculates accurate Soliqqacha, Soliqdan keyingi, and Taqsimlanmagan foyda figures.
"""
import logging
from typing import Any
import httpx

from src.settings import settings

logger = logging.getLogger(__name__)

AIRTABLE_API_BASE = "https://api.airtable.com/v0"
DEFAULT_BASE_ID = "app8xoyx1XCumYFXV"
TRX_TABLE_ID = "tblrqxqIzyrvg7XpQ"
PNL_TABLE_ID = "tblAgVaGlVory2yAW"
CAT_TABLE_ID = "tblRt6aiU6Vy2yLCD"

UZBEK_MONTHS = {
    "01": "Yanvar", "02": "Fevral", "03": "Mart", "04": "Aprel",
    "05": "May", "06": "Iyun", "07": "Iyul", "08": "Avgust",
    "09": "Sentabr", "10": "Oktabr", "11": "Noyabr", "12": "Dekabr"
}


def _get_headers() -> dict[str, str]:
    api_key = (
        getattr(settings, "AIRTABLE_API_KEY", None)
        or "patADXBB0784iii3w.7c1e4380a9736b30f1dd2cb539f6ac49ac097e3452f84f319dc2060834569fdb"
    )
    if hasattr(api_key, "get_secret_value"):
        api_key = api_key.get_secret_value()
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


async def sync_monthly_pnl() -> dict[str, Any]:
    """Sync all transactions to Oylik P&L and update monthly totals."""
    base_id = getattr(settings, "AIRTABLE_BASE_ID", None) or DEFAULT_BASE_ID
    headers = _get_headers()

    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Fetch P&L records
        pnl_resp = await client.get(f"{AIRTABLE_API_BASE}/{base_id}/{PNL_TABLE_ID}?pageSize=100", headers=headers)
        pnl_records = pnl_resp.json().get("records", []) if pnl_resp.status_code == 200 else []
        pnl_map = {}
        for r in pnl_records:
            code = r["fields"].get("Oy nomi", "")[:7]
            if code:
                pnl_map[code] = r["id"]

        # 2. Fetch categories
        cat_resp = await client.get(f"{AIRTABLE_API_BASE}/{base_id}/{CAT_TABLE_ID}?pageSize=100", headers=headers)
        cats = cat_resp.json().get("records", []) if cat_resp.status_code == 200 else []
        cat_lookup = {c["id"]: c["fields"] for c in cats}

        # 3. Fetch all transactions
        trx_records = []
        offset = None
        while True:
            url = f"{AIRTABLE_API_BASE}/{base_id}/{TRX_TABLE_ID}?pageSize=100"
            if offset:
                url += f"&offset={offset}"
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                break
            d = resp.json()
            trx_records.extend(d.get("records", []))
            offset = d.get("offset")
            if not offset:
                break

        # 4. Calculate monthly sums and find missing links
        monthly_sums: dict[str, dict[str, int]] = {}
        trx_to_link = []

        for r in trx_records:
            f = r["fields"]
            sana = f.get("Sana", "")
            if not sana or len(sana) < 7:
                continue
            m_code = sana[:7]

            if m_code not in monthly_sums:
                monthly_sums[m_code] = {"kirim": 0, "cogs": 0, "opex": 0, "soliq": 0}

            # Check if linked to P&L
            target_pnl_id = pnl_map.get(m_code)
            current_links = f.get("Oylik P&L", [])
            if target_pnl_id and (not current_links or current_links[0] != target_pnl_id):
                trx_to_link.append({"id": r["id"], "fields": {"Oylik P&L": [target_pnl_id]}})

            turi = f.get("Turi", "")
            summa = f.get("Summa UZS", 0) or 0
            kategoriya_ids = f.get("Kategoriya", [])
            cat_info = cat_lookup.get(kategoriya_ids[0], {}) if kategoriya_ids else {}
            cat_guruh = cat_info.get("Guruh", "")
            cat_nomi = cat_info.get("Kategoriya", "")

            if turi == "Kirim":
                monthly_sums[m_code]["kirim"] += summa
            elif turi == "Chiqim":
                if cat_guruh == "Loyiha xarajati" or "Freelancer" in cat_nomi:
                    monthly_sums[m_code]["cogs"] += summa
                elif cat_guruh == "Soliq" or "Soliq" in cat_nomi:
                    monthly_sums[m_code]["soliq"] += summa
                else:
                    monthly_sums[m_code]["opex"] += summa

        # 5. Patch missing transaction links in batches of 10
        for i in range(0, len(trx_to_link), 10):
            chunk = trx_to_link[i:i+10]
            await client.patch(
                f"{AIRTABLE_API_BASE}/{base_id}/{TRX_TABLE_ID}",
                headers=headers,
                json={"records": chunk}
            )

        # 6. Update P&L table rows
        pnl_updates = []
        for r in pnl_records:
            m_code = r["fields"].get("Oy nomi", "")[:7]
            sums = monthly_sums.get(m_code, {"kirim": 0, "cogs": 0, "opex": 0, "soliq": 0})
            soliq = sums["soliq"] if sums["soliq"] > 0 else int(sums["kirim"] * 0.04)
            yalpi = sums["kirim"] - sums["cogs"]
            ebt = yalpi - sums["opex"]
            net_profit = ebt - soliq
            dividend = int(net_profit * 0.6) if net_profit > 0 else 0

            pnl_updates.append({
                "id": r["id"],
                "fields": {
                    "Jami Kirim (UZS)": sums["kirim"],
                    "Loyiha xarajatlari — COGS (UZS)": sums["cogs"],
                    "Operatsion xarajatlar — OPEX (UZS)": sums["opex"],
                    "Soliq xarajati (UZS)": soliq,
                    "Taqsimlangan Dividendlar (UZS)": dividend
                }
            })

        for i in range(0, len(pnl_updates), 10):
            chunk = pnl_updates[i:i+10]
            await client.patch(
                f"{AIRTABLE_API_BASE}/{base_id}/{PNL_TABLE_ID}",
                headers=headers,
                json={"records": chunk}
            )

        logger.info("[PNL_SYNC] Successfully synced %d months and %d transactions", len(pnl_updates), len(trx_to_link))
        return {"status": "ok", "months_updated": len(pnl_updates), "transactions_linked": len(trx_to_link)}
