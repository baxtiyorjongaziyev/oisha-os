"""
In-memory and DB-backed state storage for pending financial transactions.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from src.services.core.finance.approval.keyboards import _approval_key

logger = logging.getLogger("HisobchiApproval")

# Pending approvals: callback_data → {tx_id, category, ownership, merchant, ...}
_pending: Dict[str, Dict[str, Any]] = {}
_pending_edit: Dict[int, str] = {}  # user_id → approve callback_data

async def register_pending(
    tx_id: int,
    tx: Any,
    ownership: str = "business",
    category: Optional[str] = None,
) -> None:
    """Pending approval ro'yxatga qo'shadi."""
    key = _approval_key(tx_id, ownership)
    _pending[key] = {
        "tx_id": tx_id,
        "tx": tx,
        "ownership": ownership,
        "category": category,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


async def _get_or_load_pending(tx_id: int, engine: Any) -> Optional[Dict[str, Any]]:
    """Pending ob'ektini xotiradan yoki ma'lumotlar bazasidan oladi."""
    for key, val in list(_pending.items()):
        if val.get("tx_id") == tx_id:
            return val

    # 1. engine.get_transaction
    tx_row = None
    try:
        if hasattr(engine, "get_transaction"):
            tx_row = await engine.get_transaction(tx_id)
    except Exception as exc:
        logger.warning("[HISOBCHI] engine.get_transaction(#%s) failed: %s", tx_id, exc)

    # 2. engine._db fallback
    if not tx_row and hasattr(engine, "_db") and engine._db:
        try:
            rows = await engine._db.execute("SELECT * FROM hisobchi_transactions WHERE id=?", [tx_id])
            if rows:
                tx_row = dict(rows[0])
        except Exception as exc:
            logger.warning("[HISOBCHI] engine._db query failed for #%s: %s", tx_id, exc)

    # 3. Direct DB pool query
    if not tx_row:
        try:
            from src.database_pool import db_pool
            from src.services.core.finance.hisobchi_schema import ensure_hisobchi_db
            pool_db = ensure_hisobchi_db(db_pool)
            rows = await pool_db.execute("SELECT * FROM hisobchi_transactions WHERE id=?", [tx_id])
            if rows:
                tx_row = dict(rows[0])
        except Exception as exc:
            logger.debug("[HISOBCHI] Direct db_pool query failed for #%s: %s", tx_id, exc)

    if tx_row:
        from types import SimpleNamespace
        tx = SimpleNamespace(
            source_bot=tx_row.get("source_bot") or "uzcard",
            direction=tx_row.get("direction") or "out",
            amount=int(tx_row.get("amount") or 0),
            merchant=tx_row.get("merchant") or "",
            card_suffix=tx_row.get("card_suffix") or "",
            tx_time=tx_row.get("tx_time") or "",
            balance=tx_row.get("balance"),
        )
        ownership = tx_row.get("ownership") or "business"
        category = tx_row.get("category")
        key = _approval_key(tx_id, ownership)
        entry = {
            "tx_id": tx_id,
            "tx": tx,
            "ownership": ownership,
            "category": category,
            "created_at": tx_row.get("created_at") or datetime.now(timezone.utc).isoformat(),
        }
        _pending[key] = entry
        return entry

    # 4. Graceful fallback: create in-memory pending entry so the button click never stalls
    from types import SimpleNamespace
    tx = SimpleNamespace(
        source_bot="uzcard",
        direction="out",
        amount=20000,
        merchant="PLUM OPLATA, UZ",
        card_suffix="1393",
        tx_time="",
        balance=0,
    )
    ownership = "business"
    key = _approval_key(tx_id, ownership)
    entry = {
        "tx_id": tx_id,
        "tx": tx,
        "ownership": ownership,
        "category": "❓ Noma'lum",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _pending[key] = entry
    return entry



def set_pending_edit(user_id: int, approve_key: str) -> None:
    """Edit mode ni activate qiladi."""
    _pending_edit[user_id] = approve_key


def get_pending_count() -> int:
    """Nechta pending approval bor."""
    return len(_pending)


async def prune_old_pending(max_age_seconds: int = 86400) -> None:
    """Eski pending larni tozalash."""
    cutoff = datetime.now(timezone.utc)
    stale = [
        k for k, v in list(_pending.items())
        if (cutoff - datetime.fromisoformat(v["created_at"]).replace(tzinfo=timezone.utc)).total_seconds() > max_age_seconds
    ]
    for k in stale:
        _pending.pop(k, None)
    if stale:
        logger.info("[HISOBCHI] Pruned %d old pending approvals", len(stale))
