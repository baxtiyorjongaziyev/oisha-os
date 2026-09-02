"""
Reporting and dashboard metrics mixin for ConversationEngine.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from src.services.ai.conversation.models import DashboardMetrics
from src.services.ai.quality_analyzer import ConversationAnalysis


class ConversationReportingMixin:
    """Reporting, aggregation, metrics and radar data calculation."""

    def get_dashboard_metrics(self, days: int = 7) -> DashboardMetrics:
        cutoff = datetime.now() - timedelta(days=days)
        today = datetime.now().date()

        filtered_analyses = [
            a
            for a in self.analyses.values()
            if hasattr(a, "analyzed_at")
            and (
                isinstance(a.analyzed_at, datetime)
                and a.analyzed_at >= cutoff
                or isinstance(a.analyzed_at, str)
                and datetime.fromisoformat(a.analyzed_at) >= cutoff
            )
        ]

        if not filtered_analyses:
            return DashboardMetrics()

        today_analyses = [
            a
            for a in filtered_analyses
            if (
                isinstance(a.analyzed_at, datetime)
                and a.analyzed_at.date() == today
                or isinstance(a.analyzed_at, str)
                and datetime.fromisoformat(a.analyzed_at).date() == today
            )
        ]

        today_scores = [a.overall_score for a in today_analyses]
        week_scores = [a.overall_score for a in filtered_analyses]

        sales = sum(
            1 for a in filtered_analyses if a.deal_outcome.value == "won"
        )
        lost = sum(
            1 for a in filtered_analyses if a.deal_outcome.value == "lost"
        )
        followup = sum(
            1
            for a in filtered_analyses
            if a.deal_outcome.value
            in ["follow_up_needed", "in_progress", "meeting_scheduled"]
        )

        total_concluded = sales + lost
        conversion = (sales / total_concluded * 100) if total_concluded > 0 else 0.0

        managers = set(a.manager_name for a in filtered_analyses)
        talk_time = sum(
            self.call_records[cid].duration_seconds
            for cid in self.call_records
            if cid in [a.call_id for a in filtered_analyses if hasattr(a, "call_id")]
        ) // 60

        objection_counts: Dict[str, int] = defaultdict(int)
        for a in filtered_analyses:
            for obj in a.objections_handled:
                objection_counts[obj.objection_type.value] += 1

        top_objections = [
            {"type": k, "count": v}
            for k, v in sorted(
                objection_counts.items(), key=lambda x: x[1], reverse=True
            )[:5]
        ]

        weak_areas = self._find_common_weak_areas(filtered_analyses)
        recommendations = self._generate_dashboard_recommendations(
            filtered_analyses, weak_areas
        )

        return DashboardMetrics(
            total_calls_today=len(today_analyses),
            total_calls_week=len(filtered_analyses),
            avg_score_today=sum(today_scores) / len(today_scores)
            if today_scores
            else 0.0,
            avg_score_week=sum(week_scores) / len(week_scores)
            if week_scores
            else 0.0,
            sales_count=sales,
            followup_count=followup,
            lost_count=lost,
            conversion_rate=conversion,
            active_managers=len(managers),
            total_talk_time=talk_time,
            top_objections=top_objections,
            weak_areas=weak_areas,
            recommendations=recommendations,
        )

    def _find_common_weak_areas(
        self, analyses: List[ConversationAnalysis]
    ) -> List[str]:
        stage_scores: Dict[str, List[float]] = defaultdict(list)
        for a in analyses:
            for stage in a.stages:
                stage_scores[stage.stage_name.value].append(stage.score)

        avg_stage_scores = {
            k: sum(v) / len(v) for k, v in stage_scores.items() if v
        }
        return [
            k
            for k, v in sorted(avg_stage_scores.items(), key=lambda x: x[1])
            if v < 60
        ][:3]

    def _generate_dashboard_recommendations(
        self, analyses: List[ConversationAnalysis], weak_areas: List[str]
    ) -> List[str]:
        recommendations = []
        if "objection_handling" in weak_areas:
            recommendations.append(
                "E'tirozlar bilan ishlash bo'yicha qo'shimcha trening o'tkazish tavsiya etiladi."
            )
        if "closing" in weak_areas:
            recommendations.append(
                "Bitimni yopish texnikalari bo'yicha skriptlarni yangilash kerak."
            )
        if "needs_discovery" in weak_areas:
            recommendations.append(
                "Mijoz ehtiyojlarini aniqlashda ochiq savollar berishni kuchaytirish lozim."
            )
        if len(analyses) > 0:
            avg_score = sum(a.overall_score for a in analyses) / len(analyses)
            if avg_score < 60:
                recommendations.append(
                    "Umumiy sifat past darajada. Skriptlarga rioya qilishni nazorat qilish zarur."
                )
            elif avg_score >= 80:
                recommendations.append(
                    "Jamoa yuqori natija ko'rsatmoqda. Yaxshi amaliyotlarni boshqalar bilan ulashing."
                )
        return recommendations

    def get_manager_comparison(self, days: int = 7) -> List[Dict[str, Any]]:
        cutoff = datetime.now() - timedelta(days=days)
        manager_data: Dict[str, List[ConversationAnalysis]] = defaultdict(list)

        for a in self.analyses.values():
            if (
                isinstance(a.analyzed_at, datetime)
                and a.analyzed_at >= cutoff
                or isinstance(a.analyzed_at, str)
                and datetime.fromisoformat(a.analyzed_at) >= cutoff
            ):
                manager_data[a.manager_name].append(a)

        result = []
        for manager, analyses in manager_data.items():
            scores = [a.overall_score for a in analyses]
            sales = sum(1 for a in analyses if a.deal_outcome.value == "won")
            result.append(
                {
                    "manager_name": manager,
                    "total_calls": len(analyses),
                    "avg_score": round(sum(scores) / len(scores), 1) if scores else 0,
                    "sales_count": sales,
                    "conversion_rate": round(sales / len(analyses) * 100, 1)
                    if analyses
                    else 0,
                }
            )

        return sorted(result, key=lambda x: x["avg_score"], reverse=True)

    def get_call_details(self, call_id: str) -> Optional[Dict[str, Any]]:
        analysis = self.analyses.get(call_id)
        record = self.call_records.get(call_id)

        if not analysis:
            return None

        return {
            "call_id": call_id,
            "record": record.__dict__ if record else None,
            "analysis": analysis.__dict__,
        }

    def get_trend_analysis(
        self, days: int = 30, interval: str = "daily"
    ) -> List[Dict[str, Any]]:
        cutoff = datetime.now() - timedelta(days=days)
        grouped_data: Dict[str, List[ConversationAnalysis]] = defaultdict(list)

        for a in self.analyses.values():
            dt = (
                a.analyzed_at
                if isinstance(a.analyzed_at, datetime)
                else datetime.fromisoformat(a.analyzed_at)
            )
            if dt >= cutoff:
                key = (
                    dt.strftime("%Y-%m-%d")
                    if interval == "daily"
                    else dt.strftime("%Y-W%W")
                )
                grouped_data[key].append(a)

        trend = []
        for date_key, analyses in sorted(grouped_data.items()):
            scores = [a.overall_score for a in analyses]
            trend.append(
                {
                    "period": date_key,
                    "call_count": len(analyses),
                    "avg_score": round(sum(scores) / len(scores), 1) if scores else 0,
                }
            )

        return trend

    def generate_daily_report(self) -> str:
        metrics = self.get_dashboard_metrics(days=1)
        report = f"""
