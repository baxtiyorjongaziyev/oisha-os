"""
Psychological Automation Service — Avtomatlashtirilgan Kouching va Proaktiv To'siqlarni Sindirish.

Bu modul Oisha-OS ga quyidagi to'liq avtomatlashtirilgan imkoniyatlarni beradi:
1. Kunlik ertalabki motivatsion booster (09:15) — Jamoa uchun kunni real vaziyat,
   CRM/loyiha/qo'ng'iroq ko'rsatkichlari va hafta ritmiga mos psixologik ruhda boshlash.
2. Sotuvchilarning qo'ng'iroq kechiktirishini avtomatik aniqlash (11:30 & 15:30) — AmoCRM da qotib qolgan
   (24-48 soatdan ortiq aloqaga chiqilmagan) lidlar uchun mas'ul menejerga to'g'ridan-to'g'ri
   "Hozir telefon qilsang nima bo'ladi?..." dekonstruktsiyasi va 60 soniyalik mikroskript yuborish.
3. PM loyiha kechikishi va konflikt himoyasi (11:45 & 16:30) — Airtable/loyihalarda deadline yaqinlashayotgan
   yoki statusi kechikayotgan loyihalar uchun PMga mijoz bilan diplomatik va dadil muloqot qilish
   xabarini tayyorlab berish.
4. Avtomatik hisobdorlik (Accountability Check) — Kouching yuborilgandan so'ng amaliyot natijasini kuzatish.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.services.core.psychological_boost_builder import render_morning_boost
from src.services.core.psychological_coach import PsychologicalCoach
from src.services.utils.db_rows import fetch_rows

logger = logging.getLogger("PsychologicalAutomation")


def _extract_project_name(proj: Dict[str, Any]) -> str:
    fields = proj.get("fields") if isinstance(proj.get("fields"), dict) else {}
    return (
        proj.get("name")
        or proj.get("project_name")
        or fields.get("Loyihani nomi?")
        or fields.get("Project Name")
        or fields.get("Name")
        or "Loyiha"
    )


def _row_val(row: Any, key: str, default: Any = None) -> Any:
    if isinstance(row, dict):
        return row.get(key, default)
    getter = getattr(row, "get", None)
    if callable(getter):
        try:
            val = getter(key, default)
            return default if val is None else val
        except Exception:
            return default
    return getattr(row, key, default)


class PsychologicalAutomationService:
    """To'liq avtonom psixologik qo'llab-quvvatlash va kouching servisi."""

    def __init__(
        self,
        *,
        db: Any = None,
        amocrm: Any = None,
        airtable: Any = None,
        bot_client: Any = None,
    ):
        self.db = db
        self.amocrm = amocrm
        self.airtable = airtable
        self.bot_client = bot_client

    def generate_morning_boost(
        self,
        context: Optional[Dict[str, Any]] = None,
        now: Optional[datetime] = None,
    ) -> str:
        """Ertalabki 09:15 jamoaviy psixologik impuls (vaziyat va ko'rsatkichlarga mos)."""
        return render_morning_boost(context=context, now=now)

    async def _collect_crm_metrics(self, ctx: Dict[str, Any]) -> None:
        if not self.amocrm:
            return
        try:
            if hasattr(self.amocrm, "get_stagnated_leads"):
                stag = await asyncio.to_thread(
                    self.amocrm.get_stagnated_leads, hours=24, limit=25
                )
                if isinstance(stag, (list, tuple)):
                    ctx["stagnated_count"] = len(stag)
                    if stag and isinstance(stag[0], dict):
                        top = max(
                            stag,
                            key=lambda item: float(item.get("price") or 0)
                            if isinstance(item, dict)
                            else 0.0,
                        )
                        ctx["top_stagnated_lead"] = (
                            top.get("name") or f"Lead #{top.get('id')}"
                        )
                        price = float(top.get("price") or 0)
                        if price > 0:
                            ctx["top_stagnated_value"] = (
                                f"{price:,.0f} so'm".replace(",", " ")
                                if price >= 1_000_000
                                else f"${price:,.0f}"
                            )

            if hasattr(self.amocrm, "get_all_leads"):
                all_leads = await asyncio.to_thread(self.amocrm.get_all_leads, limit=100)
                if isinstance(all_leads, (list, tuple)):
                    active = [
                        lead
                        for lead in all_leads
                        if isinstance(lead, dict)
                        and str(lead.get("status_id")) not in {"142", "143"}
                    ]
                    won = [
                        lead
                        for lead in all_leads
                        if isinstance(lead, dict) and str(lead.get("status_id")) == "142"
                    ]
                    ctx["active_leads_count"] = len(active)
                    ctx["pipeline_value"] = sum(
                        float(lead.get("price") or 0) for lead in active
                    )
                    if won:
                        ctx["won_recent_count"] = len(won)
        except Exception as exc:
            logger.warning("[PSYCH_AUTO] CRM metrics yig'ishda xatolik: %s", exc)

    async def _collect_project_and_call_metrics(self, ctx: Dict[str, Any]) -> None:
        try:
            overdue: Any = None
            if self.airtable and hasattr(self.airtable, "get_overdue_projects"):
                try:
                    overdue = await asyncio.to_thread(
                        self.airtable.get_overdue_projects, limit=10
                    )
                except TypeError:
                    overdue = await asyncio.to_thread(
                        self.airtable.get_overdue_projects
                    )
            if isinstance(overdue, (list, tuple)):
                ctx["overdue_projects_count"] = len(overdue)
                if overdue and isinstance(overdue[0], dict):
                    ctx["top_overdue_project"] = _extract_project_name(overdue[0])
            elif self.db and hasattr(self.db, "get_all_projects"):
                projs = await self.db.get_all_projects()
                if isinstance(projs, (list, tuple)):
                    ctx["active_projects_count"] = len(projs)
        except Exception as exc:
            logger.warning("[PSYCH_AUTO] Project metrics yig'ishda xatolik: %s", exc)

        if not self.db:
            return
        try:
            rows = await fetch_rows(
                self.db,
                "SELECT overall_score, duration_seconds FROM call_analyses "
                "WHERE created_at >= datetime('now', '-2 days') LIMIT 200",
                [],
            )
            if isinstance(rows, (list, tuple)) and rows:
                ctx["recent_calls_count"] = len(rows)
                solid = sum(
                    1
                    for r in rows
                    if int(_row_val(r, "duration_seconds", 0) or 0) >= 180
                )
                scores = [
                    float(_row_val(r, "overall_score", 0) or 0)
                    for r in rows
                    if float(_row_val(r, "overall_score", 0) or 0) > 0
                ]
                ctx["solid_calls_count"] = solid
                if scores:
                    ctx["avg_call_score"] = sum(scores) / len(scores)
        except Exception as exc:
            logger.debug("[PSYCH_AUTO] Call metrics o'qilmadi: %s", exc)

    async def collect_morning_context(
        self, now: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """AmoCRM, Airtable va DB dan real operatsion ko'rsatkichlarni yig'ish."""
        ctx: Dict[str, Any] = {}
        await self._collect_crm_metrics(ctx)
        await self._collect_project_and_call_metrics(ctx)
        return ctx

    async def build_morning_boost(
        self,
        now: Optional[datetime] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Real ko'rsatkichlarni yig'ib, vaziyatga mos ertalabki impuls yaratish."""
        live_ctx = await self.collect_morning_context(now=now)
        if context:
            live_ctx.update(context)
        return self.generate_morning_boost(context=live_ctx, now=now)

    async def scan_and_generate_sales_reluctance_interventions(
        self, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """AmoCRM dagi harakatsiz/qotib qolgan lidlar uchun avtomatik kouching tayyorlash."""
        interventions: List[Dict[str, Any]] = []
        if not self.amocrm:
            logger.warning("[PSYCH_AUTO] AmoCRM client mavjud emas, soxta ma'lumot berilmaydi.")
            return interventions

        try:
            leads = []
            if hasattr(self.amocrm, "get_stagnated_leads"):
                leads = await asyncio.to_thread(
                    self.amocrm.get_stagnated_leads, hours=24, limit=limit
                )
            elif hasattr(self.amocrm, "get_all_leads"):
                all_leads = await asyncio.to_thread(
                    self.amocrm.get_all_leads, limit=limit * 3
                )
                leads = [
                    lead
                    for lead in (all_leads or [])
                    if str(lead.get("status_id")) not in {"142", "143"}
                ][:limit]

            for lead in (leads or []):
                lead_id = lead.get("id")
                name = lead.get("name") or f"Lead #{lead_id}"
                price = lead.get("price") or 0
                price_str = f"${price:,.0f}" if price else "$2,500"
                manager_id = lead.get("responsible_user_id")

                breakthrough = PsychologicalCoach.deconstruct_fear(
                    text=f"mijozga telefon qilmoqchi lekin qilolmayapti {name}",
                    role="sales",
                    client_name=name,
                    context={"deal_value": price_str, "lead_id": lead_id},
                )
                formatted = (
                    f"🚨 **AVTOMATIK SOTUV PUSH & KOUCHING**\n"
                    f"👤 **Lid:** `{name}` (ID: #{lead_id}) | 💰 Qiymat: `{price_str}`\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"❓ **Nega telefon qilmayapsan? Hozir qilsang nima bo'ladi?**\n"
                    f"{breakthrough.worst_case_analysis}\n\n"
                    f"⏳ **Qilmaslikning narxi:**\n"
                    f"{breakthrough.inaction_cost}\n\n"
                    f"{breakthrough.micro_script}\n\n"
                    f"{breakthrough.action_challenge}"
                )
                interventions.append({
                    "lead_id": lead_id,
                    "manager_id": manager_id,
                    "client_name": name,
                    "deal_value": price_str,
                    "message": formatted,
                })
        except Exception as exc:
            logger.error("[PSYCH_AUTO] Sales scan xatoligi: %s", exc, exc_info=True)

        return interventions

    async def scan_and_generate_pm_interventions(
        self, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Airtable/loyiha tizimidagi xavfli loyihalar uchun avtomatik PM kouching."""
        interventions: List[Dict[str, Any]] = []
        if not self.airtable and not hasattr(self.db, "get_all_projects"):
            return interventions

        try:
            projects = []
            if self.airtable and hasattr(self.airtable, "get_overdue_projects"):
                try:
                    projects = await asyncio.to_thread(
                        self.airtable.get_overdue_projects, limit=limit
                    )
                except TypeError:
                    projects = await asyncio.to_thread(
                        self.airtable.get_overdue_projects
                    )
            elif self.db and hasattr(self.db, "get_all_projects"):
                projects = await self.db.get_all_projects()

            for proj in (projects or [])[:limit]:
                proj_name = _extract_project_name(proj)
                manager = proj.get("manager") or proj.get("pm") or "PM"
                deadline = proj.get("deadline") or "Yaqin kunlarda"

                breakthrough = PsychologicalCoach.deconstruct_fear(
                    text=f"kechikishni aytishga qo'rqyapman {proj_name}",
                    role="pm",
                    client_name=proj_name,
                    context={"project_name": proj_name, "deadline": deadline},
                )
                formatted = (
                    f"🛡 **AVTOMATIK PM LOYIHA HIMOYASI & KOUCHING**\n"
                    f"📁 **Loyiha:** `{proj_name}` | 👤 **PM:** `{manager}`\n"
                    f"📅 **Deadline:** `{deadline}`\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"{breakthrough.worst_case_analysis}\n\n"
                    f"{breakthrough.micro_script}\n\n"
                    f"{breakthrough.action_challenge}"
                )
                interventions.append({
                    "project_name": proj_name,
                    "manager": manager,
                    "deadline": deadline,
                    "message": formatted,
                })
        except Exception as exc:
            logger.error("[PSYCH_AUTO] PM scan xatoligi: %s", exc, exc_info=True)

        return interventions

    async def deliver_interventions(
        self,
        interventions: List[Dict[str, Any]],
        target_chat_id: Any,
        topic_id: Optional[int] = None,
    ) -> int:
        """Tayyorlangan kouching xabarlarini avtomatik Telegramga yetkazish."""
        if not self.bot_client or not target_chat_id:
            logger.warning("[PSYCH_AUTO] bot_client yoki target_chat_id yo'q.")
            return 0

        sent_count = 0
        for item in interventions:
            msg = item.get("message")
            if not msg:
                continue
            try:
                kwargs: Dict[str, Any] = {"parse_mode": "markdown"}
                if topic_id:
                    kwargs["message_thread_id"] = topic_id
                await self.bot_client.send_message(target_chat_id, msg, **kwargs)
                sent_count += 1
                await asyncio.sleep(0.5)
            except Exception as exc:
                logger.error("[PSYCH_AUTO] Xabar yuborishda xato: %s", exc)

        return sent_count
