from pathlib import Path

path = Path('/home/baxti/oisha-os/src/main.py')
text = path.read_text(encoding='utf-8')

helper_block = """
def _income_state_key(message_id: int) -> str:
    return f"income_workflow:{message_id}"


def _income_gate_key(message_id: int) -> str:
    return f"income_workflow_gate:{message_id}"


def _normalize_income_lookup(text: str) -> str:
    normalized = re.sub(r"[^\\w]+", " ", (text or "").lower(), flags=re.UNICODE)
    return " ".join(normalized.split())


def _extract_income_amount(text: str) -> Dict[str, Any]:
    lowered = (text or "").lower()
    currency = "USD" if ("$" in lowered or "usd" in lowered) else "UZS"
    matches = list(re.finditer(r"\\d[\\d\\s,.]*", text or ""))
    if not matches:
        return {"raw": "noma'lum", "value": None, "currency": currency}

    raw_amount = max(matches, key=lambda match: len(match.group(0))).group(0).strip()
    if currency == "USD":
        cleaned = raw_amount.replace(" ", "").replace(",", ".")
        if cleaned.count(".") > 1:
            parts = cleaned.split(".")
            cleaned = "".join(parts[:-1]) + "." + parts[-1]
        try:
            value = float(cleaned)
        except ValueError:
            value = None
    else:
        cleaned = re.sub(r"[^\\d]", "", raw_amount)
        value = int(cleaned) if cleaned else None

    return {"raw": raw_amount, "value": value, "currency": currency}


def _is_kirim_topic_message(message: Any) -> bool:
    if not settings.TOPIC_KIRIM_ID:
        return False

    topic_id = settings.TOPIC_KIRIM_ID
    direct_reply_id = getattr(message, "reply_to_msg_id", None)
    reply_to = getattr(message, "reply_to", None)
    reply_top_id = getattr(message, "reply_to_top_id", None) or getattr(reply_to, "reply_to_top_id", None)
    forum_topic = getattr(reply_to, "forum_topic", False)

    return bool(
        direct_reply_id == topic_id
        or reply_top_id == topic_id
        or (forum_topic and direct_reply_id == topic_id)
    )


def _is_group_open_confirmation(text: str) -> bool:
    lowered = (text or "").lower()
    keywords = (
        "guruh ochildi",
        "group opened",
        "group open",
        "gruppa ochildi",
        "mijoz bilan guruh",
        "client group",
    )
    return any(keyword in lowered for keyword in keywords) or "t.me/" in lowered


def _find_project_for_income(message_text: str) -> Optional[Dict[str, Any]]:
    from src.services.airtable_sync import AirtableSync

    sync = AirtableSync()
    projects = sync.get_projects()
    if not projects:
        return None

    normalized_text = _normalize_income_lookup(message_text)
    best_match = None
    best_score = 0.0

    for project in projects:
        fields = project.get("fields", {})
        project_name = AirtableSync._get_field(fields, "project_name", "") or ""
        normalized_name = _normalize_income_lookup(project_name)
        if len(normalized_name) < 4:
            continue

        if normalized_name in normalized_text:
            score = 2.0 + (len(normalized_name) / 1000)
        else:
            tokens = [token for token in normalized_name.split() if len(token) >= 4]
            if not tokens:
                continue
            hits = sum(1 for token in tokens if token in normalized_text)
            score = hits / len(tokens)

        if score > best_score:
            best_score = score
            best_match = {
                "record_id": project.get("id"),
                "project_name": project_name,
            }

    return best_match if best_score >= 0.6 else None


def _count_income_records_for_project(project_record_id: str) -> int:
    from src.services.airtable_sync import AirtableSync

    sync = AirtableSync()
    records = sync.get_finance_records()
    count = 0
    for record in records:
        if record.get("_record_type") != "income":
            continue
        if project_record_id in (record.get("fields", {}).get("Loyiha nomi") or []):
            count += 1
    return count


def _save_income_workflow_state(db: Database, payload: Dict[str, Any]) -> None:
    db.set_state(_income_state_key(int(payload["original_message_id"])), json.dumps(payload, ensure_ascii=False))
    gate_message_id = payload.get("gate_message_id")
    if gate_message_id:
        db.set_state(_income_gate_key(int(gate_message_id)), str(payload["original_message_id"]))


def _load_income_workflow_state(db: Database, reply_message_id: Optional[int]) -> Optional[Dict[str, Any]]:
    if not reply_message_id:
        return None

    raw = db.get_state(_income_state_key(int(reply_message_id)))
    if raw:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    original_id = db.get_state(_income_gate_key(int(reply_message_id)))
    if not original_id:
        return None

    raw = db.get_state(_income_state_key(int(original_id)))
    if not raw:
        return None

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


"""

