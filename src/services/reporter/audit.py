"""
Real numbers CRM pipeline audit and junk/stagnant lead identification mixin.
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from src.time_utils import get_local_now

logger = logging.getLogger(__name__)


class AuditMixin:
    """Handles deep CRM audit, junk lead detection, and stagnation alerts."""

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
            resp = requests.get(url, headers=self.crm.amocrm._get_headers(), timeout=30)
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
                timeout=30,
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
        except Exception:
            logger.debug(
                "Failed to identify junk leads for audit report",
                exc_info=True,
            )

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
                name = lead.get("name", "Nomsiz")
                l_id = lead.get("id")
                # Extract phone from custom fields if possible (simplified here)
                phone = "Raqam yo'q"
                for cf in lead.get("custom_fields_values") or []:
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
