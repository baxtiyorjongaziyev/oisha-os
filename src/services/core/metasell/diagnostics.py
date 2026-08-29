"""
Seller diagnostic analysis, stage gaps, and lift projections.
"""
from __future__ import annotations

import json
import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional, Sequence

from src.services.core.call_events import CallEventLog, aggregate_volume, team_volume
from src.services.core.metasell_revenue import aggregate_revenue, format_money
from src.services.core.sales_playbook import (
    SCORE_GOOD,
    STAGE_METRICS,
    STAGE_WEIGHTS,
    normalise_outcome,
    outcome_converted,
)
from src.services.core.metasell.constants import (
    MIN_CALLS_FOR_DIAGNOSIS,
    MIN_CALLS_PER_GROUP,
    MIN_MEANINGFUL_GAP,
    STAGE_LABELS_UZ,
    STAGE_DRILLS_UZ,
)
from src.services.core.metasell.models import (
    StageGap,
    ConversionTrend,
    SellerDiagnosis,
    _row_get,
    _json_obj,
    _json_list,
    _mean,
)

logger = logging.getLogger(__name__)

def diagnose_seller(manager_name: str, rows: Sequence[Any]) -> SellerDiagnosis:
    """Bitta sotuvchining qo'ng'iroqlaridan o'sish nuqtasini topadi.

    Sof funksiya — DB'ga bormaydi, shuning uchun test qilish oson va
    hisoblash mantig'i so'rov mantig'idan ajratilgan.
    """
    scored = [r for r in rows if int(_row_get(r, "overall_score", 0) or 0) > 0]
    total = len(scored)
    converted = [r for r in scored if _is_converted(r)]
    not_converted = [r for r in scored if not _is_converted(r)]

    diagnosis = SellerDiagnosis(
        manager_name=manager_name,
        total_calls=total,
        converted_calls=len(converted),
        conversion_rate=(len(converted) / total * 100) if total else 0.0,
        avg_score=_mean([float(_row_get(r, "overall_score", 0) or 0) for r in scored]),
    )

    revenue = aggregate_revenue(scored).get(manager_name)
    if revenue is not None:
        diagnosis.revenue_won = revenue.revenue_won
        # "Xavf ostidagi pul" — yutqazilgan bitimlar summasi. Buni
        # "shu bosqich shuncha pul yo'qotdi" deb ATAMAYMIZ: sababiy
        # bog'liqlik isbotlanmagan, bu faqat xavf hajmi.
        diagnosis.revenue_at_risk = revenue.revenue_lost
        diagnosis.deals_won = revenue.deals_won
        diagnosis.deals_lost = revenue.deals_lost

    if total < MIN_CALLS_FOR_DIAGNOSIS:
        diagnosis.reason = (
            f"Ma'lumot yetarli emas: {total} ta baholangan qo'ng'iroq "
            f"(kerak: {MIN_CALLS_FOR_DIAGNOSIS}+)."
        )
        return diagnosis

    diagnosis.top_weaknesses = _most_common(scored, "weaknesses", top=3)
    diagnosis.top_objections = _most_common(scored, "objections", top=3)

    if len(converted) < MIN_CALLS_PER_GROUP or len(not_converted) < MIN_CALLS_PER_GROUP:
        # Solishtirish uchun ikkala guruh ham kerak. Bo'lmasa — eng past
        # bosqichni ko'rsatamiz, lekin buni "dalil" deb atamaymiz.
        diagnosis.growth_stage = _weakest_stage(scored)
        if diagnosis.growth_stage:
            diagnosis.reason = (
                "Konversiya solishtiruvi uchun namuna yetarli emas — "
                "o'sish nuqtasi eng past bosqich bo'yicha ko'rsatilgan."
            )
        else:
            diagnosis.reason = "Bosqich ballari topilmadi."
        return diagnosis

    gaps = _stage_gaps(converted, not_converted)
    meaningful = [g for g in gaps if g.gap >= MIN_MEANINGFUL_GAP]
    if not meaningful:
        diagnosis.reason = (
            "Konvertirlangan va konvertirlanmagan qo'ng'iroqlar orasida "
            "sezilarli bosqich farqi yo'q — muammo texnikada emas, "
            "lead sifati yoki qo'ng'iroq hajmida bo'lishi mumkin."
        )
        return diagnosis

    best = max(meaningful, key=lambda g: g.weighted_gap)
    diagnosis.growth_stage = best.stage
    diagnosis.growth_gap = best
    diagnosis.projected_lift = _projected_lift(best, diagnosis)
    diagnosis.reason = (
        f"Konvertirlangan qo'ng'iroqlarda '{best.label}' bo'yicha o'rtacha "
        f"{best.won_avg:.0f} ball, konvertirlanmaganlarida {best.lost_avg:.0f} — "
        f"farq {best.gap:.0f} ball."
    )
    return diagnosis