confirm_block = """    # [V4.7] Callback Query Handler for Payment Confirmation
    if bot_client:
        @bot_client.on(events.CallbackQuery(data=re.compile(b\"confirm_pay:.*\")))
        async def confirm_payment_handler(event):
            sender_id = event.sender_id
            data = event.data.decode('utf-8').split(':')
            manager_id = int(data[1])

            workflow = None
            if len(data) >= 4 and data[3] == 'v2':
                workflow = _load_income_workflow_state(db, int(data[2]))

            amount = workflow.get('amount_raw') if workflow else (data[2] if len(data) > 2 else \"noma'lum\")

            user_info = db.get_user_info(sender_id)
            role = user_info.get('role') if user_info else None

            if sender_id != settings.OWNER_ID and role != 'Finance':
                await event.answer(\"Oisha: faqat owner yoki Finance to'lovni tasdiqlashi mumkin.\", alert=True)
                return

            if workflow and workflow.get('requires_client_group') and not workflow.get('client_group_confirmed'):
                await event.answer(\"Avval mijoz bilan guruh ochilganini shu threadda tasdiqlang.\", alert=True)
                return

            await event.answer(\"To'lov tasdiqlandi.\", alert=True)

            if workflow:
                workflow['finance_confirmed'] = True
                workflow['finance_confirmed_by'] = sender_id
                _save_income_workflow_state(db, workflow)

                lines = [
                    \"TO'LOV TASDIQLANDI\",
                    f\"Summa: {amount}\",
                    f\"Loyiha: {workflow.get('project_name') or 'noma-lum'}\",
                    \"Mas'ul: Moliya / Admin\",
                ]
                if workflow.get('requires_client_group'):
                    lines.append(\"Mijoz bilan guruh ochilgani tasdiqlandi.\")
                await event.edit('\\n'.join(lines))
                return

            await event.edit(f\"TO'LOV TASDIQLANDI\\nSumma: {amount}\\nMas'ul: Moliya / Admin\")
"""

