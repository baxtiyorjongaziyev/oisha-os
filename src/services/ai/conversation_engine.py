"""
AI Conversation Analysis Engine - Metasell.ai o'xshash funksionallik
AmoCRM suhbatlarini tahlil qilish va avtomatik vazifa qo'yish
"""

import logging
import json
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict
import asyncio

from .quality_analyzer import QualityAnalyzer, ConversationAnalysis, QualityMetric
from .call_analytics import CallAnalytics
from .task_manager import AITaskManager

logger = logging.getLogger(__name__)


@dataclass
class CallRecord:
    """Qo'ng'iroq yozuvi ma'lumotlari."""
    call_id: str
    lead_id: int
    manager_id: int
    manager_name: str
    started_at: datetime
    duration_seconds: int
    audio_url: Optional[str] = None
    transcript: str = ""
    notes: str = ""
    
    # AmoCRM dan
    lead_name: str = ""
    lead_status: str = ""
    

@dataclass
class DashboardMetrics:
    """Dashboard uchun metrikalar."""
    # Umumiy
    total_calls_today: int = 0
    total_calls_week: int = 0
    avg_score_today: float = 0.0
    avg_score_week: float = 0.0
    
    # Natijalar
    sales_count: int = 0
    followup_count: int = 0
    lost_count: int = 0
    conversion_rate: float = 0.0
    
    # Faollik
    active_managers: int = 0
    total_talk_time: int = 0  # Daqiqa
    
    # E'tirozlar
    top_objections: List[Dict[str, Any]] = field(default_factory=list)
    
    # Zaif tomonlar
    weak_areas: List[str] = field(default_factory=list)
    
    # Tavsiyalar
    recommendations: List[str] = field(default_factory=list)