def _is_converted(row: Any) -> bool:
    """Qo'ng'iroq konversiyaga aylanganmi?

    `converted = 1` — ishonchli "ha". Lekin `0` ni ishonchli "yo'q" deb
    BO'LMAYDI: `call_analyses.converted` ustuni `DEFAULT 0` bilan
    yaratilgan va uni faqat `call_analyzer` to'ldiradi. Boshqa
    yozuvchilar (`ConversationEngine._save_analysis_to_db`,
    `/api/sales-quality/ingest-analysis`) bu ustunni umuman yozmaydi,
    ya'ni ularning `outcome = "sale"` qatorlari ham bazada `converted = 0`
    bo'lib turadi. Nolni yakuniy deb qabul qilsak, o'sha muvaffaqiyatli
    qo'ng'iroqlar konversiyaga kirmay qoladi va sotuvchi ko'rsatkichi
    asossiz pasayadi.

    Shuning uchun: 1 bo'lsa — ha; aks holda natijadan aniqlaymiz.
    `call_analyzer` uchun ikkala signal bir xil, demak xatti-harakat
    o'zgarmaydi.
    """
    try:
        if int(_row_get(row, "converted", 0) or 0):
            return True
    except (TypeError, ValueError):
        pass
    return outcome_converted(normalise_outcome(_row_get(row, "outcome", "")))


def _metric_list_to_stages(items: Sequence[Any]) -> Dict[str, float]:
    """Metrik ro'yxatini playbook bosqichlariga yig'adi.

    `ConversationEngine` va `/api/sales-quality/ingest-analysis` ballarni
    bosqich emas, MAYDA METRIK kesimida saqlaydi:
        [{"metric": "closing", "score": 80}, ...]
    Qaysi metrik qaysi bosqichga tegishli ekani `sales_playbook.STAGE_METRICS`
    da — baholashning yagona manbasida. Bir bosqichga bir nechta metrik
    tushsa, o'rtachasi olinadi.
    """
    by_metric: Dict[str, float] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(
            item.get("metric") or item.get("name") or item.get("key") or ""
        ).strip().lower()
        if not name:
            continue
        raw = item.get("score", item.get("ball", item.get("value")))
        try:
            by_metric[name] = float(raw)
        except (TypeError, ValueError):
            continue

    stages: Dict[str, float] = {}
    for stage, metrics in STAGE_METRICS.items():
        values = [by_metric[m] for m in metrics if m in by_metric]
        if values:
            stages[stage] = sum(values) / len(values)
    return stages


def _stage_scores(row: Any) -> Dict[str, float]:
    """Bosqich ballari — ikkala saqlash formatini ham tushunadi."""
    raw = _row_get(row, "scores", "")
    if isinstance(raw, str) and raw.strip():
        try:
            raw = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            raw = {}
    if isinstance(raw, list):
        return _metric_list_to_stages(raw)
    if not isinstance(raw, dict):
        return {}

    out: Dict[str, float] = {}
    for stage in STAGE_WEIGHTS:
        value = raw.get(stage)
        if isinstance(value, dict):
            value = value.get("ball")
        try:
            out[stage] = float(value)
        except (TypeError, ValueError):
            continue
    return out


def _stage_gaps(converted: Sequence[Any], not_converted: Sequence[Any]) -> List[StageGap]:
    won: Dict[str, List[float]] = defaultdict(list)
    lost: Dict[str, List[float]] = defaultdict(list)
    for row in converted:
        for stage, score in _stage_scores(row).items():
            won[stage].append(score)
    for row in not_converted:
        for stage, score in _stage_scores(row).items():
            lost[stage].append(score)

    gaps: List[StageGap] = []
    for stage, weight in STAGE_WEIGHTS.items():
        if not won[stage] or not lost[stage]:
            continue
        won_avg = _mean(won[stage])
        lost_avg = _mean(lost[stage])
        gap = won_avg - lost_avg
        gaps.append(
            StageGap(
                stage=stage,
                won_avg=won_avg,
                lost_avg=lost_avg,
                gap=gap,
                weighted_gap=gap * weight,
            )
        )
    return gaps


def _weakest_stage(rows: Sequence[Any]) -> Optional[str]:
    totals: Dict[str, List[float]] = defaultdict(list)
    for row in rows:
        for stage, score in _stage_scores(row).items():
            totals[stage].append(score)
    if not totals:
        return None
    # Og'irlikni hisobga olamiz: past ball og'ir bosqichda ko'proq zarar.
    return min(
        totals,
        key=lambda stage: _mean(totals[stage]) / STAGE_WEIGHTS.get(stage, 1.0),
    )


def _projected_lift(gap: StageGap, diagnosis: SellerDiagnosis) -> float:
    """Bosqich tuzatilsa konversiya qancha oshishi mumkinligi (ehtiyotkor baho).

    Bu KAFOLAT emas, mo'ljal. Mantiq: konvertirlanmagan qo'ng'iroqlar shu
    bosqichda konvertirlanganlar darajasiga chiqsa, ularning bir qismi
    konversiyaga aylanadi. Ataylab konservativ koeffitsiyent (0.5).
    """
    if diagnosis.total_calls <= 0:
        return 0.0
    not_converted_share = 100.0 - diagnosis.conversion_rate
    closable = min(gap.gap / 100.0, 1.0) * not_converted_share * 0.5
    return max(0.0, min(closable, not_converted_share))


def _most_common(rows: Sequence[Any], column: str, top: int = 3) -> List[str]:
    counts: Dict[str, int] = defaultdict(int)
    for row in rows:
        for item in _json_list(_row_get(row, column, "")):
            cleaned = item.strip()
            if cleaned:
                counts[cleaned] += 1
    return [item for item, _ in sorted(counts.items(), key=lambda kv: -kv[1])[:top]]
