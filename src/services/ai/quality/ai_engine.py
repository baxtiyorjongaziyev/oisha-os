"""
Gemini and LLM analytical scoring engine mixin.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from src.services.ai.quality.models import (
    _GEMINI_MODEL,
    _parse_llm_scores,
)
from src.services.ai.quality.prompts import _build_scoring_prompt

logger = logging.getLogger("QualityAnalyzer")


class AIEngineMixin:
    """Handles LLM calls and Gemini integration for quality analysis."""

    async def _llm_analyze(self, text: str) -> Optional[Dict[str, Any]]:
        """Gemini bilan baholash. Muvaffaqiyatsiz bo'lsa `None`."""
        text = (text or "").strip()
        if not text:
            return None

        client = self._get_gemini_client()
        if client is None:
            logger.info("[QUALITY ANALYZER] Gemini mavjud emas — evristikaga o'tildi")
            return None

        try:
            from google.genai import types

            from src.services.utils.gemini_fallback import (
                generate_content_with_fallback,
            )

            response, _model = await generate_content_with_fallback(
                client,
                primary_model=_GEMINI_MODEL,
                contents=_build_scoring_prompt(text),
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2,
                ),
                log_prefix="[QUALITY ANALYZER]",
            )
            raw = getattr(response, "text", "") or ""
            return _parse_llm_scores(raw)
        except Exception as exc:
            logger.warning("[QUALITY ANALYZER] LLM baholash muvaffaqiyatsiz: %s", exc)
            return None

    def _get_gemini_client(self) -> Optional[Any]:
        if self._gemini_client is not None:
            return self._gemini_client

        try:
            from src.settings import settings

            key = settings.GEMINI_API_KEY
            api_key = key.get_secret_value() if hasattr(key, "get_secret_value") else str(key or "")
        except Exception as exc:
            logger.warning("[QUALITY ANALYZER] GEMINI_API_KEY o'qilmadi: %s", exc)
            return None

        if not api_key:
            return None

        try:
            from google import genai

            self._gemini_client = genai.Client(api_key=api_key)
        except Exception as exc:
            logger.warning("[QUALITY ANALYZER] Gemini klient yaratilmadi: %s", exc)
            return None
        return self._gemini_client

    def _ai_analyze(self, text: str) -> Dict[str, Any]:
        """Evidence-based fallback scoring when an async LLM is unavailable."""
        lowered = (text or "").lower()

        def score(signals: tuple[str, ...], base: int = 35, step: int = 20) -> int:
            return min(100, base + step * sum(signal in lowered for signal in signals))

        metrics = {
            "introduction": score(("salom", "assalomu", "ismim", "jon branding")),
            "need_identification": score(("nima kerak", "maqsad", "ehtiyoj", "kim uchun", "auditoriya")),
            "value_proposition": score(("foyda", "natija", "qiymat", "yechim", "yordam beradi")),
            "objection_handling": score(("lekin", "tushunaman", "variant", "yechim", "narx")),
            "closing": score(("kelishdik", "shartnoma", "to'lov", "boshlaymiz", "tasdiqlang")),
            "follow_up": score(("qayta qo'ng'iroq", "yuboraman", "uchrashuv", "ertaga", "muddat")),
            "tone": score(("rahmat", "iltimos", "marhamat"), base=55, step=15),
            "active_listening": score(("tushundim", "demak", "to'g'rimi", "aniqlashtir")),
            "question_quality": min(100, 35 + min(lowered.count("?"), 4) * 15),
        }
        objections = [
            label
            for signal, label in (
                ("qimmat", "Narx qimmat"),
                ("o'ylab", "O'ylab ko'rish kerak"),
                ("vaqt", "Muddat bo'yicha e'tiroz"),
                ("kerak emas", "Hozir kerak emas"),
            )
            if signal in lowered
        ]
        outcome = "unknown"
        if any(signal in lowered for signal in ("to'lov qildim", "kelishdik", "boshlaymiz")):
            outcome = "sale"
        elif any(signal in lowered for signal in ("qayta qo'ng'iroq", "ertaga", "yuboraman")):
            outcome = "follow_up"
        elif any(signal in lowered for signal in ("kerak emas", "rad", "qiziq emas")):
            outcome = "lost"

        strengths = [
            metric.replace("_", " ")
            for metric, value in metrics.items()
            if value >= 70
        ]
        weaknesses = [
            metric.replace("_", " ")
            for metric, value in metrics.items()
            if value < 55
        ]
        return {
            "summary": (text or "").strip()[:350],
            "strengths": strengths,
            "weaknesses": weaknesses,
            "client_mood": "negative" if objections else "neutral",
            "client_interest_level": min(100, 35 + metrics["closing"] // 2),
            "objections": objections,
            "outcome": outcome,
            "next_steps": ["Aniq keyingi qadam va muddatni kelishish"] if outcome == "unknown" else [],
            "metric_scores": metrics,
        }
