"""Transport-independent admin command helpers.

These helpers are the bridge from Telethon decorators to the future Aiogram
dispatcher: handlers extract a small request object, the router returns a
message payload, and the transport decides how to send it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class AdminCommandResponse:
    text: str
    parse_mode: Optional[str] = None


def build_chatid_response(
    *,
    chat_id: int,
    chat_title: str,
    topic_id: Optional[int] = None,
) -> AdminCommandResponse:
    lines = [
        f"<b>Chat ID:</b> <code>{chat_id}</code>",
        f"<b>Nom:</b> {chat_title or 'shaxsiy'}",
    ]
    if topic_id:
        lines.append(f"<b>Topic ID:</b> <code>{topic_id}</code>")
    else:
        lines.append("Topic ID olish uchun topicning ichida /chatid yozing")
    return AdminCommandResponse(text="\n".join(lines), parse_mode="html")


def resolve_start_role(
    *,
    sender_id: int,
    owner_id: int,
    fallback_owner_id: int = 150074828,
    get_role,
) -> str:
    if int(sender_id or 0) in {int(owner_id or 0), int(fallback_owner_id)}:
        return "OWNER"
    return get_role(sender_id) or "GUEST"


def build_start_response(
    *,
    role_name: str,
    now_text: str,
) -> AdminCommandResponse:
    return AdminCommandResponse(
        text=(
            "**Oisha-OS Enterprise v2.1**\n\n"
            f"Assalomu alaykum, **{role_name}**!\n"
            "Tizimga muvaffaqiyatli kirdingiz. Boshqaruv pulti tayyor.\n\n"
            f"Bugun: `{now_text}`"
        )
    )


def _crm_health_label(health_score: int) -> str:
    if health_score > 80:
        return "Optimal"
    if health_score > 50:
        return "Diqqat kerak"
    return "KRITIK HOLAT"


def build_oisha_stats_response(
    *,
    stats: dict,
    health_score: int,
) -> AdminCommandResponse:
    leads_found = int(stats.get("leads_found") or 0)
    messages_synced = int(stats.get("messages_synced") or 0)
    return AdminCommandResponse(
        text=(
            "**OISHA: BUSINESS PERFORMANCE**\n"
            "------------------------------\n"
            f"**Yangi Lidlar:** `{leads_found}` ta\n"
            f"**Xabarlar:** `{messages_synced}` ta\n"
            f"**CRM Tozalik:** `{health_score}%` ({_crm_health_label(health_score)})\n"
            "------------------------------\n"
            "*Oisha hozirda avtonom rejimda ishlamoqda.*"
        )
    )


def build_sales_priorities_response(payload: dict, *, max_items: int = 7) -> AdminCommandResponse:
    status = payload.get("status")
    if status != "ready":
        reason = payload.get("reason") or "amocrm_source_unavailable"
        return AdminCommandResponse(
            text=(
                "Bugungi sotuv prioriteti tayyor emas.\n"
                f"Manba: {payload.get('source', 'amocrm')}\n"
                f"Sabab: {reason}\n"
                "Soxta lead yoki taxminiy ro'yxat berilmadi."
            )
        )

    items = list(payload.get("items") or [])[: max(1, int(max_items))]
    if not items:
        return AdminCommandResponse(
            text=(
                "Bugun gaplashish uchun ochiq lead topilmadi.\n"
                "Manba: AmoCRM. Soxta ro'yxat berilmadi."
            )
        )

    lines = ["Bugun sotuvchi birinchi gaplashadigan leadlar:"]
    reason_labels = {
        "no_open_task": "vazifa yo'q",
        "overdue_task": "vazifa kechikkan",
        "stale_48h_plus": "48+ soat jim",
        "stale_24h_plus": "24+ soat jim",
        "no_contact_attached": "kontakt yo'q",
        "no_responsible": "mas'ul yo'q",
        "high_value": "katta qiymat",
        "priced": "narx bor",
        "price_missing": "narx aniqlanmagan",
        "fresh_lead": "yangi lead",
    }
    for index, item in enumerate(items, start=1):
        reasons = [
            reason_labels.get(str(reason), str(reason))
            for reason in item.get("reasons", [])
        ]
        reason_text = ", ".join(reasons[:4]) if reasons else "sabab ko'rsatilmagan"
        lines.append(
            f"{index}. {item.get('name')} #{item.get('lead_id')} "
            f"[{item.get('priority')}, {item.get('priority_score')}]: {reason_text}"
        )
        lines.append(f"   Keyingi qadam: {item.get('action')}")

    lines.append(
        f"Tekshirildi: {payload.get('scanned_count', 0)} lead; "
        f"yopilgan o'tkazildi: {payload.get('skipped_closed_count', 0)}."
    )
    lines.append("Manba: AmoCRM. Soxta fakt qo'shilmadi.")
    return AdminCommandResponse(text="\n".join(lines))


def build_project_risks_response(payload: dict, *, max_items: int = 7) -> AdminCommandResponse:
    status = payload.get("status")
    if status != "ready":
        reason = payload.get("reason") or "airtable_source_unavailable"
        return AdminCommandResponse(
            text=(
                "Loyiha risklari tayyor emas.\n"
                f"Manba: {payload.get('source', 'airtable')}\n"
                f"Sabab: {reason}\n"
                "Soxta deadline yoki taxminiy risk berilmadi."
            )
        )

    items = list(payload.get("items") or [])[: max(1, int(max_items))]
    if not items:
        return AdminCommandResponse(
            text=(
                "Hozircha faol loyiha riski topilmadi.\n"
                "Manba: Airtable/project source. Soxta risk berilmadi."
            )
        )

    reason_labels = {
        "deadline_missing": "deadline yo'q",
        "overdue": "muddat o'tgan",
        "due_today": "bugun deadline",
        "due_3_days": "3 kun ichida deadline",
        "owner_missing": "PM/mas'ul yo'q",
        "stage_missing": "bosqich yo'q",
        "summary_missing": "xulosa yo'q",
    }
    lines = ["Loyiha/deadline risklari:"]
    for index, item in enumerate(items, start=1):
        evidence = item.get("evidence") or {}
        reasons = [
            reason_labels.get(str(reason), str(reason))
            for reason in item.get("reasons", [])
        ]
        reason_text = ", ".join(reasons[:4]) if reasons else "sabab ko'rsatilmagan"
        deadline = evidence.get("deadline") or "belgilanmagan"
        manager = evidence.get("manager") or "PM yo'q"
        lines.append(
            f"{index}. {item.get('name')} [{item.get('risk')}, {item.get('risk_score')}]: {reason_text}"
        )
        lines.append(f"   Deadline: {deadline}; PM: {manager}")
        lines.append(f"   Keyingi qadam: {item.get('action')}")

    lines.append(
        f"Tekshirildi: {payload.get('scanned_count', 0)} loyiha; "
        f"yopilgan o'tkazildi: {payload.get('skipped_closed_count', 0)}."
    )
    lines.append("Manba: Airtable/project source. Soxta fakt qo'shilmadi.")
    return AdminCommandResponse(text="\n".join(lines))


def build_finance_risks_response(payload: dict, *, max_items: int = 7) -> AdminCommandResponse:
    status = payload.get("status")
    if status != "ready":
        reason = payload.get("reason") or "finance_source_unavailable"
        return AdminCommandResponse(
            text=(
                "Moliya risklari tayyor emas.\n"
                f"Manba: {payload.get('source', 'project_finance')}\n"
                f"Sabab: {reason}\n"
                "Soxta to'lov, qarz yoki marja berilmadi."
            )
        )

    items = list(payload.get("items") or [])[: max(1, int(max_items))]
    if not items:
        return AdminCommandResponse(
            text=(
                "Hozircha loyiha moliya riski topilmadi.\n"
                "Manba: project finance source. Soxta risk berilmadi."
            )
        )

    reason_labels = {
        "price_missing": "narx yo'q",
        "paid_amount_missing": "to'langan summa yo'q",
        "advance_below_50": "50% avans to'liq emas",
        "remaining_payment": "qoldiq to'lov bor",
        "payment_overdue": "to'lov kechikkan",
        "payment_status_missing": "to'lov statusi yo'q",
    }
    lines = ["Moliya/payment risklari:"]
    for index, item in enumerate(items, start=1):
        evidence = item.get("evidence") or {}
        reasons = [
            reason_labels.get(str(reason), str(reason))
            for reason in item.get("reasons", [])
        ]
        reason_text = ", ".join(reasons[:4]) if reasons else "sabab ko'rsatilmagan"
        budget = evidence.get("budget")
        paid = evidence.get("paid_amount")
        remaining = evidence.get("remaining_amount")
        remaining_text = remaining if remaining is not None else "noma'lum"
        lines.append(
            f"{index}. {item.get('name')} [{item.get('risk')}, {item.get('risk_score')}]: {reason_text}"
        )
        lines.append(
            f"   Byudjet: {budget if budget is not None else 'yoq'}; "
            f"To'langan: {paid if paid is not None else 'yoq'}; "
            f"Qoldiq: {remaining_text}"
        )
        lines.append(f"   Keyingi qadam: {item.get('action')}")

    lines.append(
        f"Tekshirildi: {payload.get('scanned_count', 0)} loyiha; "
        f"yopilgan o'tkazildi: {payload.get('skipped_closed_count', 0)}."
    )
    lines.append("Manba: project finance source. Marja taxmin qilinmadi.")
    return AdminCommandResponse(text="\n".join(lines))


def build_team_capacity_response(payload: dict, *, max_items: int = 7) -> AdminCommandResponse:
    status = payload.get("status")
    if status != "ready":
        reason = payload.get("reason") or "project_source_unavailable"
        return AdminCommandResponse(
            text=(
                "Jamoa yuklamasi tayyor emas.\n"
                f"Manba: {payload.get('source', 'project_assignments')}\n"
                f"Sabab: {reason}\n"
                "Soxta bandlik yoki taxminiy yuklama berilmadi."
            )
        )

    items = list(payload.get("items") or [])[: max(1, int(max_items))]
    if not items:
        return AdminCommandResponse(
            text=(
                "Hozircha jamoa yuklamasi bo'yicha risk topilmadi.\n"
                "Manba: project assignments. Soxta bandlik berilmadi."
            )
        )

    reason_labels = {
        "unassigned_projects": "egasiz loyiha",
        "high_project_count": "loyiha soni ko'p",
        "overdue_projects": "kechikkan loyiha bor",
        "due_3_days": "3 kun ichida deadline",
        "missing_deadline": "deadline yo'q",
        "missing_stage": "bosqich yo'q",
    }
    lines = ["Jamoa yuklamasi:"]
    for index, item in enumerate(items, start=1):
        evidence = item.get("evidence") or {}
        reasons = [
            reason_labels.get(str(reason), str(reason))
            for reason in item.get("reasons", [])
        ]
        reason_text = ", ".join(reasons[:4]) if reasons else "normal yuklama"
        lines.append(
            f"{index}. {item.get('owner_name')} [{item.get('load')}, {item.get('load_score')}]: {reason_text}"
        )
        lines.append(
            f"   Faol: {evidence.get('active_projects', 0)}; "
            f"Kechikkan: {evidence.get('overdue_projects', 0)}; "
            f"Yaqin deadline: {evidence.get('due_3_days', 0)}"
        )
        lines.append(f"   Keyingi qadam: {item.get('action')}")

    lines.append(
        f"Tekshirildi: {payload.get('scanned_count', 0)} loyiha; "
        f"egasiz: {payload.get('unassigned_project_count', 0)}."
    )
    lines.append("Manba: project assignments. Yuklama taxmin qilinmadi.")
    return AdminCommandResponse(text="\n".join(lines))


def build_command_center_response(payload: dict) -> AdminCommandResponse:
    summary = payload.get("summary") or {}
    sections = payload.get("sections") or {}
    unavailable = summary.get("unavailable_sections") or []
    lines = [
        "Oisha Command Center",
        (
            f"Status: {payload.get('status')} | "
            f"Attention: {summary.get('attention_items', 0)} | "
            f"Ready: {summary.get('ready_sections', 0)}/{summary.get('total_sections', 0)}"
        ),
    ]
    if unavailable:
        lines.append(f"Manba yo'q: {', '.join(str(item) for item in unavailable)}")

    labels = {
        "sales": "Sotuv",
        "projects": "Loyihalar",
        "finance": "Moliya",
        "team": "Jamoa",
    }
    for key in ("sales", "projects", "finance", "team"):
        section = sections.get(key) or {}
        items = section.get("items") or []
        if section.get("status") == "source_unavailable":
            lines.append(f"{labels[key]}: source_unavailable ({section.get('reason')})")
            continue
        if not items:
            lines.append(f"{labels[key]}: {section.get('status', 'empty')}")
            continue
        first = items[0]
        name = first.get("name") or first.get("owner_name") or first.get("lead_id") or "item"
        score = first.get("priority_score") or first.get("risk_score") or first.get("load_score")
        level = first.get("priority") or first.get("risk") or first.get("load")
        lines.append(f"{labels[key]}: {name} [{level}, {score}]")

    lines.append("Soxta data qo'shilmadi; har bo'lim o'z real manba statusini saqlaydi.")
    return AdminCommandResponse(text="\n".join(lines))
