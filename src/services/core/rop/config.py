"""AI ROP tuning config: defaults + loader. All values overridable via rop_config."""
from __future__ import annotations

from typing import Any

DEFAULTS: dict[str, Any] = {
    # --- scoring ---
    "score.weights": {
        "stage": 40, "open_next_task": 10, "proposal_sent": 12, "meeting_held": 12,
        "payment_promised": 20, "recent_0_24h": 8, "recent_gt_72h": -12,
        "objection_open": -10, "task_overdue": -12,
        "days_in_stage_le_7": 5, "days_in_stage_gt_21": -10,
    },
    # status_id -> 0..1 readiness. Curated; unknown stages fall back to 0.15.
    "score.stage_weights": {},
    "score.band_cutoffs": {"hot": 70, "warm": 40},
    "score.objection_keywords": ["qimmat", "narx", "budjet", "keyin", "o'ylab"],
    "score.payment_keywords": ["to'lov", "oplata", "perevod", "karta", "hisob"],
    # --- discipline ---
    "discipline.stagnant_days": 3,
    "discipline.terminal_stage_ids": [],
    # --- traffic light ---
    "traffic.red_no_result_days": 3,
    "traffic.red_overdue_count": 5,
    "traffic.red_discipline_count": 8,
    "traffic.big_deal_amount": 10_000_000,
    "traffic.stuck_deal_days": 14,
    "traffic.yellow_pace_pct": 0.5,
    "traffic.hot_lead_silent_hours": 48,
    # --- midday ---
    "midday.pace_pct": 0.4,
    # --- weekly ---
    "weekly.sales_target": 10,
    "weekly.revenue_target": 100_000_000,
}


async def load_config(repo) -> dict[str, Any]:
    stored = await repo.all_config()
    return {key: stored.get(key, default) for key, default in DEFAULTS.items()}


async def seed_config(repo) -> None:
    stored = await repo.all_config()
    for key, default in DEFAULTS.items():
        if key not in stored:
            await repo.set_config(key, default)
