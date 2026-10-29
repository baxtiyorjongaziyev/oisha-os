"""Wire durable delivery claims into the reviewed production check-in lane."""
from pathlib import Path
import shutil

path = Path('/home/ubuntu/oisha-os/src/schedulers/remote_staff_checkin_scheduler.py')
source = path.read_text()
old = '''    try:
        if topic_id:
            await bot_runtime.send_message(
                chat_id, text, parse_mode="HTML", message_thread_id=topic_id
            )
        else:
            await bot_runtime.send_message(chat_id, text, parse_mode="HTML")

        # Persist dispatch state'''
new = '''    from src.services.response_quality.delivery_ledger import DeliveryLedger, send_once
    ledger = DeliveryLedger("data/checkin_delivery.db")
    delivery_key = f"checkin:{chat_id}:{topic_id}:{rep_key}:{now:%Y-%m-%d-%H}"
    try:
        kwargs = {"parse_mode": "HTML"}
        if topic_id:
            kwargs["message_thread_id"] = topic_id
        result = await send_once(
            bot_runtime, chat_id=chat_id, text=text, key=delivery_key,
            ledger=ledger, **kwargs,
        )
        if result is None:
            return False

        # Persist dispatch state'''
if old not in source:
    raise SystemExit('Unexpected scheduler; unchanged')
shutil.copy2(path, path.with_suffix('.py.bak-ledger-20261029'))
source = source.replace(old, new)
source = source.replace('    now = now_fn()\n    if not is_work_hour(now)', '    now = now_fn()\n    if now.hour == 13 or not 10 <= now.hour < 19:\n        return False\n    if not is_work_hour(now)')
source = source.replace('    text = build_checkin_message(seller_name, tg_handle, now, calls_info)', '''    if calls_info is None:
        logger.warning("[CHECKIN] Telephony unavailable; no activity claim sent")
        return False
    text = build_checkin_message(seller_name, tg_handle, now, calls_info)''')
path.write_text(source)
print('Installed durable check-in claims, lunch/closing gate and unavailable-source gate')
