"""
Quality feedback, improvement tips, task generation, and manager ratings mixin.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.services.ai.quality.models import (
    CATEGORY_NOT_SALES,
    ConversationAnalysis,
    OUTCOME_NOT_SALES,
    QualityMetric,
    SCORING_METHOD_AI,
    SCORING_METHOD_HEURISTIC,
    ScoreBreakdown,
    _clamp_score,
)

logger = logging.getLogger("QualityAnalyzer")


class FeedbackGeneratorMixin:
    """Handles feedback generation, improvement tips, and manager ratings."""

    def _generate_tasks(
        self, analysis: Dict[str, Any], lead_id: Optional[int], overall_score: int
    ) -> List[Dict[str, Any]]:
        """Tahlil asosida tavsiya qilingan vazifalar."""
        tasks = []

        # Agar ball past bo'lsa, o'qish vazifasi
        if overall_score < 60:
            tasks.append(
                {
                    "title": "🎓 Sotuv mahoratini oshirish",
                    "text": "Suhbat sifati past ({}%). E'tirozlarni yengish va yopish texnikalarini o'rganish kerak.".format(
                        overall_score
                    ),
                    "due_in_hours": 24,
                    "priority": "high",
                    "lead_id": lead_id,
                }
            )

        # E'tirozlar bo'yicha vazifalar
        for objection in analysis.get("objections", []):
            tasks.append(
                {
                    "title": f"🎯 E'tiroz: {objection[:30]}...",
                    "text": f"Mijoz e'tirozi: '{objection}'. Javob tayyorlash va qayta bog'lanish.",
                    "due_in_hours": 4,
                    "priority": "high",
                    "lead_id": lead_id,
                }
            )

        # Keyingi qadamlar
        for step in analysis.get("next_steps", []):
            tasks.append(
                {
                    "title": f"📋 {step[:40]}...",
                    "text": step,
                    "due_in_hours": 24,
                    "priority": "medium",
                    "lead_id": lead_id,
                }
            )

        return tasks

    def _get_feedback_for_metric(self, metric: QualityMetric, score: int) -> str:
        """Metric va ball uchun feedback."""
        feedbacks = {
            QualityMetric.INTRODUCTION: {
                (80, 100): "A'lo tanishtirish",
                (60, 79): "Yaxshi, lekin takomillashtirish mumkin",
                (0, 59): "Tanishtirish zaif",
            },
            QualityMetric.NEED_IDENTIFICATION: {
                (80, 100): "Ehtiyojlar aniq aniqlangan",
                (60, 79): "Ehtiyojlar qisman aniqlangan",
                (0, 59): "Ehtiyojlar aniqlanmagan",
            },
            QualityMetric.VALUE_PROPOSITION: {
                (80, 100): "Qiymat ajoyib tushuntirilgan",
                (60, 79): "Qiymat yaxshi tushuntirilgan",
                (0, 59): "Qiymat tushuntirilmagan",
            },
            QualityMetric.OBJECTION_HANDLING: {
                (80, 100): "E'tirozlarni a'lo yengdi",
                (60, 79): "E'tirozlarni qisman yengdi",
                (0, 59): "E'tirozlarni yengolmadi",
            },
            QualityMetric.CLOSING: {
                (80, 100): "A'lo yopish",
                (60, 79): "Yopish o'rtacha",
                (0, 59): "Yopish zaif",
            },
        }

        feedbacks[QualityMetric.TALK_RATIO] = {
            (80, 100): "Mijoz ko'p gapirdi — a'lo tinglash",
            (60, 79): "Gapirish nisbati yaxshi, lekin takomillashtirish mumkin",
            (0, 59): "Sotuvchi haddan ko'p gapirdi — mijozni ko'proq tinglang",
        }

        default_feedbacks = {(80, 100): "A'lo", (60, 79): "O'rtacha", (0, 59): "Zaif"}

        metric_feedbacks = feedbacks.get(metric, default_feedbacks)

        for (min_score, max_score), text in metric_feedbacks.items():
            if min_score <= score <= max_score:
                return text

        return "Baholanmagan"

    def _get_improvement_tips(self, metric: QualityMetric, score: int) -> List[str]:
        """Takomillashtirish uchun tavsiyalar."""
        if score >= 80:
            return []

        tips = {
            QualityMetric.INTRODUCTION: [
                "O'zingiz va kompaniyangizni qisqa va aniq tanishtiring",
                "Muloqot maqsadini ayting",
            ],
            QualityMetric.NEED_IDENTIFICATION: [
                "Ochiq savollar ko'proq berib, mijoz ehtiyojlarini aniqlang",
                "Mijozning muammolarini chuqurroq tushunishga harakat qiling",
            ],
            QualityMetric.VALUE_PROPOSITION: [
                "Mahsulotning mijozga qanday foyda keltirishini ko'rsating",
                "Konkret misollar keltiring",
            ],
            QualityMetric.OBJECTION_HANDLING: [
                "E'tirozlarni tan oling va mijozni tushunayotganingizni ko'rsating",
                "E'tirozga emas, yechimga e'tibor qarating",
            ],
            QualityMetric.CLOSING: [
                "Aniq yopish savollarini berib, qaror qabul qilishga olib keling",
                "Keyingi qadamlarni aniqlab, vaqt belgilang",
            ],
            QualityMetric.FOLLOW_UP: [
                "Har doim keyingi qadamni aniqlang",
                "Qayta bog'lanish vaqtini kelishib oling",
            ],
            QualityMetric.TONE: [
                "Dostona va ishonchli ohangda gapiring",
                "Mijoz kayfiyatiga moslashib gapiring",
            ],
            QualityMetric.ACTIVE_LISTENING: [
                "Mijoz gapirayotganda uzatmang",
                "Mijoz fikrini qisqa qaytarib, tushunganingizni tasdiqlang",
            ],
            QualityMetric.QUESTION_QUALITY: [
                "Ochiq va aniq savollar berib, suhbatni chuqurlashtiring",
                "Ha/yo'q savollari o'rniga ochiq savollar bering",
            ],
            QualityMetric.TALK_RATIO: [
                "Mijozni ko'proq gapirishga undang — savol berib, jim qoling",
                "Ideal nisbat: mijoz ≥55%, siz ≤45%. Hozir siz ko'p gapiryapsiz",
                "'Nima deb o'ylaysiz?', 'Sizga qaysi variant qulay?' kabi ochiq savollar ishlating",
            ],
        }

        return tips.get(metric, ["Bu yo'nalishda mashq qiling"])

    def _create_fallback_analysis(
        self,
        conversation_id: str,
        lead_id: Optional[int],
        manager_id: Optional[int],
        manager_name: str,
        duration_seconds: int,
    ) -> ConversationAnalysis:
        """Xatolik bo'lsa default tahlil."""
        return ConversationAnalysis(
            conversation_id=conversation_id,
            lead_id=lead_id,
            manager_id=manager_id,
            manager_name=manager_name,
            duration_seconds=duration_seconds,
            overall_score=0,
            category="unknown",
            summary="Tahlil qilishda xatolik yuz berdi",
            scoring_method=SCORING_METHOD_HEURISTIC,
            strengths=[],
            weaknesses=["Tahlil qilishda texnik xatolik"],
            recommended_tasks=[
                {
                    "title": "⚠️ Tahlil xatoligi",
                    "text": "Suhbat tahlil qilishda xatolik. Qo'llab-quvvatlashga murojaat qiling.",
                    "due_in_hours": 24,
                    "priority": "low",
                    "lead_id": lead_id,
                }
            ],
        )

    def get_manager_rating(
        self, analyses: List[ConversationAnalysis]
    ) -> Dict[str, Any]:
        """
        Manager reytingini hisoblash.

        Returns:
            Dict with rating info including:
            - average_score
            - total_calls
            - category_distribution
            - trend
            - rank
        """
        # Reytingdan chiqariladi:
        #  - "unknown": texnik xatolik natijasi (`_create_fallback_analysis`),
        #    ball 0 — bu menejerning ishi emas;
        #  - "not_sales": shaxsiy/xizmat qo'ng'irog'i — savdo rubrikasi
        #    qo'llanmagan, uni savdo bahosi sifatida hisoblash noto'g'ri.
        analyses = [
            a for a in analyses if a.category not in ("unknown", CATEGORY_NOT_SALES)
        ]

        if not analyses:
            return {
                "average_score": 0,
                "total_calls": 0,
                "category_distribution": {},
                "trend": "stable",
                "rank": "unranked",
            }

        scores = [a.overall_score for a in analyses]
        avg_score = sum(scores) / len(scores)

        # Kategoriya taqsimoti
        categories = {}
        for a in analyses:
            cat = a.category
            categories[cat] = categories.get(cat, 0) + 1

        # Trend (oxirgi 5 ta suhbat)
        recent = scores[-5:] if len(scores) >= 5 else scores
        earlier = (
            scores[-10:-5] if len(scores) >= 10 else scores[: max(1, len(scores) // 2)]
        )

        recent_avg = sum(recent) / len(recent) if recent else 0
        earlier_avg = sum(earlier) / len(earlier) if earlier else recent_avg

        if recent_avg > earlier_avg + 5:
            trend = "improving"
        elif recent_avg < earlier_avg - 5:
            trend = "declining"
        else:
            trend = "stable"

        # Reyting
        if avg_score >= 90:
            rank = "⭐⭐⭐⭐⭐"
        elif avg_score >= 80:
            rank = "⭐⭐⭐⭐"
        elif avg_score >= 70:
            rank = "⭐⭐⭐"
        elif avg_score >= 60:
            rank = "⭐⭐"
        else:
            rank = "⭐"

        return {
            "average_score": round(avg_score, 1),
            "total_calls": len(analyses),
            "category_distribution": categories,
            "trend": trend,
            "rank": rank,
            "best_score": max(scores),
            "worst_score": min(scores),
        }
