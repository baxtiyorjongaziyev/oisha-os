from __future__ import annotations

import datetime
import re
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


STAGE_LABELS = {
    "VIP rescue": "VIP mijozni qayta ushlash",
    "Recovery follow-up": "Qolib ketgan lidni qayta jonlantirish",
    "Speed-to-lead": "Tezkor birinchi javob",
    "Advocacy": "Otziv va tavsiya olish",
    "Kickoff discipline": "Boshlanishni tartibga solish",
    "Preview excellence": "Oraliq ko'rinishni aniq yopish",
    "Feedback closure": "Feedbackni yopish",
    "Handoff readiness": "Topshirishga tayyorgarlik",
    "Payment hygiene": "To'lovni yopish",
}

OWNER_LABELS = {
    "Sales": "Sotuv",
    "Sales/Finance": "Sotuv / Moliya",
    "PM": "PM",
}

COPY_REPLACEMENTS = (
    ("owner/ETA", "mas'ul va muddat"),
    ("owner / ETA", "mas'ul va muddat"),
    ("owner", "mas'ul"),
    ("Owner", "Mas'ul"),
    ("ETA", "muddat"),
    ("next-step", "keyingi qadam"),
    ("next step", "keyingi qadam"),
    ("Next step", "Keyingi qadam"),
    ("feedback question", "feedback savoli"),
    ("Feedback matrix", "Feedback jadvali"),
    ("feedback matrix", "feedback jadvali"),
    ("closure", "yakuniy"),
    ("Closure", "Yakuniy"),
    ("kickoff", "boshlanish"),
    ("Kickoff", "Boshlanish"),
    ("preview", "oraliq ko'rinish"),
    ("Preview", "Oraliq ko'rinish"),
    ("support window", "qo'llab-quvvatlash muddati"),
    ("recap", "qisqa xulosa"),
    ("rationale", "asos"),
)


def _safe_text(value: Any, fallback: str = "Noma'lum") -> str:
    text = str(value).strip() if value is not None else ""
    return text or fallback


def _normalize_copy(value: Any, fallback: str = "Noma'lum") -> str:
    text = _safe_text(value, fallback)
    for source, target in COPY_REPLACEMENTS:
        text = text.replace(source, target)
    return text


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


def _looks_like_airtable_id(value: str) -> bool:
    return bool(re.fullmatch(r"rec[a-zA-Z0-9]{10,}", value))


def _humanize_owner_hint(value: Any) -> str:
    if isinstance(value, list):
        labels: List[str] = []
        for item in value:
            label = _humanize_owner_hint(item)
            if label and label not in labels and label != "Mas'ul aniqlansin":
                labels.append(label)
        return ", ".join(labels) if labels else "Mas'ul aniqlansin"

    text = str(value).strip() if value is not None else ""
    if not text:
        return "Mas'ul aniqlansin"

    if text in OWNER_LABELS:
        return OWNER_LABELS[text]

    if text.startswith("@"):
        return text

    if _looks_like_airtable_id(text):
        return AirtableSync.resolve_pm_handle(text)

    record_ids = re.findall(r"rec[a-zA-Z0-9]{10,}", text)
    if record_ids:
        handles: List[str] = []
        for record_id in record_ids:
            handle = AirtableSync.resolve_pm_handle(record_id)
            if handle and handle not in handles:
                handles.append(handle)
        return ", ".join(handles) if handles else "Mas'ul aniqlansin"

    return OWNER_LABELS.get(text, text)


def _humanize_stage(stage: Any) -> str:
    text = _safe_text(stage)
    return STAGE_LABELS.get(text, text)


def _render_owner_html(signal: JourneySignal, airtable: Optional[AirtableSync]) -> str:
    raw_owner = signal.meta.get("manager_ref", signal.owner_hint)

    if isinstance(raw_owner, list):
        parts: List[str] = []
        for item in raw_owner:
            label = _humanize_owner_hint(item)
            url = airtable.get_record_url(item) if airtable and _looks_like_airtable_id(str(item)) else None
            if url:
                parts.append(f"<a href='{escape(url, quote=True)}'>{escape(label)}</a>")
            else:
                parts.append(escape(label))
        return ", ".join(parts) if parts else escape(_humanize_owner_hint(signal.owner_hint))

    raw_owner_text = str(raw_owner).strip() if raw_owner is not None else ""
    if airtable and _looks_like_airtable_id(raw_owner_text):
        url = airtable.get_record_url(raw_owner_text)
        if url:
            return f"<a href='{escape(url, quote=True)}'>{escape(_humanize_owner_hint(raw_owner_text))}</a>"

    return escape(_humanize_owner_hint(signal.owner_hint))