class ConversationEngine:
    """
    Suhbat tahlili dvigateli.
    Metasell.ai ga o'xshash funksionallikni taqdim etadi.
    """
    
    def __init__(self, amocrm_client=None, db_pool=None):
        self.amocrm = amocrm_client
        self.db = db_pool
        self.analyzer = QualityAnalyzer()
        self.analytics = CallAnalytics()
        self.task_manager = AITaskManager(amocrm_client)
        
        # Saqlangan tahlillar
        self.analyses: Dict[str, ConversationAnalysis] = {}
        self.call_records: Dict[str, CallRecord] = {}
        
    async def process_call(
        self,
        call_record: CallRecord,
        auto_analyze: bool = True,
        auto_create_tasks: bool = True
    ) -> Optional[ConversationAnalysis]:
        """
        Yangi qo'ng'iroqni qayta ishlash.
        
        Args:
            call_record: Qo'ng'iroq ma'lumotlari
            auto_analyze: Avtomatik tahlil qilish
            auto_create_tasks: Avtomatik vazifa yaratish
            
        Returns:
            ConversationAnalysis: Tahlil natijasi
        """
        try:
            # Saqlash
            self.call_records[call_record.call_id] = call_record
            
            if not auto_analyze:
                logger.info(f"[ENGINE] Call {call_record.call_id} saqlandi (tahlilsiz)")
                return None
            
            # Tahlil qilish
            analysis = await self._analyze_call(call_record)
            
            if analysis:
                self.analyses[call_record.call_id] = analysis
                self.analytics.add_analysis(analysis)
                
                # Vazifalar yaratish
                if auto_create_tasks:
                    tasks = await self.task_manager.create_tasks_from_analysis(
                        analysis, 
                        auto_create=True
                    )
                    logger.info(f"[ENGINE] {len(tasks)} ta vazifa yaratildi")
                
                # Ma'lumotlar bazasiga saqlash
                await self._save_analysis_to_db(analysis, call_record)
                
                logger.info(
                    f"[ENGINE] Call {call_record.call_id} tahlil qilindi: "
                    f"ball={analysis.overall_score}, natija={analysis.outcome}"
                )
            
            return analysis
            
        except Exception as e:
            logger.error(f"[ENGINE] Call processing error: {e}")
            return None
    
    async def _analyze_call(
        self, 
        call_record: CallRecord
    ) -> Optional[ConversationAnalysis]:
        """Qo'ng'iroqni tahlil qilish."""
        try:
            # Transkriptsiya mavjudmi?
            transcript = call_record.transcript
            if not transcript and call_record.audio_url:
                # Audio dan transcript olish (STT)
                transcript = await self._transcribe_audio(call_record.audio_url)
            
            if not transcript:
                logger.warning(f"[ENGINE] No transcript for call {call_record.call_id}")
                return None
            
            # AI tahlil
            analysis = self.analyzer.analyze_conversation(
                conversation_text=transcript,
                conversation_id=call_record.call_id,
                lead_id=call_record.lead_id,
                manager_id=call_record.manager_id,
                manager_name=call_record.manager_name,
                duration_seconds=call_record.duration_seconds
            )
            
            return analysis
            
        except Exception as e:
            logger.error(f"[ENGINE] Analysis error: {e}")
            return None
    
    async def _transcribe_audio(self, audio_url: str) -> str:
        """Audio faylni matnga o'tkazish (STT)."""
        # TODO: Integrate with speech-to-text API (Google, Whisper, etc.)
        # Hozircha mock
        logger.info(f"[ENGINE] Transcribing audio: {audio_url}")
        return ""
    
    async def _save_analysis_to_db(
        self,
        analysis: ConversationAnalysis,
        call_record: CallRecord
    ):
        """Tahlil natijasini ma'lumotlar bazasiga saqlash."""
        if not self.db:
            return
        
        try:
            query = """
                INSERT INTO call_analyses (
                    call_id, lead_id, manager_id, manager_name,
                    duration_seconds, overall_score, category,
                    summary, strengths, weaknesses, client_mood,
                    client_interest_level, objections, outcome,
                    next_steps, recommended_tasks, analyzed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            await self.db.execute(query, (
                analysis.conversation_id,
                analysis.lead_id,
                analysis.manager_id,
                analysis.manager_name,
                analysis.duration_seconds,
                analysis.overall_score,
                analysis.category,
                analysis.summary,
                json.dumps(analysis.strengths),
                json.dumps(analysis.weaknesses),
                analysis.client_mood,
                analysis.client_interest_level,
                json.dumps(analysis.objections_raised),
                analysis.outcome,
                json.dumps(analysis.next_steps),
                json.dumps([t.to_dict() if hasattr(t, 'to_dict') else t for t in analysis.recommended_tasks]),
                analysis.analyzed_at.isoformat()
            ))
            
        except Exception as e:
            logger.error(f"[ENGINE] DB save error: {e}")
    
    def get_dashboard_metrics(self, days: int = 7) -> DashboardMetrics:
        """Dashboard uchun metrikalar."""
        metrics = DashboardMetrics()
        
        # Vaqt chegaralari
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Analizlarni filtrlash
        recent_analyses = [
            a for a in self.analyses.values()
            if start_date <= a.analyzed_at <= end_date
        ]
        
        if not recent_analyses:
            return metrics
        
        # Umumiy
        metrics.total_calls_week = len(recent_analyses)
        metrics.avg_score_week = sum(a.overall_score for a in recent_analyses) / len(recent_analyses)
        
        # Bugungi statistika
        today = datetime.now().date()
        today_analyses = [a for a in recent_analyses if a.analyzed_at.date() == today]
        metrics.total_calls_today = len(today_analyses)
        if today_analyses:
            metrics.avg_score_today = sum(a.overall_score for a in today_analyses) / len(today_analyses)
        
        # Natijalar
        outcomes = defaultdict(int)
        for a in recent_analyses:
            outcomes[a.outcome] += 1
        
        metrics.sales_count = outcomes.get("sale", 0)
        metrics.followup_count = outcomes.get("follow_up", 0)
        metrics.lost_count = outcomes.get("lost", 0)
        
        if recent_analyses:
            metrics.conversion_rate = (metrics.sales_count / len(recent_analyses)) * 100
        
        # Faollik
        manager_ids = set(a.manager_id for a in recent_analyses if a.manager_id)
        metrics.active_managers = len(manager_ids)
        metrics.total_talk_time = sum(a.duration_seconds for a in recent_analyses) // 60
        
        # E'tirozlar
        all_objections = []
        for a in recent_analyses:
            all_objections.extend(a.objections_raised)
        
        from collections import Counter
        top_obj = Counter(all_objections).most_common(5)
        metrics.top_objections = [{"objection": o, "count": c} for o, c in top_obj]
        
        # Zaif tomonlar
        all_weaknesses = []
        for a in recent_analyses:
            all_weaknesses.extend(a.weaknesses)
        weak_counts = Counter(all_weaknesses)
        metrics.weak_areas = [w for w, _ in weak_counts.most_common(5)]
        
        # Tavsiyalar
        metrics.recommendations = self._generate_dashboard_recommendations(
            recent_analyses, metrics
        )
        
        return metrics
    
    def _generate_dashboard_recommendations(
        self,
        analyses: List[ConversationAnalysis],
        metrics: DashboardMetrics
    ) -> List[str]:
        """Dashboard uchun tavsiyalar."""
        recommendations = []
        
        if not analyses:
            return recommendations
        
        # O'rtacha ball
        avg_score = sum(a.overall_score for a in analyses) / len(analyses)
        if avg_score < 70:
            recommendations.append(
                f"📉 O'rtacha sifat balli past ({avg_score:.1f}). "
                f"Jamoa sotuv mahoratini oshirish kerak."
            )
        elif avg_score >= 85:
            recommendations.append(
                f"🌟 A'lo natija! O'rtacha ball {avg_score:.1f}. "
                f"Jamoa sifatli ishlamoqda."
            )
        
        # Yo'qotishlar
        lost_rate = metrics.lost_count / len(analyses) * 100
        if lost_rate > 30:
            recommendations.append(
                f"⚠️ Yo'qotish stavkasi yuqori ({lost_rate:.1f}%). "
                f"Mijoz ushlab qolish strategiyasi ishlab chiqilishi kerak."
            )
        
        # Konversiya
        if metrics.conversion_rate < 20:
            recommendations.append(
                f"🎯 Konversiya stavkasi past ({metrics.conversion_rate:.1f}%). "
                f"Yopish texnikalarini takomillashtirish kerak."
            )
        
        # E'tirozlar
        all_objections = []
        for a in analyses:
            all_objections.extend(a.objections_raised)
        
        if all_objections:
            from collections import Counter
            top_obj = Counter(all_objections).most_common(1)
            if top_obj:
                recommendations.append(
                    f"🛡️ Eng ko'p uchraydigan e'tiroz: '{top_obj[0][0]}'. "
                    f"Bu yo'nalishda trening o'tkazish kerak."
                )
        
        return recommendations
    
    def get_manager_comparison(
        self,
        days: int = 7
    ) -> List[Dict[str, Any]]:
        """Managerlar taqqoslash."""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Manager bo'yicha guruhlash
        by_manager = defaultdict(list)
        for a in self.analyses.values():
            if start_date <= a.analyzed_at <= end_date:
                by_manager[a.manager_id].append(a)
        
        comparisons = []
        for manager_id, analyses in by_manager.items():
            if not analyses:
                continue
            
            scores = [a.overall_score for a in analyses]
            outcomes = defaultdict(int)
            for a in analyses:
                outcomes[a.outcome] += 1
            
            comparisons.append({
                "manager_id": manager_id,
                "manager_name": analyses[0].manager_name,
                "total_calls": len(analyses),
                "avg_score": round(sum(scores) / len(scores), 1),
                "best_score": max(scores),
                "sales_count": outcomes.get("sale", 0),
                "conversion_rate": round(outcomes.get("sale", 0) / len(analyses) * 100, 1),
                "rank": 0  # Keyinroq hisoblanadi
            })
        
        # Reyting
        comparisons.sort(key=lambda x: x["avg_score"], reverse=True)
        for i, comp in enumerate(comparisons, 1):
            comp["rank"] = i
        
        return comparisons
    
    def get_call_details(self, call_id: str) -> Optional[Dict[str, Any]]:
        """Qo'ng'iroq tafsilotlari."""
        call = self.call_records.get(call_id)
        analysis = self.analyses.get(call_id)
        
        if not call:
            return None
        
        return {
            "call": {
                "call_id": call.call_id,
                "lead_id": call.lead_id,
                "lead_name": call.lead_name,
                "manager_name": call.manager_name,
                "started_at": call.started_at.isoformat(),
                "duration_seconds": call.duration_seconds,
                "audio_url": call.audio_url
            },
            "analysis": analysis.to_dict() if analysis else None,
            "transcript": call.transcript[:1000] if call.transcript else None  # Preview
        }
    
    def get_trend_analysis(
        self,
        metric: str = "score",
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Dinamik tahlil (trend).
        
        Args:
            metric: 'score', 'conversion', 'duration'
            days: Kunlar soni
        """
        end_date = datetime.now()
        
        # Kunlik guruhlash
        daily_data = defaultdict(list)
        for a in self.analyses.values():
            date_key = a.analyzed_at.strftime("%Y-%m-%d")
            daily_data[date_key].append(a)
        
        # So'nggi N kun
        trend = []
        for i in range(days):
            date = (end_date - timedelta(days=i)).strftime("%Y-%m-%d")
            analyses = daily_data.get(date, [])
            
            if not analyses:
                trend.append({
                    "date": date,
                    "value": 0,
                    "count": 0
                })
                continue
            
            if metric == "score":
                value = sum(a.overall_score for a in analyses) / len(analyses)
            elif metric == "conversion":
                sales = len([a for a in analyses if a.outcome == "sale"])
                value = sales / len(analyses) * 100
            elif metric == "duration":
                value = sum(a.duration_seconds for a in analyses) / len(analyses) / 60
            else:
                value = 0
            
            trend.append({
                "date": date,
                "value": round(value, 1),
                "count": len(analyses)
            })
        
        # Teskari tartib (eng yangisi oxirida)
        return list(reversed(trend))
    
    async def process_amocrm_lead_calls(
        self,
        lead_id: int,
        days: int = 7
    ) -> List[ConversationAnalysis]:
        """
        AmoCRM lead uchun barcha qo'ng'iroqlarni tahlil qilish.
        
        Args:
            lead_id: AmoCRM lead ID
            days: Necha kunlik qo'ng'iroqlar
            
        Returns:
            List[ConversationAnalysis]: Tahlil natijalari
        """
        # TODO: AmoCRM dan qo'ng'iroqlarni olish
        # Hozircha mavjud tahlillarni qaytarish
        
        analyses = [
            a for a in self.analyses.values()
            if a.lead_id == lead_id
        ]
        
        return analyses
    
    def generate_daily_report(self) -> str:
        """Kunlik hisobot."""
        metrics = self.get_dashboard_metrics(days=1)
        
        lines = [
            "📊 KUNLIK SIFAT NAZORATI HISOBOTI",
            "=" * 50,
            "",
            f"📞 Qo'ng'iroqlar: {metrics.total_calls_today}",
            f"⭐ O'rtacha ball: {metrics.avg_score_today:.1f}/100",
            f"🎯 Konversiya: {metrics.conversion_rate:.1f}%",
            f"💰 Sotuvlar: {metrics.sales_count}",
            f"👥 Faol managerlar: {metrics.active_managers}",
            "",
            "📋 TAVSIYALAR:",
        ]
        
        for rec in metrics.recommendations:
            lines.append(f"  • {rec}")
        
        if not metrics.recommendations:
            lines.append("  • Bugun jamoa yaxshi ishlamoqda!")
        
        lines.append("")
        lines.append(f"Yaratilgan: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        
        return "\n".join(lines)
    
    def get_skills_radar_data(
        self,
        manager_id: Optional[int] = None,
        days: int = 7
    ) -> Dict[str, Any]:
        """
        Manager mahorati radar chart ma'lumotlari.
        Metasell.ai dagi 'Manager Radar' ga o'xshash.
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Filtrlash
        analyses = [
            a for a in self.analyses.values()
            if start_date <= a.analyzed_at <= end_date
            and (manager_id is None or a.manager_id == manager_id)
        ]
        
        if not analyses:
            return {"skills": {}, "overall": 0}
        
        # Har bir skill bo'yicha o'rtacha
        skill_scores = defaultdict(list)
        for a in analyses:
            for score in a.scores:
                skill_scores[score.metric.value].append(score.score)
        
        skills = {}
        for skill, scores in skill_scores.items():
            skills[skill] = round(sum(scores) / len(scores), 1)
        
        # Overall
        overall = sum(a.overall_score for a in analyses) / len(analyses)
        
        return {
            "skills": skills,
            "overall": round(overall, 1),
            "manager_name": analyses[0].manager_name if manager_id else "Jamoa",
            "call_count": len(analyses)
        }


# Singleton instance
_conversation_engine: Optional[ConversationEngine] = None


def get_conversation_engine(
    amocrm_client=None,
    db_pool=None
) -> ConversationEngine:
    """Global conversation engine instance."""
    global _conversation_engine
    if _conversation_engine is None:
        _conversation_engine = ConversationEngine(amocrm_client, db_pool)
    return _conversation_engine
