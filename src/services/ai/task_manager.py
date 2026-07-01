"""AI-powered automatic task creation in AmoCRM."""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

from .quality_analyzer import ConversationAnalysis

logger = logging.getLogger(__name__)


class AITaskManager:
    """AI tahlil asosida avtomatik vazifa qo'yish."""

    # Vazifa turlari
    TASK_TYPES = {
        "follow_up": 1,  # Qo'ng'iroq
        "meeting": 2,  # Uchrashuv
        "email": 3,  # Email
        "demo": 4,  # Demo
        "proposal": 5,  # Taklif
    }

    # Prioritetlar
    PRIORITY_HIGH = 3
    PRIORITY_MEDIUM = 2
    PRIORITY_LOW = 1

    def __init__(self, amocrm_client=None):
        self.amocrm = amocrm_client

    async def create_tasks_from_analysis(
        self, analysis: ConversationAnalysis, auto_create: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Suhbat tahlilidan kelib chiqib vazifalar yaratish.

        Args:
            analysis: Suhbat tahlili
            auto_create: Avtomatik yaratish (True) yoki faqat tavsiya (False)

        Returns:
            Yaratilgan/tavsiya qilingan vazifalar ro'yxati
        """
        tasks = []

        # 1. Sifat past bo'lsa - o'qish vazifasi
        quality_tasks = self._create_quality_tasks(analysis)
        tasks.extend(quality_tasks)

        # 2. E'tirozlar bo'yicha vazifalar
        objection_tasks = self._create_objection_tasks(analysis)
        tasks.extend(objection_tasks)

        # 3. Keyingi qadamlar
        followup_tasks = self._create_followup_tasks(analysis)
        tasks.extend(followup_tasks)

        # 4. Mijoz kayfiyati bo'yicha
        mood_tasks = self._create_mood_based_tasks(analysis)
        tasks.extend(mood_tasks)

        # Agar auto_create=True bo'lsa, AmoCRM da yaratish
        if auto_create and self.amocrm:
            created_tasks = []
            for task in tasks:
                created = await self._create_in_amocrm(task, analysis.lead_id)
                if created:
                    task["created_in_crm"] = True
                    created_tasks.append(task)
                    logger.info(
                        f"[AI TASK] AmoCRM da vazifa yaratildi: {task['title']}"
                    )
                else:
                    task["created_in_crm"] = False
                    logger.warning(
                        f"[AI TASK] AmoCRM da vazifa yaratilmadi: {task['title']}"
                    )
            return created_tasks

        return tasks

    def _create_quality_tasks(
        self, analysis: ConversationAnalysis
    ) -> List[Dict[str, Any]]:
        """Sifat bo'yicha vazifalar."""
        tasks = []

        if analysis.overall_score < 60:
            # Sotuv mahoratini oshirish
            tasks.append(
                {
                    "title": "🎓 Sotuv mahoratini oshirish",
                    "text": (
                        f"Suhbat sifati past ({analysis.overall_score}%). "
                        f"Kamchiliklar: {', '.join(analysis.weaknesses[:3])}. "
                        f"Sotuv bo'yicha qo'shimcha training o'tkazish kerak."
                    ),
                    "due_in_hours": 24,
                    "priority": self.PRIORITY_HIGH,
                    "task_type_id": self.TASK_TYPES["meeting"],
                    "source": "ai_quality_analysis",
                    "assigned_to": analysis.manager_id,
                }
            )

        # Zaif metric bo'yicha alohida vazifalar
        for score in analysis.scores:
            if score.score < 50:
                tasks.append(
                    {
                        "title": f"📚 {score.metric.value} mahoratini oshirish",
                        "text": (
                            f"{score.metric.value} bo'yicha ball past ({score.score}). "
                            f"Taklif: {', '.join(score.improvement_tips[:2])}"
                        ),
                        "due_in_hours": 48,
                        "priority": self.PRIORITY_MEDIUM,
                        "task_type_id": self.TASK_TYPES["follow_up"],
                        "source": "ai_skill_gap",
                        "assigned_to": analysis.manager_id,
                        "metric": score.metric.value,
                    }
                )

        return tasks

    def _create_objection_tasks(
        self, analysis: ConversationAnalysis
    ) -> List[Dict[str, Any]]:
        """E'tirozlar bo'yicha vazifalar."""
        tasks = []

        for i, objection in enumerate(analysis.objections_raised[:3], 1):
            # E'tirozga javob tayyorlash
            tasks.append(
                {
                    "title": f"🎯 E'tiroz #{i}: {objection[:40]}...",
                    "text": (
                        f"Mijoz e'tirozi: '{objection}'\n\n"
                        f"Javob tayyorlash va qayta bog'lanish kerak. "
                        f"E'tirozlar bilan ishlash bo'yicha script ni ko'rib chiqing."
                    ),
                    "due_in_hours": 4,  # Tezroq
                    "priority": self.PRIORITY_HIGH,
                    "task_type_id": self.TASK_TYPES["follow_up"],
                    "source": "ai_objection",
                    "assigned_to": analysis.manager_id,
                }
            )

        return tasks

    def _create_followup_tasks(
        self, analysis: ConversationAnalysis
    ) -> List[Dict[str, Any]]:
        """Keyingi qadamlar bo'yicha vazifalar."""
        tasks = []

        if not analysis.next_steps:
            # Agar keyingi qadam aniqlanmagan bo'lsa
            tasks.append(
                {
                    "title": "⚠️ Keyingi qadamni aniqlash",
                    "text": (
                        "Suhbatda keyingi qadam aniqlanmagan. "
                        "Mijoz bilan qayta bog'lanib, aniq vaqt belgilang."
                    ),
                    "due_in_hours": 2,
                    "priority": self.PRIORITY_HIGH,
                    "task_type_id": self.TASK_TYPES["follow_up"],
                    "source": "ai_missing_followup",
                    "assigned_to": analysis.manager_id,
                }
            )
        else:
            # Har bir keyingi qadam uchun vazifa
            for i, step in enumerate(analysis.next_steps[:3], 1):
                # Step turini aniqlash
                task_type = self._detect_task_type(step)
                due_hours = self._estimate_due_hours(step)

                tasks.append(
                    {
                        "title": f"📋 Qadam #{i}: {step[:50]}...",
                        "text": step,
                        "due_in_hours": due_hours,
                        "priority": (
                            self.PRIORITY_HIGH if i == 1 else self.PRIORITY_MEDIUM
                        ),
                        "task_type_id": task_type,
                        "source": "ai_next_step",
                        "assigned_to": analysis.manager_id,
                    }
                )

        # Natijaga qarab qo'shimcha vazifalar
        if analysis.outcome == "sale":
            tasks.append(
                {
                    "title": "🎉 Sotuvni tasdiqlash",
                    "text": (
                        f"Tabriklaymiz! Sotuv amalga oshdi (ball: {analysis.overall_score}). "
                        f"Shartnama va to'lovni tasdiqlang."
                    ),
                    "due_in_hours": 4,
                    "priority": self.PRIORITY_HIGH,
                    "task_type_id": self.TASK_TYPES["meeting"],
                    "source": "ai_sale_won",
                    "assigned_to": analysis.manager_id,
                }
            )

        return tasks

    def _create_mood_based_tasks(
        self, analysis: ConversationAnalysis
    ) -> List[Dict[str, Any]]:
        """Mijoz kayfiyatiga qarab vazifalar."""
        tasks = []

        if analysis.client_mood == "negative":
            # Mijoz narazi
            tasks.append(
                {
                    "title": "🚨 Mijoz naraziligini bartaraf etish",
                    "text": (
                        "Mijoz kayfiyati salbiy. Shikoyatlarni ko'rib chiqib, "
                        "qoniqtiruvchi yechim taklif qiling."
                    ),
                    "due_in_hours": 2,
                    "priority": self.PRIORITY_HIGH,
                    "task_type_id": self.TASK_TYPES["follow_up"],
                    "source": "ai_negative_mood",
                    "assigned_to": analysis.manager_id,
                }
            )

        elif (
            analysis.client_mood == "positive" and analysis.client_interest_level >= 80
        ):
            # Mijoz qiziqishini qo'llab-quvvatlash
            tasks.append(
                {
                    "title": "⚡ Yuqori qiziqish - tez harakat",
                    "text": (
                        f"Mijoz qiziqish darajasi yuqori ({analysis.client_interest_level}%). "
                        f"Imkoniyatni boy bermang, darhol keyingi qadamga o'ting."
                    ),
                    "due_in_hours": 1,
                    "priority": self.PRIORITY_HIGH,
                    "task_type_id": self.TASK_TYPES["follow_up"],
                    "source": "ai_hot_lead",
                    "assigned_to": analysis.manager_id,
                }
            )

        return tasks

    def _detect_task_type(self, text: str) -> int:
        """Matndan vazifa turini aniqlash."""
        text_lower = text.lower()

        if any(
            word in text_lower
            for word in ["demo", "presentation", "ko'rsat", "prezent"]
        ):
            return self.TASK_TYPES["demo"]
        elif any(
            word in text_lower for word in ["taklif", "proposal", "shartnoma", "offer"]
        ):
            return self.TASK_TYPES["proposal"]
        elif any(word in text_lower for word in ["email", "xat", "yubor", "jo'nat"]):
            return self.TASK_TYPES["email"]
        elif any(word in text_lower for word in ["uchrash", "meeting", "konsult"]):
            return self.TASK_TYPES["meeting"]
        else:
            return self.TASK_TYPES["follow_up"]

    def _estimate_due_hours(self, text: str) -> int:
        """Matndan muddatni aniqlash."""
        text_lower = text.lower()

        # Tezkor harakat
        if any(word in text_lower for word in ["hozir", "darhol", "tez", "bugun"]):
            return 2

        # Ertaga
        elif any(word in text_lower for word in ["ertaga", "tomorrow", "next day"]):
            return 24

        # Hafta ichida
        elif any(word in text_lower for word in ["hafta", "week", "yakshanba"]):
            return 72

        # Default - 24 soat
        return 24

    async def _create_in_amocrm(
        self, task: Dict[str, Any], lead_id: Optional[int]
    ) -> bool:
        """AmoCRM da vazifa yaratish."""
        if not self.amocrm or not lead_id:
            return False

        try:
            # Complete till timestamp
            due_hours = task.get("due_in_hours", 24)
            complete_till = int(
                (datetime.now() + timedelta(hours=due_hours)).timestamp()
            )

            # Vazifa text
            text = task.get("text", task.get("title", "Vazifa"))

            # AmoCRM da yaratish
            result = await self.amocrm.create_task(
                element_id=lead_id,
                text=text[:500],  # Max 500 chars
                complete_till=complete_till,
            )

            return result

        except Exception as e:
            logger.error(f"[AI TASK] AmoCRM vazifa yaratish xatosi: {e}")
            return False

    async def create_batch_tasks(
        self, analyses: List[ConversationAnalysis], auto_create: bool = False
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Bir nechta suhbatlar uchun vazifalar yaratish.

        Returns:
            Dict with tasks grouped by lead_id
        """
        all_tasks = {}

        for analysis in analyses:
            lead_id = analysis.lead_id
            if not lead_id:
                continue

            tasks = await self.create_tasks_from_analysis(analysis, auto_create)

            if lead_id not in all_tasks:
                all_tasks[lead_id] = []

            all_tasks[lead_id].extend(tasks)

        return all_tasks

    def get_task_summary(self, analyses: List[ConversationAnalysis]) -> Dict[str, Any]:
        """Vazifa tavsiyalari xulosasi."""
        summary = {
            "total_analyses": len(analyses),
            "total_recommended_tasks": 0,
            "by_category": {
                "quality_improvement": 0,
                "objection_handling": 0,
                "follow_up": 0,
                "mood_based": 0,
            },
            "high_priority": 0,
            "medium_priority": 0,
            "low_priority": 0,
        }

        for analysis in analyses:
            # Sifat vazifalari
            quality_tasks = self._create_quality_tasks(analysis)
            summary["by_category"]["quality_improvement"] += len(quality_tasks)

            # E'tiroz vazifalari
            objection_tasks = self._create_objection_tasks(analysis)
            summary["by_category"]["objection_handling"] += len(objection_tasks)

            # Follow-up vazifalari
            followup_tasks = self._create_followup_tasks(analysis)
            summary["by_category"]["follow_up"] += len(followup_tasks)

            # Mood vazifalari
            mood_tasks = self._create_mood_based_tasks(analysis)
            summary["by_category"]["mood_based"] += len(mood_tasks)

            # Prioritetlar
            all_tasks = quality_tasks + objection_tasks + followup_tasks + mood_tasks
            for task in all_tasks:
                priority = task.get("priority", 2)
                if priority == 3:
                    summary["high_priority"] += 1
                elif priority == 2:
                    summary["medium_priority"] += 1
                else:
                    summary["low_priority"] += 1

            summary["total_recommended_tasks"] += len(all_tasks)

        return summary

    def generate_task_report(
        self,
        analyses: List[ConversationAnalysis],
        created_tasks: Dict[str, List[Dict[str, Any]]],
    ) -> str:
        """Vazifa hisobotini yaratish."""
        lines = ["🤖 AI VAZIFA HISOBOTI", "=" * 50, ""]

        summary = self.get_task_summary(analyses)

        lines.extend(
            [
                "📊 Umumiy statistika:",
                f"   Tahlil qilingan suhbatlar: {summary['total_analyses']}",
                f"   Tavsiya qilingan vazifalar: {summary['total_recommended_tasks']}",
                f"   Yaratilgan vazifalar: {sum(len(t) for t in created_tasks.values())}",
                "",
                "📝 Vazifa turlari:",
                f"   Sifat oshirish: {summary['by_category']['quality_improvement']}",
                f"   E'tirozlarni yengish: {summary['by_category']['objection_handling']}",
                f"   Keyingi qadamlar: {summary['by_category']['follow_up']}",
                f"   Mijoz kayfiyati: {summary['by_category']['mood_based']}",
                "",
                "🎯 Prioritetlar:",
                f"   Yuqori: {summary['high_priority']}",
                f"   O'rtacha: {summary['medium_priority']}",
                f"   Past: {summary['low_priority']}",
                "",
            ]
        )

        # Lead bo'yicha
        if created_tasks:
            lines.append("📋 Lead bo'yicha vazifalar:")
            for lead_id, tasks in created_tasks.items():
                lines.append(f"   Lead #{lead_id}: {len(tasks)} ta vazifa")
                for task in tasks[:3]:  # Faqat 3 tasini ko'rsatish
                    status = "✅" if task.get("created_in_crm") else "📝"
                    lines.append(f"     {status} {task['title'][:50]}...")
            lines.append("")

        lines.append(f"Yaratilgan vaqt: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

        return "\n".join(lines)
