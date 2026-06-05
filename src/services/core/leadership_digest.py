"""
Leadership Digest — Blok 53, 75
B.G., F.G. va X.G. uchun alohida haftalik digest.

Har dushanba kuni avtomatik yuboriladi.
Har bir rahbar faqat o'z mas'uliyat sohasidagi ma'lumotni oladi.
"""
import asyncio
import logging
from datetime import date, datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


class LeadershipDigest:
    """
    Founder (B.G.), CEO (F.G.) va COO (X.G.) uchun
    rol asosida ajratilgan haftalik boshqaruv xulosa.
    """

    def __init__(self, crm, airtable, db, settings):
        self.crm = crm
        self.airtable = airtable
        self.db = db
        self.settings = settings

    # ------------------------------------------------------------------ B.G.
    async def get_founder_digest(self) -> str:
        """
        Founder (B.G.) fokusi:
        • Sifat va premium loyihalar
        • Portfolio/case imkoniyatlari
        • Personal brand uchun kontent
        """
        lines = [
            "👑 *B.G. — HAFTALIK DIGEST*",
            f"_{self._week_range()}_\n",
            "📌 *Fokus: Sifat · Premium mijozlar · Case · Brand*\n",
        ]

        # Premium projects (≥5M UZS budget)
        try:
            projects = await asyncio.to_thread(self.airtable.get_projects)
            premium = sorted(
                [p for p in projects
                 if self._budget(p) >= 5_000_000
                 and p.get("stage") not in self.airtable.DONE_STAGES],
                key=self._budget,
                reverse=True,
            )[:5]

            if premium:
                lines.append("💎 *Faol premium loyihalar (5M+ UZS):*")
                for p in premium:
                    name = p.get("project_name") or p.get("name") or "?"
                    stage = p.get("stage") or "?"
                    budget = self._budget(p)
                    lines.append(f"  • {name} | {stage} | {budget:,.0f} UZS")
                lines.append("")

            # Recently completed — case candidates
            completed = [
                p for p in projects
                if p.get("stage") in {"Yakunlangan", "Topshirildi"}
                and self._budget(p) >= 3_000_000
            ][:3]
            if completed:
                lines.append("📸 *Case uchun kandidatlar (yakunlangan, 3M+ UZS):*")
                for p in completed:
                    name = p.get("project_name") or p.get("name") or "?"
                    lines.append(f"  • {name} | {self._budget(p):,.0f} UZS")
                lines.append("")

        except Exception as exc:
            logger.warning("Founder digest Airtable: %s", exc)

        lines += [
            "📋 *Haftalik savol:*",
            "• Bu hafta qaysi ish portfolio sifatiga chiqadi?",
            "• B.G. personal brand uchun kontent mavzusi tayyor?",
            "• Sifat standarti to'g'ri ushlanmoqdami?",
        ]
        return "\n".join(lines)

    # ------------------------------------------------------------------ F.G.
    async def get_ceo_digest(self) -> str:
        """
        CEO (F.G.) fokusi:
        • Savdo va CRM holati
        • Pul oqimi
        • Jamoa KPI
        """
        lines = [
            "🎯 *F.G. — HAFTALIK DIGEST*",
            f"_{self._week_range()}_\n",
            "📌 *Fokus: Savdo · CRM · Pul · KPI · Jamoa*\n",
        ]

        # CRM stagnation
        try:
            stagnated = await self.crm.check_stagnated_leads(hours=48)
            count = len(stagnated) if stagnated else 0
            icon = "🔴" if count > 5 else ("🟡" if count > 0 else "🟢")
            lines.append(f"{icon} *48h harakatsiz leadlar:* {count} ta")
            if stagnated:
                for lead in stagnated[:3]:
                    lines.append(f"  • {lead.get('name', '?')}")
                if count > 3:
                    lines.append(f"  ... va yana {count - 3} ta")
            lines.append("")
        except Exception as exc:
            logger.warning("CEO digest CRM: %s", exc)

        # Sales report
        try:
            report = await asyncio.to_thread(self.crm.get_sales_report)
            if report:
                lines.append(f"💰 *Oylik savdo:* {report}\n")
        except Exception:
            pass

        # Finance summary
        try:
            fin = await asyncio.to_thread(self.airtable.get_finance_records)
            income = sum(self._fin(r) for r in fin if r.get("table") == "Kirim")
            expense = sum(self._fin(r) for r in fin if r.get("table") == "Chiqim")
            net = income - expense
            margin = (net / income * 100) if income > 0 else 0.0
            m_icon = "🔴" if margin < 30 else "🟢"
            lines.append(
                f"📊 *Moliya:* {income:,.0f} kirim | {expense:,.0f} xarajat | "
                f"{m_icon} {margin:.1f}% marja\n"
            )
        except Exception:
            pass

        lines += [
            "📋 *Haftalik savol:*",
            "• Egasiz lead qolganmi? CRM toza?",
            "• KP yuborildi, follow-up yo'q — qancha bor?",
            "• Bu oyda KPI maqsadga qancha yaqin?",
            "• Kechikkan to'lovlar nazoratda?",
        ]
        return "\n".join(lines)

    # ------------------------------------------------------------------ X.G.
    async def get_coo_digest(self) -> str:
        """
        COO (X.G.) fokusi:
        • Loyihalar va Shturmanlar
        • Deadline va xavflar
        • Airtable holati
        """
        lines = [
            "⚙️ *X.G. — HAFTALIK DIGEST*",
            f"_{self._week_range()}_\n",
            "📌 *Fokus: Loyihalar · Deadline · Shturmanlar · Xavflar*\n",
        ]

        try:
            projects = await asyncio.to_thread(self.airtable.get_projects)
            active = [p for p in projects if p.get("stage") not in self.airtable.DONE_STAGES]
            today = date.today()
            red, yellow, no_dl = [], [], []

            for p in active:
                name = p.get("project_name") or p.get("name") or "?"
                dl_str = p.get("deadline") or ""
                if not dl_str:
                    no_dl.append(name)
                    continue
                try:
                    dl = datetime.fromisoformat(dl_str[:10]).date()
                    days_left = (dl - today).days
                    if days_left <= 0:
                        red.append(f"{name} ({abs(days_left)}k kech)")
                    elif days_left <= 3:
                        yellow.append(f"{name} ({days_left}k qoldi)")
                except (ValueError, TypeError):
                    pass

            lines.append(f"📁 *Faol loyihalar:* {len(active)} ta\n")

            if red:
                lines.append(f"🔴 *Qizil — {len(red)} ta:*")
                for r in red[:6]:
                    lines.append(f"  • {r}")
                lines.append("")
            if yellow:
                lines.append(f"🟡 *Sariq — {len(yellow)} ta:*")
                for y in yellow[:6]:
                    lines.append(f"  • {y}")
                lines.append("")
            if no_dl:
                lines.append(f"⚫ Deadline yo'q: {len(no_dl)} ta loyiha\n")

        except Exception as exc:
            logger.warning("COO digest Airtable: %s", exc)

        lines += [
            "📋 *Haftalik savol:*",
            "• Har bir Shturman necha loyihani boshqarayapti (optimal: 5-9)?",
            "• Scope oshgan loyiha bormi? Qo'shimcha narx kelishildimi?",
            "• Final fayl to'lovsiz berilgan holat bormi?",
            "• Airtable yangilanmagan karta bormi?",
        ]
        return "\n".join(lines)

    # ------------------------------------------------------------------ helpers

    def _week_range(self) -> str:
        today = datetime.now()
        monday = today - timedelta(days=today.weekday())
        sunday = monday + timedelta(days=6)
        return f"{monday.strftime('%d.%m')} — {sunday.strftime('%d.%m.%Y')}"

    def _budget(self, project: dict) -> float:
        for key in ("budget", "Kelishgan narx", "Jami loyiha narxi (UZS)"):
            val = project.get(key)
            if val is not None:
                return self._to_float(val)
        return 0.0

    def _fin(self, record: dict) -> float:
        for key in ("amount", "summa", "narx", "price"):
            val = record.get(key)
            if val is not None:
                return self._to_float(val)
        return 0.0

    @staticmethod
    def _to_float(val) -> float:
        if isinstance(val, (int, float)):
            return float(val)
        try:
            return float(str(val).replace(",", "").replace(" ", "").replace("UZS", "").strip())
        except (ValueError, TypeError):
            return 0.0
