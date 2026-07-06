from __future__ import annotations

from types import SimpleNamespace
import pytest

from src.database import Database
from src.database_pool import SmartRow
from src.services.core.finance.hisobchi_engine import HisobchiEngine
from src.services.core.finance.hisobchi_handlers import (
    handle_kirim_chiqim_text,
    handle_topic_plain_text,
)
from src.services.core.finance.hisobchi_schema import init_hisobchi_tables
from src.handlers.message_handler import process_hisobchi


class DatabaseWrapper:
    def __init__(self, db: Database):
        self.db = db

    async def execute(self, query: str, params: list | None = None) -> list:
        conn = await self.db.get_connection()
        async with conn.execute(query, params or []) as cursor:
            description = cursor.description
            columns = [desc[0] for desc in description] if description else []
            rows = await cursor.fetchall()
            return [SmartRow(row, columns) for row in rows]

    async def commit(self) -> None:
        conn = await self.db.get_connection()
        await conn.commit()

    async def get_connection(self):
        return await self.db.get_connection()


@pytest.fixture
async def temp_db(tmp_path):
    db = Database(str(tmp_path / "hisobchi_group.db"))
    await db.init_instance()
    wrapped = DatabaseWrapper(db)
    await init_hisobchi_tables(wrapped)
    yield wrapped
    await db.close()


class _FakeReplyTo:
    def __init__(self, reply_to_msg_id):
        self.reply_to_msg_id = reply_to_msg_id


class _FakeMessage:
    def __init__(self, text, reply_to_msg_id=None, photo=None):
        self.message = text
        self.reply_to = _FakeReplyTo(reply_to_msg_id) if reply_to_msg_id else None
        self.photo = photo
        self.voice = None
        self.id = 123


class _FakeEvent:
    def __init__(self, chat_id, text, reply_to_msg_id=None, photo=None, is_private=False):
        self.chat_id = chat_id
        self.message = _FakeMessage(text, reply_to_msg_id, photo)
        self.is_private = is_private
        self.out = False
        self.replied = []

    async def reply(self, text, **kwargs):
        self.replied.append(text)
        return SimpleNamespace(id=999)

    async def get_sender(self):
        return SimpleNamespace(id=111, first_name="Test User", bot=False)


@pytest.mark.asyncio
async def test_handle_kirim_chiqim_text_optional_slash(temp_db) -> None:
    engine = HisobchiEngine(temp_db)

    # 1. With slash
    ev1 = _FakeEvent(-1002, "/chiqim 50000 Kofe | Biznes uchun")
    res1 = await handle_kirim_chiqim_text(ev1, engine)
    assert res1 is True
    assert len(ev1.replied) == 1
    assert "saqlandi" in ev1.replied[0]

    # 2. Without slash
    ev2 = _FakeEvent(-1002, "kirim 150000 Avans")
    res2 = await handle_kirim_chiqim_text(ev2, engine)
    assert res2 is True
    assert len(ev2.replied) == 1
    assert "saqlandi" in ev2.replied[0]

    rows = await temp_db.execute("SELECT amount, direction, merchant, reason FROM hisobchi_transactions ORDER BY id")
    assert len(rows) == 2
    assert rows[0]["amount"] == 50000
    assert rows[0]["direction"] == "out"
    assert rows[0]["merchant"] == "Kofe"
    assert rows[0]["reason"] == "Biznes uchun"

    assert rows[1]["amount"] == 150000
    assert rows[1]["direction"] == "in"
    assert rows[1]["merchant"] == "Avans"


@pytest.mark.asyncio
async def test_handle_topic_plain_text_digits(temp_db) -> None:
    engine = HisobchiEngine(temp_db)

    # Chiqim topic plain text log
    ev = _FakeEvent(-1002, "40000 taxi")
    res = await handle_topic_plain_text(ev, engine, "40000 taxi", "out")
    assert res is True
    assert len(ev.replied) == 1
    assert "Chiqim: <b>40 000 UZS</b>" in ev.replied[0]

    rows = await temp_db.execute("SELECT amount, direction, merchant FROM hisobchi_transactions")
    assert len(rows) == 1
    assert rows[0]["amount"] == 40000
    assert rows[0]["direction"] == "out"
    assert rows[0]["merchant"] == "taxi"


@pytest.mark.asyncio
async def test_process_hisobchi_integration(monkeypatch, temp_db) -> None:
    from src.settings import settings
    
    # Configure mock group & topics
    monkeypatch.setattr(settings, "HISOBCHI_FINANCE_GROUP_ID", -100999)
    monkeypatch.setattr(settings, "HISOBCHI_KIRIM_TOPIC_ID", 10)
    monkeypatch.setattr(settings, "HISOBCHI_CHIQIM_TOPIC_ID", 20)

    msg_controller = SimpleNamespace(db=temp_db)

    # Send plain text message inside Chiqim topic (topic ID = 20)
    ev = _FakeEvent(chat_id=-100999, text="25000 yandex taxi", reply_to_msg_id=20)
    
    res = await process_hisobchi(
        event=ev,
        client=None,
        sender=SimpleNamespace(id=111, bot=False),
        message_text="25000 yandex taxi",
        msg_controller=msg_controller,
        voice_processor=None,
        settings=settings,
    )
    assert res is True
    assert len(ev.replied) == 1
    assert "25 000 UZS" in ev.replied[0]

    rows = await temp_db.execute("SELECT amount, direction, merchant FROM hisobchi_transactions")
    assert len(rows) == 1
    assert rows[0]["amount"] == 25000
    assert rows[0]["direction"] == "out"
    assert rows[0]["merchant"] == "yandex taxi"
