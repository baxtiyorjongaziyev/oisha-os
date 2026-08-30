"""
Task reporting and summary calculations.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from src.services.ai.quality_analyzer import ConversationAnalysis
from src.services.ai.task_creation.builders import (
    create_followup_tasks,
    create_mood_based_tasks,
    create_objection_tasks,
    create_quality_tasks,
)


def get_task_summary(analyses: List[ConversationAnalysis]) -> Dict[str, Any]:
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
        quality_tasks = create_quality_tasks(analysis)
        summary["by_category"]["quality_improvement"] += len(quality_tasks)

        objection_tasks = create_objection_tasks(analysis)
        summary["by_category"]["objection_handling"] += len(objection_tasks)

        followup_tasks = create_followup_tasks(analysis)
        summary["by_category"]["follow_up"] += len(followup_tasks)

        mood_tasks = create_mood_based_tasks(analysis)
        summary["by_category"]["mood_based"] += len(mood_tasks)

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
    analyses: List[ConversationAnalysis],
    created_tasks: Dict[str, List[Dict[str, Any]]],
) -> str:
    lines = ["🤖 AI VAZIFA HISOBOTI", "=" * 50, ""]
    summary = get_task_summary(analyses)

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

    if created_tasks:
        lines.append("📋 Lead bo'yicha vazifalar:")
        for lead_id, tasks in created_tasks.items():
            lines.append(f"   Lead #{lead_id}: {len(tasks)} ta vazifa")
            for task in tasks[:3]:
                status = "✅" if task.get("created_in_crm") else "📝"
                lines.append(f"     {status} {task['title'][:50]}...")
        lines.append("")

    lines.append(f"Yaratilgan vaqt: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    return "\n".join(lines)
