"""
Task creation builders and heuristic detectors for AI task manager.
"""
from __future__ import annotations

from typing import Any, Dict, List

from src.services.ai.quality_analyzer import ConversationAnalysis

TASK_TYPES = {
    "follow_up": 1,
    "meeting": 2,
    "email": 3,
    "demo": 4,
    "proposal": 5,
}

PRIORITY_HIGH = 3
PRIORITY_MEDIUM = 2
PRIORITY_LOW = 1


def detect_task_type(text: str) -> int:
    text_lower = text.lower()
    if any(word in text_lower for word in ["demo", "presentation", "ko'rsat", "prezent"]):
        return TASK_TYPES["demo"]
    elif any(word in text_lower for word in ["taklif", "proposal", "shartnoma", "offer"]):
        return TASK_TYPES["proposal"]
    elif any(word in text_lower for word in ["email", "xat", "yubor", "jo'nat"]):
        return TASK_TYPES["email"]
    elif any(word in text_lower for word in ["uchrash", "meeting", "konsult"]):
        return TASK_TYPES["meeting"]
    else:
        return TASK_TYPES["follow_up"]


def estimate_due_hours(text: str) -> int:
    text_lower = text.lower()
    if any(word in text_lower for word in ["hozir", "darhol", "tez", "bugun"]):
        return 2
    elif any(word in text_lower for word in ["ertaga", "tomorrow", "next day"]):
        return 24
    elif any(word in text_lower for word in ["hafta", "week", "yakshanba"]):
        return 72
    return 24


def create_quality_tasks(analysis: ConversationAnalysis) -> List[Dict[str, Any]]:
    tasks = []
    if analysis.overall_score < 60:
        tasks.append(
            {
                "title": "🎓 Sotuv mahoratini oshirish",
                "text": (
                    f"Suhbat sifati past ({analysis.overall_score}%). "
                    f"Kamchiliklar: {', '.join(analysis.weaknesses[:3])}. "
                    f"Sotuv bo'yicha qo'shimcha training o'tkazish kerak."
                ),
                "due_in_hours": 24,
                "priority": PRIORITY_HIGH,
                "task_type_id": TASK_TYPES["meeting"],
                "source": "ai_quality_analysis",
                "assigned_to": analysis.manager_id,
            }
        )

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
                    "priority": PRIORITY_MEDIUM,
                    "task_type_id": TASK_TYPES["follow_up"],
                    "source": "ai_skill_gap",
                    "assigned_to": analysis.manager_id,
                    "metric": score.metric.value,
                }
            )
    return tasks


def create_objection_tasks(analysis: ConversationAnalysis) -> List[Dict[str, Any]]:
    tasks = []
    for i, objection in enumerate(analysis.objections_raised[:3], 1):
        tasks.append(
            {
                "title": f"🎯 E'tiroz #{i}: {objection[:40]}...",
                "text": (
                    f"Mijoz e'tirozi: '{objection}'\n\n"
                    f"Javob tayyorlash va qayta bog'lanish kerak. "
                    f"E'tirozlar bilan ishlash bo'yicha script ni ko'rib chiqing."
                ),
                "due_in_hours": 4,
                "priority": PRIORITY_HIGH,
                "task_type_id": TASK_TYPES["follow_up"],
                "source": "ai_objection",
                "assigned_to": analysis.manager_id,
            }
        )
    return tasks


def create_followup_tasks(analysis: ConversationAnalysis) -> List[Dict[str, Any]]:
    tasks = []
    if not analysis.next_steps:
        tasks.append(
            {
                "title": "⚠️ Keyingi qadamni aniqlash",
                "text": (
                    "Suhbatda keyingi qadam aniqlanmagan. "
                    "Mijoz bilan qayta bog'lanib, aniq vaqt belgilang."
                ),
                "due_in_hours": 2,
                "priority": PRIORITY_HIGH,
                "task_type_id": TASK_TYPES["follow_up"],
                "source": "ai_missing_followup",
                "assigned_to": analysis.manager_id,
            }
        )
    else:
        for i, step in enumerate(analysis.next_steps[:3], 1):
            task_type = detect_task_type(step)
            due_hours = estimate_due_hours(step)
            tasks.append(
                {
                    "title": f"📋 Qadam #{i}: {step[:50]}...",
                    "text": step,
                    "due_in_hours": due_hours,
                    "priority": (
                        PRIORITY_HIGH if i == 1 else PRIORITY_MEDIUM
                    ),
                    "task_type_id": task_type,
                    "source": "ai_next_step",
                    "assigned_to": analysis.manager_id,
                }
            )

    if analysis.outcome == "sale":
        tasks.append(
            {
                "title": "🎉 Sotuvni tasdiqlash",
                "text": (
                    f"Tabriklaymiz! Sotuv amalga oshdi (ball: {analysis.overall_score}). "
                    f"Shartnama va to'lovni tasdiqlang."
                ),
                "due_in_hours": 4,
                "priority": PRIORITY_HIGH,
                "task_type_id": TASK_TYPES["meeting"],
                "source": "ai_sale_won",
                "assigned_to": analysis.manager_id,
            }
        )
    return tasks


def create_mood_based_tasks(analysis: ConversationAnalysis) -> List[Dict[str, Any]]:
    tasks = []
    if analysis.client_mood == "negative":
        tasks.append(
            {
                "title": "🚨 Mijoz naraziligini bartaraf etish",
                "text": (
                    "Mijoz kayfiyati salbiy. Shikoyatlarni ko'rib chiqib, "
                    "qoniqtiruvchi yechim taklif qiling."
                ),
                "due_in_hours": 2,
                "priority": PRIORITY_HIGH,
                "task_type_id": TASK_TYPES["follow_up"],
                "source": "ai_negative_mood",
                "assigned_to": analysis.manager_id,
            }
        )
    elif analysis.client_mood == "positive" and analysis.client_interest_level >= 80:
        tasks.append(
            {
                "title": "⚡ Yuqori qiziqish - tez harakat",
                "text": (
                    f"Mijoz qiziqish darajasi yuqori ({analysis.client_interest_level}%). "
                    f"Imkoniyatni boy bermang, darhol keyingi qadamga o'ting."
                ),
                "due_in_hours": 1,
                "priority": PRIORITY_HIGH,
                "task_type_id": TASK_TYPES["follow_up"],
                "source": "ai_hot_lead",
                "assigned_to": analysis.manager_id,
            }
        )
    return tasks
