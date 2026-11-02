"""Automated Personalized Telegram Daily Brief Service.

Formats customized, actionable morning briefs for sales representatives with
monthly targets, needed funnel steps, hot deals, overdue calls/tasks, and weekly skill focus.
"""
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional


@dataclass
class ManagerDailyBrief:
    """Individual manager morning brief ready for Telegram delivery."""

    manager_id: str
    manager_name: str
    has_telegram: bool
    telegram_chat_id: Optional[str]
    brief_text: str
    status: str = "pending"  # "pending", "sent", "failed"
    error: Optional[str] = None


class DailyBriefService:
    """Service to generate and dispatch personalized Telegram daily briefs."""

    def format_brief(
        self,
        name: str,
        month_label: str,
        fact_mln: float,
        plan_pct: int,
        target_mln: float,
        sales_needed: int,
        kval_needed: int,
        leads_needed: int,
        hot_deals_cnt: int,
        hot_deals_sum_mln: float,
        overdue_calls_cnt: int,
        overdue_tasks_cnt: int,
        weak_skill: str,
        skill_score: int,
        level_num: int,
        level_title: str,
    ) -> str:
        """Format personalized morning briefing text for sales representative."""
        lines = [
            f"Xayrli tong, {name}!",
            "",
            f"{month_label} yakuni: {fact_mln:.1f} mln soʻm (rejaning {plan_pct}%).",
            f"Avgust maqsadi: {target_mln:.0f} mln soʻm.",
            f"Buning uchun: {sales_needed} ta sotuv ← {kval_needed} ta sifatli lid ← {leads_needed} ta lid.",
            "",
            "Bugun:",
            f"1. {hot_deals_cnt} ta issiq bitim yopilishni kutmoqda ({hot_deals_sum_mln:.1f} mln soʻm)",
            f"2. {overdue_calls_cnt} ta vaʼda qilingan qayta qoʻngʻiroq kechikkan",
            f"3. {overdue_tasks_cnt} ta bitimda vazifa muddati oʻtgan",
            "",
            f"Haftaning koʻnikmasi: {weak_skill} ({skill_score} ball). Darslikda 5 daqiqalik mashq bor.",
            "",
            f"Daraja: {level_num}/5 — {level_title}.",
        ]
        return "\n".join(lines)

    def prepare_brief(self, mgr: Dict[str, Any]) -> ManagerDailyBrief:
        """Prepare single manager daily brief object."""
        name = str(mgr.get("name", "Menejer"))
        has_tg = bool(mgr.get("has_telegram", False))
        chat_id = str(mgr.get("telegram_chat_id")) if mgr.get("telegram_chat_id") else None

        fact = float(mgr.get("fact", 0)) / 1_000_000
        plan_pct = int(mgr.get("plan_percent", 0))
        target = float(mgr.get("target", 0)) / 1_000_000
        sales = int(mgr.get("sales_needed", 20))
        kval = int(mgr.get("kval_needed", 100))
        leads = int(mgr.get("leads_needed", 250))

        hot_cnt = int(mgr.get("hot_deals_count", 0))
        hot_sum = float(mgr.get("hot_deals_sum", 0)) / 1_000_000
        overdue_calls = int(mgr.get("overdue_calls", 0))
        overdue_tasks = int(mgr.get("overdue_tasks", 0))

        skill = str(mgr.get("focus_skill", "Yakunlash va keyingi qadam"))
        score = int(mgr.get("skill_score", 50))
        lvl_num = int(mgr.get("level", 3))
        lvl_title = str(mgr.get("level_title", "Barqaror"))

        text = self.format_brief(
            name=name,
            month_label=str(mgr.get("month_label", "Iyul")),
            fact_mln=fact,
            plan_pct=plan_pct,
            target_mln=target,
            sales_needed=sales,
            kval_needed=kval,
            leads_needed=leads,
            hot_deals_cnt=hot_cnt,
            hot_deals_sum_mln=hot_sum,
            overdue_calls_cnt=overdue_calls,
            overdue_tasks_cnt=overdue_tasks,
            weak_skill=skill,
            skill_score=score,
            level_num=lvl_num,
            level_title=lvl_title,
        )

        return ManagerDailyBrief(
            manager_id=str(mgr.get("id", "mgr")),
            manager_name=name,
            has_telegram=has_tg,
            telegram_chat_id=chat_id,
            brief_text=text,
        )

    def prepare_bulk_briefs(self, managers: List[Dict[str, Any]]) -> List[ManagerDailyBrief]:
        """Prepare daily briefs for all sales representatives."""
        return [self.prepare_brief(m) for m in managers]

    def dispatch_briefs(
        self,
        briefs: List[ManagerDailyBrief],
        sender_fn: Optional[Callable[[str, str], bool]] = None,
    ) -> Dict[str, Any]:
        """Dispatch briefs via provided sender callback or mark ready."""
        sent_count = 0
        skipped_count = 0
        failed_count = 0

        for b in briefs:
            if not b.has_telegram or not b.telegram_chat_id:
                b.status = "skipped"
                b.error = "Telegram chat id mavjud emas"
                skipped_count += 1
                continue

            if sender_fn:
                try:
                    success = sender_fn(b.telegram_chat_id, b.brief_text)
                    if success:
                        b.status = "sent"
                        sent_count += 1
                    else:
                        b.status = "failed"
                        b.error = "Joʻnatish xatosi"
                        failed_count += 1
                except Exception as exc:
                    b.status = "failed"
                    b.error = str(exc)
                    failed_count += 1
            else:
                # Dry-run or queue mode
                b.status = "sent"
                sent_count += 1

        return {
            "total": len(briefs),
            "sent": sent_count,
            "skipped": skipped_count,
            "failed": failed_count,
            "briefs": briefs,
        }
