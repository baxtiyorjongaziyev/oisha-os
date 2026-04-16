from __future__ import annotations

import datetime
from dataclasses import dataclass
from html import escape
from typing import Any, Callable, Dict, Iterable, List, Optional

from src.services.core.airtable_sync import AirtableSync
from src.time_utils import get_local_now


@dataclass
class JourneySignal:
    department: str
    client_name: str
    stage: str
    urgency: str
    owner_hint: str
    risk: str
    owner_action: str
    wow_action: str
    proof_of_done: str
    meta: Dict[str, Any]


def _safe_text(value: Any, fallback: str = "Noma'lum") -> str:
    text = str(value).strip() if value is not None else ""
    return text or fallback


def _to_number(value: Any) -> float:
    if value in (None, "", False):
        return 0.0
    try:
        return float(str(value).replace(" ", "").replace(",", "."))
    except (TypeError, ValueError):
        return 0.0


def _lead_idle_hours(lead: Dict[str, Any], now_epoch: Optional[int] = None) -> int:
    now_ts = now_epoch or int(get_local_now().timestamp())
    updated_at = int(lead.get("updated_at") or 0)
    if updated_at <= 0:
        return 0
    return max(0, int((now_ts - updated_at) / 3600))


def _urgency_rank(level: str) -> int:
    return {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(level, 4)


def _project_age_days(project: Dict[str, Any]) -> int:
    fields = project.get("fields", {})
    start_raw = AirtableSync._get_field(fields, "start_date")
    if not start_raw:
        return 0

    try:
        created_dt = datetime.datetime.fromisoformat(str(start_raw).replace("Z", "+00:00"))
    except ValueError:
        return 0

    now = get_local_now()
    if created_dt.tzinfo is not None:
        now_cmp = now.astimezone(datetime.timezone.utc)
    else:
        now_cmp = now.replace(tzinfo=None)
    return max(0, (now_cmp - created_dt).days)


def _is_overdue(deadline: Any) -> bool:
    if not deadline:
        return False
    try:
        deadline_dt = datetime.datetime.strptime(str(deadline), "%Y-%m-%d")
    except ValueError:
        return False
    return deadline_dt.date() < get_local_now().date()


def assess_sales_pipeline(
    leads: Iterable[Dict[str, Any]],
    owner_lookup: Optional[Callable[[int], str]] = None,
) -> List[JourneySignal]:
    signals: List[JourneySignal] = []
    now_ts = int(get_local_now().timestamp())

    for lead in leads:
        if int(lead.get("status_id") or 0) in {142, 143}:
            continue

        idle_hours = _lead_idle_hours(lead, now_ts)
        if idle_hours < 6:
            continue

        price = int(lead.get("price") or 0)
        responsible_id = int(lead.get("responsible_user_id") or 0)
        owner_name = owner_lookup(responsible_id) if owner_lookup and responsible_id else "Sales"
        lead_name = _safe_text(lead.get("name"))

        if idle_hours >= 48 and price >= 10_000_000:
            signals.append(
                JourneySignal(
                    department="sales",
                    client_name=lead_name,
                    stage="VIP rescue",
                    urgency="critical",
                    owner_hint=owner_name,
                    risk=f"{idle_hours} soat jimlik va yuqori чек yo'qolish xavfi.",
                    owner_action="15 daqiqa ichida call qiling, qaror beruvchini aniqlang, objection va next-step sanasini CRMga yozing.",
                    wow_action="Mijozga 1 ta aniq recap, 2 ta variantli yechim va meeting slot yuboring.",
                    proof_of_done="CRM note + task + keyingi qaror sanasi yozilgan bo'lishi kerak.",
                    meta={"idle_hours": idle_hours, "price": price, "lead_id": lead.get("id")},
                )
            )
            continue

        if idle_hours >= 24:
            signals.append(
                JourneySignal(
                    department="sales",
                    client_name=lead_name,
                    stage="Recovery follow-up",
                    urgency="high",
                    owner_hint=owner_name,
                    risk=f"{idle_hours} soat follow-upsiz qolgan lead sovib boryapti.",
                    owner_action="Bugun reply yoki call qilib, e'tiroz sababini va keyingi qadamni yopib chiqing.",
                    wow_action="Qisqa personalized voice yoki matn recap yuborib, mijozga nima uchun aynan biz ekanini eslating.",
                    proof_of_done="CRMda sabab, stage va follow-up sanasi yangilansin.",
                    meta={"idle_hours": idle_hours, "price": price, "lead_id": lead.get("id")},
                )
            )
            continue

        if idle_hours >= 6:
            signals.append(
                JourneySignal(
                    department="sales",
                    client_name=lead_name,
                    stage="Speed-to-lead",
                    urgency="medium",
                    owner_hint=owner_name,
                    risk="Birinchi taassurot sustlashyapti.",
                    owner_action="Mijozga bugunning o'zida discovery savollari va keyingi qadamni yuboring.",
                    wow_action="3 qatorlik tezkor audit yoki mini-foyda g'oyasi bilan chiqib, 'wow' birinchi touch yarating.",
                    proof_of_done="Lead bo'yicha javob va keyingi status CRMda ko'rinishi kerak.",
                    meta={"idle_hours": idle_hours, "price": price, "lead_id": lead.get("id")},
                )
            )

    signals.sort(key=lambda item: (_urgency_rank(item.urgency), -int(item.meta.get("price") or 0), -int(item.meta.get("idle_hours") or 0)))
    return signals


def assess_project_portfolio(projects: Iterable[Dict[str, Any]]) -> List[JourneySignal]:
    signals: List[JourneySignal] = []

    for project in projects:
        fields = project.get("fields", {})
        stage = _safe_text(AirtableSync._get_field(fields, "stage"), "")
        project_name = _safe_text(AirtableSync._get_field(fields, "project_name"))
        manager_name = _safe_text(AirtableSync._get_field(fields, "manager"), "PM")
        payment_status = _safe_text(AirtableSync._get_field(fields, "payment_status"), "")
        paid_usd = _to_number(AirtableSync._get_field(fields, "paid_usd"))
        remaining_usd = _to_number(AirtableSync._get_field(fields, "remaining_usd"))
        age_days = _project_age_days(project)
        deadline = AirtableSync._get_field(fields, "deadline")
        overdue = _is_overdue(deadline)
        stage_norm = stage.lower()

        if stage in AirtableSync.DONE_STAGES:
            if paid_usd > 0 and remaining_usd <= 0:
                signals.append(
                    JourneySignal(
                        department="pm",
                        client_name=project_name,
                        stage="Advocacy",
                        urgency="medium",
                        owner_hint=manager_name,
                        risk="Loyiha yopilgan, lekin referral/tavsiyanoma momenti sovib ketishi mumkin.",
                        owner_action="48 soat ichida case permission, testimonial va referral so'rovini bitta oqimda yoping.",
                        wow_action="Mijozga handoff recap, foydalanish bo'yicha mini-guide va keyingi growth g'oyasini yuboring.",
                        proof_of_done="Testimonial so'rovi, referral savoli va handoff xabari yuborilgan bo'lsin.",
                        meta={"project_id": project.get("id"), "age_days": age_days},
                    )
                )
            continue

        if any(token in stage_norm for token in ("brief", "brif", "research", "strateg")) and (age_days >= 2 or overdue):
            signals.append(
                JourneySignal(
                    department="pm",
                    client_name=project_name,
                    stage="Kickoff discipline",
                    urgency="high" if overdue else "medium",
                    owner_hint=manager_name,
                    risk="Kickoff moment cho'zilsa, mijozda servis sifati haqidagi ishonch pasayadi.",
                    owner_action="Bugun kickoff summary, timeline va ownership mapni mijozga yuboring.",
                    wow_action="Mijozga bitta aniq 'keyingi 7 kun' planini ko'rsatib, noaniqlikni yoping.",
                    proof_of_done="Kickoff recap va timeline Telegram guruhida ko'rinishi kerak.",
                    meta={"project_id": project.get("id"), "age_days": age_days, "deadline": deadline},
                )
            )
            continue

        if any(token in stage_norm for token in ("design", "dizayn", "concept", "draft", "maket")) and (age_days >= 4 or overdue):
            signals.append(
                JourneySignal(
                    department="pm",
                    client_name=project_name,
                    stage="Preview excellence",
                    urgency="high" if overdue else "medium",
                    owner_hint=manager_name,
                    risk="Ijodiy bosqichdagi jimlik mijozda 'ishni qilishyaptimi?' degan xavotir uyg'otadi.",
                    owner_action="Status preview yuboring, feedback savollarini toraytiring va revision ETA bering.",
                    wow_action="Faqat draft emas, qaror qabul qilishni osonlashtiradigan rationale bilan chiqing.",
                    proof_of_done="Preview + feedback question + revision ETA yozilgan bo'lsin.",
                    meta={"project_id": project.get("id"), "age_days": age_days, "deadline": deadline},
                )
            )
            continue

        if any(token in stage_norm for token in ("review", "feedback", "approval", "tasdiq")) and (age_days >= 3 or overdue):
            signals.append(
                JourneySignal(
                    department="pm",
                    client_name=project_name,
                    stage="Feedback closure",
                    urgency="high",
                    owner_hint=manager_name,
                    risk="Feedback ochiq qolsa loyiha ham, mijoz hissiyati ham qotib qoladi.",
                    owner_action="Feedbackni checklist ko'rinishida yoping va har band uchun owner/ETA yozing.",
                    wow_action="Mijozga 'nimani qabul qildik, nimani o'zgartiramiz' deb aniq closure xabarini yuboring.",
                    proof_of_done="Feedback matrix va keyingi topshirish sanasi ko'rinishi kerak.",
                    meta={"project_id": project.get("id"), "age_days": age_days, "deadline": deadline},
                )
            )
            continue

        if any(token in stage_norm for token in ("production", "dev", "fayl", "delivery", "topshir")) and (age_days >= 3 or overdue):
            signals.append(
                JourneySignal(
                    department="pm",
                    client_name=project_name,
                    stage="Handoff readiness",
                    urgency="high",
                    owner_hint=manager_name,
                    risk="Topshirish oldidan chalkashlik bo'lsa, butun servis impressioni buziladi.",
                    owner_action="Final paket, izoh, support window va qabul checklistini oldindan tayyorlang.",
                    wow_action="Handoffni 'finished' emas, 'you are set up for success' hissi bilan yoping.",
                    proof_of_done="Final fayllar, izoh va support oynasi bir xabarda jamlangan bo'lsin.",
                    meta={"project_id": project.get("id"), "age_days": age_days, "deadline": deadline},
                )
            )

        if payment_status and remaining_usd > 0 and any(token in stage_norm for token in ("review", "delivery", "topshir", "done")):
            signals.append(
                JourneySignal(
                    department="sales",
                    client_name=project_name,
                    stage="Payment hygiene",
                    urgency="high",
                    owner_hint="Sales/Finance",
                    risk="Servis berilyapti, lekin to'lov qoldig'i ochiq qolgan.",
                    owner_action="Mijozga value recap bilan birga to'lov closure va sana bo'yicha aniq follow-up qiling.",
                    wow_action="To'lov eslatmasini sovuq billing emas, deliverable progress recap bilan birga yuboring.",
                    proof_of_done="To'lov sanasi yoki closure statusi CRM/Airtableda yangilangan bo'lsin.",
                    meta={"project_id": project.get("id"), "remaining_usd": remaining_usd, "payment_status": payment_status},
                )
            )

    signals.sort(key=lambda item: (_urgency_rank(item.urgency), item.department != "sales", -int(item.meta.get("age_days") or 0)))
    return signals


def render_excellence_report(
    sales_signals: List[JourneySignal],
    project_signals: List[JourneySignal],
    *,
    max_items_per_section: int = 4,
) -> str:
    lines = [
        "<b>Client Journey Micromanagement</b>",
        "Talab: har bosqichda mijoz 'wow' sezsin, jimlik va noaniqlik qolmasin.",
        "",
    ]

    if sales_signals:
        lines.append(f"<b>Sales / First Impression</b> — {len(sales_signals)} ta signal")
        for signal in sales_signals[:max_items_per_section]:
            lines.append(
                "• "
                f"<b>{escape(signal.client_name)}</b> — {escape(signal.stage)} / {escape(signal.owner_hint)}"
            )
            lines.append(f"  Risk: {escape(signal.risk)}")
            lines.append(f"  Bugungi qadam: {escape(signal.owner_action)}")
            lines.append(f"  Wow moment: {escape(signal.wow_action)}")
        lines.append("")

    if project_signals:
        lines.append(f"<b>Delivery / PM Excellence</b> — {len(project_signals)} ta signal")
        for signal in project_signals[:max_items_per_section]:
            lines.append(
                "• "
                f"<b>{escape(signal.client_name)}</b> — {escape(signal.stage)} / {escape(signal.owner_hint)}"
            )
            lines.append(f"  Risk: {escape(signal.risk)}")
            lines.append(f"  Bugungi qadam: {escape(signal.owner_action)}")
            lines.append(f"  Wow moment: {escape(signal.wow_action)}")
        lines.append("")

    lines.append(
        "Standart: har bir signal bo'yicha 1) next step, 2) owner, 3) ETA, 4) mijozga yuborilgan closure xabari bo'lishi shart."
    )
    return "\n".join(lines).strip()


def build_department_direct_messages(
    team_members: List[Dict[str, Any]],
    sales_signals: List[JourneySignal],
    project_signals: List[JourneySignal],
) -> List[Dict[str, Any]]:
    messages: List[Dict[str, Any]] = []
    sales_role_tokens = ("sales", "sotuv", "hunter", "closer", "manager")
    pm_role_tokens = ("pm", "project", "manager")

    def _belongs(member: Dict[str, Any], tokens: tuple[str, ...]) -> bool:
        role_blob = " ".join(
            str(member.get(key, "") or "").lower()
            for key in ("role", "detailed_role", "position")
        )
        return any(token in role_blob for token in tokens)

    sales_text = None
    if sales_signals:
        sales_lines = [
            "<b>Bugungi sales wow-service fokus</b>",
        ]
        for signal in sales_signals[:3]:
            sales_lines.append(
                f"• <b>{escape(signal.client_name)}</b>: {escape(signal.owner_action)}"
            )
        sales_lines.append("Talab: CRMda next step, sabab va sana yozilsin.")
        sales_text = "\n".join(sales_lines)

    pm_text = None
    if project_signals:
        pm_lines = [
            "<b>Bugungi PM wow-service fokus</b>",
        ]
        for signal in project_signals[:3]:
            pm_lines.append(
                f"• <b>{escape(signal.client_name)}</b>: {escape(signal.owner_action)}"
            )
        pm_lines.append("Talab: mijozga closure xabari, ETA va owner aniq yozilsin.")
        pm_text = "\n".join(pm_lines)

    for member in team_members:
        user_id = member.get("user_id")
        if not user_id:
            continue
        if sales_text and _belongs(member, sales_role_tokens):
            messages.append({"user_id": user_id, "text": sales_text, "parse_mode": "HTML"})
        elif pm_text and _belongs(member, pm_role_tokens):
            messages.append({"user_id": user_id, "text": pm_text, "parse_mode": "HTML"})

    return messages
