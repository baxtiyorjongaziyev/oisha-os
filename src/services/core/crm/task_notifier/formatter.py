"""
Helper functions for formatting AmoCRM task notifications.
"""
from __future__ import annotations

import html
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger('AmoCRMTaskNotifier')

DEFAULT_FORWARD_GROUP_ID = -1003854308552
DEFAULT_FORWARD_TOPIC_ID = 443
DEFAULT_SUBDOMAIN = "jonbrandingagency"

PIPELINE_MAP = {
    11162698: "1. PRESALES",
    11162702: "2. CLOSER",
    10123318: "Farmer",
    10427390: "Sifat Nazorati",
    10947042: "Reactivation",
    10947046: "Partnership",
}

STATUS_MAP = {
    87609510: "Неразобранное",
    87609514: "Yangi so'rov",
    87609518: "Aloqaga chiqildi",
    87609522: "Kvalifikatsiya",
    87609526: "Uchrashuv belgilandi",
    87609534: "Uchrashuv o'tdi",
    87609538: "KP / Taklif",
    87609542: "Muzokara",
    87609546: "Shartnoma tayyorlanmoqda",
    87609550: "Avans kutilmoqda",
    142: "Успешно реализовано",
    143: "Закрыто и не реализовано",
}

TASK_TYPE_MAP = {
    1: "📞 Qo'ng'iroq",
    2: "🤝 Uchrashuv",
    3: "✉️ Xat",
    4061818: "⏰ Eslatma",
    4082430: "💳 To'lov olish",
    4266998: "📂 Portfolio Send",
    4267854: "📝 Vazifa",
}


def _format_timestamp(ts: Optional[int | float]) -> str:
    """Format unix timestamp into Tashkent local time string."""
    if not ts:
        return "Noma'lum"
    try:
        dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone()
        return dt.strftime("%d.%m.%Y %H:%M")
    except Exception:
        return str(ts)

def _format_price(price: Any) -> Optional[str]:
    """Format price in readable sum."""
    if not price:
        return None
    try:
        val = int(price)
        if val <= 0:
            return None
        return f"{val:,}".replace(",", " ") + " so'm"
    except (ValueError, TypeError):
        return str(price)

def _extract_custom_field_value(entity: Dict[str, Any], field_id: int) -> Optional[str]:
    """Extract custom field value by field_id."""
    cfs = entity.get("custom_fields_values") or []
    for cf in cfs:
        if cf.get("field_id") == field_id:
            values = cf.get("values") or []
            if values and isinstance(values, list):
                val_obj = values[0]
                if isinstance(val_obj, dict):
                    return val_obj.get("value")
                return str(val_obj)
    return None


def format_task_notification(
    task: Dict[str, Any],
    lead_or_contact: Optional[Dict[str, Any]] = None,
    contact_details: Optional[Dict[str, Any]] = None,
    phone: Optional[str] = None,
    responsible_name: Optional[str] = None,
    alert_type: str = "due",
    subdomain: str = DEFAULT_SUBDOMAIN,
) -> Tuple[str, Optional[List[List[Dict[str, str]]]]]:
    """Format task alert into a rich, fully-detailed HTML message with amoCRM link button.

    alert_type: 'due' | 'overdue' | 'new'
    """
    if alert_type == "overdue":
        title_header = "⚠️ <b>Просроченная задача! (Muddati o'tgan)</b>"
    elif alert_type == "new":
        title_header = "📋 <b>Yangi vazifa biriktirildi</b>"
    else:
        title_header = "🔔 <b>Пора выполнить задачу! (Vazifa vaqti keldi)</b>"

    entity_type = task.get("entity_type") or "leads"
    entity_id = task.get("entity_id")
    if not entity_id and "element_id" in task:
        entity_id = task.get("element_id")

    lead_data = lead_or_contact if entity_type in ("leads", 2) else None
    contact_data = contact_details or (lead_or_contact if entity_type in ("contacts", 1) else None)

    lead_name = lead_data.get("name") if lead_data else ("Noma'lum" if entity_type in ("leads", 2) else None)
    contact_name = contact_data.get("name") if contact_data else None

    # Resolve phone
    if not phone and contact_data:
        phone = contact_data.get("phone")

    # Resolve stage & pipeline
    stage_str = None
    if lead_data:
        p_id = lead_data.get("pipeline_id")
        s_id = lead_data.get("status_id")
        p_name = PIPELINE_MAP.get(p_id, f"Voronka #{p_id}" if p_id else "")
        s_name = STATUS_MAP.get(s_id, f"Status #{s_id}" if s_id else "")
        if p_name and s_name:
            stage_str = f"{p_name} ➔ {s_name}"
        elif s_name:
            stage_str = s_name

    # Custom fields
    service_name = None
    source_name = None
    telegram_user = None
    price_str = None

    if lead_data:
        service_name = _extract_custom_field_value(lead_data, 1034671)  # Tanlangan xizmatlar
        source_name = _extract_custom_field_value(lead_data, 1034663)   # Lead manbasi
        telegram_user = _extract_custom_field_value(lead_data, 1037937) # Telegram @username
        price_str = _format_price(lead_data.get("price"))

    if not telegram_user and contact_data:
        telegram_user = _extract_custom_field_value(contact_data, 1340887)

    # Task details
    task_type_id = task.get("task_type_id") or task.get("task_type")
    task_type_str = TASK_TYPE_MAP.get(task_type_id, "📝 Vazifa" if task_type_id else None)
    task_text = (task.get("text") or "").strip() or "Vazifa matni ko'rsatilmagan"
    safe_task_text = html.escape(task_text)
    safe_resp_name = html.escape(responsible_name or "Mas'ul xodim")
    due_str = _format_timestamp(task.get("complete_till"))

    # Build rich message body
    lines = [title_header, ""]

    if lead_name:
        lines.append(f"📌 <b>Bitim:</b> <b>{html.escape(lead_name)}</b>")

    if contact_name and contact_name != lead_name:
        lines.append(f"👤 <b>Mijoz:</b> {html.escape(contact_name)}")

    if phone:
        lines.append(f"📞 <b>Telefon:</b> <code>{html.escape(phone)}</code>")

    if telegram_user:
        clean_tg = telegram_user.lstrip("@").strip()
        lines.append(f"💬 <b>Telegram:</b> @{html.escape(clean_tg)}")

    if stage_str:
        lines.append(f"📊 <b>Bosqich:</b> {html.escape(stage_str)}")

    if service_name:
        lines.append(f"🎯 <b>Xizmat:</b> {html.escape(service_name)}")

    if source_name:
        lines.append(f"📍 <b>Manba:</b> {html.escape(source_name)}")

    if price_str:
        lines.append(f"💰 <b>Byudjet:</b> {html.escape(price_str)}")

    lines.append("")
    if task_type_str:
        lines.append(f"🏷️ <b>Vazifa turi:</b> {task_type_str}")
    lines.append(f"📝 <b>Vazifa:</b> {safe_task_text}")
    lines.append(f"👤 <b>Mas'ul:</b> {safe_resp_name}")
    lines.append(f"⏰ <b>Muddat:</b> {due_str}")

    msg = "\n".join(lines)

    # Build inline action buttons
    button_row = []
    if entity_id:
        url_path = "leads" if entity_type in ("leads", 2) else "contacts"
        crm_url = f"https://{subdomain}.amocrm.ru/{url_path}/detail/{entity_id}"
        button_row.append({"text": "🌐 Перейти в amoCRM", "url": crm_url})

    buttons = [button_row] if button_row else None
    return msg, buttons
