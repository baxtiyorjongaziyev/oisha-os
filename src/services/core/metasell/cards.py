"""
Telegram card and team report formatting for MetaSell conversion engine.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Sequence

from src.services.core.metasell.constants import (
    MIN_ACCEPTABLE_ANSWER_RATE,
    MIN_CALLS_FOR_DIAGNOSIS,
    STAGE_DRILLS_UZ,
    STAGE_LABELS_UZ,
)
from src.services.core.metasell.models import ConversionTrend, SellerDiagnosis
from src.services.core.metasell_revenue import format_money
from src.services.core.sales_playbook import SCORE_GOOD


def build_seller_card(
    diagnosis: SellerDiagnosis, volume: Optional[Any] = None
) -> str:
    """Bitta sotuvchi uchun haftalik o'sish kartochkasi."""
    lines = [
        f"🎯 KONVERSIYA KARTOCHKASI — {diagnosis.manager_name}",
        "",
        f"Qo'ng'iroqlar: {diagnosis.total_calls} ta",
        f"Konversiya: {diagnosis.conversion_rate:.0f}% "
        f"({diagnosis.converted_calls} ta keyingi qadamga chiqdi)",
        f"O'rtacha ball: {diagnosis.avg_score:.0f}/100",
    ]

    if volume is not None and volume.total:
        answer_line = (
            f"Javob berish: {volume.answer_rate:.0f}% "
            f"({volume.missed} ta javobsiz / {volume.total} ta) · "
            f"o'rtacha {volume.avg_duration_label}"
        )
        if volume.answer_rate < MIN_ACCEPTABLE_ANSWER_RATE:
            answer_line = "📵 " + answer_line
        lines.append(answer_line)

    if diagnosis.deals_won or diagnosis.deals_lost:
        lines += [
            f"Yopilgan bitim: {diagnosis.deals_won} ta yutildi "
            f"({format_money(diagnosis.revenue_won)}), "
            f"{diagnosis.deals_lost} ta yutqazildi "
            f"({format_money(diagnosis.revenue_at_risk)})",
        ]

    if not diagnosis.has_diagnosis:
        lines += ["", f"ℹ️ {diagnosis.reason}"]
        return "\n".join(lines)

    stage_label = STAGE_LABELS_UZ.get(diagnosis.growth_stage, diagnosis.growth_stage)
    lines += [
        "",
        f"📌 SHU HAFTA BITTA VAZIFA: {stage_label}",
        "",
        f"Nega aynan shu: {diagnosis.reason}",
    ]

    drill = STAGE_DRILLS_UZ.get(diagnosis.growth_stage, "")
    if drill:
        lines += ["", f"Mashq: {drill}"]

    if diagnosis.projected_lift >= 1:
        target = [
            "",
            f"Mo'ljal: shu bosqich tuzatilsa konversiya ~"
            f"{diagnosis.projected_lift:.0f}% ga oshishi mumkin.",
        ]
        if diagnosis.revenue_at_risk > 0:
            target.append(
                f"Yutqazilgan bitimlar hajmi: "
                f"{format_money(diagnosis.revenue_at_risk)} — "
                "shu bosqich xavf ostidagi pulning asosiy sababi."
            )
        lines += target

    if diagnosis.top_weaknesses:
        lines += ["", "Takrorlanayotgan kamchiliklar:"]
        lines += [f"  • {item}" for item in diagnosis.top_weaknesses]

    if diagnosis.top_objections:
        lines += [
            "",
            "Eng ko'p uchragan e'tirozlar: "
            + ", ".join(diagnosis.top_objections),
        ]

    return "\n".join(lines)


def build_team_report(
    diagnoses: Sequence[SellerDiagnosis],
    trend: Optional[ConversionTrend] = None,
    volumes: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """Rahbariyat uchun jamoa konversiya hisoboti."""
    ranked = [d for d in diagnoses if d.total_calls >= MIN_CALLS_FOR_DIAGNOSIS]
    if not ranked:
        return None

    total_calls = sum(d.total_calls for d in ranked)
    total_converted = sum(d.converted_calls for d in ranked)
    team_rate = (total_converted / total_calls * 100) if total_calls else 0.0
    revenue_won = sum(d.revenue_won for d in ranked)
    revenue_at_risk = sum(d.revenue_at_risk for d in ranked)

    volumes = volumes or {}
    team_vol = volumes.get("__team__")

    lines = ["📊 JAMOA KONVERSIYASI (oxirgi 30 kun)", ""]
    if team_vol is not None and team_vol.total:
        def true_eff(conv: int, tot: int) -> float:
            return (conv / tot * 100) if tot > 0 else 0.0

        lines += [
            f"Qo'ng'iroqlar: {team_vol.total} ta  |  "
            f"Samarali: {team_vol.answered}  |  "
            f"O'tkazib yuborilgan: {team_vol.missed}",
            f"O'rtacha davomiylik: {team_vol.avg_duration_label}  |  "
            f"Javob berish: {team_vol.answer_rate:.0f}%",
            f"Umumiy samaradorlik: "
            f"{true_eff(total_converted, team_vol.total):.0f}% "
            f"(javobsizlar ham hisobda)",
        ]
    else:
        lines.append(f"Baholangan qo'ng'iroqlar: {total_calls} ta")
    lines.append(
        trend.headline()
        if trend is not None
        else f"Konversiya: {team_rate:.0f}% ({total_converted} ta)"
    )
    if revenue_won or revenue_at_risk:
        lines += [
            f"Yutilgan bitimlar: {format_money(revenue_won)}",
            f"Yutqazilgan bitimlar: {format_money(revenue_at_risk)}",
        ]
    lines += ["", "SOTUVCHILAR:"]

    for item in ranked:
        marker = "🟢" if item.conversion_rate >= team_rate else "🔴"
        lines.append(
            f"{marker} {item.manager_name}: {item.conversion_rate:.0f}% "
            f"konversiya · {item.avg_score:.0f} ball · {item.total_calls} qo'ng'iroq"
        )
        if item.has_diagnosis:
            stage_label = STAGE_LABELS_UZ.get(item.growth_stage, item.growth_stage)
            lines.append(f"    O'sish nuqtasi: {stage_label}")

    low_answer = [
        (name, vol)
        for name, vol in volumes.items()
        if name != "__team__"
        and vol.total >= 5
        and vol.answer_rate < MIN_ACCEPTABLE_ANSWER_RATE
    ]
    if low_answer:
        lines += [
            "",
            "📵 Javob berish foizi past (bu qo'ng'iroqlar ballarda ko'rinmaydi):",
        ]
        lines += [
            f"  • {name} — {vol.answer_rate:.0f}% "
            f"({vol.missed} ta javobsiz / {vol.total} ta)"
            for name, vol in sorted(low_answer, key=lambda item: item[1].answer_rate)
        ]

    paradox = [
        d
        for d in ranked
        if d.avg_score >= SCORE_GOOD and d.conversion_rate < team_rate
    ]
    if paradox:
        lines += [
            "",
            "⚠️ Ball yuqori, konversiya past (skript bajarilyapti, bitim yopilmayapti):",
        ]
        lines += [
            f"  • {d.manager_name} — {d.avg_score:.0f} ball, "
            f"{d.conversion_rate:.0f}% konversiya"
            for d in paradox
        ]

    return "\n".join(lines)