def _render_airtable_card_line(signal: JourneySignal, airtable: Optional[AirtableSync]) -> Optional[str]:
    if not airtable:
        return None

    record_id = signal.meta.get("project_id")
    if not record_id or not _looks_like_airtable_id(str(record_id)):
        return None

    url = airtable.get_record_url(str(record_id))
    if not url:
        return None

    return f"  Airtable kartasi: <a href='{escape(url, quote=True)}'>yozuvni ochish</a>"


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
                    owner_hint=_humanize_owner_hint(owner_name),
                    risk=f"{idle_hours} soat jimlik bo'ldi, yuqori qiymatli mijozni yo'qotish xavfi bor.",
                    owner_action="15 daqiqa ichida qo'ng'iroq qiling, qaror beruvchini aniqlang va keyingi qadam sanasini CRMga yozing.",
                    wow_action="Mijozga qisqa xulosa, 2 ta aniq yechim varianti va uchrashuv vaqti yuboring.",
                    proof_of_done="CRM note, vazifa va keyingi qaror sanasi yozilgan bo'lishi kerak.",
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
                    owner_hint=_humanize_owner_hint(owner_name),
                    risk=f"{idle_hours} soat follow-upsiz qolgan lid sovib boryapti.",
                    owner_action="Bugun javob yoki qo'ng'iroq qilib, e'tiroz sababini va keyingi qadamni yopib chiqing.",
                    wow_action="Qisqa shaxsiy voice yoki matn xulosasi yuborib, nega aynan biz ekanini eslating.",
                    proof_of_done="CRMda sabab, bosqich va follow-up sanasi yangilansin.",
                    meta={"idle_hours": idle_hours, "price": price, "lead_id": lead.get("id")},
                )
            )
            continue

        signals.append(
            JourneySignal(
                department="sales",
                client_name=lead_name,
                stage="Speed-to-lead",
                urgency="medium",
                owner_hint=_humanize_owner_hint(owner_name),
                risk="Birinchi taassurot sustlashyapti.",
                owner_action="Mijozga bugunning o'zida discovery savollari va keyingi qadamni yuboring.",
                wow_action="3 qatorlik tezkor audit yoki mini foyda g'oyasi bilan birinchi wow taassurot yarating.",
                proof_of_done="Lid bo'yicha javob va keyingi status CRMda ko'rinishi kerak.",
                meta={"idle_hours": idle_hours, "price": price, "lead_id": lead.get("id")},
            )
        )

    signals.sort(
        key=lambda item: (
            _urgency_rank(item.urgency),
            -int(item.meta.get("price") or 0),
            -int(item.meta.get("idle_hours") or 0),
        )
    )
    return signals


def assess_project_portfolio(projects: Iterable[Dict[str, Any]]) -> List[JourneySignal]:
    signals: List[JourneySignal] = []

    for project in projects:
        fields = project.get("fields", {})
        stage = _safe_text(AirtableSync._get_field(fields, "stage"), "")
        project_name = _safe_text(AirtableSync._get_field(fields, "project_name"))
        manager_raw = AirtableSync._get_field(fields, "manager")
        manager_name = _humanize_owner_hint(manager_raw)
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
                        risk="Loyiha yopilgan, lekin tavsiyanoma va referral momenti sovib ketishi mumkin.",
                        owner_action="48 soat ichida case permission, testimonial va referral so'rovini bitta oqimda yoping.",
                        wow_action="Mijozga handoff xulosasi, foydalanish bo'yicha mini qo'llanma va keyingi growth g'oyasini yuboring.",
                        proof_of_done="Testimonial so'rovi, referral savoli va handoff xabari yuborilgan bo'lsin.",
                        meta={"project_id": project.get("id"), "age_days": age_days, "manager_ref": manager_raw},
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
                    risk="Boshlanish momenti cho'zilsa, mijozda servis sifati haqidagi ishonch pasayadi.",
                    owner_action="Bugun boshlanish xulosasi, timeline va ownership xaritasini mijozga yuboring.",
                    wow_action="Mijozga keyingi 7 kunlik aniq reja ko'rsatib, noaniqlikni yoping.",
                    proof_of_done="Boshlanish xulosasi va timeline Telegram guruhida ko'rinishi kerak.",
                    meta={"project_id": project.get("id"), "age_days": age_days, "deadline": deadline, "manager_ref": manager_raw},
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
                    owner_action="Oraliq ko'rinish yuboring, feedback savollarini toraytiring va qayta topshirish muddatini bering.",
                    wow_action="Faqat draft emas, qaror qabul qilishni osonlashtiradigan asos bilan chiqing.",
                    proof_of_done="Oraliq ko'rinish, feedback savoli va qayta topshirish muddati yozilgan bo'lsin.",
                    meta={"project_id": project.get("id"), "age_days": age_days, "deadline": deadline, "manager_ref": manager_raw},
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
                    owner_action="Feedbackni checklist ko'rinishida yoping va har band uchun mas'ul odam hamda muddat yozing.",
                    wow_action="Mijozga 'nimani qabul qildik, nimani o'zgartiramiz' degan aniq yakuniy xabarni yuboring.",
                    proof_of_done="Feedback jadvali va keyingi topshirish sanasi ko'rinishi kerak.",
                    meta={"project_id": project.get("id"), "age_days": age_days, "deadline": deadline, "manager_ref": manager_raw},
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
                    risk="Topshirish oldidan chalkashlik bo'lsa, butun servis taassuroti buziladi.",
                    owner_action="Final paket, izoh, qo'llab-quvvatlash muddati va qabul checklistini oldindan tayyorlang.",
                    wow_action="Topshirishni shunchaki 'tugadi' emas, 'siz endi bemalol ishlata olasiz' hissi bilan yoping.",
                    proof_of_done="Final fayllar, izoh va qo'llab-quvvatlash muddati bitta xabarda jamlangan bo'lsin.",
                    meta={"project_id": project.get("id"), "age_days": age_days, "deadline": deadline, "manager_ref": manager_raw},
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
                    owner_action="Mijozga qiymat xulosasi bilan birga to'lovni yopish va sana bo'yicha aniq follow-up qiling.",
                    wow_action="To'lov eslatmasini sovuq billing emas, topshirilgan ishlar xulosasi bilan birga yuboring.",
                    proof_of_done="To'lov sanasi yoki yopilish statusi CRM/Airtableda yangilangan bo'lsin.",
                    meta={"project_id": project.get("id"), "remaining_usd": remaining_usd, "payment_status": payment_status, "manager_ref": manager_raw},
                )
            )

    signals.sort(
        key=lambda item: (
            _urgency_rank(item.urgency),
            item.department != "sales",
            -int(item.meta.get("age_days") or 0),
        )
    )
    return signals


