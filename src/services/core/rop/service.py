"""AI ROP orchestrator: fetch -> compute -> render. Returns a delivery plan.
Never sends; the scheduler sends."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from src.services.core.rop.config import load_config, seed_config
from src.services.core.rop.daily import (
    build_ceo_dashboard, build_ceo_midday, build_ceo_morning, build_evening,
    build_midday, build_morning, score_seller_leads,
)
from src.services.core.rop.discipline import find as find_discipline
from src.services.core.rop.fetchers import RopFetchError, _tashkent_day_start_epoch
from src.services.core.rop.rop_messages import (
    render_ceo_dashboard, render_ceo_midday, render_ceo_morning,
    render_empty_roster_notice, render_seller_evening, render_seller_midday,
    render_seller_morning,
)
from src.services.core.rop.targets import load_roster
from src.services.core.rop.traffic_light import SellerMetrics, evaluate
from src.services.core.rop.weekly import monday_start, no_result_streak_days, progress
from src.time_utils import get_local_now

logger = logging.getLogger("RopService")
SLOTS = ("morning", "midday", "evening")


def _bucket_actuals(completed_tasks: list[dict]) -> dict:
    calls = sum(1 for t in completed_tasks if t.get("task_type_id") == 1)
    meetings = sum(1 for t in completed_tasks if t.get("task_type_id") == 2)
    follow_ups = len(completed_tasks) - calls - meetings
    return {"calls": calls, "meetings": meetings, "follow_ups": follow_ups}


def _find_seller_calls(seller_name: str, today_calls: dict[str, dict]) -> dict:
    if not today_calls:
        return {}
    s_lower = seller_name.strip().lower()
    if s_lower in today_calls:
        return today_calls[s_lower]
    s_first = s_lower.split()[0] if s_lower else ""
    for k, v in today_calls.items():
        if k in s_lower or s_lower in k or (s_first and s_first in k):
            return v
    return {}


def _resolve_lead_owner_uid(lead: dict, roster_ids: set[int]) -> int | None:
    """Resolve seller responsible_user_id from AmoCRM tags first, then responsible_user_id."""
    try:
        from src.services.core.crm.team_roster import find_staff
        tags = lead.get("_embedded", {}).get("tags") or []
        for t in tags:
            t_name = str(t.get("name") or "").strip()
            if not t_name:
                continue
            member = find_staff(t_name)
            if member and member.amocrm_user_id in roster_ids:
                return int(member.amocrm_user_id)
    except Exception:  # noqa: BLE001
        pass

    uid = lead.get("responsible_user_id")
    if uid and int(uid) in roster_ids:
        return int(uid)
    return int(uid) if uid else None


class RopService:
    def __init__(self, repo, fetcher, *, ceo_chat_id, now_fn=get_local_now):
        self._repo = repo
        self._fetch = fetcher
        self._ceo = ceo_chat_id
        self._now_fn = now_fn

    async def _fetch_secondary_data(self, all_lead_ids: list[int], roster_ids: set[int], slot: str, now: datetime) -> dict | None:
        is_monday = now.weekday() == 0
        try:
            open_tasks = await self._fetch.fetch_open_tasks_for_leads(all_lead_ids)
            completed_by_entity, completed_by_user = await self._fetch.fetch_today_completed_tasks(list(roster_ids), now=now)
            today_events = await self._fetch.fetch_today_events(all_lead_ids, now=now)
            notes = await self._fetch.fetch_notes_for_leads(all_lead_ids) if slot in ("morning", "evening") else {}
            won_today = await self._fetch.fetch_won_leads_since(_tashkent_day_start_epoch(now)) if slot in ("midday", "evening") else []
            recent_events, won_week = {}, []
            if slot == "evening" or (slot == "morning" and is_monday):
                since_7d = int((now - timedelta(days=7)).timestamp())
                recent_events = await self._fetch.fetch_recent_events(all_lead_ids, since_7d)
                won_week = await self._fetch.fetch_won_leads_since(int(monday_start(now).timestamp()))
            return {
                "open_tasks": open_tasks, "completed_by_entity": completed_by_entity,
                "completed_by_user": completed_by_user, "today_events": today_events,
                "notes": notes, "won_today": won_today, "recent_events": recent_events, "won_week": won_week,
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning("[ROP] %s slot aborted — secondary fetch failed: %s", slot, exc)
            return None

    def _eval_seller(self, s, ctx: dict) -> tuple[int, str] | None:
        slot, s_leads, config, now = ctx["slot"], ctx["leads_by_user"].get(s.responsible_user_id, []), ctx["config"], ctx["now"]
        evs = {lid: ctx["data"]["today_events"].get(lid, []) + ctx["data"]["recent_events"].get(lid, []) for lid in (l["id"] for l in s_leads)}
        scored = score_seller_leads(s_leads, ctx["data"]["open_tasks"], ctx["data"]["notes"], evs, config, now)
        actuals = _bucket_actuals(ctx["data"]["completed_by_user"].get(s.responsible_user_id, []))
        won = [l for l in ctx["data"]["won_today"] if _resolve_lead_owner_uid(l, ctx["roster_ids"]) == s.responsible_user_id]
        actuals["won"], actuals["won_revenue"] = len(won), sum(int(l.get("price") or 0) for l in won)
        calls = _find_seller_calls(s.seller_name, ctx["today_calls"])

        if slot == "morning":
            tasks = {l["id"]: ctx["data"]["open_tasks"].get(l["id"], []) for l in s_leads}
            mp = build_morning(s, scored, tasks, find_discipline(s_leads, ctx["data"]["open_tasks"], ctx["data"]["notes"], config, now), config, now)
            ctx["morning_plans"].append(mp)
            return (s.telegram_user_id, render_seller_morning(mp)) if s.telegram_user_id else None
        if slot == "midday":
            touched = {lid for lid in (l["id"] for l in s_leads) if ctx["data"]["completed_by_entity"].get(lid) or ctx["data"]["today_events"].get(lid)}
            mc = build_midday(s, scored, actuals, touched, config, call_stats=calls)
            ctx["midday_checks"].append(mc)
            ctx["traffic"][s.responsible_user_id] = self._traffic_for(s, scored, actuals, [], config, now, ctx["data"]["recent_events"], ctx["prior_snapshot"], s_leads, ctx["data"]["open_tasks"])
            return (s.telegram_user_id, render_seller_midday(mc)) if not mc.on_track and s.telegram_user_id else None

        overdue = sum(1 for lid in (l["id"] for l in s_leads) for t in ctx["data"]["open_tasks"].get(lid, []) if (t.get("complete_till") or 0) and float(t["complete_till"]) < now.timestamp())
        ev = build_evening(s, scored, actuals, overdue, call_stats=calls)
        ctx["evening_results"].append(ev)
        ctx["traffic"][s.responsible_user_id] = self._traffic_for(s, scored, actuals, find_discipline(s_leads, ctx["data"]["open_tasks"], ctx["data"]["notes"], config, now), config, now, ctx["data"]["recent_events"], ctx["prior_snapshot"], s_leads, ctx["data"]["open_tasks"])
        return (s.telegram_user_id, render_seller_evening(ev)) if s.telegram_user_id else None

    async def _append_ceo_summary(self, plan: list, ctx: dict, no_owner: list) -> None:
        if not self._ceo:
            return
        slot, now, cfg, data = ctx["slot"], ctx["now"], ctx["config"], ctx["data"]
        if slot == "morning":
            await self._write_snapshot(now, ctx["morning_plans"])
            await self._cleanup_snapshots(now)
            recap = progress(data["won_week"], cfg) if now.weekday() == 0 else None
            no_owner_finds = [find_discipline([l], {}, {}, cfg, now)[0] for l in no_owner if find_discipline([l], {}, {}, cfg, now)]
            plan.append((self._ceo, render_ceo_morning(build_ceo_morning(ctx["morning_plans"], no_owner_finds, recap))))
        elif slot == "midday":
            plan.append((self._ceo, render_ceo_midday(build_ceo_midday(ctx["midday_checks"], ctx["traffic"]))))
        else:
            exp_tom = sum(int(l.price * l.score / 100) for ev in ctx["evening_results"] for l in ev.tomorrow_closings if l.band in ("HOT", "WARM"))
            dash = build_ceo_dashboard(ctx["evening_results"], ctx["traffic"], progress(data["won_week"], cfg), exp_tom, ctx["skipped"])
            plan.append((self._ceo, render_ceo_dashboard(dash)))

    async def run(self, slot: str) -> list[tuple[int, str]]:
        assert slot in SLOTS, slot
        await seed_config(self._repo)
        config, now = await load_config(self._repo), self._now_fn()
        roster = await load_roster(self._repo)
        if not roster:
            return [(self._ceo, render_empty_roster_notice())] if self._ceo else []
        try:
            leads = await self._fetch.fetch_active_sales_leads()
        except RopFetchError as exc:
            logger.warning("[ROP] %s slot aborted — active leads fetch failed: %s", slot, exc)
            return []

        roster_ids = {s.responsible_user_id for s in roster}
        leads_by_user: dict[int, list[dict]] = {uid: [] for uid in roster_ids}
        no_owner: list[dict] = []
        for l in leads:
            uid = _resolve_lead_owner_uid(l, roster_ids)
            (leads_by_user[uid] if uid in leads_by_user else no_owner).append(l)

        sec_data = await self._fetch_secondary_data([l["id"] for l in leads], roster_ids, slot, now)
        if sec_data is None:
            return []

        calls: dict = {}
        if slot in ("midday", "evening") and hasattr(self._fetch, "fetch_today_calls"):
            try:
                calls = await self._fetch.fetch_today_calls(now)
            except Exception as exc:  # noqa: BLE001
                logger.warning("[ROP] fetch_today_calls failed: %s", exc)

        ctx = {
            "slot": slot, "now": now, "config": config, "roster_ids": roster_ids, "leads_by_user": leads_by_user,
            "data": sec_data, "today_calls": calls, "prior_snapshot": await self._latest_snapshot(now),
            "morning_plans": [], "midday_checks": [], "evening_results": [], "traffic": {}, "skipped": 0,
        }
        plan: list[tuple[int, str]] = []
        for s in roster:
            try:
                item = self._eval_seller(s, ctx)
                if item:
                    plan.append(item)
            except Exception:  # noqa: BLE001
                logger.exception("[ROP] seller %s compute failed", s.responsible_user_id)
                ctx["skipped"] += 1

        await self._append_ceo_summary(plan, ctx, no_owner)
        return plan

    # ---- snapshot helpers ----

    def _snapshot_key(self, now: datetime) -> str:
        return f"snapshot.{now.strftime('%Y-%m-%d')}"

    async def _write_snapshot(self, now, morning_plans) -> None:
        data = {str(ls.lead_id): ls.band for mp in morning_plans for ls in mp.top_closings}
        await self._repo.set_config(self._snapshot_key(now), data)

    async def _latest_snapshot(self, now) -> dict:
        cfg = await self._repo.all_config()
        keys = sorted(k for k in cfg if k.startswith("snapshot."))
        return cfg.get(keys[-1], {}) if keys else {}

    async def _cleanup_snapshots(self, now) -> None:
        cfg = await self._repo.all_config()
        cutoff = (now - timedelta(days=2)).strftime("%Y-%m-%d")
        for k in list(cfg):
            if k.startswith("snapshot.") and k.split(".", 1)[1] < cutoff:
                await self._repo.set_config(k, {})

    def _traffic_for(
        self, seller, scored, actuals, findings, config, now, recent_events,
        prior_snapshot, s_leads, open_tasks,
    ):
        won_today = actuals.get("won", 0)
        overdue_count = sum(
            1 for lid in (l["id"] for l in s_leads)
            for t in open_tasks.get(lid, [])
            if (t.get("complete_till") or 0) and float(t["complete_till"]) < now.timestamp()
        )
        hot_silent = 0.0
        for ls in scored:
            if ls.band == "HOT" and any("aloqa yo'q" in r for r in ls.reasons):
                hot_silent = max(hot_silent, config["traffic.hot_lead_silent_hours"])
        band_dropped = any(prior_snapshot.get(str(ls.lead_id)) == "HOT" and ls.band != "HOT" for ls in scored)
        metrics = SellerMetrics(
            won_today=won_today, no_result_streak_days=0, overdue_count=overdue_count,
            calls_done=actuals["calls"], calls_target=seller.calls,
            follow_ups_done=actuals["follow_ups"], follow_ups_target=seller.follow_ups,
            meetings_done=actuals["meetings"], meetings_target=seller.meetings,
            biggest_stuck_deal_amount=0, biggest_stuck_deal_days=0.0,
            hot_lead_max_silent_hours=hot_silent, hot_band_dropped=band_dropped,
        )
        return evaluate(metrics, findings, config)
