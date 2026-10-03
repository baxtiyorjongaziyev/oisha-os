async def analyze_and_save(self, lead, lead_id, context, existing_tasks):
    tasks_history = self.serialize_tasks(existing_tasks)

    lead_details = self.serialize_lead_details(lead)

    _, call_summary = await self.get_call_notes_and_transcripts(int(lead_id), context["phone"])

    notes_history = await self.get_lead_notes_history(int(lead_id))

    category, explanation, detailed_summary, next_step_task, telegram_draft_reply = await self.classify_contact(
        lead_name=context["lead_name"],
        contact_name=context["contact_name"],
        phone=context["phone"],
        username=context["username"],
        call_summary=call_summary,
        telegram_history=context["telegram_history"],
        lead_details=lead_details,
        group_history=context["group_history"],
        tasks_history=tasks_history,
        notes_history=notes_history,
        telegram_unanswered_info=context["telegram_unanswered_info"],
    )

    # Score lead temperature (Iliq/Sovuq) -- only meaningful for actual clients
    temperature = None
    temperature_reason = ""
    if category == "Mijoz":
        temperature, temperature_reason = self.score_lead_temperature(
            lead=lead,
            telegram_history=context["telegram_history"] + ("\n\n" + context["group_history"] if context["group_history"] else ""),
            call_summary=call_summary,
            notes_history=notes_history,
            is_unanswered=context["is_unanswered_tg"] or context["is_unanswered_group"],
        )

    await self.save_audit_result(
        lead_id=int(lead_id),
        lead_name=context["lead_name"],
        contact_id=context["contact_id"],
        contact_name=context["contact_name"],
        phone=context["phone"],
        username=context["username"],
        telegram_user_id=context["telegram_user_id"],
        call_summary=call_summary,
        telegram_history=context["telegram_history"] + ("\n\n" + context["group_history"] if context["group_history"] else ""),
        category=category,
        explanation=explanation,
        detailed_summary=detailed_summary,
        task_text=next_step_task,
        temperature=temperature,
    )

    return category, detailed_summary, next_step_task, telegram_draft_reply, temperature, temperature_reason