handler_block = """    # [NEW] Kirim (Inflow) Celebration Listener
    if settings.TOPIC_KIRIM_ID:
        @bot_client.on(events.NewMessage(chats=settings.TEAM_GROUP_ID))
        async def kirim_celebration_handler(event):
            if not _is_kirim_topic_message(event.message):
                return

            sender = await event.get_sender()
            if getattr(sender, 'bot', False):
                return

            text = (event.raw_text or '').strip()
            lowered = text.lower()
            reply_to_id = getattr(event.message, 'reply_to_msg_id', None)
            workflow = _load_income_workflow_state(db, reply_to_id)

            if workflow and _is_group_open_confirmation(text):
                if not workflow.get('requires_client_group'):
                    await event.reply(\"Bu kirim uchun mijoz guruhi majburiy emas.\")
                    return

                if workflow.get('client_group_confirmed'):
                    await event.reply(\"Mijoz bilan guruh ochilgani oldinroq qayd qilingan.\")
                    return

                workflow['client_group_confirmed'] = True
                workflow['client_group_confirmed_by'] = sender.id
                workflow['client_group_confirmation_text'] = text
                _save_income_workflow_state(db, workflow)

                from telethon import Button
                buttons = [[Button.inline(\"Tasdiqlash (Moliya)\", data=f\"confirm_pay:{workflow['manager_id']}:{workflow['original_message_id']}:v2\")]]
                await event.reply(\"Mijoz bilan guruh ochilgani qayd qilindi. Endi moliya tasdiqlashi mumkin.\", buttons=buttons)
                return

            is_inflow = re.search(r'\\d+', text) and any(kw in lowered for kw in ['$', 'som', \"so'm\", 'sum', 'usd', 'uzs', 'kirim', \"to'lov\", 'tulov'])
            if not is_inflow:
                return

            sender_id = sender.id
            first_name = getattr(sender, 'first_name', 'Xodim')
            amount_info = _extract_income_amount(text)
            amount_str = amount_info.get('raw') or \"noma'lum\"

            logger.info(f\"[KIRIM] Generating celebration for {first_name} for {amount_str}...\")

            try:
                celebration_text = await advisor_agent.generate_sales_celebration(manager_name=first_name, amount=amount_str)
            except Exception as e:
                logger.error(f\"[CELEBRATION ERROR] AI failed: {e}\")
                celebration_text = f\"BARAKALLA, {first_name}!\\n\\nSizni ajoyib natija bilan tabriklaymiz!\"

            project_match = _find_project_for_income(text)
            is_first_payment = False
            if project_match and project_match.get('record_id'):
                is_first_payment = _count_income_records_for_project(project_match['record_id']) == 0

            workflow = {
                'original_message_id': event.message.id,
                'manager_id': sender_id,
                'manager_name': first_name,
                'amount_raw': amount_str,
                'amount_value': amount_info.get('value'),
                'currency': amount_info.get('currency'),
                'source_text': text,
                'project_id': (project_match or {}).get('record_id'),
                'project_name': (project_match or {}).get('project_name'),
                'requires_client_group': bool(is_first_payment and project_match),
                'client_group_confirmed': False,
                'finance_confirmed': False,
            }

            if workflow['requires_client_group']:
                gate_message = await event.reply(
                    f\"{celebration_text}\\n\\nBirinchi kirim aniqlandi.\\n\"
                    f\"Loyiha: {workflow.get('project_name')}\\n\"
                    \"Mijoz bilan guruh ochilmaguncha moliya tasdiqlamaydi. Shu threadda 'guruh ochildi' deb yozing yoki guruh linkini yuboring.\"
                )
            else:
                from telethon import Button
                buttons = [[Button.inline(\"Tasdiqlash (Moliya)\", data=f\"confirm_pay:{sender_id}:{event.message.id}:v2\")]]
                gate_message = await event.reply(celebration_text, parse_mode='html', buttons=buttons)

            workflow['gate_message_id'] = gate_message.id
            _save_income_workflow_state(db, workflow)
            logger.info(f\"[KIRIM] Workflow created for {first_name}. First payment={workflow['requires_client_group']}\")
"""

if 'def _income_state_key' not in text:
    if 'import json\n' not in text:
        text = text.replace('import asyncio\n', 'import asyncio\nimport json\n', 1)
    anchor = 'async def push_block_to_amocrm(user_id, phone, block_text):\n'
    if anchor not in text:
        raise SystemExit('push_block anchor not found')
    text = text.replace(anchor, helper_block + anchor, 1)

confirm_start = text.index('    # [V4.7] Callback Query Handler for Payment Confirmation')
confirm_end = text.index('    # 4. Botni ishga tushirish', confirm_start)
text = text[:confirm_start] + confirm_block + '\n\n' + text[confirm_end:]

handler_start = text.index('    # [NEW] Kirim (Inflow) Celebration Listener')
handler_end = text.index('    print("', handler_start)
text = text[:handler_start] + handler_block + '\n' + text[handler_end:]

path.write_text(text, encoding='utf-8')
print('patched main.py')
