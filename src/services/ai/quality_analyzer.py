"""AI-powered conversation quality analysis for sales calls."""

import logging
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class QualityMetric(Enum):
    """Sifat ko'rsatkichlari."""
    INTRODUCTION = "introduction"  # O'zini tanishtirish
    NEED_IDENTIFICATION = "need_identification"  # Ehtiyoj aniqlash
    OBJECTION_HANDLING = "objection_handling"  # E'tirozlarni yengish
    VALUE_PROPOSITION = "value_proposition"  # Qiymat tushuntirish
    CLOSING = "closing"  # Yopish
    FOLLOW_UP = "follow_up"  # Keyingi qadam
    TONE = "tone"  # Ohang
    ACTIVE_LISTENING = "active_listening"  # Faql eshitish
    QUESTION_QUALITY = "question_quality"  # Savollar sifati


@dataclass
class ScoreBreakdown:
    """Batafsil ball tahlili."""
    metric: QualityMetric
    score: int  # 0-100
    weight: float  # 0.0-1.0
    feedback: str
    examples: List[str] = field(default_factory=list)
    improvement_tips: List[str] = field(default_factory=list)


@dataclass
class ConversationAnalysis:
    """Suhbat tahlili natijalari."""
    conversation_id: str
    lead_id: Optional[int]
    manager_id: Optional[int]
    manager_name: str
    duration_seconds: int
    overall_score: int  # 0-100
    category: str  # "excellent", "good", "average", "poor", "critical"
    
    # Batafsil ballar
    scores: List[ScoreBreakdown] = field(default_factory=list)
    
    # Tahlil
    summary: str = ""
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    
    # Mijoz bilan bog'liq
    client_mood: str = ""  # "positive", "neutral", "negative"
    client_interest_level: int = 0  # 0-100
    objections_raised: List[str] = field(default_factory=list)
    
    # Natija
    outcome: str = ""  # "sale", "follow_up", "lost", "callback"
    next_steps: List[str] = field(default_factory=list)
    
    # Vazifalar
    recommended_tasks: List[Dict[str, Any]] = field(default_factory=list)
    
    # Metadata
    analyzed_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Dict formatga o'tkazish."""
        return {
            "conversation_id": self.conversation_id,
            "lead_id": self.lead_id,
            "manager_id": self.manager_id,
            "manager_name": self.manager_name,
            "duration_seconds": self.duration_seconds,
            "overall_score": self.overall_score,
            "category": self.category,
            "scores": [
                {
                    "metric": s.metric.value,
                    "score": s.score,
                    "weight": s.weight,
                    "feedback": s.feedback,
                    "examples": s.examples,
                    "improvement_tips": s.improvement_tips
                }
                for s in self.scores
            ],
            "summary": self.summary,
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
            "client_mood": self.client_mood,
            "client_interest_level": self.client_interest_level,
            "objections_raised": self.objections_raised,
            "outcome": self.outcome,
            "next_steps": self.next_steps,
            "recommended_tasks": self.recommended_tasks,
            "analyzed_at": self.analyzed_at.isoformat()
        }


