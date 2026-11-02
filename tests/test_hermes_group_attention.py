"""Unit tests for Hermes group_attention module."""
import os
import sqlite3
import pytest
from unittest.mock import MagicMock

from ops.hermes.group_attention import Attention, is_real_reply


def test_is_real_reply():
    # 1. No reply
    msg = MagicMock(reply_to_message=None, message_thread_id=None)
    assert is_real_reply(msg) is False

    # 2. Forum topic anchor (forum_topic_created object)
    topic_created_reply = MagicMock(message_id=115, forum_topic_created=MagicMock())
    msg_in_topic = MagicMock(reply_to_message=topic_created_reply, message_thread_id=115)
    assert is_real_reply(msg_in_topic) is False

    # 3. Forum topic anchor (message_id == message_thread_id without forum_topic_created)
    anchor_reply = MagicMock(message_id=115, forum_topic_created=None)
    msg_in_topic2 = MagicMock(reply_to_message=anchor_reply, message_thread_id=115)
    assert is_real_reply(msg_in_topic2) is False

    # 4. Real reply inside a forum topic
    real_user_reply = MagicMock(message_id=12891, forum_topic_created=None)
    msg_real_reply = MagicMock(reply_to_message=real_user_reply, message_thread_id=115)
    assert is_real_reply(msg_real_reply) is True

    # 5. Real reply in a non-forum chat
    msg_direct_reply = MagicMock(reply_to_message=MagicMock(message_id=50, forum_topic_created=None), message_thread_id=None)
    assert is_real_reply(msg_direct_reply) is True


def test_observe_forum_topic_and_reply_cancellation(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    adapter = MagicMock()
    adapter._topic_gates_pass.return_value = True
    adapter._telegram_allowed_chats.return_value = set()
    adapter._message_mentions_bot.return_value = False
    adapter._message_matches_mention_patterns.return_value = False

    attention = Attention(adapter)
    chat_id = -1003854308552
    thread_id = 115

    # 1. Baxtiyorjon asks a question in topic 115 targeting @RayxonJonbranding.
    # In Telegram Bot API, reply_to_message points to topic creation message.
    topic_anchor = MagicMock(
        message_id=thread_id,
        forum_topic_created=MagicMock(),
        from_user=MagicMock(id=8084726703, is_bot=False, username=None)
    )
    mention_entity = MagicMock(type='mention')
    q_msg = MagicMock()
    q_msg.chat.id = chat_id
    q_msg.message_id = 12891
    q_msg.message_thread_id = thread_id
    q_msg.from_user = MagicMock(id=150074828, is_bot=False, username="BaxtiyorjonGaziyev")
    q_msg.reply_to_message = topic_anchor
    q_msg.text = "@RayxonJonbranding urinishlariz kammi?"
    q_msg.entities = [mention_entity]
    q_msg.parse_entity.return_value = "@RayxonJonbranding"
    q_msg.to_dict.return_value = {"text": q_msg.text}

    attention.observe(q_msg)

    # Verify that ONLY @rayxonjonbranding was recorded, NOT 8084726703
    rows = attention.db.execute("SELECT target, status FROM questions WHERE message=12891").fetchall()
    assert len(rows) == 1
    assert rows[0] == ("@rayxonjonbranding", "pending")

    # 2. Baxtiyorjon replies to his own message -> should NOT resolve
    self_reply_msg = MagicMock()
    self_reply_msg.chat.id = chat_id
    self_reply_msg.message_id = 12892
    self_reply_msg.message_thread_id = thread_id
    self_reply_msg.from_user = MagicMock(id=150074828, is_bot=False, username="BaxtiyorjonGaziyev")
    self_reply_msg.reply_to_message = MagicMock(
        message_id=12891,
        forum_topic_created=None,
        from_user=MagicMock(id=150074828, is_bot=False)
    )
    self_reply_msg.text = "va bugungi rejani ham yozing"
    self_reply_msg.entities = []
    attention.observe(self_reply_msg)

    rows = attention.db.execute("SELECT target, status FROM questions WHERE message=12891").fetchall()
    assert rows[0] == ("@rayxonjonbranding", "pending")

    # 3. Rayxona replies to Baxtiyorjon's question -> should resolve to 'answered'
    ans_msg = MagicMock()
    ans_msg.chat.id = chat_id
    ans_msg.message_id = 12893
    ans_msg.message_thread_id = thread_id
    ans_msg.from_user = MagicMock(id=987654321, is_bot=False, username="RayxonJonbranding")
    ans_msg.reply_to_message = MagicMock(
        message_id=12891,
        forum_topic_created=None,
        from_user=MagicMock(id=150074828, is_bot=False)
    )
    ans_msg.text = "Xozir kopaytiramiz"
    ans_msg.entities = []
    attention.observe(ans_msg)

    rows = attention.db.execute("SELECT target, status FROM questions WHERE message=12891").fetchall()
    assert rows[0] == ("@rayxonjonbranding", "answered")
