"""Meta ↔ AmoCRM lead solishtirmasi (reconciliation alert).

Har 15 daqiqada Meta'dagi so'nggi 24 soatlik leadlar Oisha yetkazish bazasi
(``deliveries.amocrm_ok``) bilan solishtiriladi. 30 daqiqadan eski, lekin
AmoCRM'ga yetmagan lead bo'lsa — texnik chatga alert.

Nega kerak: 2026-09-30..10-02 da 68 ta lead 2 kun jim yo'qoldi — poller
"Routed" deb yozib turdi, hech qaysi alert ishlamadi. Bu tekshiruv natijaga
(Meta soni == AmoCRM soni) qaraydi, jarayon loglariga emas.
"""
from __future__ import annotations

import asyncio
import datetime
import logging
import os
import sqlite3
from typing import Dict, Iterable, List, Optional, Tuple

logger = logging.getLogger("LeadgenReconciliation")

_INTERVAL_SEC = int(os.getenv("LEADGEN_RECONCILE_INTERVAL_SEC", "900"))
_GRACE_MIN = int(os.getenv("LEADGEN_RECONCILE_GRACE_MIN", "30"))
_WINDOW_HOURS = int(os.getenv("LEADGEN_RECONCILE_WINDOW_HOURS", "24"))
_REALERT_SEC = int(os.getenv("LEADGEN_RECONCILE_REALERT_SEC", "3600"))

_state: Dict[str, float] = {"last_alert_at": 0.0, "last_missing": 0.0}


def find_missing(
    meta_leads: Iterable[Tuple[str, datetime.datetime]],
    delivered_ids: Iterable[str],
    now: datetime.datetime,
    grace_min: int = _GRACE_MIN,
) -> List[Tuple[str, datetime.datetime]]:
    """Grace'dan eski, lekin AmoCRM'ga yetmagan Meta leadlari (eng eskisi birinchi)."""
    delivered = set(delivered_ids)
    cutoff = now - datetime.timedelta(minutes=grace_min)
    missing = [(lid, ct) for lid, ct in meta_leads if ct <= cutoff and lid not in delivered]
    return sorted(missing, key=lambda x: x[1])


def _delivered_ids() -> List[str]:
    from src.services.core.instagram.leadgen_delivery import _DB_PATH

    with sqlite3.connect(_DB_PATH, timeout=10) as conn:
        return [r[0] for r in conn.execute("SELECT leadgen_id FROM deliveries WHERE amocrm_ok = 1")]


def _meta_leads(since: datetime.datetime) -> List[Tuple[str, datetime.datetime]]:
    from src.schedulers import meta_leadgen_scheduler as m

    token = m._get_page_token()
    if not token:
        return []
    version = os.getenv("META_GRAPH_API_VERSION", "v19.0").strip() or "v19.0"
    rows: Dict[str, datetime.datetime] = {}
    for form_id in m._get_active_form_ids(token, version):
        url = f"https://graph.facebook.com/{version}/{form_id}/leads"
        for lead in m._get_pages(url, token, "id,created_time"):
            ct = datetime.datetime.strptime(lead["created_time"][:19], "%Y-%m-%dT%H:%M:%S")
            if ct >= since and lead.get("id"):
                rows[str(lead["id"])] = ct
    return list(rows.items())


def _format_alert(missing: List[Tuple[str, datetime.datetime]], meta_total: int, now: datetime.datetime) -> str:
    oldest_h = (now - missing[0][1]).total_seconds() / 3600
    ids = "\n".join(f"• <code>{lid}</code>" for lid, _ in missing[:5])
    more = f"\n… yana {len(missing) - 5} ta" if len(missing) > 5 else ""
    return (
        "🚨 <b>[OISHA: LEADLAR AMOCRM'GA YETMAYAPTI]</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"Meta (so'nggi {_WINDOW_HOURS} soat): <b>{meta_total}</b> lead\n"
        f"AmoCRM'ga yetmagan: <b>{len(missing)}</b> ta (eng eskisi {oldest_h:.1f} soat)\n"
        f"{ids}{more}\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🔎 oisha-leads logini tekshiring (userbot-auth workflow → step=leads)."
    )


async def reconcile_once(now: Optional[datetime.datetime] = None) -> int:
    """Bir marta solishtiradi; yetmagan leadlar sonini qaytaradi."""
    from src.services.core.instagram.leadgen_watchdog import send_admin_alert

    now = now or datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    meta = await asyncio.to_thread(_meta_leads, now - datetime.timedelta(hours=_WINDOW_HOURS))
    delivered = await asyncio.to_thread(_delivered_ids)
    missing = find_missing(meta, delivered, now)

    mono = asyncio.get_running_loop().time()
    if missing:
        grew = len(missing) > _state["last_missing"]
        due = not _state["last_alert_at"] or mono - _state["last_alert_at"] >= _REALERT_SEC
        if grew or due:
            if await asyncio.to_thread(send_admin_alert, _format_alert(missing, len(meta), now), True):
                _state["last_alert_at"] = mono
        logger.warning("[RECONCILE] %d/%d Meta lead AmoCRM'ga yetmagan", len(missing), len(meta))
    elif _state["last_missing"]:
        await asyncio.to_thread(
            send_admin_alert,
            f"✅ <b>[OISHA] Leadlar tiklandi</b> — so'nggi {_WINDOW_HOURS} soatdagi {len(meta)} ta Meta lead AmoCRM'da.",
            True,
        )
        _state["last_alert_at"] = 0.0
    _state["last_missing"] = float(len(missing))
    return len(missing)


async def leadgen_reconciliation_loop() -> None:
    logger.info("[RECONCILE] Loop started (interval=%ds, grace=%dmin)", _INTERVAL_SEC, _GRACE_MIN)
    await asyncio.sleep(120)
    while True:
        try:
            await reconcile_once()
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.warning("[RECONCILE] Tekshiruv xatosi: %s", type(exc).__name__)
        await asyncio.sleep(_INTERVAL_SEC)
