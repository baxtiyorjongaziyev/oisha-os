import json

with open('data/private_chats_data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

with open('data/chats_readable.txt', 'w', encoding='utf-8') as out:
    for chat in data['chats']:
        username = chat.get('username') or 'None'
        out.write(f"=== CHAT WITH: {chat['name']} (@{username}) ===\n")
        # Messages are returned newest first, let's reverse to read chronologically
        for m in reversed(chat['messages']):
            date_str = m['date'][:16].replace('T', ' ')
            out.write(f"[{date_str}] {m['sender']}: {m['text']}\n")
        out.write("\n\n")
print("SUCCESS_READABLE")
