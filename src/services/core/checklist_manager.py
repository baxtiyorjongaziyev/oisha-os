import logging
from typing import List, Dict, Any, Optional
from src.database import Database
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class ChecklistManager:
    """
    Project Checklist & Task Delegation Engine v5.0.
    Generates standard tasks based on service type and assigns to staff.
    """

    TEMPLATES = {
        "Naming": [
            {"title": "Mijoz brifingi", "role": "PM", "days": 1},
            {"title": "Research (Bozor tahlili)", "role": "Namer", "days": 3},
            {"title": "Nomlar ro'yxati (Shortlist)", "role": "Namer", "days": 5},
            {"title": "Final nom tanlovi", "role": "PM", "days": 7},
        ],
        "Logo": [
            {"title": "Moodboard va g'oya", "role": "Designer", "days": 2},
            {"title": "Logotip Draft 1", "role": "Designer", "days": 4},
            {"title": "Prezentatsiya", "role": "Designer", "days": 6},
            {"title": "Final fayllar", "role": "Designer", "days": 8},
        ],
        "Visual Identity": [
            {"title": "Identifikatlar (Rang, Shrift)", "role": "Designer", "days": 5},
            {"title": "Vizual til (Concept)", "role": "Designer", "days": 8},
            {"title": "Pattern va Grafika", "role": "Designer", "days": 10},
        ],
        "Brandbook": [
            {"title": "Logobook (Qoidalar)", "role": "Designer", "days": 4},
            {"title": "Brendbuk (To'liq versiya)", "role": "Designer", "days": 10},
            {"title": "Loyiha topshirish", "role": "PM", "days": 12},
        ],
        "Qadoq": [
            {"title": "Qadoq strukturasi (Dieline)", "role": "Designer", "days": 3},
            {"title": "Grafik dizayn", "role": "Designer", "days": 7},
            {"title": "Final renderlar", "role": "Designer", "days": 10},
        ],
        "Patentlash": [
            {"title": "Oldindan tekshiruv", "role": "PM", "days": 2},
            {"title": "Ariza topshirish", "role": "PM", "days": 5},
            {"title": "Guvohnoma olish", "role": "PM", "days": 180},
        ],
    }

    def __init__(self, db: Database):
        self.db = db

    def get_checklist(self, service_type: str) -> List[Dict[str, Any]]:
        """Xizmat turi bo'yicha standart cheklistni olish."""
        # Case insensitive lookup + default to Branding
        return self.TEMPLATES.get(service_type, self.TEMPLATES["Branding"])

    async def deploy_checklist(
        self, project_name: str, client_id: int, service_type: str
    ) -> str:
        """
        Loyihani cheklistiga ko'ra vazifalarni DB-ga qo'shadi va Telegram xabarini qaytaradi.
        """
        tasks = self.get_checklist(service_type)
        delegation_report = f"📋 **LOYIHA CHEKLISTI: {service_type}**\n\n"

        now = datetime.now()

        for task in tasks:
            # 1. Staff topish
            target_id = await self._find_staff_by_role(task["role"])
            deadline = (now + timedelta(days=task["days"])).strftime("%Y-%m-%d")

            # 2. DB-ga vazifa qo'shish
            task_id = await self.db.add_task(
                assigned_to=target_id,
                description=f"[{project_name}] {task['title']}",
                deadline=deadline,
                title=task["title"],
                priority="High" if task["days"] <= 3 else "Medium",
            )

            # 3. Hisobot tayyorlash
            assignee_tag = (
                f"@{target_id}"
                if target_id
                else f"<i>(Xali belgilanmagan: {task['role']})</i>"
            )
            delegation_report += f"🔹 **{task['title']}**\n   👤 Mas'ul: {assignee_tag}\n   ⏳ Muddat: {deadline}\n\n"

        delegation_report += "✅ _Barcha vazifalar tizimga kiritildi. 👸🛡️_"
        return delegation_report

    async def _find_staff_by_role(self, role: str) -> Optional[int]:
        """Rol bo'yicha birinchi topilgan xodimni qaytaradi."""
        try:
            async with await self.db.get_connection() as conn:
                async with conn.execute(
                    "SELECT user_id FROM users WHERE role = ? OR detailed_role = ? LIMIT 1",
                    (role, role),
                ) as cursor:
                    row = await cursor.fetchone()
                    return row[0] if row else None
        except Exception as e:
            logger.error(f"[CHECKLIST] Staff lookup error: {e}")
            return None
