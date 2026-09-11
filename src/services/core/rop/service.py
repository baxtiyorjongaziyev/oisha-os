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


class RopService:
    def __init__(self, repo, fetcher, *, ceo_chat_id, now_fn=get_local_now):
        self._repo = repo
        self._fetch = fetcher
        self._ceo = ceo_chat_id
        self._now_fn = now_fn

    async def run(self, slot: str) -> list[tuple[int, str]]:
        assert slot in SLOTS, slot
        await seed_config(self._repo)
        config = await load_config(self._repo)
        now: datetime = self._now_fn()

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
            uid = l.get("responsible_user_id")
            if not uid:
                no_owner.append(l)
            elif uid in leads_by_user:
                leads_by_user[uid].append(l)

        all_lead_ids = [l["id"] for l in leads]
        is_monday = now.weekday() == 0
        recent_events: dict = {}
        won_today: list[dict] = []
        won_week: list[dict] = []
        try:
            open_tasks = await self._fetch.fetch_open_tasks_for_leads(all_lead_ids)
            completed_by_entity, completed_by_user = await self._fetch.fetch_today_completed_tasks(
                list(roster_ids), now=now
            )
            today_events = await self._fetch.fetch_today_events(all_lead_ids, now=now)
            notes = (
                await self._fetch.fetch_notes_for_leads(all_lead_ids)
                if slot in ("morning", "evening")
                else {}
            )

            if slot in ("midday", "evening"):
                won_today = await self._fetch.fetch_won_leads_since(_tashkent_day_start_epoch(now))
            if slot == "evening" or (slot == "morning" and is_monday):
                since_7d = int((now - timedelta(days=7)).timestamp())
                recent_events = await self._fetch.fetch_recent_events(all_lead_ids, since_7d)
                won_week = await self._fetch.fetch_won_leads_since(int(monday_start(now).timestamp()))
        except Exception as exc:  # noqa: BLE001
            logger.warning("[ROP] %s slot aborted — secondary fetch failed: %s", slot, exc)
            return []

        prior_snapshot = await self._latest_snapshot(now)
        plan: list[tuple[int, str]] = []
        skipped = 0
        morning_plans = []
        midday_checks = []
        evening_results = []
        traffic: dict[int, object] = {}

        for s in roster:
            try:
                s_leads = leads_by_user.get(s.responsible_user_id, [])
                events_by_lead = {
                    lid: today_events.get(lid, []) + recent_events.get(lid, [])
                    for lid in (l["id"] for l in s_leads)
                }
                scored = score_seller_leads(
                    s_leads, open_tasks, notes, events_by_lead, config, now
                )
                s_completed = completed_by_user.get(s.responsible_user_id, [])
                actuals = _bucket_actuals(s_completed)
                s_won_today = [
                    l for l in won_today
                    if l.get("responsible_user_id") == s.responsible_user_id
                ]
                actuals["won"] = len(s_won_today)
                actuals["won_revenue"] = sum(int(l.get("price") or 0) for l in s_won_today)

                if slot == "morning":
                    tasks_by_lead = {l["id"]: open_tasks.get(l["id"], []) for l in s_leads}
                    findings = find_discipline(
                        s_leads, open_tasks, notes, config, now
                    )
                    mp = build_morning(s, scored, tasks_by_lead, findings, config, now)
                    morning_plans.append(mp)
                    if s.telegram_user_id:
                        plan.append((s.telegram_user_id, render_seller_morning(mp)))

                elif slot == "midday":
                    touched = {
                        lid for lid in (l["id"] for l in s_leads)
                        if completed_by_entity.get(lid) or today_events.get(lid)
                    }
                    check = build_midday(s, scored, actuals, touched, config)
                    midday_checks.append(check)
                    traffic[s.responsible_user_id] = self._traffic_for(
                        s, scored, actuals, [], config, now, recent_events,
                        prior_snapshot, s_leads, open_tasks,
                    )
                    if not check.on_track and s.telegram_user_id:
                        plan.append((s.telegram_user_id, render_seller_midday(check)))

                else:  # evening
                    overdue_count = sum(
                        1 for lid in (l["id"] for l in s_leads)
                        for t in open_tasks.get(lid, [])
                        if (t.get("complete_till") or 0) and float(t["complete_till"]) < now.timestamp()
                    )
                    ev = build_evening(s, scored, actuals, overdue_count)
                    evening_results.append(ev)
                    findings = find_discipline(s_leads, open_tasks, notes, config, now)
                    traffic[s.responsible_user_id] = self._traffic_for(
                        s, scored, actuals, findings, config, now, recent_events,
                        prior_snapshot, s_leads, open_tasks,
                    )
                    if s.telegram_user_id:
                        plan.append((s.telegram_user_id, render_seller_evening(ev)))
            except Exception:  # noqa: BLE001
                logger.exception("[ROP] seller %s compute failed", s.responsible_user_id)
                skipped += 1

        no_owner_findings = [
            find_discipline([l], {}, {}, config, now)[0]
            for l in no_owner
            if find_discipline([l], {}, {}, config, now)
        ]

        if slot == "morning":
            await self._write_snapshot(now, morning_plans)
            await self._cleanup_snapshots(now)
            weekly_recap = progress(won_week, config) if is_monday else None
            ceo = build_ceo_morning(morning_plans, no_owner_findings, weekly_recap)
            if self._ceo:
                plan.append((self._ceo, render_ceo_morning(ceo)))
        elif slot == "midday":
            ceo = build_ceo_midday(midday_checks, traffic)
            if self._ceo:
                plan.append((self._ceo, render_ceo_midday(ceo)))
        else:
            weekly = progress(won_week, config)
            # expected tomorrow = sum of HOT+WARM expected across sellers' scored lists
            expected_tomorrow = sum(
                int(l.price * l.score / 100)
                for ev in evening_results
                for l in ev.tomorrow_closings
                if l.band in ("HOT", "WARM")
            )
            dash = build_ceo_dashboard(
                evening_results, traffic, weekly, expected_tomorrow, skipped
            )
            if self._ceo:
                plan.append((self._ceo, render_ceo_dashboard(dash)))

        return plan

    # ---- snapshot helpers ----

    def _snapshot_key(self, now: datetime) -> str:
        return f"snapshot.{now.strftime('%Y-%m-%d')}"

    async def _write_snapshot(self, now, morning_plans) -> None:
        data = {
            str(ls.lead_id): ls.band
            for mp in morning_plans
            for ls in mp.top_closings
        }
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
        streak = 0
        overdue_count = sum(
            1 for lid in (l["id"] for l in s_leads)
            for t in open_tasks.get(lid, [])
            if (t.get("complete_till") or 0) and float(t["complete_till"]) < now.timestamp()
        )
        hot_silent = 0.0
        for ls in scored:
            if ls.band == "HOT":
                if any("aloqa yo'q" in r for r in ls.reasons):
                    hot_silent = max(hot_silent, config["traffic.hot_lead_silent_hours"])
        band_dropped = any(
            prior_snapshot.get(str(ls.lead_id)) == "HOT" and ls.band != "HOT"
            for ls in scored
        )
        biggest_amt, biggest_days = 0, 0.0
        metrics = SellerMetrics(
            won_today=won_today,
            no_result_streak_days=streak,
            overdue_count=overdue_count,
            calls_done=actuals["calls"], calls_target=seller.calls,
            follow_ups_done=actuals["follow_ups"], follow_ups_target=seller.follow_ups,
            meetings_done=actuals["meetings"], meetings_target=seller.meetings,
            biggest_stuck_deal_amount=biggest_amt,
            biggest_stuck_deal_days=biggest_days,
            hot_lead_max_silent_hours=hot_silent,
            hot_band_dropped=band_dropped,
        )
        return evaluate(metrics, findings, config)
