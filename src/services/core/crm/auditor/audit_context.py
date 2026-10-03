async def _group_context(self, lead_id, lead_name, contact_name, telegram_user_id):
    from src.services.core.crm.auditor.classifier import logger

    # Lookup Shared Group Chats & histories
    group_history_parts = []
    is_unanswered_group = False
    group_unanswered_duration = ""
    try:
        shared_groups = await self.find_shared_group_chats(lead_name, contact_name, telegram_user_id)
        for group_entity, group_title in shared_groups:
            g_hist, g_unanswered, g_duration = await self.get_group_chat_history_and_unanswered(group_entity, limit=15)
            if g_hist:
                group_history_parts.append(f"--- Guruh: {group_title} ---\n{g_hist}")
                if g_unanswered:
                    is_unanswered_group = True
                    group_unanswered_duration = g_duration
    except Exception as group_err:
        logger.warning("[AUDITOR] Error fetching shared group chats for lead %s: %s", lead_id, group_err)

    group_history = "\n\n".join(group_history_parts)

    return group_history, is_unanswered_group, group_unanswered_duration


async def collect_contact_context(self, lead, lead_id):
    lead_name = lead.get("name") or "Noma'lum Bitim"
    contacts = lead.get("_embedded", {}).get("contacts", []) or lead.get("contacts", [])

    contact_id = None
    contact_name = "Noma'lum Kontakt"
    phone = ""
    username = ""

    if contacts:
        contact_id = contacts[0].get("id")
        contact_name = contacts[0].get("name") or contact_name
        if contact_id:
            phone, username = await self.get_contact_phone_and_username(int(contact_id))

    # Lookup Telegram Account & chat history
    telegram_user_id = None
    telegram_history = ""
    is_unanswered_tg = False
    tg_unanswered_duration = ""
    if phone or username:
        telegram_user_id, username = await self.get_or_lookup_telegram_user(phone, username)
        if telegram_user_id:
            telegram_history, is_unanswered_tg, tg_unanswered_duration = await self.get_telegram_history_and_unanswered(telegram_user_id, limit=20)

    group_history, is_unanswered_group, group_unanswered_duration = await _group_context(
        self, lead_id, lead_name, contact_name, telegram_user_id
    )

    # Determine Telegram unanswered status info
    telegram_unanswered_info = ""
    if is_unanswered_tg:
        telegram_unanswered_info += f"Mijoz shaxsiy telegramda oxirgi xabarni yozgan ({tg_unanswered_duration}) va javob berilmagan. "
    if is_unanswered_group:
        telegram_unanswered_info += f"Mijoz loyiha guruhida oxirgi xabarni yozgan ({group_unanswered_duration}) va javob berilmagan."
    if not telegram_unanswered_info:
        telegram_unanswered_info = "Barcha Telegram xabarlariga javob berilgan."

    return {
        "lead_name": lead_name, "contact_id": contact_id, "contact_name": contact_name,
        "phone": phone, "username": username, "telegram_user_id": telegram_user_id,
        "telegram_history": telegram_history, "group_history": group_history,
        "is_unanswered_tg": is_unanswered_tg, "is_unanswered_group": is_unanswered_group,
        "telegram_unanswered_info": telegram_unanswered_info,
    }
