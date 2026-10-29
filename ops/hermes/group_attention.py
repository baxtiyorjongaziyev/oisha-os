"""Scoped, durable unanswered-question tracking for the Hermes Telegram adapter."""
import asyncio
import json
import logging
import os
import re
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

log = logging.getLogger(__name__)
CHATS = {-1003792973489, -1003854308552, -1003967389019,
         -1002450888212, -1003114662117}
QUESTION = re.compile(r"\?|\b(kim|qachon|qayerda|nega|nimaga|qancha|qanday)\b", re.I)


class Attention:
    def __init__(self, adapter):
        self.adapter = adapter
        home = Path(os.environ.get('HERMES_HOME', '/home/hermes/.hermes'))
        path = home / 'group_attention.sqlite'
        self.db = sqlite3.connect(path)
        os.chmod(path, 0o600)
        self.db.execute('''CREATE TABLE IF NOT EXISTS questions (
            chat INTEGER, message INTEGER, topic INTEGER, target TEXT,
            payload TEXT, due REAL, status TEXT DEFAULT 'pending',
            PRIMARY KEY(chat,message,target))''')
        self.db.commit()

    def observe(self, msg):
        if msg.chat.id not in CHATS or not msg.from_user or msg.from_user.is_bot:
            return
        if self.adapter._topic_gates_pass(msg.message_thread_id, warn_non_numeric=False) is False:
            return
        allowed = self.adapter._telegram_allowed_chats()
        if allowed and str(msg.chat.id) not in allowed:
            return
        reply = msg.reply_to_message
        targets = {str(msg.from_user.id), '@' + (msg.from_user.username or '').lower()}
        if reply:
            for target in targets | {''}:
                self.db.execute("UPDATE questions SET status='answered' WHERE chat=? AND message=? AND target=? AND status='pending'",
                                (msg.chat.id, reply.message_id, target))
        text = msg.text or ''
        # Explicitly addressed Oisha turns are handled immediately by the main adapter.
        if self.adapter._message_mentions_bot(msg) or self.adapter._message_matches_mention_patterns(msg):
            self.db.commit()
            return
        if not QUESTION.search(text) or text.startswith('/'):
            self.db.commit()
            return
        people = set()
        for entity in msg.entities or ():
            if entity.type == 'mention':
                people.add(msg.parse_entity(entity).lower())
            elif entity.type == 'text_mention' and entity.user and not entity.user.is_bot:
                people.add(str(entity.user.id))
        if reply and reply.from_user and not reply.from_user.is_bot:
            people.add('@' + reply.from_user.username.lower() if reply.from_user.username else str(reply.from_user.id))
        people -= targets
        payload = json.dumps(msg.to_dict(), ensure_ascii=False, default=str)
        # Seven-day retention; old questions are not revived after long downtime.
        self.db.execute('DELETE FROM questions WHERE due<?', (time.time() - 7 * 86400,))
        for person in people or {''}:
            self.db.execute('INSERT OR IGNORE INTO questions(chat,message,topic,target,payload,due) VALUES(?,?,?,?,?,?)',
                            (msg.chat.id, msg.message_id, msg.message_thread_id, person, payload, time.time() + 1800))
        self.db.commit()

    async def tick(self):
        # Workday messages only; no overnight reminders or weekend interruptions.
        now = datetime.now(ZoneInfo('Asia/Tashkent'))
        if now.weekday() == 6 or not 9 <= now.hour < 19:
            return
        self.db.execute("UPDATE questions SET status='expired' WHERE status='pending' AND due<?", (time.time() - 86400,))
        rows = self.db.execute("SELECT chat,message,topic,target,payload FROM questions WHERE status='pending' AND due<=? ORDER BY due LIMIT 3", (time.time(),)).fetchall()
        for chat, mid, topic, target, payload in rows:
            allowed = self.adapter._telegram_allowed_chats()
            if allowed and str(chat) not in allowed:
                continue
            if self.adapter._topic_gates_pass(topic, warn_non_numeric=False) is False:
                continue
            # At-most-once delivery: an uncertain network result is never blindly retried.
            changed = self.db.execute("UPDATE questions SET status='dispatching' WHERE chat=? AND message=? AND target=? AND status='pending'", (chat, mid, target)).rowcount
            self.db.commit()
            if not changed:
                continue
            try:
                await self.deliver(chat, mid, topic, target, payload)
                status = 'delivered'
            except Exception:
                log.warning('Attention delivery uncertain chat=%s message=%s', chat, mid)
                status = 'uncertain'
            self.db.execute('UPDATE questions SET status=? WHERE chat=? AND message=? AND target=?', (status, chat, mid, target))
            self.db.commit()

    async def deliver(self, chat, mid, topic, target, payload):
        from telegram import Message, ReplyParameters
        if target:
            mention = target if target.startswith('@') else f'<a href="tg://user?id={int(target)}">Hamkasb</a>'
            await self.adapter._bot.send_message(
                chat_id=chat, message_thread_id=topic,
                reply_parameters=ReplyParameters(message_id=mid, allow_sending_without_reply=False),
                text=f'{mention}, yuqoridagi savolga bog‘langan javobni ko‘rmadim. Imkon bo‘lsa, qisqacha javob yoki qachon aniqlashingizni yozib qo‘ysangiz.',
                parse_mode='HTML')
            return
        from gateway.platforms.base import MessageType
        msg = Message.de_json(json.loads(payload), self.adapter._bot)
        if not self.adapter._is_user_authorized_from_message(msg):
            return
        event = self.adapter._build_message_event(msg, MessageType.TEXT)
        event.text = ('Guruhdagi quyidagi savolga 30 daqiqa ichida bog‘langan reply kelmadi. '
                      'Faqat tekshirilgan ma’lumot bilan qisqa javob ber; shaxslar nomidan va’da berma. '
                      'Ma’lumot yetmasa buni ayt. Hech qanday tashqi yozish amalini bajarma.\n\n' + (msg.text or ''))
        await self.adapter.handle_message(event)

    async def loop(self):
        try:
            while True:
                await asyncio.sleep(60)
                try:
                    await self.tick()
                except Exception:
                    log.warning('Attention sweep failed')
        finally:
            self.db.close()


def start(adapter):
    prior = getattr(adapter, '_oisha_attention_task', None)
    if prior and not prior.done():
        return
    adapter._oisha_attention = Attention(adapter)
    adapter._oisha_attention_task = asyncio.create_task(adapter._oisha_attention.loop())


def observe(adapter, msg):
    start(adapter)
    adapter._oisha_attention.observe(msg)