def _render_signal_lines(signal: JourneySignal, airtable: Optional[AirtableSync]) -> List[str]:
    lines = [
        f"• <b>{escape(signal.client_name)}</b>",
        f"  Bosqich: {escape(_humanize_stage(signal.stage))}",
        f"  Mas'ul: {_render_owner_html(signal, airtable)}",
        f"  Xavf: {escape(_normalize_copy(signal.risk))}",
        f"  Bugungi qadam: {escape(_normalize_copy(signal.owner_action))}",
        f"  Mijoz ko'radigan wow qadam: {escape(_normalize_copy(signal.wow_action))}",
    ]
    card_line = _render_airtable_card_line(signal, airtable)
    if card_line:
        lines.append(card_line)
    return lines


def render_excellence_report(
    sales_signals: List[JourneySignal],
    project_signals: List[JourneySignal],
    *,
    max_items_per_section: int = 4,
) -> str:
    try:
        airtable = AirtableSync()
    except Exception:
        airtable = None

    total_signals = len(sales_signals) + len(project_signals)
    critical_count = sum(1 for signal in sales_signals + project_signals if signal.urgency == "critical")

    score = 100
    if total_signals > 0:
        score = max(0, 100 - (critical_count * 20) - (total_signals * 2))

    if score >= 90:
        score_emoji = "💎"
    elif score >= 75:
        score_emoji = "⭐"
    elif score >= 50:
        score_emoji = "⚠️"
    else:
        score_emoji = "🚨"

    lines = [
        f"<b>{score_emoji} Oisha Wow-Service Audit</b>",
        f"<b>Servis sifati bahosi: {score}%</b>",
        "Talab: har bosqichda mijoz 'wow' sezsin, jimlik va noaniqlik qolmasin.",
        "",
    ]

    if sales_signals:
        lines.append(f"<b>Sotuv / Birinchi taassurot</b> - {len(sales_signals)} ta signal")
        for signal in sales_signals[:max_items_per_section]:
            lines.extend(_render_signal_lines(signal, airtable))
        lines.append("")

    if project_signals:
        lines.append(f"<b>PM / Yetkazib berish sifati</b> - {len(project_signals)} ta signal")
        for signal in project_signals[:max_items_per_section]:
            lines.extend(_render_signal_lines(signal, airtable))
        lines.append("")

    lines.append(
        "Standart: har bir signal bo'yicha 1) keyingi qadam, 2) mas'ul odam, 3) muddat, 4) mijozga yuborilgan yakuniy xabar bo'lishi shart."
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
        sales_lines = ["<b>Bugungi sotuv wow-service fokusi</b>"]
        for signal in sales_signals[:3]:
            sales_lines.append(
                f"• <b>{escape(signal.client_name)}</b>: {escape(_normalize_copy(signal.owner_action))}"
            )
        sales_lines.append("Talab: CRMda keyingi qadam, sabab va sana yozilsin.")
        sales_text = "\n".join(sales_lines)

    pm_text = None
    if project_signals:
        pm_lines = ["<b>Bugungi PM wow-service fokusi</b>"]
        for signal in project_signals[:3]:
            pm_lines.append(
                f"• <b>{escape(signal.client_name)}</b>: {escape(_normalize_copy(signal.owner_action))}"
            )
        pm_lines.append("Talab: mijozga yakuniy xabar, mas'ul odam va muddat aniq yozilsin.")
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
