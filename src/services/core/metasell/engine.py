"""
MetaSell Conversion Engine for aggregating scored calls, trends, and team reports.
"""
from __future__ import annotations

import asyncio
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
from src.services.utils.db_rows import fetch_rows
from src.services.core.metasell.constants import (
    MIN_CALLS_FOR_DIAGNOSIS,
    MIN_CALLS_PER_GROUP,
    MIN_MEANINGFUL_GAP,
    MIN_CALLS_FOR_TREND,
    MIN_ACCEPTABLE_ANSWER_RATE,
    STAGE_LABELS_UZ,
    STAGE_DRILLS_UZ,
    _ANALYSIS_COLUMNS,
    _SELECT_RECENT_SQL,
    _SELECT_WINDOW_SQL,
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
from src.services.core.metasell.diagnostics import (
    diagnose_seller,
    _is_converted,
    _metric_list_to_stages,
    _stage_scores,
    _stage_gaps,
    _weakest_stage,
    _projected_lift,
    _most_common,
)

logger = logging.getLogger(__name__)

class MetaSellConversionEngine:
    """`call_analyses` ustidan konversiya tahlili va sotuvchi kartochkalari."""

    def __init__(self, db: Any):
        self.db = db

    async def fetch_scored_calls(
        self, days: int = 30, offset_days: int = 0
    ) -> List[Dict[str, Any]]:
        """Baholangan savdo qo'ng'iroqlari.

        `offset_days` — oynani o'tmishga suradi. Trend uchun kerak:
        joriy davr `offset_days=0`, oldingi davr `offset_days=days`.
        """
        if self.db is None:
            return []
        window_start = int(days) + int(offset_days)
        try:
            if offset_days:
                return await fetch_rows(
                    self.db,
                    _SELECT_WINDOW_SQL,
                    [f"-{window_start} days", f"-{int(offset_days)} days"],
                )
            return await fetch_rows(
                self.db, _SELECT_RECENT_SQL, [f"-{int(days)} days"]
            )
        except Exception as exc:
            logger.error("[METASELL] Qo'ng'iroqlarni o'qib bo'lmadi: %s", exc)
            return []

    async def diagnose_all(self, days: int = 30) -> List[SellerDiagnosis]:
        rows = await self.fetch_scored_calls(days)
        return self.diagnose_rows(rows)

    @staticmethod
    def diagnose_rows(rows: Sequence[Any]) -> List[SellerDiagnosis]:
        """Sotuvchilar bo'yicha diagnoz — konversiya bo'yicha saflangan."""
        by_manager: Dict[str, List[Any]] = defaultdict(list)
        for row in rows:
            name = str(_row_get(row, "manager_name", "") or "").strip()
            if not name:
                # Menejeri noma'lum qo'ng'iroqni hech kimga yozib bo'lmaydi.
                continue
            by_manager[name].append(row)

        diagnoses = [
            diagnose_seller(name, items) for name, items in by_manager.items()
        ]
        return sorted(diagnoses, key=lambda d: d.conversion_rate, reverse=True)

    @staticmethod
    def build_trend(
        current: Sequence[Any], previous: Sequence[Any], days: int
    ) -> ConversionTrend:
        """Ikki davr konversiyasini solishtiradi (sof funksiya)."""

        def rate(rows: Sequence[Any]) -> float:
            scored = [r for r in rows if int(_row_get(r, "overall_score", 0) or 0) > 0]
            if not scored:
                return 0.0
            return sum(1 for r in scored if _is_converted(r)) / len(scored) * 100

        current_n = len([r for r in current if int(_row_get(r, "overall_score", 0) or 0) > 0])
        previous_n = len([r for r in previous if int(_row_get(r, "overall_score", 0) or 0) > 0])
        reliable = current_n >= MIN_CALLS_FOR_TREND and previous_n >= MIN_CALLS_FOR_TREND
        reason = ""
        if not reliable:
            reason = (
                f"solishtirish uchun har ikki davrda {MIN_CALLS_FOR_TREND}+ "
                f"qo'ng'iroq kerak (joriy: {current_n}, oldingi: {previous_n})"
            )
        return ConversionTrend(
            days=days,
            current_rate=rate(current),
            previous_rate=rate(previous),
            current_calls=current_n,
            previous_calls=previous_n,
            reliable=reliable,
            reason=reason,
        )

    async def conversion_trend(self, days: int = 30) -> ConversionTrend:
        """Joriy davrni oldingi shuncha kunlik davr bilan solishtiradi."""
        current = await self.fetch_scored_calls(days)
        previous = await self.fetch_scored_calls(days, offset_days=days)
        return self.build_trend(current, previous, days)

    @staticmethod
    def true_efficiency(converted_calls: int, all_calls_including_missed: int) -> float:
        """Umumiy samaradorlik — javobsiz qo'ng'iroqlarni ham hisobga oladi.

        `conversion_rate` faqat BAHOLANGAN qo'ng'iroqlar ustidan hisoblanadi,
        ya'ni ko'tarilmagan qo'ng'iroq unga umuman ta'sir qilmaydi. Bu esa
        telefon ko'tarmaydigan sotuvchini yaxshi ko'rsatadi. Umumiy
        samaradorlik shu teshikni yopadi: maxraj — JAMI qo'ng'iroqlar.
        """
        if all_calls_including_missed <= 0:
            return 0.0
        return converted_calls / all_calls_including_missed * 100

    async def team_summary(self, days: int = 30) -> Dict[str, Any]:
        """Jamoa bo'yicha konversiya manzarasi (dashboard uchun)."""
        rows = await self.fetch_scored_calls(days)
        previous = await self.fetch_scored_calls(days, offset_days=days)
        trend = self.build_trend(rows, previous, days)
        diagnoses = self.diagnose_rows(rows)
        scored = [r for r in rows if int(_row_get(r, "overall_score", 0) or 0) > 0]
        converted = [r for r in scored if _is_converted(r)]
        revenue = aggregate_revenue(scored)
        # Qo'ng'iroq hajmi alohida jadvaldan — javobsizlar bilan birga.
        events = await CallEventLog(self.db).fetch_recent(days)
        volume = team_volume(events)
        by_manager_volume = aggregate_volume(events)

        stage_focus: Dict[str, int] = defaultdict(int)
        for item in diagnoses:
            if item.growth_stage:
                stage_focus[item.growth_stage] += 1

        return {
            "days": days,
            "total_calls": len(scored),
            "converted_calls": len(converted),
            "conversion_rate": round(
                (len(converted) / len(scored) * 100) if scored else 0.0, 1
            ),
            "avg_score": round(
                _mean([float(_row_get(r, "overall_score", 0) or 0) for r in scored]), 1
            ),
            "trend": trend.to_dict(),
            "volume": {
                "total": volume.total,
                "answered": volume.answered,
                "missed": volume.missed,
                "answer_rate": round(volume.answer_rate, 1),
                "avg_duration": volume.avg_duration_label,
            },
            "true_efficiency": round(
                self.true_efficiency(len(converted), volume.total or len(scored)), 1
            ),
            "seller_volume": [v.to_dict() for v in by_manager_volume.values()],
            "revenue_won": round(sum(r.revenue_won for r in revenue.values())),
            "revenue_at_risk": round(sum(r.revenue_lost for r in revenue.values())),
            "revenue_open": round(sum(r.revenue_open for r in revenue.values())),
            "sellers": [d.to_dict() for d in diagnoses],
            "team_focus": [
                {
                    "stage": stage,
                    "label": STAGE_LABELS_UZ.get(stage, stage),
                    "sellers_affected": count,
                    "drill": STAGE_DRILLS_UZ.get(stage, ""),
                }
                for stage, count in sorted(stage_focus.items(), key=lambda kv: -kv[1])
            ],
            "has_data": bool(scored),
        }

    # ------------------------------------------------------------------
    # Telegram kartochkasi — sotuvchi o'qiydigan yakuniy mahsulot
    # ------------------------------------------------------------------

    @staticmethod
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
        self,
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
            lines += [
                f"Qo'ng'iroqlar: {team_vol.total} ta  |  "
                f"Samarali: {team_vol.answered}  |  "
                f"O'tkazib yuborilgan: {team_vol.missed}",
                f"O'rtacha davomiylik: {team_vol.avg_duration_label}  |  "
                f"Javob berish: {team_vol.answer_rate:.0f}%",
                f"Umumiy samaradorlik: "
                f"{self.true_efficiency(total_converted, team_vol.total):.0f}% "
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

        # Telefon ko'tarmayotganlar — ular sifat statistikasida KO'RINMAYDI,
        # chunki baholanmagan qo'ng'iroq ball olmaydi. Shuning uchun alohida.
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

        # Ballari yuqori, lekin konversiyasi past sotuvchilar — eng qimmat
        # signal: playbook'ni "bajaryapti", lekin bitim yopilmayapti.
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

    async def generate_seller_cards(self, days: int = 30) -> List[tuple[str, str]]:
        """Har bir sotuvchi uchun (ism, kartochka matni)."""
        diagnoses = await self.diagnose_all(days)
        volumes = await self.fetch_volumes(days)
        return [
            (d.manager_name, self.build_seller_card(d, volumes.get(d.manager_name)))
            for d in diagnoses
        ]

    async def fetch_volumes(self, days: int = 30) -> Dict[str, Any]:
        """Sotuvchi kesimida hajm + `__team__` kaliti ostida yig'indi."""
        events = await CallEventLog(self.db).fetch_recent(days)
        volumes: Dict[str, Any] = dict(aggregate_volume(events))
        volumes["__team__"] = team_volume(events)
        return volumes

    async def generate_team_report(self, days: int = 30) -> Optional[str]:
        diagnoses = await self.diagnose_all(days)
        trend = await self.conversion_trend(days)
        volumes = await self.fetch_volumes(days)
        return self.build_team_report(diagnoses, trend, volumes)
