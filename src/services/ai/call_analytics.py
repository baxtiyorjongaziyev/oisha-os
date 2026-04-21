"""Advanced call analytics and visualization data."""

import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict

from .quality_analyzer import ConversationAnalysis, QualityMetric

logger = logging.getLogger(__name__)


@dataclass
class DailyStats:
    """Kunlik statistika."""
    date: str
    total_calls: int = 0
    analyzed_calls: int = 0
    average_score: float = 0.0
    total_duration: int = 0
    
    # Natijalar bo'yicha
    sales_made: int = 0
    follow_ups: int = 0
    lost: int = 0
    callbacks: int = 0
    
    # Vaqt bo'yicha
    peak_hour: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "date": self.date,
            "total_calls": self.total_calls,
            "analyzed_calls": self.analyzed_calls,
            "average_score": round(self.average_score, 1),
            "total_duration": self.total_duration,
            "avg_duration": round(self.total_duration / max(self.total_calls, 1), 0),
            "outcomes": {
                "sales": self.sales_made,
                "follow_up": self.follow_ups,
                "lost": self.lost,
                "callback": self.callbacks
            }
        }


@dataclass
class ManagerPerformance:
    """Manager samaradorligi."""
    manager_id: int
    manager_name: str
    
    # Asosiy ko'rsatkichlar
    total_calls: int = 0
    average_score: float = 0.0
    total_duration: int = 0
    
    # Natijalar
    sales_count: int = 0
    conversion_rate: float = 0.0
    
    # Dinamika
    trend: str = "stable"  # improving, declining, stable
    rank: int = 0
    
    # Taqsimot
    score_distribution: Dict[str, int] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "manager_id": self.manager_id,
            "manager_name": self.manager_name,
            "total_calls": self.total_calls,
            "average_score": round(self.average_score, 1),
            "avg_duration_min": round(self.total_duration / max(self.total_calls, 1) / 60, 1),
            "sales_count": self.sales_count,
            "conversion_rate": round(self.conversion_rate, 1),
            "trend": self.trend,
            "rank": self.rank,
            "score_distribution": self.score_distribution
        }


@dataclass
class LostClientAnalysis:
    """Yo'qotilgan mijozlar tahlili."""
    total_lost: int = 0
    
    # Sabablar bo'yicha
    reasons: Dict[str, int] = field(default_factory=dict)
    
    # Sifat bo'yicha
    avg_score_before_lost: float = 0.0
    
    # Aniqlangan oqibatlar
    preventable_count: int = 0  # Sifat yaxshilansa ushlab qolish mumkin
    
    # Tavsiyalar
    recommendations: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_lost": self.total_lost,
            "reasons": self.reasons,
            "avg_score_before_lost": round(self.avg_score_before_lost, 1),
            "preventable_count": self.preventable_count,
            "preventable_percent": round(self.preventable_count / max(self.total_lost, 1) * 100, 1),
            "recommendations": self.recommendations
        }


