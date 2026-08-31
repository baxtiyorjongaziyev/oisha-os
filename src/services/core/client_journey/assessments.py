"""Journey signals and assessment logic for projects and leads."""
from __future__ import annotations

import datetime
from typing import Any, Dict, Iterable, List, Optional
from zoneinfo import ZoneInfo

from src.services.core.airtable_sync import AirtableSync
from src.services.core.client_journey.models import JourneySignal, _safe_text, _to_number, _urgency_rank


def _humanize_owner_hint(raw: Any) -> str:
    if not raw:
        return "PM"
    if isinstance(raw, str):
        return raw.strip() or "PM"
    if isinstance(raw, list) and raw:
        first = raw[0]
        if isinstance(first, dict):
            return first.get("name") or first.get("email") or "PM"
        return str(first)
    if isinstance(raw, dict):
        return raw.get("name") or raw.get("email") or "PM"
    return "PM"


def _is_overdue(deadline_val: Any) -> bool:
    if not deadline_val:
        return False
    try:
        if isinstance(deadline_val, str):
            clean = deadline_val.strip()[:10]
            dl = datetime.datetime.strptime(clean, "%Y-%m-%d").date()
        elif isinstance(deadline_val, (datetime.date, datetime.datetime)):
            dl = deadline_val.date() if isinstance(deadline_val, datetime.datetime) else deadline_val
        else:
            return False
        return dl < datetime.datetime.now(ZoneInfo("Asia/Tashkent")).date()
    except Exception:
        return False


def _project_age_days(project: Dict[str, Any]) -> int:
    raw = project.get("createdTime") or project.get("created_time")
    if not raw:
        return 0
    try:
        dt = datetime.datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        now = datetime.datetime.now(ZoneInfo("Asia/Tashkent"))
        return max(0, (now.date() - dt.date()).days)
    except Exception:
        return 0


def _build_advocacy_signal(name: str, mgr: str, raw_mgr: Any, age: int, pid: Any) -> JourneySignal:
    return JourneySignal(
        department="pm", client_name=name, stage="Advocacy", urgency="medium", owner_hint=mgr,
        risk="Loyiha yopilgan, lekin tavsiyanoma va referral momenti sovib ketishi mumkin.",
        owner_action="48 soat ichida case permission, testimonial va referral so'rovini bitta oqimda yoping.",
        wow_action="Mijozga handoff xulosasi, foydalanish bo'yicha mini qo'llanma va keyingi growth g'oyasini yuboring.",
        proof_of_done="Testimonial so'rovi, referral savoli va handoff xabari yuborilgan bo'lsin.",
        meta={"project_id": pid, "age_days": age, "manager_ref": raw_mgr},
    )


def _build_kickoff_signal(name: str, mgr: str, raw_mgr: Any, age: int, overdue: bool, dl: Any, pid: Any) -> JourneySignal:
    return JourneySignal(
        department="pm", client_name=name, stage="Kickoff discipline", urgency="high" if overdue else "medium", owner_hint=mgr,
        risk="Boshlanish momenti cho'zilsa, mijozda servis sifati haqidagi ishonch pasayadi.",
        owner_action="Bugun boshlanish xulosasi, timeline va ownership xaritasini mijozga yuboring.",
        wow_action="Mijozga keyingi 7 kunlik aniq reja ko'rsatib, noaniqlikni yoping.",
        proof_of_done="Boshlanish xulosasi va timeline Telegram guruhida ko'rinishi kerak.",
        meta={"project_id": pid, "age_days": age, "deadline": dl, "manager_ref": raw_mgr},
    )


def _build_preview_signal(name: str, mgr: str, raw_mgr: Any, age: int, overdue: bool, dl: Any, pid: Any) -> JourneySignal:
    return JourneySignal(
        department="pm", client_name=name, stage="Preview excellence", urgency="high" if overdue else "medium", owner_hint=mgr,
        risk="Ijodiy bosqichdagi jimlik mijozda 'ishni qilishyaptimi?' degan xavotir uyg'otadi.",
        owner_action="Oraliq ko'rinish yuboring, feedback savollarini toraytiring va qayta topshirish muddatini bering.",
        wow_action="Faqat draft emas, qaror qabul qilishni osonlashtiradigan asos bilan chiqing.",
        proof_of_done="Oraliq ko'rinish, feedback savoli va qayta topshirish muddati yozilgan bo'lsin.",
        meta={"project_id": pid, "age_days": age, "deadline": dl, "manager_ref": raw_mgr},
    )


