from pathlib import Path
path = Path('/home/baxti/oisha-os/src/main.py')
text = path.read_text(encoding='utf-8')
old = """    history = []
    async for msg in client.iter_messages(chat_id, limit=5):
        history.append(f\"{'Mijoz' if msg.incoming else 'Siz'}: {msg.text}\")
    history_context = \"\\n\".join(history)
"""
new = """    history = []
    async for msg in client.iter_messages(chat_id, limit=5):
        msg_text = getattr(msg, 'text', None) or getattr(msg, 'raw_text', None) or ''
        if not msg_text:
            continue
        is_outgoing = bool(getattr(msg, 'out', False))
        speaker = 'Siz' if is_outgoing else 'Mijoz'
        history.append(f\"{speaker}: {msg_text}\")
    history_context = \"\\n\".join(history)
"""
if old not in text:
    raise SystemExit('target snippet not found')
backup = path.with_suffix('.py.bak-shadow')
backup.write_text(text, encoding='utf-8')
path.write_text(text.replace(old, new, 1), encoding='utf-8')
print('patched')
