"""Jon Branding micro-criteria checklist evaluator over real call_analyses rows.

Computes percentage adherence (0-100%) per sales-script micro-criterion and
splits results into verified strengths and weaknesses without fabricating data.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence

from src.services.core.metasell.diagnostics import _is_converted, _stage_scores
from src.services.core.metasell.models import _json_list, _mean, _row_get
from src.services.core.sales_playbook import MAX_ACCEPTABLE_PAUSE_SECONDS

STRENGTH_THRESHOLD_PCT = 65.0


@dataclass(frozen=True)
class CriterionSpec:
    """Metadata for a single Jon Branding playbook micro-criterion."""

    key: str
    title: str
    strength_desc: str
    weakness_desc: str


CRITERIA_SPECS: tuple[CriterionSpec, ...] = (
    CriterionSpec(
        key="active_listening",
        title="Faol tinglash va reaksiya",
        strength_desc="Mijozning gapini boʻlmasdan tinglaydi va fikrlariga mantiqiy javob qaytaradi.",
        weakness_desc="Mijoz gapini boʻlib qoʻyish yoki monologga oʻtib ketish holatlari kuzatilgan.",
    ),
    CriterionSpec(
        key="situation_discovery",
        title="Mijoz vaziyatini ochish",
        strength_desc="Suhbat boshida vaziyatni, mavjud muammo va maqsadlarni aniqlash uchun toʻgʻri savollar beradi.",
        weakness_desc="Biznes turi, maqsad va qaror qabul qiluvchini oxirigacha ochmasdan taklifga oʻtadi.",
    ),
    CriterionSpec(
        key="context_and_greeting",
        title="Murojaat sababi va kontekst",
        strength_desc="Mijozning qoldirgan arizasi yoki avvalgi qiziqishini aniq eslatib, suhbatga zamin yaratadi.",
        weakness_desc="Qoʻngʻiroq maqsadini boshida aniq aytmaydi yoki avvalgi suhbat kontekstini eslatmaydi.",
    ),
    CriterionSpec(
        key="trust_and_cases",
        title="Ishonch hosil qilish va keyslar",
        strength_desc="Kompaniya tajribasi va mos portfolio keyslarini keltirib, mijozdagi xavotirni samarali yopadi.",
        weakness_desc="Taklifni real keyslar va agentlik tajribasi bilan asoslamaydi yoki umumiy gapiradi.",
    ),
    CriterionSpec(
        key="price_fork_discipline",
        title="Narx vilkasi va toʻlov shartlari",
        strength_desc="Narxni faqat dan-gacha vilka usulida va bosqichma-bosqich toʻlov tartibi bilan tushuntiradi.",
        weakness_desc="Mijoz imkoniyatini aniqlamasdan bitta qatʼiy raqam aytadi yoki toʻlov shartlarini oʻtkazib yuboradi.",
    ),
    CriterionSpec(
        key="objection_depth",
        title="Eʼtirozlarni chuqur ochish",
        strength_desc="Mijoz ikkilanganda tub sababni oxirigacha aniqlab, aniq yechim va argument beradi.",
        weakness_desc="Mijoz «hozircha shart emas» yoki «oʻylab koʻraman» deganda tub sababni ochmay, suhbatni tez toʻxtatadi.",
    ),
    CriterionSpec(
        key="closing_confirmation",
        title="Suhbat yakunini tasdiqlash",
        strength_desc="Suhbat oxirida kelishilgan keyingi qadam va aniq muddatni xulosalab tasdiqlaydi.",
        weakness_desc="Suhbat oxirida kelishilgan shartlar va keyingi qadam muddatini takrorlamasdan, xulosasiz yakunlaydi.",
    ),
    CriterionSpec(
        key="tone_subordination",
        title="Muloqot ohangi (subordinatsiya)",
        strength_desc="Professional masofa va hurmat ohangini saqlaydi, keraksiz sukutlarsiz ravon gaplashadi.",
        weakness_desc="Baʼzi qoʻngʻiroqlarda norasmiy iboralar (subordinatsiya buzilishi) yoki uzoq sukut kuzatilgan.",
    ),
)


def _clamp(val: float) -> float:
    return max(0.0, min(100.0, float(val)))


def _extract_raw_metrics(row: Any) -> Dict[str, float]:
    raw = _row_get(row, "scores", "")
    if isinstance(raw, str) and raw.strip():
        try:
            raw = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {}
    metrics: Dict[str, float] = {}
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, Mapping):
                key = str(item.get("metric") or item.get("name") or item.get("key") or "").strip().lower()
                val = item.get("score", item.get("ball", item.get("value")))
                if key and isinstance(val, (int, float)):
                    metrics[key] = _clamp(val)
    elif isinstance(raw, Mapping):
        checklist = raw.get("checklist")
        if isinstance(checklist, Mapping):
            for key, val in checklist.items():
                if isinstance(val, (int, float)):
                    metrics[f"checklist:{key}"] = _clamp(val)
    return metrics


def _norm_apostrophes(value: str) -> str:
    return re.sub(r"[ʻʼ`'\u2018\u2019]", "ʻ", value.lower())


def _has_any(texts: Sequence[str], needles: Sequence[str]) -> bool:
    joined = _norm_apostrophes(" ".join(str(t) for t in texts if t))
    return any(_norm_apostrophes(n) in joined for n in needles)


def _score_closing_and_tone(
    stages: Dict[str, float],
    metrics: Dict[str, float],
    overall: float,
    weaknesses: Sequence[str],
    next_steps: str,
    pause: float,
    converted: bool,
) -> tuple[float, float]:
    comm = stages.get("muloqot_sifati", overall)
    closing = metrics.get("closing", stages.get("yakunlash", overall))
    if converted:
        closing = max(closing, 72.0)
    elif next_steps in ("", "N/A", "[]") or _has_any(
        weaknesses, ("yakun", "xulosasiz", "tasdiq", "keyingi qadam")
    ):
        closing = min(closing, 35.0)

    tone = metrics.get("tone", comm)
    if _has_any(weaknesses, ("norasmiy", "subordinatsiya", "masofa", "ohang", "qoʻpol")):
        tone -= 25.0
    if pause > MAX_ACCEPTABLE_PAUSE_SECONDS:
        tone -= 12.0
    return closing, tone


def _score_row_criteria(row: Any) -> Dict[str, float]:
    stages = _stage_scores(row)
    metrics = _extract_raw_metrics(row)
    overall = float(_row_get(row, "overall_score", 0) or 0)
    strengths = [str(x) for x in _json_list(_row_get(row, "strengths", ""))]
    weaknesses = [str(x) for x in _json_list(_row_get(row, "weaknesses", ""))]
    objections = [str(x) for x in _json_list(_row_get(row, "objections", ""))]
    duration = int(_row_get(row, "duration_seconds", 0) or 0)
    converted = _is_converted(row)

    listen = metrics.get("active_listening", stages.get("muloqot_sifati", overall))
    if _has_any(strengths, ("tingla", "boʻlma", "reaksiya")):
        listen += 8.0
    if _has_any(weaknesses, ("boʻlib", "tinglama", "koʻp gapir", "monolog")):
        listen -= 22.0

    discovery = metrics.get("need_identification", stages.get("ehtiyojlar", overall))
    if 0 < duration < 120:
        discovery -= 15.0

    val_prop = metrics.get("value_proposition", stages.get("qiymat", overall))
    trust = val_prop + (8.0 if _has_any(strengths, ("keys", "portfolio", "tajriba", "kafolat")) else 0.0)
    if _has_any(weaknesses, ("vaʼda", "yolgʻon", "yolgon")):
        trust -= 30.0

    price_fork = val_prop
    if _has_any(weaknesses, ("vilka", "bitta raqam", "qatʼiy raqam", "arzon", "toʻlov", "tolov", "bron")):
        price_fork = min(price_fork - 25.0, 35.0)

    obj_score = metrics.get("objection_handling", stages.get("etirozlar", overall))
    if objections and not converted and obj_score < 55.0:
        obj_score -= 10.0
    if _has_any(weaknesses, ("eʼtiroz", "etiroz", "hozircha shart emas", "ikkilan", "tub sabab")):
        obj_score -= 15.0

    closing, tone = _score_closing_and_tone(
        stages,
        metrics,
        overall,
        weaknesses,
        str(_row_get(row, "next_steps", "") or "").strip(),
        float(_row_get(row, "longest_pause_seconds", 0.0) or 0.0),
        converted,
    )
    computed = {
        "active_listening": listen,
        "situation_discovery": discovery,
        "context_and_greeting": metrics.get("introduction", stages.get("salomlashish", overall)),
        "trust_and_cases": trust,
        "price_fork_discipline": price_fork,
        "objection_depth": obj_score,
        "closing_confirmation": closing,
        "tone_subordination": tone,
    }
    return {
        k: _clamp(metrics.get(f"checklist:{k}", v)) for k, v in computed.items()
    }


def _filter_scored_rows(rows: Sequence[Any], manager_name: Optional[str]) -> List[Any]:
    target = (manager_name or "").strip().lower()
    out: List[Any] = []
    for row in rows:
        if int(_row_get(row, "overall_score", 0) or 0) <= 0:
            continue
        row_mgr = str(_row_get(row, "manager_name", "") or "").strip()
        if target and target not in row_mgr.lower():
            continue
        out.append(row)
    return out


def evaluate_manager_checklist(
    rows: Sequence[Any],
    *,
    manager_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Aggregate real micro-criteria percentages for a manager or team."""
    filtered = _filter_scored_rows(rows, manager_name)
    if not filtered:
        return {
            "available": False,
            "manager_name": manager_name or "Jamoa",
            "evaluated_calls": 0,
            "criteria": [],
            "strengths": [],
            "weaknesses": [],
        }

    target = (manager_name or "").strip()
    resolved_name = (
        str(_row_get(filtered[0], "manager_name", "") or "").strip()
        if target
        else "Jamoa"
    )
    per_key: Dict[str, List[float]] = {spec.key: [] for spec in CRITERIA_SPECS}
    for row in filtered:
        for key, val in _score_row_criteria(row).items():
            per_key[key].append(val)

    criteria = [
        {
            "key": spec.key,
            "title": spec.title,
            "pct": round(_mean(per_key[spec.key]), 1),
            "status": "strength" if round(_mean(per_key[spec.key]), 1) >= STRENGTH_THRESHOLD_PCT else "weakness",
            "description": (
                spec.strength_desc
                if round(_mean(per_key[spec.key]), 1) >= STRENGTH_THRESHOLD_PCT
                else spec.weakness_desc
            ),
            "evaluated_calls": len(per_key[spec.key]),
        }
        for spec in CRITERIA_SPECS
    ]
    return {
        "available": True,
        "manager_name": resolved_name,
        "evaluated_calls": len(filtered),
        "criteria": criteria,
        "strengths": sorted((c for c in criteria if c["pct"] >= STRENGTH_THRESHOLD_PCT), key=lambda c: -c["pct"]),
        "weaknesses": sorted((c for c in criteria if c["pct"] < STRENGTH_THRESHOLD_PCT), key=lambda c: c["pct"]),
    }
