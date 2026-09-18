"""Weak-stages aggregation for the Sifat nazorati (quality control) dashboard."""
from collections import defaultdict
from typing import Dict

from src.services.sales_quality.helpers import _safe_json_dict, _safe_json_list

# Playbook bosqich kalitlari (sales_playbook.STAGE_WEIGHTS bilan bir xil) ->
# foydalanuvchiga ko'rinadigan o'zbekcha nom. Yangi bosqich qo'shilsa
# sales_playbook.py va shu lug'at birga yangilanadi.
STAGE_LABELS: Dict[str, str] = {
    "salomlashish": "Salomlashish",
    "ehtiyojlar": "Ehtiyojlarni aniqlash",
    "qiymat": "Qiymat taqdimoti",
    "etirozlar": "E'tirozlar",
    "yakunlash": "Yakunlash",
    "muloqot_sifati": "Muloqot sifati",
}

_WEAK_STAGE_THRESHOLD = 60  # sales_playbook.SCORE_AVERAGE bilan bir xil


def _compute_weak_stages(records: list, limit: int = 4) -> list:
    """`call_analyses` qatorlaridagi `scores` dict'idan har bosqich bo'yicha
    o'rtacha ballni hisoblab, eng past `limit` tasini qaytaradi.

    records: har biri "scores" (JSON dict string yoki dict) va "weaknesses"
    (JSON list string yoki list) kalitlariga ega dict.
    """
    stage_scores: Dict[str, list] = defaultdict(list)
    stage_weak_examples: Dict[str, str] = {}

    for record in records:
        scores = _safe_json_dict(record.get("scores"))
        if not scores:
            continue
        weaknesses = _safe_json_list(record.get("weaknesses"))
        first_weakness = weaknesses[0] if weaknesses else ""

        for stage_key, score in scores.items():
            if (
                stage_key not in STAGE_LABELS
                or not isinstance(score, (int, float))
                or isinstance(score, bool)
            ):
                continue
            stage_scores[stage_key].append(float(score))
            if score < _WEAK_STAGE_THRESHOLD and stage_key not in stage_weak_examples:
                stage_weak_examples[stage_key] = first_weakness

    stages = []
    for stage_key, scores in stage_scores.items():
        rate = sum(scores) / len(scores)
        weak_count = sum(1 for s in scores if s < _WEAK_STAGE_THRESHOLD)
        stages.append({
            "stage_key": stage_key,
            "label": STAGE_LABELS[stage_key],
            "rate": round(rate, 1),
            "count": weak_count,
            "weak_example": stage_weak_examples.get(stage_key, ""),
        })

    stages.sort(key=lambda s: s["rate"])
    return stages[:limit]
