import asyncio

from src.services.core.crm.auditor.db_storage import _maybe_await


async def _add_audit_note(self, lead_id, detailed_summary):
    from src.services.core.crm.auditor.classifier import logger

    # Add note to AmoCRM lead
    if detailed_summary:
        try:
            full_note_text = f"🤖 **Oisha-OS: Bitim va Suhbatlar Mukammal Tahlili**\n\n{detailed_summary}"
            await asyncio.to_thread(self.amocrm.add_lead_note, int(lead_id), full_note_text)
            logger.info("[AUDITOR] Added audit note to AmoCRM for lead %s.", lead_id)
        except Exception as note_err:
            logger.error("[AUDITOR] Failed to add audit note to AmoCRM for lead %s: %s", lead_id, note_err)


async def _save_draft(self, lead_id, telegram_user_id, is_unanswered_tg, telegram_draft_reply):
    from src.services.core.crm.auditor.classifier import logger

    # Save draft in Telegram if unanswered
    if telegram_user_id and is_unanswered_tg and telegram_draft_reply:
        try:
            draft_text = telegram_draft_reply.strip()
            await self.tg_client.edit_draft(int(telegram_user_id), draft_text)
            logger.info("[AUDITOR] Saved draft reply in Telegram for user %s: %s", telegram_user_id, draft_text[:50])

            # Add note to AmoCRM that a draft reply has been saved
            try:
                draft_note = f"🤖 **Oisha-OS Telegram Draft:**\nMijozning shaxsiy Telegramdagi oxirgi javobsiz xabariga userbot orqali taklif etilgan javob qoralama (draft) sifatida saqlandi:\n\n\"{draft_text}\"\n\n*(Menejer ushbu javobni tahrirlashi yoki o'zgartirmasdan shaxsiy Telegram orqali yuborishi mumkin)*"
                await asyncio.to_thread(self.amocrm.add_lead_note, int(lead_id), draft_note)
            except Exception:
                logger.warning("[CRM_AUDIT] Failed to add draft reply note to AmoCRM for lead %s", lead_id, exc_info=True)
        except Exception as draft_err:
            logger.error("[AUDITOR] Failed to save draft in Telegram for user %s: %s", telegram_user_id, draft_err)


async def _create_follow_up(self, lead, lead_id, next_step_task, existing_tasks):
    from src.services.core.crm.auditor.classifier import logger

    # Create task in AmoCRM (with duplication prevention)
    if next_step_task:
        next_step_task_clean = next_step_task.strip()
        # Double check duplication logic
        is_dup = self.is_duplicate_task(next_step_task_clean, existing_tasks)
        if is_dup:
            logger.info("[AUDITOR] Skipped creating duplicate task for lead %s: %s", lead_id, next_step_task_clean)
            try:
                dup_note = f"🤖 **Oisha-OS Eslatma:**\nKeyingi qadam vazifasi ('{next_step_task_clean}') bitimda allaqachon faol yoki bajarilganligi sababli takroran yaratilmadi."
                await asyncio.to_thread(self.amocrm.add_lead_note, int(lead_id), dup_note)
            except Exception:
                logger.warning("[CRM_AUDIT] Failed to add duplicate task note to AmoCRM for lead %s", lead_id, exc_info=True)
        else:
            try:
                responsible_user_id = lead.get("responsible_user_id")
                # Calculate tomorrow at 18:00 local time (GMT+5 offset)
                from src.utils.task_scheduler import task_deadline
                complete_till = task_deadline(due_in_hours=24)

                task_text = f"🤖 Oisha-OS Keyingi Qadam:\n{next_step_task_clean}"
                await self.amocrm.create_task(
                    element_id=int(lead_id),
                    text=task_text,
                    complete_till=complete_till,
                    responsible_user_id=responsible_user_id,
                )
                logger.info("[AUDITOR] Created follow-up task in AmoCRM for lead %s (responsible: %s).", lead_id, responsible_user_id)
            except Exception as task_err:
                logger.error("[AUDITOR] Failed to create follow-up task in AmoCRM for lead %s: %s", lead_id, task_err)


async def _tag_lead(self, lead_id, category, temperature, temperature_reason):
    from src.services.core.crm.auditor.classifier import logger

    # Tag lead in AmoCRM automatically
    try:
        add_tag = getattr(self.amocrm, "add_lead_tag", None)
        if callable(add_tag):
            await _maybe_await(add_tag(int(lead_id), category))
            logger.info("[AUDITOR] Auto-tagged lead %s as '%s' in AmoCRM.", lead_id, category)
            if temperature:
                await _maybe_await(add_tag(int(lead_id), temperature))
                logger.info(
                    "[AUDITOR] Auto-tagged lead %s as '%s' in AmoCRM (%s).",
                    lead_id, temperature, temperature_reason,
                )
    except Exception as tag_err:
        logger.warning("[AUDITOR] Failed to tag lead %s as '%s' in AmoCRM: %s", lead_id, category, tag_err)


