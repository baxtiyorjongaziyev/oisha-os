"""AI ROP roster: sellers are exactly the active rows in rop_targets."""
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