*Kunlik Suhbatlar Tahlili Hisoboti*
📅 Sana: {datetime.now().strftime('%Y-%m-%d')}

📊 *Asosiy Ko'rsatkichlar:*
• Jami qo'ng'iroqlar: {metrics.total_calls_today}
• O'rtacha sifat bali: {metrics.avg_score_today:.1f}/100
• Sotuvlar: {metrics.sales_count}
• Qayta aloqa: {metrics.followup_count}
• Yo'qotilgan: {metrics.lost_count}

⚠️ *Asosiy E'tirozlar:*
"""
        for obj in metrics.top_objections[:3]:
            report += f"\n• {obj['type']}: {obj['count']} ta"

        if metrics.weak_areas:
            report += "\n\n🔍 *Rivojlantirish Kerak Bo'lgan Sohalar:*"
            for area in metrics.weak_areas:
                report += f"\n• {area}"

        return report.strip()

    def get_skills_radar_data(
        self, manager_name: Optional[str] = None
    ) -> Dict[str, float]:
        analyses = list(self.analyses.values())
        if manager_name:
            analyses = [a for a in analyses if a.manager_name == manager_name]

        if not analyses:
            return {}

        stage_totals: Dict[str, List[float]] = defaultdict(list)
        for a in analyses:
            for stage in a.stages:
                stage_totals[stage.stage_name.value].append(stage.score)

        return {
            k: round(sum(v) / len(v), 1)
            for k, v in stage_totals.items()
            if v
        }
