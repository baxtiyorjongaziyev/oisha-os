"""Durable claims prevent automatic retry of uncertain Telegram sends."""
import hashlib
import sqlite3
import time
from pathlib import Path


class DeliveryLedger:
    def __init__(self, path: str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS deliveries (key TEXT PRIMARY KEY, payload_hash TEXT NOT NULL, state TEXT NOT NULL, message_id TEXT, updated REAL NOT NULL)')

    def connect(self):
        return sqlite3.connect(self.path, timeout=10)

    def claim(self, key: str, text: str) -> bool:
        digest = hashlib.sha256(text.encode()).hexdigest()
        with self.connect() as db:
            result = db.execute('INSERT OR IGNORE INTO deliveries VALUES (?, ?, ?, NULL, ?)', (key, digest, 'sending', time.time()))
            return result.rowcount == 1

    def finish(self, key: str, message_id: str | None):
        state = 'delivered' if message_id else 'uncertain'
        with self.connect() as db:
            db.execute('UPDATE deliveries SET state=?, message_id=?, updated=? WHERE key=?', (state, message_id, time.time(), key))

    def reconcile(self, key: str, *, verified_message_id: str | None = None,
                  verified_not_sent: bool = False) -> bool:
        """Resolve uncertainty only after an external delivery check."""
        if bool(verified_message_id) == bool(verified_not_sent):
            raise ValueError('Provide exactly one verified outcome')
        with self.connect() as db:
            if verified_not_sent:
                result = db.execute("DELETE FROM deliveries WHERE key=? AND state IN ('sending','uncertain')", (key,))
            else:
                result = db.execute("UPDATE deliveries SET state='delivered', message_id=?, updated=? WHERE key=? AND state IN ('sending','uncertain')", (verified_message_id, time.time(), key))
            return result.rowcount == 1


async def send_once(bot, *, chat_id, text, key, ledger, **kwargs):
    if not ledger.claim(key, text):
        return None
    try:
        response = await bot.send_message(chat_id, text, **kwargs)
    except BaseException:
        ledger.finish(key, None)
        raise
    mid = getattr(response, 'message_id', None)
    if mid is None:
        mid = getattr(response, 'id', None)
    ledger.finish(key, str(mid) if mid is not None else None)
    return response
