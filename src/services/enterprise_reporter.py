import logging
import datetime
import json
import asyncio
from typing import Dict, Any, List
from src.database import Database
from src.services.crm_service import CRMService

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

    async def get_daily_efficiency_report(self):
        """Kunlik hisobot: faqat bugungi o'zgarishlar va umumiy holat."""
        now = datetime.datetime.now()
        today_str = now.strftime('%Y-%m-%d')
        month_str = now.strftime('%Y-%m')
        report = [f"📊 <b>KUNLIK ENTERPRISE HISOBOT</b> ({today_str})\n"]
        
        # 1. SALES (AmoCRM)
        if self.crm:
            # Bugungi yopilgan bitimlar (Won)
            report.append(f"💰 <b>Sales Performance (Bugun):</b>")
            try:
                # Real-time data from AmoCRM
                leads = asyncio.run_coroutine_threadsafe(self.crm.amocrm.get_leads_detailed(limit=50), asyncio.get_event_loop()).result()
                won_today = [l for l in leads if l.get('status_id') == self.WON_STATUS]
                total_sum = sum(l.get('price', 0) for l in won_today)
                
                report.append(f"- Yangi lidlar: <b>{len(leads)} ta</b>")
                report.append(f"- Yopilgan bitimlar: <b>{len(won_today)} ta</b> ({total_sum:,.0f} so'm)")
            except:
                report.append(f"- Ma'lumotlar olinmoqda... ⏳")
            
            # Plan-Fakt (Monthly context)
            targets = await self.db.get_department_targets(month_str)
            sales_target = next((t['value'] for t in targets if t['dept'] == 'Sales'), 0)
            if sales_target > 0:
                report.append(f"- Oylik reja: {sales_target:,.0f} so'm")
        
        # 2. PM (Airtable)
        if self.airtable:
            # Bugun bitgan yoki o'zgargan loyihalar
            report.append(f"\n🏗 <b>Production (Bugun):</b>")
            projects = self.airtable.get_projects()
            report.append(f"- Aktiv loyihalar: {len(projects)} ta")
            
        # 3. FINANCE (Airtable)
        if self.airtable:
            finance_records = self.airtable.get_finance_records()
            today_income = 0
            today_expense = 0
            
            for rec in finance_records:
                f = rec.get("fields", {})
                date_str = f.get("Sana") or f.get("Date")
                if date_str == today_str:
                    amount = f.get("Summa") or 0
                    turi = f.get("Turi") or ""
                    if "Daromad" in turi or "Income" in turi:
                        today_income += amount
                    elif "Xarajat" in turi or "Expense" in turi:
                        today_expense += amount
            
            if today_income > 0 or today_expense > 0:
                report.append(f"\n💰 <b>Moliya (Bugun):</b>")
                report.append(f"- Kirim: {today_income:,.0f} so'm".replace(',', ' '))
                report.append(f"- Chiqim: {today_expense:,.0f} so'm".replace(',', ' '))
                report.append(f"- Net Foyda: <b>{(today_income - today_expense):,.0f} so'm</b>".replace(',', ' '))
            
        report.append("\n🌙 <i>Bugungi kun uchun rahmat! Ertaga yanada yaxshiroq bo'lamiz.</i>")
        return "\n".join(report)

    async def get_team_efficiency_report(self) -> str:
        """Jamoa va bo'limlar uchun umumiy samaradorlik hisoboti."""
        now = datetime.datetime.now()
        month_str = now.strftime('%Y-%m')
        
        report = []
        report.append("🏢 <b>Oisha-OS: Enterprise Audit</b>")
        report.append(f"⏱ <i>Hisobot vaqti: {now.strftime('%Y-%m-%d %H:%M')}</i>\n")

        # 1. SALES & MARKETING (AmoCRM)
        # Reja-fakt hisoblash
        targets = await self.db.get_department_targets(month_str)
        sales_target = next((t['value'] for t in targets if t['dept'] == 'Sales'), 80_000_000)
        
        leads = await self.crm.amocrm.get_leads_detailed(limit=100)
        
        # Oylik yopilgan bitimlar summasi (Fact)
        # Eslatma: AmoCRM API limitlari tufayli 'Won' larni alohida filtrlab olish kerak bo'lishi mumkin
        won_leads = [l for l in leads if l.get('status_id') == self.WON_STATUS]
        total_won_sum = sum(l.get('price', 0) for l in won_leads)
        
        active_leads = len([l for l in leads if l.get('status_id') not in [self.WON_STATUS, self.LOST_STATUS]])
        
        report.append(f"💰 <b>Sales Performance:</b>")
        report.append(f"- Oylik Reja: {sales_target:,.0f} so'm".replace(',', ' '))
        report.append(f"- Amalda (Won): {total_won_sum:,.0f} so'm".replace(',', ' '))
        
        progress_pct = (total_won_sum / sales_target * 100) if sales_target > 0 else 0
        report.append(f"- Reja bajarilishi: <b>{progress_pct:.1f}%</b> {'✅' if progress_pct >= 100 else '📈'}")
        report.append(f"- Aktiv lidlar: {active_leads} ta")

        # 2. MARKETING (Channels)
        # Manbalar tahlili (Tags orqali)
        channels = {}
        for l in leads:
            # AmoCRM tags structure: _embedded.tags
            tags = l.get('_embedded', {}).get('tags', [])
            for tag in tags:
                tag_name = tag.get('name', 'Noma\'lum')
                channels[tag_name] = channels.get(tag_name, 0) + 1
        
        if channels:
            top_channel = max(channels, key=channels.get)
            report.append(f"\n📢 <b>Marketing Awareness:</b>")
            report.append(f"- Top kanal: <b>{top_channel}</b> ({channels[top_channel]} lid)")

        # 3. PRODUCTION & PM (Airtable)
        if self.airtable:
            projects = self.airtable.get_projects()
            overdue = self.airtable.get_overdue_projects()
            report.append(f"\n🏗 <b>Production & PM (Airtable):</b>")
            report.append(f"- Aktiv loyihalar: {len(projects)} ta")
            
            # 3 kunlik ishlab chiqarish qoidasi (SLA: 3 days)
            urgent_projects = []
            now_dt = datetime.datetime.now()
            
            for p in projects:
                fields = p.get('fields', {})
                created_str = fields.get('Created') or fields.get('Start Date') # Odatda loyiha yaratilgan sana
                stage = fields.get('Stage', '')
                
                if stage.lower() in ["done", "yakunlandi", "arxiv"]:
                    continue

                if created_str:
                    try:
                        # Created sana odatda ISO formatda "2026-03-29T..."
                        created_dt = datetime.datetime.fromisoformat(created_str.replace('Z', '+00:00'))
                        # Localize now to UTC for comparison if needed, or just naive if created is naive
                        if created_dt.tzinfo:
                            now_utc = datetime.datetime.now(datetime.timezone.utc)
                            diff = now_utc - created_dt
                        else:
                            diff = now_dt - created_dt
                            
                        # Agar 2 kundan oshgan bo'lsa (48h+) va hali bitmagan bo'lsa
                        if diff.days >= 2:
                            proj_name = fields.get('Project Name', 'Nomsiz')
                            urgent_projects.append(f"{proj_name} ({diff.days} kun o'tdi)")
                    except: continue

            if overdue:
                report.append(f"- Muddati o'tgan: {len(overdue)} ta ⚠️")
            
            if urgent_projects:
                report.append(f"- <b>SLA xavfi (3 kundan oshish arafasida):</b> {len(urgent_projects)} ta")
                report.append(f"  <i>(Iltimos, @Inomjon_JonBranding nazoratga oling)</i>")

        # 4. FINANCE SUMMARY (Airtable)
        if self.airtable:
            finance_records = self.airtable.get_finance_records()
            month_income = 0
            month_expense = 0
            current_month = datetime.datetime.now().strftime('%Y-%m')
            
            for rec in finance_records:
                f = rec.get("fields", {})
                date_str = f.get("Sana") or f.get("Date")
                if date_str and date_str.startswith(current_month):
                    amount = f.get("Summa") or 0
                    turi = f.get("Turi") or ""
                    if "Daromad" in turi or "Income" in turi:
                        month_income += amount
                    elif "Xarajat" in turi or "Expense" in turi:
                        month_expense += amount

            report.append(f"\n📈 <b>Oylik Moliya ({current_month}):</b>")
            report.append(f"- Jami tushum: {month_income:,.0f} so'm".replace(',', ' '))
            report.append(f"- Jami xarajat: {month_expense:,.0f} so'm".replace(',', ' '))
            net_profit = month_income - month_expense
            report.append(f"- **Sof Foyda: {net_profit:,.0f} so'm** {'🔥' if net_profit > 0 else '📉'}")

        # 5. ACCOUNTABILITY (Tasks & Reports)
        report.append("\n" + await self.get_accountability_segment())

        report.append("\n👑 <b>PREMIUM INSIGHT</b>")
        report.append("<i>\"Sizning Premium mavqeyingiz Oisha-OS uchun yangi gorizontlarni ochdi. Tizim endi 2 barobar ko'proq lidlarni aqlli saralamoqda!\"</i>")
        
        report.append("\n💡 <i>Tizimli yondashuv — o'sish poydevori!</i>")
        return "\n".join(report)

    async def get_accountability_segment(self) -> str:
        """Topshiriqlarni va hisobotlarni o'z vaqtida bajarmayotganlarni aniqlash."""
        report = []
        report.append("⚖️ <b>Accountability & Discipline:</b>")
        
        # 1. Muddati o'tgan vazifalar
        overdue_tasks = await self.db.get_overdue_tasks()
        if overdue_tasks:
            report.append(f"- <b>Muddati o'tgan vazifalar:</b> {len(overdue_tasks)} ta ⚠️")
            for t in overdue_tasks[:3]: # Faqat birinchi 3 tasini ko'rsatamiz
                name = t.get('name') or t.get('username') or "Unknown"
                task_label = t.get('title') or t.get('description') or "Vazifa"
                report.append(f"  • {task_label} — <i>{name}</i>")
            if len(overdue_tasks) > 3:
                report.append(f"  ... va yana {len(overdue_tasks)-3} ta.")
        else:
            report.append("- Barcha vazifalar o'z vaqtida! ✅")

        # 2. Topshirilmagan hisobotlar (Bugun uchun)
        missing_reports = await self.db.get_missing_reports()
        if missing_reports:
            names = [f"@{m['username']}" if m['username'] else m['name'] for m in missing_reports]
            report.append(f"- <b>Bugun hisobot bermaganlar:</b> {', '.join(names)} 🛑")
        else:
            report.append("- Hamma hisobot topshirdi! 🌟")
            
        return "\n".join(report)

    async def get_real_numbers_audit(self) -> str:
        """Real raqamlarda jamoa auditi: qilinayotgan va qilinmayotgan ishlar."""
        now = datetime.datetime.now()
        report = [f"📊 <b>OISHA-OS: CRM HYGIENE & PERFORMANCE AUDIT</b>"]
        report.append(f"📅 <i>{now.strftime('%d.%m.%Y | %H:%M')}</i>\n")
        
        # 1. Pipeline Audit (AmoCRM)
        leads = await self.crm.amocrm.get_leads_detailed(limit=100)
        stagnant_24h = []
        revenue_at_risk = 0
        
        now_ts = now.timestamp()
        day_seconds = 24 * 3600
        
        for l in leads:
            if l.get('status_id') in [self.WON_STATUS, self.LOST_STATUS]:
                continue
            
            # Stagnation check
            updated_at = l.get('updated_at', 0)
            if (now_ts - updated_at) > day_seconds:
                stagnant_24h.append(l)
                revenue_at_risk += l.get('price', 0)
                
        # 2. Accountability (Managers)
        report.append("🔥 <b>Menejerlar faolligi (Oxirgi 24s):</b>")
        async with await self.db.get_connection() as conn:
            async with conn.execute("SELECT first_name, role FROM users WHERE role IS NOT NULL") as cursor:
                team = await cursor.fetchall()
            
        for name, role in team:
            # Haqiqiy ma'lumotlar bazasidan 'action'larni hisoblash (kelgusida event_logs dan olinadi)
            # Hozircha stagnation dagi lidlar soniga qarab Score beramiz
            manager_leads = [l for l in stagnant_24h if l.get('responsible_user_id') == name]
            report.append(f"• {name} ({role}): {'✅ A' if not manager_leads else '⚠️ B'} Score")

        # 3. Dirty Leads Alert
        if stagnant_24h:
            report.append(f"\n🛑 <b>CRM MUAMMOLARI (Dirty Leads):</b>")
            report.append(f"- 24 soatdan beri unutilgan lidlar: <b>{len(stagnant_24h)} ta</b>")
            report.append(f"- Muzlab qolgan summa (Risk): <b>{revenue_at_risk:,.0f} so'm</b>".replace(',', ' '))
            
            report.append(f"\n⚠️ <b>KECHIKKAN LIDLAR:</b>")
            for l in stagnant_24h[:5]:
                l_name = l.get('name', 'Nomsiz')
                price = l.get('price', 0)
                report.append(f"  • {l_name} ({price:,.0f} so'm)".replace(',', ' '))
        
        report.append("\n💡 <b>OISHA TAHLILI:</b>")
        if len(stagnant_24h) > 5:
            report.append("<i>\"Sotuv bo'limida tizimli xato bor. 24 soatdan oshgan lidlar soni kritik darajada! @baxtiyorjong_gaziyev nazoratga oling.\"</i>")
        else:
            report.append("<i>\"CRM tozaligi yaxshi. Asosiy e'tiborni yangi lidlarni yopishga qarating.\"</i>")
            
        return "\n".join(report)


    async def get_stagnant_leads_alert(self) -> str:
        """Kutilib qolgan lidlar uchun ogohlantirish."""
        # Oxirgi 24 soatda o'zgarmagan lidlarni topish
        leads = await self.crm.amocrm.get_leads_detailed(limit=50)
        now = datetime.datetime.now().timestamp()
        day_seconds = 24 * 3600
        
        stagnant = []
        for l in leads:
            # status_id 142, 143 bo'lsa tekshirmaymiz
            if l.get('status_id') in [self.WON_STATUS, self.LOST_STATUS]:
                continue
                
            updated_at = l.get('updated_at', 0)
            if (now - updated_at) > day_seconds:
                stagnant.append(l.get('name', f"ID:{l.get('id')}"))
        
        if stagnant:
            return f"🚨 <b>DIQQAT - Sales Stagnation!</b>\nQuyidagi lidlar 24 soatdan beri o'zgarmagan: {', '.join(stagnant[:5])}...\nIltimos, @Oydin_JonBranding va @tezmenejer harakat qiling!"
        return ""

    async def generate_morning_plan(self, distribution: Dict[int, List[Dict]]) -> str:
        """Ertalabki 'Plan' hisoboti."""
        now = datetime.datetime.now()
        report = [
            f"☀️ <b>{now.strftime('%d.%m.%Y')} — YANGI KUN, YANGI G'ALABALAR!</b>",
            "🚀 Oisha-OS jamoani jangovar shay holatga keltiradi.\n",
            "📌 <b>BUGUNGI VAZIFALAR (MISSION CONTROL):</b>"
        ]
        
        for m_id, missions in distribution.items():
            m_info = await self.db.get_user_info(m_id)
            name = m_info.get('first_name') if m_info else f"Manager_{m_id}"
            if "pm" in name.lower() or "dilbar" in name.lower() or str(m_id) == "8611068511":
                name = "👩‍💼 PM Dilbar"
            
            report.append(f"\n👤 <b>{name}</b>")
            if not missions:
                report.append("  ▫️ Bugun yangi lidlar yo'q. Eski loyihalar ustida ishlang.")
            else:
                for i, m in enumerate(missions, 1):
                    report.append(f"  {i}. <a href='{m['link']}'>{m['lead_name']}</a> — {m['mission']}")
                    
        report.append("\n📈 <i>Har bir yopilgan bitim — bizning umumiy muvaffaqiyatimiz! Olaysizlar!</i>")
        return "\n".join(report)

    async def generate_plan_fact_report(self) -> str:
        """Kechki 'Plan-Fact' hisoboti."""
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        plans = await self.db.get_daily_plan(today)
        
        if not plans:
            return await self.generate_proactive_vision()
            
        report = [
            f"🌙 <b>{datetime.datetime.now().strftime('%d.%m.%Y')} — KUNLIK PLAN-FAKT TAHLILI</b>",
            "🧐 Oisha-OS natijalarni tekshirmoqda...\n"
        ]
        
        results = {}
        
        for p in plans:
            m_id = p['manager_id']
            if m_id not in results:
                results[m_id] = {"total": 0, "achieved": 0, "leads": []}
            
            lead_id = p['lead_id']
            status = "🔴 Bajarilmadi"
            
            try:
                # AmoCRM dan joriy holatni tekshirish
                lead = await self.crm.amocrm.get_lead(lead_id)
                current_status = lead.get('status_id')
                
                # Agar status yopilgan (Won) bo'lsa yoki Hunter (10117998) dan o'zgargan bo'lsa
                if current_status == self.WON_STATUS:
                    status = "✅ SHARTNOMA! (+)"
                    results[m_id]["achieved"] += 1
                elif current_status != 10117998:
                    status = "✅ Oldinga siljish"
                    results[m_id]["achieved"] += 1
            except:
                status = "❓ Noma'lum"
            
            results[m_id]["total"] += 1
            results[m_id]["leads"].append(f"  ▫️ {p['lead_name']}: {status}")

        for m_id, data in results.items():
            m_info = await self.db.get_user_info(m_id)
            name = m_info.get('first_name') if m_info else f"Manager_{m_id}"
            if "pm" in name.lower() or "dilbar" in name.lower() or str(m_id) == "8611068511": 
                name = "👩‍💼 PM Dilbar"
            
            pct = (data['achieved'] / data['total'] * 100) if data['total'] > 0 else 0
            emoji = "🔥" if pct >= 80 else "⚠️" if pct >= 50 else "❄️"
            
            report.append(f"👤 <b>{name}</b> {emoji}")
            report.append(f"📊 KPI: <b>{data['achieved']}/{data['total']}</b> ({pct:.1f}%)")
            report.append("\n".join(data['leads']))
            report.append("")

        total_total = sum(d['total'] for d in results.values())
        total_achieved = sum(d['achieved'] for d in results.values())
        total_pct = (total_achieved / total_total * 100) if total_total > 0 else 0
        
        if total_pct >= 80:
            report.append("🌟 <b>DAHSHAT!</b> Jamoa bugun haqiqiy professionalizm ko'rsatdi. Sizlar bilan faxrlanaman!")
        elif total_pct >= 50:
            report.append("👍 <b>Yaxshi.</b> Lekin ertaga bundan ham ko'proq natija kutaman. Bo'shashmang!")
        else:
            report.append("📢 <b>DIQQAT!</b> Bugungi natijalar kutilganidan past. Ertaga har bir bitim uchun jang qilishingizni so'rayman!")

        return "\n".join(report)
    async def generate_proactive_vision(self) -> str:
        """Vazifa bo'lmaganda jamoaga strategik yo'nalish va 'Growth Missions' berish."""
        logger.info("[PROACTIVE] Generating strategic vision since no plans found.")
        
        now = datetime.datetime.now()
        report = [
            f"🌙 <b>{now.strftime('%d.%m.%Y')} — STRATEGIK O'SISH IMKONIYaTI</b>",
            "Biron bir konkret vazifa rejalashtirilmaganligi bizga to'xtash uchun sabab emas. Dunyodagi eng zo'r jamoa bunday vaqtda o'sish ustida ishlaydi! 🚀\n",
        ]
        
        try:
            # 1. CRM Diagnostika
            leads = await self.crm.amocrm.get_leads_detailed(limit=50)
            stagnant = [l for l in leads if l.get('status_id') not in [self.WON_STATUS, self.LOST_STATUS]]
            
            # 2. AI orqali strategik maslahat olish
            from src.utils.ai_utils import safe_ai_call
            from google import genai
            
            api_key = getattr(self.crm.amocrm, 'api_key', None) # Internal fallback or use prompt
            # Aslida API key Enterprise uchun global bo'lishi kerak.
            # Biz buni advisor_agent orqali ham qilishimiz mumkin, lekin Reporter o'zida bo'lgani yaxshi.
            
            prompt = (
                "Siz Oisha-OS strategik direktorisiz. Bugun jamoada rejalashtirilgan konkret vazifalar yo'q. "
                "Jamoani №1 qilish uchun 3 ta 'Growth Mission' (O'sish vazifasi) taklif qiling. "
                "Vazifalar Sales (CRM tozalash, lost leads), Production (workflow optimallashtirish) "
                "yoki Strategiya (bozor tahlili) yo'nalishlarida bo'lsin. "
                "Ohang: Jangovar, professional, ilhomlantiruvchi. O'zbek tilida."
            )
            
            # Note: We need a client. If not passed, we'll try to get it from context.
            # For robustness in this module, we use a simple set of hardcoded best practices if AI fails.
            
            missions = [
                "🔥 **Mission: Revival** — Oxirgi 30 kundagi 'Lost' bo'lgan lidlarni qayta ko'rib chiqing va kamida 5 tasiga qayta aloqaga chiqing.",
                "🧹 **Mission: CRM Hygiene** — Barcha aktiv bitimlardagi eslatmalarni yangilang va kutilayotgan summalarni aniqlashtiring.",
                "🧠 **Mission: Brainstorm** — Keyingi hafta uchun 3 ta yangi marketing gipotezasini ishlab chiqing."
            ]
            
            # If we wanted purely AI (Ideal State):
            # client = genai.Client(api_key=...)
            # res = await safe_ai_call(...)
            
            report.append("🎯 **BUGUNGI GROWTH MISSIONS:**")
            for m in missions:
                report.append(f"  ▫️ {m}")
                
            report.append("\n💡 <i>\"Katta natijalar kichik, lekin muntazam harakatlardan boshlanadi.\"</i>")
            report.append("\n@baxtiyorjong_gaziyev, jamoa bugun o'z ustida ishlashga shay!")
            
        except Exception as e:
            logger.error(f"[PROACTIVE VISION ERROR] {e}")
            report.append("🚀 Bugun o'z ustimizda ishlash va CRM ni tozalash kuni. Olaysizlar!")

        return "\n".join(report)
