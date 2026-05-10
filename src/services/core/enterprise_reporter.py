import logging
import datetime
import asyncio
import time
import requests
from typing import Dict, Any, List, Set
from src.database import Database
from src.services.core.crm_service import CRMService
from src.time_utils import get_local_now

logger = logging.getLogger(__name__)


class EnterpriseReporter:
    """Jamoa samaradorligi va Plan-Fakt hisobotlarini tayyorlash xizmati."""

    def __init__(self, db: Database, crm: CRMService, airtable=None):
        self.db = db
        self.crm = crm
        self.airtable = airtable
        # Standart statuslar (AmoCRM defaults)
        self.WON_STATUS = 142
        self.LOST_STATUS = 143
        self.HUNTER_PIPELINE_ID = 10117998
        self.CLOSER_PIPELINE_ID = 10123314

    async def get_daily_efficiency_report(self):
        """Kunlik hisobot: faqat bugungi o'zgarishlar va umumiy holat."""
        now = get_local_now()
        today_str = now.strftime("%Y-%m-%d")
        month_str = now.strftime("%Y-%m")
        report = [f"📊 <b>KUNLIK ENTERPRISE HISOBOT</b> ({today_str})\n"]

        # 1. SALES (AmoCRM)
        if self.crm:
            # Bugungi yopilgan bitimlar (Won)
            report.append("💰 <b>Sales Performance (Bugun):</b>")
            try:
                # Real-time data from AmoCRM
                leads = asyncio.run_coroutine_threadsafe(
                    self.crm.amocrm.get_leads_detailed(limit=50),
                    asyncio.get_event_loop(),
                ).result()
                won_today = [lead for lead in leads if lead.get("status_id") == self.WON_STATUS]
                total_sum = sum(lead.get("price", 0) for lead in won_today)

                report.append(f"- Yangi lidlar: <b>{len(leads)} ta</b>")
                report.append(
                    f"- Yopilgan bitimlar: <b>{len(won_today)} ta</b> ({total_sum:,.0f} so'm)"
                )
            except Exception as e:
                logger.warning(f"Error getting lead statistics: {e}")
                report.append("- Ma'lumotlar olinmoqda... ⏳")

            # Plan-Fakt (Monthly context)
            targets = await self.db.get_department_targets(month_str)
            sales_target = next(
                (t["value"] for t in targets if t["dept"] == "Sales"), 0
            )
            if sales_target > 0:
                report.append(f"- Oylik reja: {sales_target:,.0f} so'm")

        # 2. PM (Airtable)
        if self.airtable:
            # Bugun bitgan yoki o'zgargan loyihalar
            report.append("\n🏗 <b>Production (Bugun):</b>")
            projects = self.airtable.get_projects()
            report.append(f"- Aktiv loyihalar: {len(projects)} ta")

        # 3. FINANCE (Airtable)
        if self.airtable:
            finance_records = self.airtable.get_finance_records()
            today_income = 0
            today_expense = 0

            for rec in finance_records:
                f = rec.get("fields", {})
                rec_type = rec.get("_record_type", "")
                if rec_type == "income":
                    date_str = f.get("To'lov sanasi") or f.get("Sana") or ""
                    amount = f.get("To'lov miqdori") or f.get("Summa") or 0
                    if date_str and date_str.startswith(today_str):
                        today_income += amount
                elif rec_type == "expense":
                    date_str = f.get("Chiqim sanasi") or f.get("Sana") or ""
                    amount = f.get("Chiqim miqdori") or f.get("Summa") or 0
                    if date_str and date_str.startswith(today_str):
                        today_expense += amount

            if today_income > 0 or today_expense > 0:
                report.append("\n💰 <b>Moliya (Bugun):</b>")
                report.append(f"- Kirim: {today_income:,.0f} so'm".replace(",", " "))
                report.append(f"- Chiqim: {today_expense:,.0f} so'm".replace(",", " "))
                report.append(
                    f"- Net Foyda: <b>{(today_income - today_expense):,.0f} so'm</b>".replace(
                        ",", " "
                    )
                )

        report.append(
            "\n🌙 <i>Bugungi kun uchun rahmat! Ertaga yanada yaxshiroq bo'lamiz.</i>"
        )
        return "\n".join(report)

    async def get_team_efficiency_report(self) -> str:
        """Jamoa va bo'limlar uchun umumiy samaradorlik hisoboti."""
        now = get_local_now()
        month_str = now.strftime("%Y-%m")

        report = []
        report.append("🏢 <b>Oisha-OS: Enterprise Audit</b>")
        report.append(f"⏱ <i>Hisobot vaqti: {now.strftime('%Y-%m-%d %H:%M')}</i>\n")

        # 1. SALES & MARKETING (AmoCRM)
        # Reja-fakt hisoblash
        targets = await self.db.get_department_targets(month_str)
        sales_target = next(
            (t["value"] for t in targets if t["dept"] == "Sales"), 80_000_000
        )

        leads = await self.crm.amocrm.get_leads_detailed(limit=100)

        # Oylik yopilgan bitimlar summasi (Fact)
        # Eslatma: AmoCRM API limitlari tufayli 'Won' larni alohida filtrlab olish kerak bo'lishi mumkin
        won_leads = [lead for lead in leads if lead.get("status_id") == self.WON_STATUS]
        total_won_sum = sum(lead.get("price", 0) for lead in won_leads)

        active_leads = len(
            [
                lead
                for lead in leads
                if lead.get("status_id") not in [self.WON_STATUS, self.LOST_STATUS]
            ]
        )

        report.append("💰 <b>Sales Performance:</b>")
        report.append(f"- Oylik Reja: {sales_target:,.0f} so'm".replace(",", " "))
        report.append(f"- Amalda (Won): {total_won_sum:,.0f} so'm".replace(",", " "))

        progress_pct = (total_won_sum / sales_target * 100) if sales_target > 0 else 0
        report.append(
            f"- Reja bajarilishi: <b>{progress_pct:.1f}%</b> {'✅' if progress_pct >= 100 else '📈'}"
        )
        report.append(f"- Aktiv lidlar: {active_leads} ta")

        # 2. MARKETING (Channels)
        # Manbalar tahlili (Tags orqali)
        channels = {}
        for lead in leads:
            # AmoCRM tags structure: _embedded.tags
            tags = lead.get("_embedded", {}).get("tags", [])
            for tag in tags:
                tag_name = tag.get("name", "Noma'lum")
                channels[tag_name] = channels.get(tag_name, 0) + 1

        if channels:
            top_channel = max(channels, key=channels.get)
            report.append("\n📢 <b>Marketing Awareness:</b>")
            report.append(
                f"- Top kanal: <b>{top_channel}</b> ({channels[top_channel]} lid)"
            )

        # 3. PRODUCTION & PM (Airtable)
        if self.airtable:
            projects = self.airtable.get_projects()
            overdue = self.airtable.get_overdue_projects()
            report.append("\n🏗 <b>Production & PM (Airtable):</b>")
            report.append(f"- Aktiv loyihalar: {len(projects)} ta")

            # 3 kunlik ishlab chiqarish qoidasi (SLA: 3 days)
            urgent_projects = []
            now_dt = get_local_now()

            from src.services.core.airtable_sync import AirtableSync as _AT

            for p in projects:
                fields = p.get("fields", {})
                created_str = _AT._get_field(fields, "start_date")
                stage = _AT._get_field(fields, "stage") or ""

                if stage in _AT.DONE_STAGES:
                    continue

                if created_str:
                    try:
                        created_dt = datetime.datetime.fromisoformat(
                            created_str.replace("Z", "+00:00")
                        )
                        if created_dt.tzinfo:
                            now_utc = datetime.datetime.now(datetime.timezone.utc)
                            diff = now_utc - created_dt
                        else:
                            diff = now_dt - created_dt

                        if diff.days >= 2:
                            proj_name = (
                                _AT._get_field(fields, "project_name") or "Nomsiz"
                            )
                            urgent_projects.append(
                                f"{proj_name} ({diff.days} kun o'tdi)"
                            )
                    except:
                        continue

            if overdue:
                report.append(f"- Muddati o'tgan: {len(overdue)} ta ⚠️")

                report.append(
                    f"- <b>SLA xavfi (3 kundan oshish arafasida):</b> {len(urgent_projects)} ta"
                )

                # Tag specific PMs for urgent projects
                pm_mentions = set()
                for p in projects:
                    fields = p.get("fields", {})
                    # Re-check if urgent (simplified for reporting)
                    pm_value = _AT._get_field(fields, "manager")
                    pm_mention = _AT.resolve_pm_handle(pm_value)
                    pm_mentions.add(pm_mention)

                if pm_mentions:
                    mentions_str = ", ".join(sorted(pm_mentions))
                    report.append(f"  <i>(Iltimos, {mentions_str} nazoratga oling)</i>")

        # 4. FINANCE SUMMARY (Airtable — Kirim + Chiqim)
        if self.airtable:
            finance_records = self.airtable.get_finance_records()
            month_income = 0
            month_expense = 0
            current_month = datetime.datetime.now().strftime("%Y-%m")

            for rec in finance_records:
                f = rec.get("fields", {})
                rec_type = rec.get("_record_type", "")
                if rec_type == "income":
                    date_str = f.get("To'lov sanasi") or f.get("Sana") or ""
                    amount = f.get("To'lov miqdori") or f.get("Summa") or 0
                    if date_str and date_str.startswith(current_month):
                        month_income += amount
                elif rec_type == "expense":
                    date_str = f.get("Chiqim sanasi") or f.get("Sana") or ""
                    amount = f.get("Chiqim miqdori") or f.get("Summa") or 0
                    if date_str and date_str.startswith(current_month):
                        month_expense += amount

            report.append(f"\n📈 <b>Oylik Moliya ({current_month}):</b>")
            report.append(f"- Jami tushum: {month_income:,.0f} so'm".replace(",", " "))
            report.append(
                f"- Jami xarajat: {month_expense:,.0f} so'm".replace(",", " ")
            )
            net_profit = month_income - month_expense
            report.append(
                f"- <b>Sof Foyda: {net_profit:,.0f} so'm</b> {'🔥' if net_profit > 0 else '📉'}"
            )

        # 5. ACCOUNTABILITY (Tasks & Reports)
        report.append("\n" + await self.get_accountability_segment())

        report.append("\n👑 <b>XULOSA</b>")
        report.append(
            f"<i>Oisha-OS avtomatik hisobot — {get_local_now().strftime('%Y-%m-%d %H:%M')}</i>"
        )

        report.append("\n💡 <i>Tizimli yondashuv — o'sish poydevori!</i>")
        return "\n".join(report)

    async def get_accountability_segment(self) -> str:
        """Topshiriqlarni va hisobotlarni o'z vaqtida bajarmayotganlarni aniqlash."""
        report = []
        report.append("⚖️ <b>Accountability & Discipline:</b>")

        # 1. Muddati o'tgan vazifalar
        overdue_tasks = await self.db.get_overdue_tasks()
        if overdue_tasks:
            report.append(
                f"- <b>Muddati o'tgan vazifalar:</b> {len(overdue_tasks)} ta ⚠️"
            )
            for t in overdue_tasks[:3]:  # Faqat birinchi 3 tasini ko'rsatamiz
                name = t.get("name") or t.get("username") or "Unknown"
                task_label = t.get("title") or t.get("description") or "Vazifa"
                report.append(f"  • {task_label} — <i>{name}</i>")
            if len(overdue_tasks) > 3:
                report.append(f"  ... va yana {len(overdue_tasks)-3} ta.")
        else:
            report.append("- Barcha vazifalar o'z vaqtida! ✅")

        # 2. Topshirilmagan hisobotlar (Bugun uchun)
        missing_reports = await self.db.get_missing_reports()
        if missing_reports:
            names = [
                f"@{m['username']}" if m["username"] else m["name"]
                for m in missing_reports
            ]
            report.append(f"- <b>Bugun hisobot bermaganlar:</b> {', '.join(names)} 🛑")
        else:
            report.append("- Hamma hisobot topshirdi! 🌟")

        return "\n".join(report)

    async def get_real_numbers_audit(self) -> str:
        """Real raqamlarda jamoa auditi: qilinayotgan va qilinmayotgan ishlar.

        [FIXED v2.3] Now checks multiple health indicators:
        - Multi-period stagnation (24h, 48h, 7d)
        - Leads without tasks
        - Overdue tasks
        - Unsorted messages
        - Weighted health score (0-100%)
        """
        now = get_local_now()
        report = ["📊 *OISHA-OS: CRM HYGIENE & PERFORMANCE AUDIT*"]
        report.append(f"📅 _{now.strftime('%d.%m.%Y | %H:%M')}_\n")

        # 1. Fetch all leads (up to 200 for comprehensive analysis)
        all_leads: List[Dict] = []
        for page in [1, 2]:
            url = f"{self.crm.amocrm.base_url}/api/v4/leads?limit=100&page={page}"
            resp = requests.get(url, headers=self.crm.amocrm._get_headers())
            if resp.status_code == 200:
                page_leads = resp.json().get("_embedded", {}).get("leads", [])
                all_leads.extend(page_leads)
            else:
                break

        if not all_leads:
            return "❌ **XATO:** AmoCRM'dan lidlar olinmadi. Token tekshiring."

        # 2. Fetch all tasks
        all_tasks = await self.crm.amocrm.get_tasks()
        {
            t.get("entity_id") for t in all_tasks if t.get("entity_type") == "leads"
        }
        now_ts = time.time()

        # 3. Comprehensive Health Metrics
        metrics = {
            "total_leads": len(all_leads),
            "active_leads": 0,
            "stagnant_24h": [],
            "stagnant_48h": [],
            "stagnant_7d": [],
            "no_tasks": [],
            "overdue_tasks": [],
            "revenue_at_risk": 0,
        }

        for lead in all_leads:
            status_id = lead.get("status_id")

            # Skip Won/Lost leads from active counts
            if status_id in [self.WON_STATUS, self.LOST_STATUS]:
                continue

            metrics["active_leads"] += 1
            lead_id = lead.get("id")
            updated_at = lead.get("updated_at", 0)
            hours_stagnant = (now_ts - updated_at) / 3600
            price = lead.get("price", 0) or 0

            # Multi-period stagnation tracking
            if hours_stagnant > 24:
                metrics["stagnant_24h"].append(lead)
                metrics["revenue_at_risk"] += price
            if hours_stagnant > 48:
                metrics["stagnant_48h"].append(lead)
            if hours_stagnant > 7 * 24:
                metrics["stagnant_7d"].append(lead)

            # Check for tasks
            lead_tasks = [t for t in all_tasks if t.get("entity_id") == lead_id]
            if not lead_tasks:
                metrics["no_tasks"].append(lead)
            else:
                # Check for overdue tasks
                if any(t.get("complete_till", 0) < now_ts for t in lead_tasks):
                    metrics["overdue_tasks"].append(lead)

        # 4. Check unsorted messages
        unsorted_count = 0
        try:
            un_resp = requests.get(
                f"{self.crm.amocrm.base_url}/api/v4/leads/unsorted",
                headers=self.crm.amocrm._get_headers(),
            )
            if un_resp.status_code == 200:
                unsorted_count = len(
                    un_resp.json().get("_embedded", {}).get("unsorted", [])
                )
        except Exception as e:
            logger.warning(f"[AUDIT] Unsorted fetch failed: {e}")

        # 5. Calculate Health Score (0-100%)
        # Formula: Start at 100, deduct penalties
        health_score = 100
        penalties = {
            "no_tasks": len(metrics["no_tasks"]) * 10,  # -10 per lead without tasks
            "overdue": len(metrics["overdue_tasks"]) * 5,  # -5 per overdue task
            "stagnant_24h": len(metrics["stagnant_24h"]) * 3,  # -3 per 24h stagnant
            "stagnant_48h": len(metrics["stagnant_48h"]) * 5,  # -5 per 48h stagnant
            "stagnant_7d": len(metrics["stagnant_7d"]) * 10,  # -10 per 7d stagnant
            "unsorted": unsorted_count * 2,  # -2 per unsorted
        }

        total_penalty = sum(penalties.values())
        # Scale penalty: max 100 points deducted
        health_score = max(0, 100 - min(total_penalty, 100))

        # 6. Build Comprehensive Report
        report.append(f"📈 **CRM SALOMATLIGI: {health_score}%**")

        if health_score >= 80:
            report.append("🟢 *Holat: Yaxshi*")
        elif health_score >= 60:
            report.append("🟡 *Holat: O'rtacha - Diqqat talab*")
        elif health_score >= 40:
            report.append("🟠 *Holat: Yomon - Tezkor choralar*")
        else:
            report.append("🔴 *Holat: Kritik - Darhol ishga kiring!*")

        report.append("\n📊 **ASOSIY KO'RSATKICHLAR:**")
        report.append(f"• Jami aktiv lidlar: **{metrics['active_leads']} ta**")

        # Task-related issues (HIGHEST PRIORITY)
        if metrics["no_tasks"] or metrics["overdue_tasks"]:
            report.append("\n⚠️ **VAZIFA MUAMMOLARI (YUQORI USTUVORLIK):**")
            if metrics["no_tasks"]:
                report.append(
                    f"• ❌ Vazifasiz lidlar: **{len(metrics['no_tasks'])} ta**"
                )
            if metrics["overdue_tasks"]:
                report.append(
                    f"• ⏰ Muddati o'tgan vazifalar: **{len(metrics['overdue_tasks'])} ta**"
                )

        # Stagnation issues
        if any(
            [metrics["stagnant_24h"], metrics["stagnant_48h"], metrics["stagnant_7d"]]
        ):
            report.append("\n🐌 **STAGNATSiya (Harakatsiz lidlar):**")
            if metrics["stagnant_24h"]:
                report.append(
                    f"• 24 soatdan oshgan: **{len(metrics['stagnant_24h'])} ta**"
                )
            if metrics["stagnant_48h"]:
                report.append(
                    f"• 48 soatdan oshgan: **{len(metrics['stagnant_48h'])} ta**"
                )
            if metrics["stagnant_7d"]:
                report.append(
                    f"• 7 kundan oshgan: **{len(metrics['stagnant_7d'])} ta** ⚠️"
                )

        # Financial risk
        if metrics["revenue_at_risk"] > 0:
            report.append("\n💰 **MOLIYAVIY XAVF:**")
            report.append(
                f"• Muzlab qolgan summa: **{metrics['revenue_at_risk']:,.0f} so'm**".replace(
                    ",", " "
                )
            )

        # Unsorted
        if unsorted_count > 0:
            report.append("\n📥 **SARALANMAGAN:**")
            report.append(f"• Saralanmagan xabarlar: **{unsorted_count} ta**")

        # Junk Leads summary
        try:
            junk_leads = await self.identify_junk_leads(limit=100)
            if junk_leads:
                report.append("\n🧹 **JUNK LEADS (BEKORCHI):**")
                report.append(f"• Jami shubhali sdelkalar: **{len(junk_leads)} ta**")
                report.append("  _(Batafsil ko'rish uchun: `/junk_audit`)_")
        except:
            pass

        # 7. Accountability (Managers) - FIXED
        report.append("\n👥 **MENEdjerlar FAOLLIGI:**")
        try:
            async with await self.db.get_connection() as conn:
                async with conn.execute(
                    "SELECT first_name, role FROM users WHERE role IS NOT NULL"
                ) as cursor:
                    team = await cursor.fetchall()

            for name, role in team:
                # Count all problematic leads for this manager
                manager_problems = sum(
                    1
                    for lead in metrics["no_tasks"] + metrics["overdue_tasks"]
                    if lead.get("responsible_user_id") == name
                )

                if manager_problems == 0:
                    report.append(f"• {name} ({role}): ✅ A'lo")
                elif manager_problems <= 2:
                    report.append(f"• {name} ({role}): 🟡 {manager_problems} muammo")
                else:
                    report.append(
                        f"• {name} ({role}): 🔴 {manager_problems} muammo - Diqqat!"
                    )
        except Exception as e:
            logger.warning(f"[AUDIT] Manager stats failed: {e}")
            report.append("• Menejеr ma'lumotlari olinmadi")

        # 8. Detailed Problem List (if issues exist)
        problem_leads = metrics["no_tasks"][:3]  # Show first 3 as examples
        if problem_leads:
            report.append("\n📝 **NAMUNA VAZIFASIZ LIDLAR:**")
            for lead in problem_leads:
                l_name = lead.get("name", "Nomsiz")
                l_id = lead.get("id")
                report.append(f"  • {l_name} (ID: {l_id})")

        # 9. OISHA Analysis - ACCURATE
        report.append("\n💡 **OISHA TAHLILI:**")

        if health_score >= 80:
            report.append(
                '_"CRM tartibi yaxshi. Asosiy e\'tiborni yangi lidlarni yopishga qarating."_'
            )
        elif health_score >= 60:
            report.append(
                "_\"CRM'da ayrim muammolar mavjud. Vazifasiz lidlarga e'tibor bering.\"_"
            )
        elif health_score >= 40:
            report.append(
                '_"⚠️ CRM tartibi yomon! Darhol vazifalar qo\'shing va stagnat lidlar bilan ishlang."_'
            )
        else:
            report.append(
                '_"🚨 KRITIK! CRM to\'la tartibsizlikda! @baxtiyorjong_gaziyev darhol nazoratga oling!"_'
            )
        return "\n".join(report)

    async def identify_junk_leads(self, limit: int = 250) -> List[Dict[str, Any]]:
        """Identify 'junk' leads in amoCRM based on inactivity, lack of data, or stagnation."""
        # 1. Fetch leads
        all_leads = await self.crm.amocrm.get_leads_detailed(limit=limit)
        if not all_leads:
            return []

        # 2. Fetch all tasks to check for task-less leads
        all_tasks = await self.crm.amocrm.get_tasks()
        task_entity_ids: Set[int] = {
            t.get("entity_id") for t in all_tasks if t.get("entity_type") == "leads"
        }

        junk_leads = []
        now_ts = time.time()

        for lead in all_leads:
            reasons = []
            status_id = lead.get("status_id")

            # Skip Won/Lost statuses
            if status_id in [self.WON_STATUS, self.LOST_STATUS]:
                continue

            # Rule 1: Extreme Stagnation (> 14 days)
            updated_at = lead.get("updated_at", 0)
            stagnant_days = (now_ts - updated_at) / (24 * 3600)
            if stagnant_days > 14:
                reasons.append(f"{int(stagnant_days)} kundan beri harakatsiz")

            # Rule 2: No Future Task
            if lead.get("id") not in task_entity_ids:
                reasons.append("Vazifasi yo'q (No Task)")

            # Rule 3: Missing Price in high-intent stages
            price = lead.get("price", 0) or 0
            if price == 0 and stagnant_days > 3:
                reasons.append("Qiymati 0 so'm (Price is 0)")

            # Rule 4: No Contact Person linked
            contacts = lead.get("_embedded", {}).get("contacts", [])
            if not contacts:
                reasons.append("Kontakt bog'lanmagan")

            if reasons:
                lead["junk_reasons"] = reasons
                junk_leads.append(lead)

        # Sort by most reasons/stagnancy
        junk_leads.sort(key=lambda x: len(x.get("junk_reasons", [])), reverse=True)
        return junk_leads

    async def get_junk_leads_report(self, limit: int = 200) -> str:
        """Generate a formatted report of junk leads for administrative review."""
        junk_leads = await self.identify_junk_leads(limit=limit)

        if not junk_leads:
            return "✅ **CRM HYGIENE OK:** Hozircha keraksiz yoki 'bekorchi' sdelkalar topilmadi."

        report = ["🧹 **OISHA: JUNK LEADS AUDIT (BEKORCHI SDELKALAR)**"]
        report.append(f"🔍 Jami tekshirildi: {limit} ta lid")
        report.append(f"⚠️ Topildi: **{len(junk_leads)} ta** shubhali sdelka\n")

        # Show top 15 junk leads
        for i, lead in enumerate(junk_leads[:15], 1):
            name = lead.get("name", "Nomsiz")
            l_id = lead.get("id")
            reasons = ", ".join(lead.get("junk_reasons", []))

            # Simple link to AmoCRM
            link = f"https://{self.crm.amocrm.subdomain}.amocrm.ru/leads/detail/{l_id}"

            report.append(f"{i}. <b>{name}</b> (ID: {l_id})")
            report.append(f"   🛑 Sabab: <i>{reasons}</i>")
            report.append(f"   🔗 [CRM LINK]({link})\n")

        if len(junk_leads) > 15:
            report.append(f"... va yana {len(junk_leads)-15} ta shubhali sdelka.")

        report.append(
            "\n💡 **MASLAHAT:** Bu sdelkalarni yopish yoki menejerlarga vazifa qo'shish tavsiya etiladi."
        )
        return "\n".join(report)

    async def get_stagnant_leads_alert(self, limit: int = 50) -> str:
        """Stagnant leads alert (24h+) in the specific format requested by user."""
        leads = await self.crm.amocrm.get_leads_detailed(limit=limit)
        if not leads:
            return ""

        now = get_local_now().timestamp()
        day_seconds = 24 * 3600

        stagnant_items = []
        for lead in leads:
            # Skip Won/Lost statuses
            if lead.get("status_id") in [self.WON_STATUS, self.LOST_STATUS]:
                continue

            updated_at = lead.get("updated_at", 0)
            if (now - updated_at) > day_seconds:
                name = l.get("name", "Nomsiz")
                l_id = l.get("id")
                # Extract phone from custom fields if possible (simplified here)
                phone = "Raqam yo'q"
                for cf in l.get("custom_fields_values") or []:
                    if cf.get("field_code") == "PHONE":
                        phone = cf.get("values", [{}])[0].get("value", "Raqam yo'q")
                        break

                link = (
                    f"https://{self.crm.amocrm.subdomain}.amocrm.ru/leads/detail/{l_id}"
                )
                stagnant_items.append(f"• {name} {phone} ({link})")

        if stagnant_items:
            # Limit to top 10 for readability
            items_str = "\n".join(stagnant_items[:10])
            report = (
                f"🚨 **STAGNATION ALERT (24h+)**\n\n"
                f"Quyidagi bitimlar harakatsiz qolmoqda:\n"
                f"{items_str}\n\n"
                f"@Oydin_JonBranding va @tezmenejer, iltimos statusni tekshiring."
            )
            return report
        return ""

    async def generate_morning_plan(self, distribution: Dict[int, List[Dict]]) -> str:
        """Ertalabki 'Plan' hisoboti."""
        now = get_local_now()
        report = [
            f"☀️ <b>{now.strftime('%d.%m.%Y')} — YANGI KUN, YANGI G'ALABALAR!</b>",
            "🚀 Oisha-OS jamoani jangovar shay holatga keltiradi.\n",
            "📌 <b>BUGUNGI VAZIFALAR (MISSION CONTROL):</b>",
        ]

        for m_id, missions in distribution.items():
            m_info = await self.db.get_user_info(m_id)
            name = m_info.get("first_name") if m_info else f"Manager_{m_id}"
            if (
                "pm" in name.lower()
                or "dilbar" in name.lower()
                or str(m_id) == "8611068511"
            ):
                name = "👩‍💼 PM Dilbar"

            report.append(f"\n👤 <b>{name}</b>")
            if not missions:
                report.append(
                    "  ▫️ Bugun yangi lidlar yo'q. Eski loyihalar ustida ishlang."
                )
            else:
                # Voronkalarni guruhlash (Refined with Role logic)
                hunters = [
                    m
                    for m in missions
                    if m.get("role") == "HUNTER"
                    or any(
                        x in (m.get("pipeline") or "").lower()
                        for x in ["hunter", "so'rov", "qual"]
                    )
                ]
                setters = [m for m in missions if m not in hunters]

                if hunters:
                    report.append("  🏹 <b>HUNTER MISSIONS:</b>")
                    for i, m in enumerate(hunters, 1):
                        report.append(
                            f"    {i}. {m['lead_name']} — {m['mission']} <a href='{m['link']}'>[CRM]</a>"
                        )

                if setters:
                    report.append("  🎯 <b>SETTER / CLOSER MISSIONS:</b>")
                    for i, m in enumerate(setters, 1):
                        report.append(
                            f"    {i}. {m['lead_name']} — {m['mission']} <a href='{m['link']}'>[CRM]</a>"
                        )

    async def generate_plan_fact_report(self) -> str:
        """Kechki 'Plan-Fakt' hisoboti."""
        today = get_local_now().strftime("%Y-%m-%d")
        plans = await self.db.get_daily_plan(today)

        if not plans:
            # Vazifalar rejalashtirilmagan - jamoadan talab qilish
            return await self.generate_missing_plan_demand()

        report = [
            f"🌙 <b>{get_local_now().strftime('%d.%m.%Y')} — KUNLIK PLAN-FAKT TAHLILI</b>",
            "🧐 Oisha-OS natijalarni tekshirmoqda...\n",
        ]

        results = {}

        for p in plans:
            m_id = p["manager_id"]
            if m_id not in results:
                results[m_id] = {"total": 0, "achieved": 0, "leads": []}

            lead_id = p["lead_id"]
            status = "🔴 Bajarilmadi"

            try:
                lead = await self.crm.amocrm.get_lead(lead_id)
                if not lead:
                    status = "❓ Noma'lum"
                else:
                    current_status = lead.get("status_id")
                    current_pipeline = lead.get("pipeline_id")
                    src = (p.get("source_pipeline") or "").upper() or None

                    if current_status == self.WON_STATUS:
                        status = "✅ SHARTNOMA! (+)"
                        results[m_id]["achieved"] += 1
                    elif current_status == self.LOST_STATUS:
                        status = "⚫ Yutqazilgan"
                    elif src == "HUNTER":
                        if current_pipeline != self.HUNTER_PIPELINE_ID:
                            status = "✅ Oldinga siljish (Hunter → boshqa pipeline)"
                            results[m_id]["achieved"] += 1
                    elif src == "CLOSER":
                        pass
                    else:
                        if (
                            current_pipeline == self.CLOSER_PIPELINE_ID
                            and current_status != self.WON_STATUS
                        ):
                            pass
                        elif current_pipeline != self.HUNTER_PIPELINE_ID:
                            status = "✅ Oldinga siljish"
                            results[m_id]["achieved"] += 1
            except Exception as e:
                logger.warning(f"[PLAN-FACT] lead {lead_id}: {e}")
                status = "❓ Noma'lum"

            results[m_id]["total"] += 1
            results[m_id]["leads"].append(f"  ▫️ {p['lead_name']}: {status}")

        for m_id, data in results.items():
            m_info = await self.db.get_user_info(m_id)
            name = m_info.get("first_name") if m_info else f"Manager_{m_id}"
            if (
                "pm" in name.lower()
                or "dilbar" in name.lower()
                or str(m_id) == "8611068511"
            ):
                name = "👩‍💼 PM Dilbar"

            pct = (data["achieved"] / data["total"] * 100) if data["total"] > 0 else 0
            emoji = "🔥" if pct >= 80 else "⚠️" if pct >= 50 else "❄️"

            report.append(f"👤 <b>{name}</b> {emoji}")
            report.append(
                f"📊 KPI: <b>{data['achieved']}/{data['total']}</b> ({pct:.1f}%)"
            )
            report.append("\n".join(data["leads"]))
            report.append("")

        total_total = sum(d["total"] for d in results.values())
        total_achieved = sum(d["achieved"] for d in results.values())
        total_pct = (total_achieved / total_total * 100) if total_total > 0 else 0

        if total_pct >= 80:
            report.append(
                "🌟 <b>DAHSHAT!</b> Jamoa bugun haqiqiy professionalizm ko'rsatdi. Sizlar bilan faxrlanaman!"
            )
        elif total_pct >= 50:
            report.append(
                "👍 <b>Yaxshi.</b> Lekin ertaga bundan ham ko'proq natija kutaman. Bo'shashmang!"
            )
        else:
            report.append(
                "📢 <b>DIQQAT!</b> Bugungi natijalar kutilganidan past. Ertaga har bir bitim uchun jang qilishingizni so'rayman!"
            )

        return "\n".join(report)

    async def generate_missing_plan_demand(self) -> str:
        """Vazifalar rejalashtirilmaganda jamoadan talab qilish xabari."""
        now = get_local_now()

        # Real ma'lumotlarni olish
        try:
            leads = await self.crm.amocrm.get_leads_detailed(limit=50)
            active_leads = [
                lead
                for lead in leads
                if lead.get("status_id") not in [self.WON_STATUS, self.LOST_STATUS]
            ]
            total_value = sum(int(lead.get("price", 0) or 0) for lead in active_leads)
        except Exception as e:
            logger.warning(f"[MISSING PLAN] Lead fetch failed: {e}")
            active_leads = []
            total_value = 0

        report = [
            f"🌙 <b>{now.strftime('%d.%m.%Y')} — KUNLIK REJA TALAB ETILMOQDA</b>",
            "📢 <b>DIQQAT!</b> Bugun uchun rejalashtirilgan vazifalar topilmadi.\n",
            "🎯 <b>HAR BIR MENEJERDAN REJA KUTILYAPTI:</b>",
            "• Bugun qaysi lidlarga ishlayapsiz?",
            "• Qanday natijalar kutyapsiz?",
            "• Qanday yordam kerak?\n",
        ]

        if active_leads:
            report.append(
                f"💼 <b>AKTIV BITIMLAR:</b> {len(active_leads)} ta (qiymati: {total_value:,.0f} so'm)".replace(
                    ",", " "
                )
            )
            report.append(
                "📊 <i>CRM'dagi aktiv lidlaringiz bo'yicha rejani yuboring!</i>\n"
            )

        report.extend(
            [
                "✍️ <b>JAVOB FORMATI:</b>",
                "<code>PLAN:</code>",
                "<code>1) Asosiy vazifa</code>",
                "<code>2) Bugun yopiladigan bitim</code>",
                "<code>3) Kerakli yordam</code>\n",
                "⏰ <b>DEADLINE:</b> Kechki hisobotdan oldin (20:00)",
                "👑 <b>@baxtiyorjong_gaziyev nazorat qilmoqda</b>",
            ]
        )

        return "\n".join(report)

    async def generate_proactive_vision(self) -> str:
        """Vazifa bo'lmaganda jamoaga strategik yo'nalish va 'Growth Missions' berish."""
        logger.info("[PROACTIVE] Generating strategic vision since no plans found.")

        now = get_local_now()
        report = [
            f"🌙 <b>{now.strftime('%d.%m.%Y')} — STRATEGIK O'SISH IMKONIYaTI</b>",
            "Biron bir konkret vazifa rejalashtirilmaganligi bizga to'xtash uchun sabab emas. Dunyodagi eng zo'r jamoa bunday vaqtda o'sish ustida ishlaydi! 🚀\n",
        ]

        try:
            # 1. CRM Diagnostika
            leads = await self.crm.amocrm.get_leads_detailed(limit=50)
            [
                lead
                for lead in leads
                if lead.get("status_id") not in [self.WON_STATUS, self.LOST_STATUS]
            ]

            # 2. AI orqali strategik maslahat olish

            getattr(
                self.crm.amocrm, "api_key", None
            )  # Internal fallback or use prompt
            # Aslida API key Enterprise uchun global bo'lishi kerak.
            # Biz buni advisor_agent orqali ham qilishimiz mumkin, lekin Reporter o'zida bo'lgani yaxshi.


            # Note: We need a client. If not passed, we'll try to get it from context.
            # For robustness in this module, we use a simple set of hardcoded best practices if AI fails.

            missions = [
                "🔥 **Mission: Revival** — Oxirgi 30 kundagi 'Lost' bo'lgan lidlarni qayta ko'rib chiqing va kamida 5 tasiga qayta aloqaga chiqing.",
                "🧹 **Mission: CRM Hygiene** — Barcha aktiv bitimlardagi eslatmalarni yangilang va kutilayotgan summalarni aniqlashtiring.",
                "🧠 **Mission: Brainstorm** — Keyingi hafta uchun 3 ta yangi marketing gipotezasini ishlab chiqing.",
            ]

            # If we wanted purely AI (Ideal State):
            # client = genai.Client(api_key=...)
            # res = await safe_ai_call(...)

            report.append("🎯 **BUGUNGI GROWTH MISSIONS:**")
            for m in missions:
                report.append(f"  ▫️ {m}")

            report.append(
                '\n💡 <i>"Katta natijalar kichik, lekin muntazam harakatlardan boshlanadi."</i>'
            )
            report.append(
                "\n@baxtiyorjong_gaziyev, jamoa bugun o'z ustida ishlashga shay!"
            )

        except Exception as e:
            logger.error(f"[PROACTIVE VISION ERROR] {e}")
            report.append(
                "🚀 Bugun o'z ustimizda ishlash va CRM ni tozalash kuni. Olaysizlar!"
            )

        return "\n".join(report)

    async def generate_weekly_report_uz(
        self,
        period_start: str,
        period_end: str,
        active_deals: int,
        active_value: int,
        completed_deals: int,
        completed_value: int,
        lost_deals: int,
        lost_value: int,
        new_deals: int,
        new_companies: int,
        new_contacts: int,
    ) -> str:
        """Generate weekly CRM report in Uzbek language.

        Args:
            period_start: Start date (DD.MM.YYYY)
            period_end: End date (DD.MM.YYYY)
            active_deals: Number of active deals at end of period
            active_value: Value of active deals in UZS
            completed_deals: Number of successfully completed deals
            completed_value: Value of completed deals
            lost_deals: Number of unrealized deals
            lost_value: Value of lost deals
            new_deals: New deals created
            new_companies: New companies created
            new_contacts: New contacts created

        Returns:
            Formatted report string in Uzbek
        """

        # Format numbers with spaces for thousands
        def format_money(amount: int) -> str:
            if amount == 0:
                return "0"
            return f"{amount:,}".replace(",", " ")

        report = []

        # Header
        report.append("📊 *HAFTALIK HISOBOT*")
        report.append(f"📅 *Davri: {period_start} - {period_end}*\n")

        # Active deals section
        report.append("💼 *AKTIV BITIMLAR (davr oxirida):*")
        report.append(f"• Jami: *{active_deals} ta*")
        report.append(f"• Qiymati: *{format_money(active_value)} soʻm*\n")

        # Completed deals section
        report.append("✅ *YOPILGAN BITIMLAR:*")
        if completed_deals > 0:
            report.append(
                f"• Muvaffaqiyatli: *{completed_deals} ta* ({format_money(completed_value)} soʻm)"
            )
        else:
            report.append("• Muvaffaqiyatli: *0 ta* ⚠️")

        if lost_deals > 0:
            report.append(
                f"• Bekor qilingan: *{lost_deals} ta* ({format_money(lost_value)} soʻm)"
            )
        report.append("")

        # New entries section
        report.append("🆕 *YANGI YARATILGAN:*")
        report.append(f"• Bitimlar: *{new_deals} ta* 📈")
        report.append(f"• Kompaniyalar: *{new_companies} ta* 🏢")
        report.append(f"• Kontaktlar: *{new_contacts} ta* 👥\n")

        # Summary analysis
        report.append("📈 *OISHA TAHLILI:*")

        if new_deals > 100:
            report.append(
                f"_✅ Ajoyib! Haftada {new_deals} ta yangi bitim - aktiv sotuv jarayoni._"
            )
        elif new_deals > 50:
            report.append(
                "_🟡 O'rtacha. Yangi bitimlar oqimi yaxshi, lekin yanada kuchaytirish mumkin._"
            )
        else:
            report.append(
                "_🔴 Diqqat! Yangi leadlar kam. Marketing kanallarini ko'rib chiqish vaqt._"
            )

        if completed_deals == 0 and active_deals > 100:
            report.append(
                f"_⚠️ {active_deals} ta aktiv bitim ichida yopilgan yo'q - menejerlar nazoratini kuchaytiring._"
            )

        report.append("\n📊 *Davom ettirish uchun @baxtiyorjong_gaziyev nazoratida* 👑")

        return "\n".join(report)
