"""
Prompt construction and sales playbook criteria builders for Quality Analyzer.
"""
from __future__ import annotations

from src.services.core.sales_playbook import (
    rubric_prompt_uz,
)
from src.services.ai.quality.models import (
    _LLM_METRICS,
)

def _build_scoring_prompt(transcript: str) -> str:
    """Jon Branding rasmiy playbook'i bo'yicha baholash so'rovi."""
    metrics_spec = ",\n".join(f'    "{m}": <0-100>' for m in _LLM_METRICS)
    return (
        "Sen Jon Branding agentligining savdo sifati nazoratchisisan. "
        "Quyidagi telefon suhbatini RASMIY PLAYBOOK bo'yicha bahola.\n\n"
        f"{rubric_prompt_uz()}\n"
        "BAHOLANADIGAN METRIKLAR (har biri 0-100, yuqoridagi playbook mezonlari asosida):\n"
        "- introduction: 1-bosqich (salomlashish) bo'yicha\n"
        "- need_identification: 2-bosqich (ehtiyojlar) bo'yicha\n"
        "- value_proposition: 3-bosqich (qiymat, vilka narx, portfolio) bo'yicha\n"
        "- objection_handling: 4-bosqich (e'tirozlar) bo'yicha\n"
        "- closing: 5-bosqich (yakunlash — uchrashuv/KP/portfolio/to'lov) bo'yicha\n"
        "- follow_up: keyingi qadam uchun aniq muddat va mas'ul belgilandimi\n"
        "- tone: 6-bosqich — professional ohang, hurmat\n"
        "- active_listening: mijozni bo'lmasdan eshitdimi, tasdiqladimi\n"
        "- question_quality: savollar ochiq va maqsadlimi\n\n"
        "QOIDALAR:\n"
        "- Faqat transkripsiyada haqiqatan sodir bo'lgan narsani bahola. "
        "Taxmin qilma, to'qima.\n"
        "- Bosqich umuman sodir bo'lmagan bo'lsa — past ball qo'y va sababini yoz.\n"
        "- Suhbat savdoga aloqador bo'lmasa (shaxsiy, xizmat, tasodifiy qo'ng'iroq), "
        'barcha ballarni 0 qilib, "outcome" ni "not_sales" deb belgila.\n\n'
        "Javobni FAQAT quyidagi JSON ko'rinishida ber:\n"
        "{\n"
        '  "metric_scores": {\n'
        f"{metrics_spec}\n"
        "  },\n"
        '  "summary": "<2-3 gap xulosa>",\n'
        '  "strengths": ["<menejer nimani yaxshi qildi>"],\n'
        '  "weaknesses": ["<nimani o\'tkazib yubordi>"],\n'
        '  "client_mood": "positive|neutral|negative",\n'
        '  "client_interest_level": <0-100>,\n'
        '  "objections": ["<mijoz bildirgan e\'tiroz>"],\n'
        '  "outcome": "sale|follow_up|lost|callback|not_sales|unknown",\n'
        '  "next_steps": ["<aniq keyingi qadam>"]\n'
        "}\n\n"
        f"Transkripsiya:\n{transcript}"
    )
