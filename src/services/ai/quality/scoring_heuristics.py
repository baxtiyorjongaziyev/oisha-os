"""
Heuristic scoring, talk ratio computation, and conversation analysis assembly mixin.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from src.services.core.sales_playbook import (
    category_for_score,
)
from src.services.utils.transcript import speaker_split
from src.services.ai.quality.models import (
    ConversationAnalysis,
    QualityMetric,
    ScoreBreakdown,
    SCORING_METHOD_AI,
    SCORING_METHOD_HEURISTIC,
    OUTCOME_NOT_SALES,
    CATEGORY_NOT_SALES,
)

logger = logging.getLogger("QualityAnalyzer")


class ScoringHeuristicsMixin:
    """Handles rule-based calculations, metric breakdowns, and report assembly."""

    @staticmethod
    def _compute_talk_ratio(text: str) -> tuple[int, int]:
        """Back-compat: (client_pct, agent_pct) only. Rol aniqlanmasa (0, 0)."""
        client_pct, agent_pct, attributed = speaker_split(text)
        if not attributed:
            return 0, 0
        return client_pct, agent_pct

    def analyze_conversation(
        self,
        conversation_text: str,
        conversation_id: str,
        lead_id: Optional[int] = None,
        manager_id: Optional[int] = None,
        manager_name: str = "",
        duration_seconds: int = 0,
    ) -> ConversationAnalysis:
        """Suhbatni tahlil qilish va sifat ballari berish (heuristic)."""
        analysis = self._ai_analyze(conversation_text)
        return self._assemble(
            analysis,
            conversation_text,
            conversation_id=conversation_id,
            lead_id=lead_id,
            manager_id=manager_id,
            manager_name=manager_name,
            duration_seconds=duration_seconds,
            scoring_method=SCORING_METHOD_HEURISTIC,
        )

    async def analyze_conversation_ai(
        self,
        conversation_text: str,
        conversation_id: str,
        lead_id: Optional[int] = None,
        manager_id: Optional[int] = None,
        manager_name: str = "",
        duration_seconds: int = 0,
    ) -> ConversationAnalysis:
        """Suhbatni haqiqiy LLM (Gemini) bilan baholaydi."""
        analysis = await self._llm_analyze(conversation_text)
        if analysis is None:
            analysis = self._ai_analyze(conversation_text)
            scoring_method = SCORING_METHOD_HEURISTIC
        else:
            scoring_method = SCORING_METHOD_AI

        return self._assemble(
            analysis,
            conversation_text,
            conversation_id=conversation_id,
            lead_id=lead_id,
            manager_id=manager_id,
            manager_name=manager_name,
            duration_seconds=duration_seconds,
            scoring_method=scoring_method,
        )

    def _assemble(
        self,
        analysis: Dict[str, Any],
        conversation_text: str,
        *,
        conversation_id: str,
        lead_id: Optional[int],
        manager_id: Optional[int],
        manager_name: str,
        duration_seconds: int,
        scoring_method: str,
    ) -> ConversationAnalysis:
        """Xom tahlil dict'idan yakuniy `ConversationAnalysis` quradi.

        Evristika ham, LLM ham shu yerdan o'tadi — ballash qoidalari
        (og'irliklar, talk_ratio, kategoriya) bitta joyda turadi.
        """
        try:
            # Gapirish nisbatini hisoblash (transcript dan)
            client_pct, agent_pct, attributed = speaker_split(conversation_text)

            # talk_ratio ballini hisoblash: mijoz ≥55% → 100, 40-55% → 65, <40% → 30.
            # Rol aniqlanmasa (rolsiz "A:/B:" yorliqlar) — ball qo'ymaymiz.
            # Ilgari bunda 30 ball qo'yilar edi, ya'ni transkripsiya formati
            # uchun menejer jazolanardi.
            skip_metrics: set = set()
            is_sales_call = str(analysis.get("outcome") or "") != OUTCOME_NOT_SALES

            if attributed and is_sales_call:
                if client_pct >= 55:
                    talk_ratio_score = 100
                elif client_pct >= 40:
                    talk_ratio_score = 65
                else:
                    talk_ratio_score = 30
                analysis.setdefault("metric_scores", {})["talk_ratio"] = talk_ratio_score
            else:
                if not attributed:
                    client_pct = agent_pct = 0
                skip_metrics.add(QualityMetric.TALK_RATIO)

            if not is_sales_call:
                # Shaxsiy/xizmat/tasodifiy qo'ng'iroq — savdo rubrikasi
                # qo'llanmaydi. Ilgari gapirish nisbati baribir 30-100 ball
                # berib, noldan katta umumiy ball hosil qilardi va menejer
                # reytingiga qo'shilardi.
                return ConversationAnalysis(
                    conversation_id=conversation_id,
                    lead_id=lead_id,
                    manager_id=manager_id,
                    manager_name=manager_name,
                    duration_seconds=duration_seconds,
                    overall_score=0,
                    category=CATEGORY_NOT_SALES,
                    scores=[],
                    summary=analysis.get("summary", ""),
                    talk_ratio_client=client_pct,
                    talk_ratio_agent=agent_pct,
                    client_mood=analysis.get("client_mood", "neutral"),
                    outcome=OUTCOME_NOT_SALES,
                    recommended_tasks=[],
                    scoring_method=scoring_method,
                )

            # Ballar hisoblash
            scores = self._calculate_scores(analysis, skip_metrics=skip_metrics)

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
                talk_ratio_client=client_pct,
                talk_ratio_agent=agent_pct,
                client_mood=analysis.get("client_mood", "neutral"),
                client_interest_level=analysis.get("client_interest_level", 50),
                objections_raised=analysis.get("objections", []),
                outcome=analysis.get("outcome", "unknown"),
                next_steps=analysis.get("next_steps", []),
                recommended_tasks=recommended_tasks,
                scoring_method=scoring_method,
            )

        except Exception as e:
            logger.error(f"[QUALITY ANALYZER] Tahlil xatosi: {e}")
            # Xatolik bo'lsa default qiymatlar
            return self._create_fallback_analysis(
                conversation_id, lead_id, manager_id, manager_name, duration_seconds
            )

    def _calculate_scores(
        self,
        analysis: Dict[str, Any],
        skip_metrics: Optional[set] = None,
    ) -> List[ScoreBreakdown]:
        """Har bir metric bo'yicha ball hisoblash.

        `skip_metrics` — baholab bo'lmaydigan metriklar (masalan, transkripsiyada
        rollar yo'q bo'lsa talk_ratio). Ular ro'yxatga umuman kirmaydi, shuning
        uchun umumiy ballni pastga tortmaydi.
        """
        scores = []
        metric_scores = analysis.get("metric_scores", {})
        skip = skip_metrics or set()

        for metric, weight in self.weights.items():
            if metric in skip:
                continue
            score = metric_scores.get(metric.value, 50)  # Default 50

            # Feedback va tavsiyalar
            feedback = self._get_feedback_for_metric(metric, score)
            tips = self._get_improvement_tips(metric, score)

            scores.append(
                ScoreBreakdown(
                    metric=metric,
                    score=score,
                    weight=weight,
                    feedback=feedback,
                    improvement_tips=tips,
                )
            )

        return scores

    def _calculate_overall_score(self, scores: List[ScoreBreakdown]) -> int:
        """Og'irliklar bilan umumiy ball hisoblash."""
        if not scores:
            return 0

        # Og'irliklar yig'indisi bo'yicha normallashtiramiz — metrik chetlab
        # o'tilganda (skip_metrics) qolganlari to'liq 100 balllik shkalada
        # qoladi, aks holda ball sun'iy ravishda pasayardi.
        total_weight = sum(s.weight for s in scores)
        if total_weight <= 0:
            return 0
        weighted_sum = sum(s.score * s.weight for s in scores)
        return int(weighted_sum / total_weight)

    def _get_category(self, score: int) -> str:
        """Ball asosida rasmiy playbook toifasi."""
        return category_for_score(score)