def _build_feedback_signal(name: str, mgr: str, raw_mgr: Any, age: int, dl: Any, pid: Any) -> JourneySignal:
    return JourneySignal(
        department="pm", client_name=name, stage="Feedback closure", urgency="high", owner_hint=mgr,
        risk="Feedback ochiq qolsa loyiha ham, mijoz hissiyati ham qotib qoladi.",
        owner_action="Feedbackni checklist ko'rinishida yoping va har band uchun mas'ul odam hamda muddat yozing.",
        wow_action="Mijozga 'nimani qabul qildik, nimani o'zgartiramiz' degan aniq yakuniy xabarni yuboring.",
        proof_of_done="Feedback jadvali va keyingi topshirish sanasi ko'rinishi kerak.",
        meta={"project_id": pid, "age_days": age, "deadline": dl, "manager_ref": raw_mgr},
    )


def _build_handoff_signal(name: str, mgr: str, raw_mgr: Any, age: int, dl: Any, pid: Any) -> JourneySignal:
    return JourneySignal(
        department="pm", client_name=name, stage="Handoff readiness", urgency="high", owner_hint=mgr,
        risk="Topshirish oldidan chalkashlik bo'lsa, butun servis taassuroti buziladi.",
        owner_action="Final paket, izoh, qo'llab-quvvatlash muddati va qabul checklistini oldindan tayyorlang.",
        wow_action="Topshirishni shunchaki 'tugadi' emas, 'siz endi bemalol ishlata olasiz' hissi bilan yoping.",
        proof_of_done="Final fayllar, izoh va qo'llab-quvvatlash muddati bitta xabarda jamlangan bo'lsin.",
        meta={"project_id": pid, "age_days": age, "deadline": dl, "manager_ref": raw_mgr},
    )


def _assess_stage_signal(name: str, stage: str, stage_norm: str, age: int, overdue: bool, mgr: str, raw_mgr: Any, dl: Any, pid: Any, paid: float, remaining: float) -> Optional[JourneySignal]:
    if stage in AirtableSync.DONE_STAGES:
        return _build_advocacy_signal(name, mgr, raw_mgr, age, pid) if (paid > 0 and remaining <= 0) else None
    if any(t in stage_norm for t in ("brief", "brif", "research", "strateg")) and (age >= 2 or overdue):
        return _build_kickoff_signal(name, mgr, raw_mgr, age, overdue, dl, pid)
    if any(t in stage_norm for t in ("design", "dizayn", "concept", "draft", "maket")) and (age >= 4 or overdue):
        return _build_preview_signal(name, mgr, raw_mgr, age, overdue, dl, pid)
    if any(t in stage_norm for t in ("review", "feedback", "approval", "tasdiq")) and (age >= 3 or overdue):
        return _build_feedback_signal(name, mgr, raw_mgr, age, dl, pid)
    if any(t in stage_norm for t in ("production", "dev", "fayl", "delivery", "topshir")) and (age >= 3 or overdue):
        return _build_handoff_signal(name, mgr, raw_mgr, age, dl, pid)
    return None


def assess_project_portfolio(projects: Iterable[Dict[str, Any]]) -> List[JourneySignal]:
    """Loyihalar portfelini skanlab, JourneySignal ro'yxatini qaytarish."""
    signals: List[JourneySignal] = []
    for project in projects:
        fields = project.get("fields", {})
        stage = _safe_text(AirtableSync._get_field(fields, "stage"), "")
        name = _safe_text(AirtableSync._get_field(fields, "project_name")) or _safe_text(fields.get("Loyiha ID") or fields.get("AmoCRM_ID") or project.get("id"), "Nomsiz loyiha")
        raw_mgr = AirtableSync._get_field(fields, "manager")
        mgr = _humanize_owner_hint(raw_mgr)
        payment_status = _safe_text(AirtableSync._get_field(fields, "payment_status"), "")
        paid = _to_number(AirtableSync._get_field(fields, "paid_usd"))
        remaining = _to_number(AirtableSync._get_field(fields, "remaining_usd"))
        age = _project_age_days(project)
        dl = AirtableSync._get_field(fields, "deadline")
        overdue = _is_overdue(dl)
        stage_norm = stage.lower()
        pid = project.get("id")

        stage_sig = _assess_stage_signal(name, stage, stage_norm, age, overdue, mgr, raw_mgr, dl, pid, paid, remaining)
        if stage_sig:
            signals.append(stage_sig)
            continue

        if payment_status and remaining > 0 and any(t in stage_norm for t in ("review", "delivery", "topshir", "done")):
            signals.append(JourneySignal(
                department="sales", client_name=name, stage="Payment hygiene", urgency="high", owner_hint="Sales/Finance",
                risk="Servis berilyapti, lekin to'lov qoldig'i ochiq qolgan.",
                owner_action="Mijozga qiymat xulosasi bilan birga to'lovni yopish va sana bo'yicha aniq follow-up qiling.",
                wow_action="To'lov eslatmasini sovuq billing emas, topshirilgan ishlar xulosasi bilan birga yuboring.",
                proof_of_done="To'lov sanasi yoki yopilish statusi CRM/Airtableda yangilangan bo'lsin.",
                meta={"project_id": pid, "remaining_usd": remaining, "payment_status": payment_status, "manager_ref": raw_mgr},
            ))

    signals.sort(key=lambda item: (_urgency_rank(item.urgency), item.department != "sales", -int(item.meta.get("age_days") or 0)))
    return signals


