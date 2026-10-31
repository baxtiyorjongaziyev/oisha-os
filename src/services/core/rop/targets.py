"""AI ROP roster: sellers are the active rows in rop_targets (seeded from SSoT)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SellerTarget:
    responsible_user_id: int
    seller_name: str
    telegram_user_id: int | None
    expected_sales: int
    calls: int
    follow_ups: int
    meetings: int
    proposals: int
    payments: int
    max_overdue: int


async def load_roster(repo) -> list[SellerTarget]:
    rows = await repo.list_active_targets()
    return [
        SellerTarget(
            responsible_user_id=int(r["responsible_user_id"]),
            seller_name=r.get("seller_name") or f"Menejer_{r['responsible_user_id']}",
            telegram_user_id=r.get("telegram_user_id"),
            expected_sales=int(r.get("expected_sales", 1)),
            calls=int(r.get("calls", 10)),
            follow_ups=int(r.get("follow_ups", 20)),
            meetings=int(r.get("meetings", 2)),
            proposals=int(r.get("proposals", 0)),
            payments=int(r.get("payments", 1)),
            max_overdue=int(r.get("max_overdue", 0)),
        )
        for r in rows
    ]


async def seed_default(
    repo, responsible_user_id: int, telegram_user_id: int | None, seller_name: str
) -> None:
    await repo.upsert_target(
        responsible_user_id,
        seller_name=seller_name,
        telegram_user_id=telegram_user_id,
        expected_sales=1,
        calls=10,
        follow_ups=20,
        meetings=2,
        proposals=0,
        payments=1,
        max_overdue=0,
        active=1,
    )


async def ensure_ssot_roster(repo) -> list[SellerTarget]:
    """Ensure active sales sellers from SSoT team_roster are seeded in rop_targets.

    Maps the canonical 50/20/10/3/1 daily funnel targets:
    - calls: 50 solid conversations (>=3 min)
    - follow_ups: 20 meaningful conversations
    - proposals: 10 EVQN invitations
    - meetings: 3 held meetings
    - expected_sales / payments: 1 closed sale
    """
    from src.services.core.crm.team_roster import EXCLUDED_NON_STAFF_SLUGS, get_active_staff

    existing = await repo.list_active_targets()
    existing_ids = {int(r["responsible_user_id"]) for r in existing if r.get("responsible_user_id")}

    # Deactivate any non-staff rows if present and repo supports set_active
    if hasattr(repo, "set_active"):
        for r in existing:
            name_low = str(r.get("seller_name") or "").strip().lower()
            if any(slug in name_low for slug in EXCLUDED_NON_STAFF_SLUGS):
                await repo.set_active(int(r["responsible_user_id"]), False)

    sellers = get_active_staff(include_owner=False, roles=("seller",))
    for s in sellers:
        uid = int(s.amocrm_user_id or 0)
        if not uid or uid in existing_ids:
            continue
        await repo.upsert_target(
            uid,
            seller_name=s.name,
            telegram_user_id=s.tg_user_id,
            expected_sales=1,
            calls=50,
            follow_ups=20,
            meetings=3,
            proposals=10,
            payments=1,
            max_overdue=0,
            active=1,
        )
    return await load_roster(repo)
