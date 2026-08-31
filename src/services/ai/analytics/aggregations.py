"""
Aggregation, slicing and calculation mixin for CallAnalytics.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.services.ai.analytics.models import DailyStats, LostClientAnalysis, ManagerPerformance
from src.services.ai.quality_analyzer import ConversationAnalysis


class CallAnalyticsAggregationsMixin:
    """Aggregations, summary statistics, ratings, and distributions."""

    def _filter_by_date(
        self,
        analyses: List[ConversationAnalysis],
        start_date: Optional[str],
        end_date: Optional[str],
    ) -> List[ConversationAnalysis]:
        if not start_date and not end_date:
            return analyses

        filtered = []
        for a in analyses:
            created = a.created_at if hasattr(a, "created_at") else datetime.now().isoformat()
            date_str = created[:10]
            if start_date and date_str < start_date:
                continue
            if end_date and date_str > end_date:
                continue
            filtered.append(a)
        return filtered

    def _get_summary_stats(self, analyses: List[ConversationAnalysis]) -> Dict[str, Any]:
        if not analyses:
            return {}

        total = len(analyses)
        scores = [a.overall_score for a in analyses]
        sales = sum(1 for a in analyses if a.deal_outcome.value == "won")
        lost = sum(1 for a in analyses if a.deal_outcome.value == "lost")
        follow_up = sum(
            1
            for a in analyses
            if a.deal_outcome.value in ["follow_up_needed", "in_progress", "meeting_scheduled"]
        )

        return {
            "total_calls": total,
            "average_score": round(sum(scores) / total, 1),
            "min_score": min(scores),
            "max_score": max(scores),
            "sales_count": sales,
            "conversion_rate": round(sales / total * 100, 1) if total > 0 else 0,
            "follow_up_count": follow_up,
            "lost_count": lost,
            "high_quality_percentage": round(sum(1 for s in scores if s >= 80) / total * 100, 1),
            "low_quality_percentage": round(sum(1 for s in scores if s < 60) / total * 100, 1),
        }

    def _get_daily_stats(self, analyses: List[ConversationAnalysis]) -> List[Dict[str, Any]]:
        by_date: Dict[str, List[ConversationAnalysis]] = defaultdict(list)
        for a in analyses:
            created = a.created_at if hasattr(a, "created_at") else datetime.now().isoformat()
            by_date[created[:10]].append(a)

        result = []
        for date_str in sorted(by_date.keys()):
            day_analyses = by_date[date_str]
            scores = [a.overall_score for a in day_analyses]
            sales = sum(1 for a in day_analyses if a.deal_outcome.value == "won")
            follow_ups = sum(
                1
                for a in day_analyses
                if a.deal_outcome.value in ["follow_up_needed", "in_progress", "meeting_scheduled"]
            )
            lost = sum(1 for a in day_analyses if a.deal_outcome.value == "lost")

            stats = DailyStats(
                date=date_str,
                total_calls=len(day_analyses),
                analyzed_calls=len(day_analyses),
                average_score=sum(scores) / len(scores) if scores else 0,
                sales_made=sales,
                follow_ups=follow_ups,
                lost=lost,
            )
            result.append(stats.to_dict())

        return result

    def _get_manager_ratings(self, analyses: List[ConversationAnalysis]) -> List[Dict[str, Any]]:
        by_manager: Dict[str, List[ConversationAnalysis]] = defaultdict(list)
        for a in analyses:
            by_manager[a.manager_name].append(a)

        ratings = []
        for name, manager_analyses in by_manager.items():
            scores = [a.overall_score for a in manager_analyses]
            sales = sum(1 for a in manager_analyses if a.deal_outcome.value == "won")
            total = len(manager_analyses)

            skill_scores: Dict[str, List[float]] = defaultdict(list)
            for a in manager_analyses:
                for stage in a.stages:
                    skill_scores[stage.stage_name.value].append(stage.score)

            avg_skills = {k: sum(v) / len(v) for k, v in skill_scores.items()}
            perf = ManagerPerformance(
                manager_id=0,
                manager_name=name,
                total_calls=total,
                average_score=sum(scores) / total if scores else 0,
                sales_made=sales,
                conversion_rate=(sales / total * 100) if total > 0 else 0,
                skill_scores=avg_skills,
                strengths=self._get_top_strengths(manager_analyses),
                areas_for_improvement=self._get_improvement_areas(manager_analyses),
                trend=self._calculate_trend(manager_analyses),
            )
            ratings.append(perf.to_dict())

        return sorted(ratings, key=lambda x: x["average_score"], reverse=True)

    def _get_quality_distribution(self, analyses: List[ConversationAnalysis]) -> Dict[str, int]:
        distribution = {
            "excellent (90-100)": 0,
            "good (75-89)": 0,
            "average (60-74)": 0,
            "poor (40-59)": 0,
            "critical (<40)": 0,
        }
        for a in analyses:
            score = a.overall_score
            if score >= 90:
                distribution["excellent (90-100)"] += 1
            elif score >= 75:
                distribution["good (75-89)"] += 1
            elif score >= 60:
                distribution["average (60-74)"] += 1
            elif score >= 40:
                distribution["poor (40-59)"] += 1
            else:
                distribution["critical (<40)"] += 1
        return distribution

    def _get_outcome_analysis(self, analyses: List[ConversationAnalysis]) -> Dict[str, Any]:
        outcomes: Dict[str, int] = defaultdict(int)
        for a in analyses:
            outcomes[a.deal_outcome.value] += 1
        total = len(analyses)
        return {
            "counts": dict(outcomes),
            "percentages": {
                k: round(v / total * 100, 1) for k, v in outcomes.items()
            }
            if total > 0
            else {},
        }

    def _get_objection_analysis(self, analyses: List[ConversationAnalysis]) -> Dict[str, Any]:
        total_objections = 0
        handled_well = 0
        by_type: Dict[str, Dict[str, int]] = defaultdict(lambda: {"total": 0, "handled": 0})

        for a in analyses:
            for obj in a.objections_handled:
                total_objections += 1
                type_name = obj.objection_type.value
                by_type[type_name]["total"] += 1
                if obj.was_handled_well:
                    handled_well += 1
                    by_type[type_name]["handled"] += 1

        top_objections = []
        for type_name, counts in sorted(by_type.items(), key=lambda x: x[1]["total"], reverse=True):
            success_rate = (counts["handled"] / counts["total"] * 100) if counts["total"] > 0 else 0
            top_objections.append(
                {
                    "type": type_name,
                    "count": counts["total"],
                    "success_rate": round(success_rate, 1),
                }
            )

        return {
            "total_objections": total_objections,
            "overall_handling_rate": round(handled_well / total_objections * 100, 1)
            if total_objections > 0
            else 0,
            "top_objections": top_objections[:5],
        }

    def _analyze_lost_clients(self, analyses: List[ConversationAnalysis]) -> Dict[str, Any]:
        lost_analyses = [a for a in analyses if a.deal_outcome.value == "lost"]
        if not lost_analyses:
            return LostClientAnalysis().to_dict()

        reasons: Dict[str, int] = defaultdict(int)
        unhandled: Dict[str, int] = defaultdict(int)

        for a in lost_analyses:
            for w in a.key_weaknesses:
                reasons[w] += 1
            for obj in a.objections_handled:
                if not obj.was_handled_well:
                    unhandled[obj.objection_type.value] += 1

        preventable = sum(
            1 for a in lost_analyses if any(o.was_handled_well is False for o in a.objections_handled)
        )
        preventable_pct = (preventable / len(lost_analyses) * 100) if lost_analyses else 0

        recs = []
        if unhandled:
            top_unhandled = max(unhandled.items(), key=lambda x: x[1])[0]
            recs.append(f"'{top_unhandled}' e'tirozi bo'yicha skriptlarni kuchaytirish")
        if preventable_pct > 30:
            recs.append("Yo'qotilgan mijozlarning 30%+ qismi yaxshiroq e'tiroz ishlash bilan saqlanishi mumkin edi")

        return LostClientAnalysis(
            total_lost=len(lost_analyses),
            lost_reasons=dict(reasons),
            unhandled_objections=dict(unhandled),
            preventable_percentage=preventable_pct,
            recommendations=recs,
        ).to_dict()

    def _get_time_analysis(self, analyses: List[ConversationAnalysis]) -> Dict[str, Any]:
        by_hour: Dict[int, List[float]] = defaultdict(list)
        for a in analyses:
            created = a.created_at if hasattr(a, "created_at") else datetime.now().isoformat()
            try:
                dt = datetime.fromisoformat(created)
                by_hour[dt.hour].append(a.overall_score)
            except Exception:
                pass

        hourly = []
        for hour in range(9, 19):
            scores = by_hour.get(hour, [])
            hourly.append(
                {
                    "hour": f"{hour:02d}:00",
                    "call_count": len(scores),
                    "avg_score": round(sum(scores) / len(scores), 1) if scores else 0,
                }
            )

        best_hour = max(hourly, key=lambda x: x["avg_score"])["hour"] if hourly else "11:00"
        return {"hourly": hourly, "best_performing_hour": best_hour}

    def _generate_recommendations(self, analyses: List[ConversationAnalysis]) -> List[Dict[str, Any]]:
        recommendations = []
        if not analyses:
            return recommendations

        avg_score = sum(a.overall_score for a in analyses) / len(analyses)
        if avg_score < 70:
            recommendations.append(
                {
                    "type": "training",
                    "priority": "high",
                    "title": "Umumiy sifatni oshirish",
                    "description": f"O'rtacha sifat bali ({avg_score:.1f}) past. Asosiy e'tiborni bosqichma-bosqich skriptga qaratish kerak.",
                }
            )

        stage_scores: Dict[str, List[float]] = defaultdict(list)
        for a in analyses:
            for stage in a.stages:
                stage_scores[stage.stage_name.value].append(stage.score)

        for stage_name, scores in stage_scores.items():
            stage_avg = sum(scores) / len(scores)
            if stage_avg < 60:
                recommendations.append(
                    {
                        "type": "skill",
                        "priority": "high",
                        "title": f"'{stage_name}' bosqichini kuchaytirish",
                        "description": f"Ushbu bosqichda o'rtacha ball {stage_avg:.1f}/100. Qo'shimcha materiallar tayyorlash kerak.",
                    }
                )

        return recommendations

    def _get_skill_breakdown(self, analyses: List[ConversationAnalysis]) -> Dict[str, Any]:
        stage_scores: Dict[str, List[float]] = defaultdict(list)
        for a in analyses:
            for stage in a.stages:
                stage_scores[stage.stage_name.value].append(stage.score)
        return {
            k: {
                "score": round(sum(v) / len(v), 1),
                "count": len(v),
            }
            for k, v in stage_scores.items()
        }

    def _get_progress_over_time(self, analyses: List[ConversationAnalysis]) -> List[Dict[str, Any]]:
        by_date: Dict[str, List[float]] = defaultdict(list)
        for a in analyses:
            created = a.created_at if hasattr(a, "created_at") else datetime.now().isoformat()
            by_date[created[:10]].append(a.overall_score)
        return [
            {
                "date": d,
                "score": round(sum(scores) / len(scores), 1),
                "calls": len(scores),
            }
            for d, scores in sorted(by_date.items())
        ]

    def _get_top_strengths(self, analyses: List[ConversationAnalysis]) -> List[str]:
        strengths: Dict[str, int] = defaultdict(int)
        for a in analyses:
            for s in a.key_strengths:
                strengths[s] += 1
        return [k for k, v in sorted(strengths.items(), key=lambda x: x[1], reverse=True)[:3]]

    def _get_improvement_areas(self, analyses: List[ConversationAnalysis]) -> List[str]:
        weaknesses: Dict[str, int] = defaultdict(int)
        for a in analyses:
            for w in a.key_weaknesses:
                weaknesses[w] += 1
        return [k for k, v in sorted(weaknesses.items(), key=lambda x: x[1], reverse=True)[:3]]

    def _calculate_trend(self, analyses: List[ConversationAnalysis]) -> str:
        if len(analyses) < 4:
            return "insufficient_data"
        half = len(analyses) // 2
        first_half = analyses[:half]
        second_half = analyses[half:]
        avg1 = sum(a.overall_score for a in first_half) / len(first_half)
        avg2 = sum(a.overall_score for a in second_half) / len(second_half)
        diff = avg2 - avg1
        if diff > 5:
            return "improving"
        elif diff < -5:
            return "declining"
        return "stable"

    def _get_empty_dashboard(self) -> Dict[str, Any]:
        return {
            "summary": {
                "total_calls": 0,
                "average_score": 0,
                "conversion_rate": 0,
            },
            "daily_stats": [],
            "manager_ratings": [],
            "quality_distribution": {},
            "outcome_analysis": {},
            "objection_analysis": {},
            "lost_clients": {},
            "time_analysis": {},
            "recommendations": [],
        }