class QualityAnalyzer:
    """AI-powered conversation quality analyzer."""
    
    # Sifat kategoriyalari
    CATEGORIES = {
        (90, 100): "excellent",
        (80, 89): "good",
        (60, 79): "average",
        (40, 59): "poor",
        (0, 39): "critical"
    }
    
    # Ballar uchun og'irliklar
    DEFAULT_WEIGHTS = {
        QualityMetric.INTRODUCTION: 0.10,
        QualityMetric.NEED_IDENTIFICATION: 0.15,
        QualityMetric.VALUE_PROPOSITION: 0.15,
        QualityMetric.OBJECTION_HANDLING: 0.15,
        QualityMetric.CLOSING: 0.15,
        QualityMetric.FOLLOW_UP: 0.10,
        QualityMetric.TONE: 0.10,
        QualityMetric.ACTIVE_LISTENING: 0.05,
        QualityMetric.QUESTION_QUALITY: 0.05
    }
    
    def __init__(self, openai_api_key: Optional[str] = None):
        self.api_key = openai_api_key
        self.weights = self.DEFAULT_WEIGHTS.copy()
        
    def set_weights(self, weights: Dict[QualityMetric, float]):
        """Og'irliklarni sozlash."""
        self.weights.update(weights)
        # Normalize
        total = sum(self.weights.values())
        if total > 0:
            self.weights = {k: v/total for k, v in self.weights.items()}
    
    def analyze_conversation(
        self,
        conversation_text: str,
        conversation_id: str,
        lead_id: Optional[int] = None,
        manager_id: Optional[int] = None,
        manager_name: str = "",
        duration_seconds: int = 0
    ) -> ConversationAnalysis:
        """
        Suhbatni tahlil qilish va sifat ballari berish.
        
        Args:
            conversation_text: Suhbat matni yoki transcript
            conversation_id: Suhbat ID
            lead_id: AmoCRM lead ID
            manager_id: Manager ID
            manager_name: Manager ismi
            duration_seconds: Suhbat davomiyligi
            
        Returns:
            ConversationAnalysis: Tahlil natijalari
        """
        try:
            # AI tahlil (simulyatsiya - haqiqiy LLM integration bilan almashtirish mumkin)
            analysis = self._ai_analyze(conversation_text)
            
            # Ballar hisoblash
            scores = self._calculate_scores(analysis)
            
            # Umumiy ball
            overall_score = self._calculate_overall_score(scores)
            
            # Kategoriya aniqlash
            category = self._get_category(overall_score)
            
            # Tavsiya qilingan vazifalar
            recommended_tasks = self._generate_tasks(analysis, lead_id, overall_score)
            
            return ConversationAnalysis(
                conversation_id=conversation_id,
                lead_id=lead_id,
                manager_id=manager_id,
                manager_name=manager_name,
                duration_seconds=duration_seconds,
                overall_score=overall_score,
                category=category,
                scores=scores,
                summary=analysis.get("summary", ""),
                strengths=analysis.get("strengths", []),
                weaknesses=analysis.get("weaknesses", []),
                client_mood=analysis.get("client_mood", "neutral"),
                client_interest_level=analysis.get("client_interest_level", 50),
                objections_raised=analysis.get("objections", []),
                outcome=analysis.get("outcome", "unknown"),
                next_steps=analysis.get("next_steps", []),
                recommended_tasks=recommended_tasks
            )
            
        except Exception as e:
            logger.error(f"[QUALITY ANALYZER] Tahlil xatosi: {e}")
            # Xatolik bo'lsa default qiymatlar
            return self._create_fallback_analysis(
                conversation_id, lead_id, manager_id, manager_name, duration_seconds
            )
    
    def _ai_analyze(self, text: str) -> Dict[str, Any]:
        """
        AI orqali suhbatni tahlil qilish.
        Bu yerda haqiqiy LLM (OpenAI, Claude, etc) ishlatiladi.
        Hozircha mock implementation.
        """
        # TODO: Integrate with actual LLM API
        # Bu yerda suhbatni tahlil qilib, quyidagi ma'lumotlarni qaytaradi:
        # - Har bir metric bo'yicha baxo
        # - Kuchli tomonlar
        # - Zaif tomonlar
        # - Mijoz kayfiyati
        # - E'tirozlar
        # - Natija
        
        # Mock tahlil (real implementatsiyada bu AI dan keladi)
        return {
            "summary": "Suhbat umuman yaxshi o'tdi, lekin ba'zi kamchiliklar bor.",
            "strengths": ["Mijoz bilan samimiy muloqot", "Mahsulot tavsiyasi aniq"],
            "weaknesses": ["E'tirozlarni to'liq yengilmagan", "Keyingi qadam aniqlanmagan"],
            "client_mood": "positive",
            "client_interest_level": 75,
            "objections": ["Narx juda baland"],
            "outcome": "follow_up",
            "next_steps": ["Narx chegirma imkoniyatini tekshirish", "Qayta qo'ng'iroq"],
            "metric_scores": {
                "introduction": 85,
                "need_identification": 70,
                "value_proposition": 80,
                "objection_handling": 60,
                "closing": 65,
                "follow_up": 50,
                "tone": 90,
                "active_listening": 75,
                "question_quality": 70
            }
        }
    
    def _calculate_scores(self, analysis: Dict[str, Any]) -> List[ScoreBreakdown]:
        """Har bir metric bo'yicha ball hisoblash."""
        scores = []
        metric_scores = analysis.get("metric_scores", {})
        
        for metric, weight in self.weights.items():
            score = metric_scores.get(metric.value, 50)  # Default 50
            
            # Feedback va tavsiyalar
            feedback = self._get_feedback_for_metric(metric, score)
            tips = self._get_improvement_tips(metric, score)
            
            scores.append(ScoreBreakdown(
                metric=metric,
                score=score,
                weight=weight,
                feedback=feedback,
                improvement_tips=tips
            ))
        
        return scores
    
    def _calculate_overall_score(self, scores: List[ScoreBreakdown]) -> int:
        """Og'irliklar bilan umumiy ball hisoblash."""
        if not scores:
            return 0
        
        weighted_sum = sum(s.score * s.weight for s in scores)
        return int(weighted_sum)
    
    def _get_category(self, score: int) -> str:
        """Ball asosida kategoriya aniqlash."""
        for (min_score, max_score), category in self.CATEGORIES.items():
            if min_score <= score <= max_score:
                return category
        return "unknown"
    
    def _generate_tasks(
        self,
        analysis: Dict[str, Any],
        lead_id: Optional[int],
        overall_score: int
    ) -> List[Dict[str, Any]]:
        """Tahlil asosida tavsiya qilingan vazifalar."""
        tasks = []
        
        # Agar ball past bo'lsa, o'qish vazifasi
        if overall_score < 60:
            tasks.append({
                "title": "🎓 Sotuv mahoratini oshirish",
                "text": "Suhbat sifati past ({}%). E'tirozlarni yengish va yopish texnikalarini o'rganish kerak.".format(overall_score),
                "due_in_hours": 24,
                "priority": "high",
                "lead_id": lead_id
            })
        
        # E'tirozlar bo'yicha vazifalar
        for objection in analysis.get("objections", []):
            tasks.append({
                "title": f"🎯 E'tiroz: {objection[:30]}...",
                "text": f"Mijoz e'tirozi: '{objection}'. Javob tayyorlash va qayta bog'lanish.",
                "due_in_hours": 4,
                "priority": "high",
                "lead_id": lead_id
            })
        
        # Keyingi qadamlar
        for step in analysis.get("next_steps", []):
            tasks.append({
                "title": f"📋 {step[:40]}...",
                "text": step,
                "due_in_hours": 24,
                "priority": "medium",
                "lead_id": lead_id
            })
        
        return tasks
    
    def _get_feedback_for_metric(self, metric: QualityMetric, score: int) -> str:
        """Metric va ball uchun feedback."""
        feedbacks = {
            QualityMetric.INTRODUCTION: {
                (80, 100): "A'lo tanishtirish",
                (60, 79): "Yaxshi, lekin takomillashtirish mumkin",
                (0, 59): "Tanishtirish zaif"
            },
            QualityMetric.NEED_IDENTIFICATION: {
                (80, 100): "Ehtiyojlar aniq aniqlangan",
                (60, 79): "Ehtiyojlar qisman aniqlangan",
                (0, 59): "Ehtiyojlar aniqlanmagan"
            },
            QualityMetric.VALUE_PROPOSITION: {
                (80, 100): "Qiymat ajoyib tushuntirilgan",
                (60, 79): "Qiymat yaxshi tushuntirilgan",
                (0, 59): "Qiymat tushuntirilmagan"
            },
            QualityMetric.OBJECTION_HANDLING: {
                (80, 100): "E'tirozlarni a'lo yengdi",
                (60, 79): "E'tirozlarni qisman yengdi",
                (0, 59): "E'tirozlarni yengolmadi"
            },
            QualityMetric.CLOSING: {
                (80, 100): "A'lo yopish",
                (60, 79): "Yopish o'rtacha",
                (0, 59): "Yopish zaif"
            }
        }
        
        default_feedbacks = {
            (80, 100): "A'lo",
            (60, 79): "O'rtacha",
            (0, 59): "Zaif"
        }
        
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
                "Muloqot maqsadini ayting"
            ],
            QualityMetric.NEED_IDENTIFICATION: [
                "Ochiq savollar ko'proq berib, mijoz ehtiyojlarini aniqlang",
                "Mijozning muammolarini chuqurroq tushunishga harakat qiling"
            ],
            QualityMetric.VALUE_PROPOSITION: [
                "Mahsulotning mijozga qanday foyda keltirishini ko'rsating",
                "Konkret misollar keltiring"
            ],
            QualityMetric.OBJECTION_HANDLING: [
                "E'tirozlarni tan oling va mijozni tushunayotganingizni ko'rsating",
                "E'tirozga emas, yechimga e'tibor qarating"
            ],
            QualityMetric.CLOSING: [
                "Aniq yopish savollarini berib, qaror qabul qilishga olib keling",
                "Keyingi qadamlarni aniqlab, vaqt belgilang"
            ],
            QualityMetric.FOLLOW_UP: [
                "Har doim keyingi qadamni aniqlang",
                "Qayta bog'lanish vaqtini kelishib oling"
            ],
            QualityMetric.TONE: [
                "Dostona va ishonchli ohangda gapiring",
                "Mijoz kayfiyatiga moslashib gapiring"
            ],
            QualityMetric.ACTIVE_LISTENING: [
                "Mijoz gapirayotganda uzatmang",
                "Mijoz fikrini qisqa qaytarib, tushunganingizni tasdiqlang"
            ],
            QualityMetric.QUESTION_QUALITY: [
                "Ochiq va aniq savollar berib, suhbatni chuqurlashtiring",
                "Ha/yo'q savollari o'rniga ochiq savollar bering"
            ]
        }
        
        return tips.get(metric, ["Bu yo'nalishda mashq qiling"])
    
    def _create_fallback_analysis(
        self,
        conversation_id: str,
        lead_id: Optional[int],
        manager_id: Optional[int],
        manager_name: str,
        duration_seconds: int
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
            strengths=[],
            weaknesses=["Tahlil qilishda texnik xatolik"],
            recommended_tasks=[{
                "title": "⚠️ Tahlil xatoligi",
                "text": "Suhbat tahlil qilishda xatolik. Qo'llab-quvvatlashga murojaat qiling.",
                "due_in_hours": 24,
                "priority": "low",
                "lead_id": lead_id
            }]
        )
    
    def get_manager_rating(
        self,
        analyses: List[ConversationAnalysis]
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
        if not analyses:
            return {
                "average_score": 0,
                "total_calls": 0,
                "category_distribution": {},
                "trend": "stable",
                "rank": "unranked"
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
        earlier = scores[-10:-5] if len(scores) >= 10 else scores[:max(1, len(scores)//2)]
        
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
            "worst_score": min(scores)
        }