class CallAnalytics:
    """Qo'ng'iroq analitikasi va vizualizatsiya."""
    
    def __init__(self):
        self.analyses: List[ConversationAnalysis] = []
        
    def add_analysis(self, analysis: ConversationAnalysis):
        """Tahlil natijasini qo'shish."""
        self.analyses.append(analysis)
        
    def add_analyses(self, analyses: List[ConversationAnalysis]):
        """Bir nechta tahlil natijalarini qo'shish."""
        self.analyses.extend(analyses)
    
    def get_dashboard_data(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Dashboard uchun to'liq ma'lumotlar.
        
        Returns:
            Dict with all analytics data for visualization
        """
        # Sana bo'yicha filtr
        analyses = self._filter_by_date(start_date, end_date)
        
        if not analyses:
            return self._get_empty_dashboard()
        
        return {
            "summary": self._get_summary_stats(analyses),
            "daily_stats": self._get_daily_stats(analyses),
            "manager_ratings": self._get_manager_ratings(analyses),
            "quality_distribution": self._get_quality_distribution(analyses),
            "outcome_analysis": self._get_outcome_analysis(analyses),
            "objection_analysis": self._get_objection_analysis(analyses),
            "lost_clients": self._analyze_lost_clients(analyses),
            "time_analysis": self._get_time_analysis(analyses),
            "recommendations": self._generate_recommendations(analyses),
            "generated_at": datetime.now().isoformat()
        }
    
    def get_manager_dashboard(
        self,
        manager_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Manager uchun shaxsiy dashboard."""
        analyses = [
            a for a in self._filter_by_date(start_date, end_date)
            if a.manager_id == manager_id
        ]
        
        if not analyses:
            return {"error": "Ma'lumot topilmadi"}
        
        manager_name = analyses[0].manager_name if analyses else ""
        
        return {
            "manager_id": manager_id,
            "manager_name": manager_name,
            "period": {
                "start": start_date.isoformat() if start_date else None,
                "end": end_date.isoformat() if end_date else None
            },
            "summary": self._get_summary_stats(analyses),
            "skill_breakdown": self._get_skill_breakdown(analyses),
            "progress_over_time": self._get_progress_over_time(analyses),
            "strengths": self._get_top_strengths(analyses),
            "areas_for_improvement": self._get_improvement_areas(analyses),
            "recent_calls": [a.to_dict() for a in sorted(analyses, key=lambda x: x.analyzed_at, reverse=True)[:10]]
        }
    
    def _filter_by_date(
        self,
        start_date: Optional[datetime],
        end_date: Optional[datetime]
    ) -> List[ConversationAnalysis]:
        """Sana bo'yicha filtrlash."""
        filtered = self.analyses
        
        if start_date:
            filtered = [a for a in filtered if a.analyzed_at >= start_date]
        
        if end_date:
            filtered = [a for a in filtered if a.analyzed_at <= end_date]
        
        return filtered
    
    def _get_summary_stats(self, analyses: List[ConversationAnalysis]) -> Dict[str, Any]:
        """Asosiy statistika."""
        total_calls = len(analyses)
        
        if not total_calls:
            return {}
        
        scores = [a.overall_score for a in analyses]
        durations = [a.duration_seconds for a in analyses]
        
        # Natijalar bo'yicha
        outcomes = defaultdict(int)
        for a in analyses:
            outcomes[a.outcome] += 1
        
        return {
            "total_calls": total_calls,
            "average_score": round(sum(scores) / len(scores), 1),
            "best_score": max(scores),
            "worst_score": min(scores),
            "total_duration_hours": round(sum(durations) / 3600, 1),
            "avg_duration_min": round(sum(durations) / len(durations) / 60, 1),
            "outcomes": dict(outcomes),
            "conversion_rate": round(outcomes.get("sale", 0) / total_calls * 100, 1)
        }
    
    def _get_daily_stats(self, analyses: List[ConversationAnalysis]) -> List[Dict[str, Any]]:
        """Kunlik statistika."""
        daily = defaultdict(lambda: DailyStats(date=""))
        
        for a in analyses:
            date_str = a.analyzed_at.strftime("%Y-%m-%d")
            
            if not daily[date_str].date:
                daily[date_str].date = date_str
            
            daily[date_str].total_calls += 1
            daily[date_str].analyzed_calls += 1
            daily[date_str].total_duration += a.duration_seconds
            
            # Natija
            if a.outcome == "sale":
                daily[date_str].sales_made += 1
            elif a.outcome == "follow_up":
                daily[date_str].follow_ups += 1
            elif a.outcome == "lost":
                daily[date_str].lost += 1
            elif a.outcome == "callback":
                daily[date_str].callbacks += 1
        
        # O'rtacha ball hisoblash
        for date_str in daily:
            day_analyses = [a for a in analyses if a.analyzed_at.strftime("%Y-%m-%d") == date_str]
            if day_analyses:
                daily[date_str].average_score = sum(a.overall_score for a in day_analyses) / len(day_analyses)
        
        # Sanaga qarab sortlash
        return [daily[d].to_dict() for d in sorted(daily.keys())]
    
    def _get_manager_ratings(self, analyses: List[ConversationAnalysis]) -> List[Dict[str, Any]]:
        """Manager reytinglari."""
        by_manager = defaultdict(list)
        
        for a in analyses:
            if a.manager_id:
                by_manager[a.manager_id].append(a)
        
        performances = []
        
        for manager_id, manager_analyses in by_manager.items():
            perf = ManagerPerformance(
                manager_id=manager_id,
                manager_name=manager_analyses[0].manager_name if manager_analyses else ""
            )
            
            perf.total_calls = len(manager_analyses)
            perf.average_score = sum(a.overall_score for a in manager_analyses) / len(manager_analyses)
            perf.total_duration = sum(a.duration_seconds for a in manager_analyses)
            
            # Natijalar
            sales = len([a for a in manager_analyses if a.outcome == "sale"])
            perf.sales_count = sales
            perf.conversion_rate = sales / perf.total_calls * 100 if perf.total_calls > 0 else 0
            
            # Taqsimot
            for a in manager_analyses:
                perf.score_distribution[a.category] = perf.score_distribution.get(a.category, 0) + 1
            
            # Trend
            sorted_analyses = sorted(manager_analyses, key=lambda x: x.analyzed_at)
            perf.trend = self._calculate_trend(sorted_analyses)
            
            performances.append(perf)
        
        # Reytinglash
        performances.sort(key=lambda x: x.average_score, reverse=True)
        for i, perf in enumerate(performances, 1):
            perf.rank = i
        
        return [p.to_dict() for p in performances]
    
    def _get_quality_distribution(self, analyses: List[ConversationAnalysis]) -> Dict[str, Any]:
        """Sifat taqsimoti."""
        categories = defaultdict(int)
        score_ranges = {
            "90-100": 0,
            "80-89": 0,
            "70-79": 0,
            "60-69": 0,
            "50-59": 0,
            "0-49": 0
        }
        
        for a in analyses:
            categories[a.category] += 1
            
            if a.overall_score >= 90:
                score_ranges["90-100"] += 1
            elif a.overall_score >= 80:
                score_ranges["80-89"] += 1
            elif a.overall_score >= 70:
                score_ranges["70-79"] += 1
            elif a.overall_score >= 60:
                score_ranges["60-69"] += 1
            elif a.overall_score >= 50:
                score_ranges["50-59"] += 1
            else:
                score_ranges["0-49"] += 1
        
        return {
            "by_category": dict(categories),
            "by_score_range": score_ranges
        }
    
    def _get_outcome_analysis(self, analyses: List[ConversationAnalysis]) -> Dict[str, Any]:
        """Natija tahlili."""
        outcomes = defaultdict(lambda: {"count": 0, "avg_score": 0.0, "total_duration": 0.0})
        
        for a in analyses:
            outcomes[a.outcome]["count"] += 1
            outcomes[a.outcome]["avg_score"] += a.overall_score
            outcomes[a.outcome]["total_duration"] += a.duration_seconds
        
        # O'rtacha ball hisoblash
        for outcome in outcomes:
            count = outcomes[outcome]["count"]
            if count > 0:
                outcomes[outcome]["avg_score"] = round(outcomes[outcome]["avg_score"] / count, 1)
                outcomes[outcome]["avg_duration_min"] = round(outcomes[outcome]["total_duration"] / count / 60, 1)
        
        return dict(outcomes)
    
    def _get_objection_analysis(self, analyses: List[ConversationAnalysis]) -> Dict[str, Any]:
        """E'tirozlar tahlili."""
        all_objections = []
        objection_success = defaultdict(lambda: {"total": 0, "converted": 0})
        
        for a in analyses:
            for obj in a.objections_raised:
                all_objections.append(obj)
                objection_success[obj]["total"] += 1
                if a.outcome == "sale":
                    objection_success[obj]["converted"] += 1
        
        # Eng ko'p uchraydigan e'tirozlar
        from collections import Counter
        common_objections = Counter(all_objections).most_common(10)
        
        # Konversiya stavkasi bo'yicha
        objection_rates = []
        for obj, stats in objection_success.items():
            rate = stats["converted"] / stats["total"] * 100 if stats["total"] > 0 else 0
            objection_rates.append({
                "objection": obj,
                "count": stats["total"],
                "conversion_rate": round(rate, 1)
            })
        
        objection_rates.sort(key=lambda x: x["conversion_rate"], reverse=True)
        
        return {
            "total_objections": len(all_objections),
            "unique_objections": len(set(all_objections)),
            "most_common": [{"objection": obj, "count": count} for obj, count in common_objections],
            "by_success_rate": objection_rates[:10]
        }
    
    def _analyze_lost_clients(self, analyses: List[ConversationAnalysis]) -> Dict[str, Any]:
        """Yo'qotilgan mijozlar tahlili."""
        lost_analyses = [a for a in analyses if a.outcome == "lost"]
        
        if not lost_analyses:
            return {"total_lost": 0, "reasons": {}, "preventable_count": 0}
        
        analysis = LostClientAnalysis(total_lost=len(lost_analyses))
        
        # Sabablar (zaif tomonlardan kelib chiqib)
        for a in lost_analyses:
            for weakness in a.weaknesses:
                analysis.reasons[weakness] = analysis.reasons.get(weakness, 0) + 1
        
        # O'rtacha ball
        analysis.avg_score_before_lost = sum(a.overall_score for a in lost_analyses) / len(lost_analyses)
        
        # Oldini olish mumkinmi?
        # Agar ball 60-80 orasida bo'lsa, yaxshi sotuv bilan ushlab qolish mumkin
        analysis.preventable_count = len([
            a for a in lost_analyses 
            if 60 <= a.overall_score <= 80
        ])
        
        # Tavsiyalar
        if analysis.reasons:
            top_reason = max(analysis.reasons.items(), key=lambda x: x[1])
            analysis.recommendations.append(
                f"Eng katta yo'qotish sababi: '{top_reason[0]}'. Bu yo'nalishda training o'tkazish kerak."
            )
        
        if analysis.preventable_count > 0:
            analysis.recommendations.append(
                f"{analysis.preventable_count} ta mijozni sifatli sotuv bilan ushlab qolish mumkin edi."
            )
        
        return analysis.to_dict()
    
    def _get_time_analysis(self, analyses: List[ConversationAnalysis]) -> Dict[str, Any]:
        """Vaqt tahlili."""
        # Soat bo'yicha
        hourly_distribution = defaultdict(int)
        for a in analyses:
            hour = a.analyzed_at.hour
            hourly_distribution[hour] += 1
        
        # Eng faol soat
        peak_hour = max(hourly_distribution.items(), key=lambda x: x[1])[0] if hourly_distribution else None
        
        # Davomiylik bo'yicha
        durations = [a.duration_seconds / 60 for a in analyses]  # Daqiqa
        
        return {
            "peak_hour": peak_hour,
            "hourly_distribution": dict(hourly_distribution),
            "avg_duration_min": round(sum(durations) / len(durations), 1) if durations else 0,
            "min_duration_min": round(min(durations), 1) if durations else 0,
            "max_duration_min": round(max(durations), 1) if durations else 0
        }
    
    def _generate_recommendations(self, analyses: List[ConversationAnalysis]) -> List[str]:
        """Umumiy tavsiyalar."""
        recommendations = []
        
        if not analyses:
            return recommendations
        
        # O'rtacha ball past bo'lsa
        avg_score = sum(a.overall_score for a in analyses) / len(analyses)
        if avg_score < 70:
            recommendations.append(
                f"📉 O'rtacha sifat balli past ({avg_score:.1f}). Jamoa sotuv mahoratini oshirish kerak."
            )
        
        # Yo'qotishlar ko'p bo'lsa
        lost_rate = len([a for a in analyses if a.outcome == "lost"]) / len(analyses) * 100
        if lost_rate > 30:
            recommendations.append(
                f"⚠️ Yo'qotish stavkasi yuqori ({lost_rate:.1f}%). Mijoz ushlab qolish strategiyasi ishlab chiqilishi kerak."
            )
        
        # Konversiya past bo'lsa
        conversion = len([a for a in analyses if a.outcome == "sale"]) / len(analyses) * 100
        if conversion < 20:
            recommendations.append(
                f"🎯 Konversiya stavkasi past ({conversion:.1f}%). Yopish texnikalarini takomillashtirish kerak."
            )
        
        # E'tirozlar bilan ishlash
        objections = []
        for a in analyses:
            objections.extend(a.objections_raised)
        
        if len(objections) > len(analyses) * 0.5:
            recommendations.append(
                "🛡️ Ko'p e'tirozlar qo'yilmoqda. E'tirozlarni yengish bo'yicha training o'tkazish kerak."
            )
        
        return recommendations
    
    def _get_skill_breakdown(
        self,
        analyses: List[ConversationAnalysis]
    ) -> Dict[str, Any]:
        """Manager mahorat tahlili."""
        skill_scores = defaultdict(list)
        
        for a in analyses:
            for score in a.scores:
                skill_scores[score.metric.value].append(score.score)
        
        return {
            skill: {
                "average": round(sum(scores) / len(scores), 1),
                "best": max(scores),
                "worst": min(scores)
            }
            for skill, scores in skill_scores.items()
        }
    
    def _get_progress_over_time(
        self,
        analyses: List[ConversationAnalysis]
    ) -> List[Dict[str, Any]]:
        """Vaqt bo'yicha progress."""
        sorted_analyses = sorted(analyses, key=lambda x: x.analyzed_at)
        
        # Haftalik o'rtacha
        weekly = defaultdict(list)
        for a in sorted_analyses:
            week_key = a.analyzed_at.strftime("%Y-W%W")
            weekly[week_key].append(a.overall_score)
        
        return [
            {
                "period": week,
                "average_score": round(sum(scores) / len(scores), 1),
                "calls": len(scores)
            }
            for week, scores in sorted(weekly.items())
        ]
    
    def _get_top_strengths(self, analyses: List[ConversationAnalysis]) -> List[str]:
        """Kuchli tomonlar."""
        all_strengths = []
        for a in analyses:
            all_strengths.extend(a.strengths)
        
        from collections import Counter
        return [s for s, _ in Counter(all_strengths).most_common(5)]
    
    def _get_improvement_areas(self, analyses: List[ConversationAnalysis]) -> List[str]:
        """Takomillashtirish kerak joylar."""
        all_weaknesses = []
        for a in analyses:
            all_weaknesses.extend(a.weaknesses)
        
        from collections import Counter
        return [w for w, _ in Counter(all_weaknesses).most_common(5)]
    
    def _calculate_trend(self, analyses: List[ConversationAnalysis]) -> str:
        """Trend hisoblash."""
        if len(analyses) < 5:
            return "insufficient_data"
        
        # Birinchi va oxirgi 5 ta suhbatni taqqoslash
        first_5 = analyses[:5]
        last_5 = analyses[-5:]
        
        first_avg = sum(a.overall_score for a in first_5) / 5
        last_avg = sum(a.overall_score for a in last_5) / 5
        
        if last_avg > first_avg + 5:
            return "improving"
        elif last_avg < first_avg - 5:
            return "declining"
        else:
            return "stable"
    
    def _get_empty_dashboard(self) -> Dict[str, Any]:
        """Bo'sh dashboard."""
        return {
            "summary": {},
            "daily_stats": [],
            "manager_ratings": [],
            "quality_distribution": {},
            "outcome_analysis": {},
            "objection_analysis": {},
            "lost_clients": {},
            "time_analysis": {},
            "recommendations": [],
            "generated_at": datetime.now().isoformat()
        }
