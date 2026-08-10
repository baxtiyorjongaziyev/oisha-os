"""MetaSell konversiya dvigateli — ball emas, KONVERSIYA ustida ishlaydi.

NIMA UCHUN KERAK:
    `sales_quality_coach` sotuvchilarni o'rtacha BALL bo'yicha saflaydi.
    Lekin ball o'z-o'zidan pul keltirmaydi: menejer 85 ball olib ham
    uchrashuv kelisha olmasligi mumkin. Sotuvchi konversiyasini oshirish
    uchun javob berish kerak bo'lgan savol boshqacha:

        "Aynan QAYSI bosqich shu menejerda bitimni yo'qotmoqda?"

    Bu modul har bir sotuvchi uchun konvertirlangan va konvertirlanmagan
    qo'ng'iroqlarning bosqich ballarini SOLISHTIRADI. Eng katta farq
    ko'rsatgan bosqich — o'sish nuqtasi. Bu taxmin emas, sotuvchining
    o'z qo'ng'iroqlaridan olingan dalil.

METODOLOGIYA (ataylab sodda va shaffof — "qora quti" bo'lmasligi kerak):
    konversiya      = playbook `CONVERTING_OUTCOMES` bilan tugagan qo'ng'iroqlar ulushi
    bosqich_farqi   = o'rtacha_ball(konvertirlangan) - o'rtacha_ball(konvertirlanmagan)
    o'sish_nuqtasi  = eng katta musbat farqli bosqich (og'irlik hisobga olingan)

    Statistik ishonch past bo'lsa (namuna kam) — modul JIM TURADI va
    "ma'lumot yetarli emas" deb qaytaradi. Yolg'on ishonch bilan noto'g'ri
    maslahat berish — konversiyani pasaytiradi.

Guardrail: bu modul hech narsani AVTOMATIK o'zgartirmaydi. Playbook
(`sales_playbook.py`) faqat odam qo'li bilan o'zgaradi.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from src.services.core.sales_playbook import (
    SCORE_GOOD,
    STAGE_WEIGHTS,
    normalise_outcome,
    outcome_converted,
)
from src.services.utils.db_rows import fetch_rows

logger = logging.getLogger(__name__)

# Sotuvchi bo'yicha xulosa chiqarish uchun minimal namuna. Bundan kam
# bo'lsa — bitta omadli/omadsiz qo'ng'iroq butun tavsiyani buzadi.
MIN_CALLS_FOR_DIAGNOSIS = 6
MIN_CALLS_PER_GROUP = 2

# Bosqich ballari orasidagi farq shundan kichik bo'lsa — shovqin deb
# qaraladi, o'sish nuqtasi sifatida ko'rsatilmaydi.
MIN_MEANINGFUL_GAP = 5.0

STAGE_LABELS_UZ = {
    "salomlashish": "Salomlashish va tanishtirish",
    "ehtiyojlar": "Ehtiyojni aniqlash",
    "qiymat": "Qiymat taqdimoti",
    "etirozlar": "E'tirozlar bilan ishlash",
    "yakunlash": "Yakunlash va keyingi qadam",
    "muloqot_sifati": "Muloqot sifati",
}

# Har bosqich uchun aniq, bajarib bo'ladigan mashq. Umumiy "yaxshiroq
# ishlang" maslahati konversiyani oshirmaydi — aniq harakat oshiradi.
STAGE_DRILLS_UZ = {
    "salomlashish": (
        "Har qo'ng'iroqni bir xil boshlang: ism + 'Jon Branding' + qo'ng'iroq "
        "maqsadi. Shu uch elementni 10 ta qo'ng'iroqda og'zaki mashq qiling."
    ),
    "ehtiyojlar": (
        "Taklif aytishdan OLDIN kamida 4 ta ochiq savol bering: biznes turi, "
        "maqsad, muddat, qaror qabul qiluvchi. Savol bermay narx aytmang."
    ),
    "qiymat": (
        "Taklifni mijoz aytgan og'riqqa bog'lab ayting: 'Siz ... dedingiz — "
        "shuning uchun biz ...'. Narxni faqat vilka usulida ayting."
    ),
    "etirozlar": (
        "'Qimmat' va 'o'ylab ko'raman' uchun tayyor javobni yodlang. "
        "'O'ylab ko'raman' javobidan keyin ALBATTA aniq sana belgilang."
    ),
    "yakunlash": (
        "Hech bir qo'ng'iroqni keyingi qadamsiz tugatmang. Yakunda aniq "
        "taklif qiling: 'Kelasi seshanba soat 15:00 da uchrashamizmi?'"
    ),
    "muloqot_sifati": (
        "Mijozni bo'lmang. Har javobidan keyin 2 soniya kuting. Maqsad — "
        "mijoz suhbatning yarmidan ko'pini gapirsin."
    ),
}


def _row_get(row: Any, key: str, default: Any = None) -> Any:
    if isinstance(row, dict):
        value = row.get(key, default)
        return default if value is None else value
    value = getattr(row, key, default)
    return default if value is None else value


def _json_obj(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


def _json_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(v) for v in value]
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [str(v) for v in parsed]
        except (json.JSONDecodeError, TypeError):
            return []
    return []


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


@dataclass
class StageGap:
    """Bitta bosqich bo'yicha konvertirlangan/konvertirlanmagan farqi."""

    stage: str
    won_avg: float
    lost_avg: float
    gap: float
    weighted_gap: float

    @property
    def label(self) -> str:
        return STAGE_LABELS_UZ.get(self.stage, self.stage)