def assess_sales_pipeline(leads: Iterable[Dict[str, Any]]) -> List[JourneySignal]:
    """Sotuv voronkasini skanlab, JourneySignal ro'yxatini qaytarish."""
    signals: List[JourneySignal] = []
    now = datetime.datetime.now(ZoneInfo("Asia/Tashkent"))
    for lead in leads:
        name = _safe_text(lead.get("name"), "Lid")
        price = _to_number(lead.get("price"))
        idle_hours = 0
        updated_at = lead.get("updated_at")
        if updated_at:
            try:
                dt = datetime.datetime.fromtimestamp(float(updated_at), tz=datetime.timezone.utc).astimezone(ZoneInfo("Asia/Tashkent"))
                idle_hours = max(0, int((now - dt).total_seconds() // 3600))
            except Exception:
                idle_hours = 0
        manager = _humanize_owner_hint(lead.get("responsible_user_id") or "Sotuv")

        if price >= 5_000_000 and idle_hours >= 12:
            signals.append(
                JourneySignal(
                    department="sales",
                    client_name=name,
                    stage="VIP rescue",
                    urgency="critical" if idle_hours >= 24 else "high",
                    owner_hint=manager,
                    risk="Katta qiymatli lid harakatsiz turibdi, mijoz boshqa variantlarni ko'rib chiqishi mumkin.",
                    owner_action="30 daqiqa ichida shaxsiy audio/video yoki maxsus taklif bilan aloqaga chiqing.",
                    wow_action="Oddiy narx emas, mijoz biznesiga mos maxsus yechim loyihasini taqdim eting.",
                    proof_of_done="CRMda yangi vazifa va mijozga yuborilgan xabar ko'rinsin.",
                    meta={"lead_id": lead.get("id"), "price": price, "idle_hours": idle_hours},
                )
            )
        elif idle_hours >= 24:
            signals.append(
                JourneySignal(
                    department="sales",
                    client_name=name,
                    stage="Recovery follow-up",
                    urgency="high",
                    owner_hint=manager,
                    risk="Lid bilan aloqa uzildi, qiziqish so'nib bormoqda.",
                    owner_action="Bugun yangi qiymat beruvchi savol yoki case study bilan qayta bog'laning.",
                    wow_action="Mijoz sohasiga oid mini audit yoki foydali ma'lumot jo'nating.",
                    proof_of_done="CRMda follow-up statusi yangilansin.",
                    meta={"lead_id": lead.get("id"), "price": price, "idle_hours": idle_hours},
                )
            )
        elif idle_hours >= 2:
            signals.append(
                JourneySignal(
                    department="sales",
                    client_name=name,
                    stage="Speed-to-lead",
                    urgency="medium",
                    owner_hint=manager,
                    risk="Birinchi javob tezligi mijoz qaroriga bevosita ta'sir qiladi.",
                    owner_action="Lidga darhol birinchi samimiy xabar va qisqa brifing savolini yo'llang.",
                    wow_action="5 daqiqa ichida tezkor va professional javob bering.",
                    proof_of_done="Lid statusi 'Ko'rib chiqilmoqda'ga o'tsin.",
                    meta={"lead_id": lead.get("id"), "price": price, "idle_hours": idle_hours},
                )
            )

    signals.sort(key=lambda s: (_urgency_rank(s.urgency), -int(s.meta.get("idle_hours") or 0)))
    return signals