@dataclass
class SellerDiagnosis:
    """Bitta sotuvchining konversiya diagnozi."""

    manager_name: str
    total_calls: int
    converted_calls: int
    conversion_rate: float
    avg_score: float
    growth_stage: Optional[str] = None
    growth_gap: Optional[StageGap] = None
    top_weaknesses: List[str] = field(default_factory=list)
    top_objections: List[str] = field(default_factory=list)
    projected_lift: float = 0.0
    reason: str = ""

    @property
    def has_diagnosis(self) -> bool:
        return self.growth_stage is not None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "manager_name": self.manager_name,
            "total_calls": self.total_calls,
            "converted_calls": self.converted_calls,
            "conversion_rate": round(self.conversion_rate, 1),
            "avg_score": round(self.avg_score, 1),
            "growth_stage": self.growth_stage,
            "growth_stage_label": (
                STAGE_LABELS_UZ.get(self.growth_stage, "") if self.growth_stage else ""
            ),
            "growth_gap": round(self.growth_gap.gap, 1) if self.growth_gap else None,
            "drill": (
                STAGE_DRILLS_UZ.get(self.growth_stage, "") if self.growth_stage else ""
            ),
            "top_weaknesses": self.top_weaknesses,
            "top_objections": self.top_objections,
            "projected_lift": round(self.projected_lift, 1),
            "has_diagnosis": self.has_diagnosis,
            "reason": self.reason,
        }


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
    raw = _row_get(row, "converted", None)
    if raw not in (None, ""):
        try:
            return bool(int(raw))
        except (TypeError, ValueError):
            pass
    return outcome_converted(normalise_outcome(_row_get(row, "outcome", "")))


def _stage_scores(row: Any) -> Dict[str, float]:
    scores = _json_obj(_row_get(row, "scores", ""))
    out: Dict[str, float] = {}
    for stage in STAGE_WEIGHTS:
        value = scores.get(stage)
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


class MetaSellConversionEngine:
    """`call_analyses` ustidan konversiya tahlili va sotuvchi kartochkalari."""

    def __init__(self, db: Any):
        self.db = db

    async def fetch_scored_calls(self, days: int = 30) -> List[Dict[str, Any]]:
        """Oxirgi `days` kun ichidagi baholangan savdo qo'ng'iroqlari."""
        if self.db is None:
            return []
        try:
            return await fetch_rows(
                self.db,
                "SELECT manager_name, overall_score, scores, outcome, converted, "
                "weaknesses, strengths, objections, category, call_id, lead_id, "
                "duration_seconds, created_at "
                "FROM call_analyses "
                "WHERE overall_score > 0 AND created_at >= datetime('now', ?) "
                "ORDER BY created_at DESC",
                [f"-{int(days)} days"],
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

    async def team_summary(self, days: int = 30) -> Dict[str, Any]:
        """Jamoa bo'yicha konversiya manzarasi (dashboard uchun)."""
        rows = await self.fetch_scored_calls(days)
        diagnoses = self.diagnose_rows(rows)
        scored = [r for r in rows if int(_row_get(r, "overall_score", 0) or 0) > 0]
        converted = [r for r in scored if _is_converted(r)]

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
    def build_seller_card(diagnosis: SellerDiagnosis) -> str:
        """Bitta sotuvchi uchun haftalik o'sish kartochkasi."""
        lines = [
            f"🎯 KONVERSIYA KARTOCHKASI — {diagnosis.manager_name}",
            "",
            f"Qo'ng'iroqlar: {diagnosis.total_calls} ta",
            f"Konversiya: {diagnosis.conversion_rate:.0f}% "
            f"({diagnosis.converted_calls} ta keyingi qadamga chiqdi)",
            f"O'rtacha ball: {diagnosis.avg_score:.0f}/100",
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
            lines += [
                "",
                f"Mo'ljal: shu bosqich tuzatilsa konversiya ~"
                f"{diagnosis.projected_lift:.0f}% ga oshishi mumkin.",
            ]

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

    def build_team_report(self, diagnoses: Sequence[SellerDiagnosis]) -> Optional[str]:
        """Rahbariyat uchun jamoa konversiya hisoboti."""
        ranked = [d for d in diagnoses if d.total_calls >= MIN_CALLS_FOR_DIAGNOSIS]
        if not ranked:
            return None

        total_calls = sum(d.total_calls for d in ranked)
        total_converted = sum(d.converted_calls for d in ranked)
        team_rate = (total_converted / total_calls * 100) if total_calls else 0.0

        lines = [
            "📊 JAMOA KONVERSIYASI (oxirgi 30 kun)",
            "",
            f"Qo'ng'iroqlar: {total_calls} ta",
            f"Konversiya: {team_rate:.0f}% ({total_converted} ta)",
            "",
            "SOTUVCHILAR:",
        ]

        for item in ranked:
            marker = "🟢" if item.conversion_rate >= team_rate else "🔴"
            lines.append(
                f"{marker} {item.manager_name}: {item.conversion_rate:.0f}% "
                f"konversiya · {item.avg_score:.0f} ball · {item.total_calls} qo'ng'iroq"
            )
            if item.has_diagnosis:
                stage_label = STAGE_LABELS_UZ.get(item.growth_stage, item.growth_stage)
                lines.append(f"    O'sish nuqtasi: {stage_label}")

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
        return [(d.manager_name, self.build_seller_card(d)) for d in diagnoses]

    async def generate_team_report(self, days: int = 30) -> Optional[str]:
        diagnoses = await self.diagnose_all(days)
        return self.build_team_report(diagnoses)
