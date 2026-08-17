from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from src.database import Database
from src.database_pool import SmartRow
from src.services.core.finance.hisobchi_card_parser import parse_card_notification
from src.services.core.finance.hisobchi_engine import HisobchiEngine, _normalize_merchant
from src.services.core.finance.handlers import (
    backfill_card_bot_messages,
    handle_finance_group_reply,
    resolve_finance_destination,
    resync_since_sequential,
)
from src.services.core.telegram.bot_runtime import AiogramBotRuntime
from src.services.core.finance.hisobchi_schema import (
    init_hisobchi_tables,
    ensure_hisobchi_db,
    run_one_time_reset_and_resync,
)


HUMO_SAMPLE = """💸 To'lov
➖ 4.000,00 UZS
📍 AO PAYNET QR DLYA S
💳 HUMOCARD *6224
🕓 22:26 18.06.2026
💰 2.135,00 UZS"""

UZCARD_SAMPLE = """🔴 Platezh
➖ 8 000.00 UZS
💳 ***1393
📍 PAYNET AJ QR DLYA SAMOZANYATIX UZKARD, UZ
🕓 18.06.26 22:26
💵 700.00 UZS"""


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


class _MappingCursor:
    description = [("id", None, None, None, None, None, None)]

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def fetchall(self):
        return [SmartRow([7], ["id"])]


class _MappingConnection:
    def execute(self, query, params):
        return _MappingCursor()

    async def commit(self):
        return None


class _ProductionLikeDatabase:
    async def get_connection(self):
        return _MappingConnection()


@pytest.mark.asyncio
async def test_database_adapter_preserves_turso_mapping_values() -> None:
    adapter = ensure_hisobchi_db(_ProductionLikeDatabase())
    rows = await adapter.execute("SELECT 7 AS id")
    assert rows[0]["id"] == 7


@pytest.fixture
async def temp_db(tmp_path):
    db = Database(str(tmp_path / "hisobchi.db"))
    await db.init_instance()
    wrapped = DatabaseWrapper(db)
    await init_hisobchi_tables(wrapped)
    yield wrapped
    await db.close()


@pytest.mark.asyncio
async def test_production_database_object_is_supported_directly(tmp_path) -> None:
    db = Database(str(tmp_path / "direct.db"))
    await db.init_instance()
    await init_hisobchi_tables(db)
    engine = HisobchiEngine(db)
    tx_id = await engine.save_transaction(
        source_bot="humo",
        direction="out",
        amount=1_000,
        merchant="TEST MERCHANT",
        card_suffix="0001",
        tx_time="12:00 20.06.2026",
        balance=5_000,
        raw_text="test",
    )
    assert tx_id == 1
    await db.close()


def test_real_humo_and_uzcard_notifications_parse() -> None:
    humo = parse_card_notification("@HUMOcardbot", HUMO_SAMPLE)
    uzcard = parse_card_notification("CardXabarBot", UZCARD_SAMPLE)

    assert humo is not None
    assert humo.amount == 4_000
    assert humo.balance == 2_135
    assert humo.card_suffix == "6224"
    assert humo.merchant == "AO PAYNET QR DLYA S"

    assert uzcard is not None
    assert uzcard.amount == 8_000
    assert uzcard.balance == 700
    assert uzcard.card_suffix == "1393"
    assert uzcard.merchant.startswith("PAYNET AJ")


def test_question_text_matches_income_or_expense() -> None:
    engine = HisobchiEngine()
    expense = parse_card_notification("humocardbot", HUMO_SAMPLE)
    assert expense is not None
    income = SimpleNamespace(**{**expense.__dict__, "direction": "in"})

    assert "nima uchun ketdi" in engine.build_finance_question(expense, 1)
    assert "nima uchun keldi" in engine.build_finance_question(income, 2)


def test_merchant_normalization_preserves_unicode_letters() -> None:
    assert _normalize_merchant("O‘ZBEK NON — Chilonzor") == "O‘ZBEK NON CHILONZOR"


@pytest.mark.asyncio
async def test_duplicate_notification_is_saved_once(temp_db) -> None:
    engine = HisobchiEngine(temp_db)
    tx = parse_card_notification("humocardbot", HUMO_SAMPLE)
    assert tx is not None

    first_id, first_created = await engine.save_transaction_once(
        source_bot=tx.source_bot,
        direction=tx.direction,
        amount=tx.amount,
        merchant=tx.merchant,
        card_suffix=tx.card_suffix,
        tx_time=tx.tx_time,
        balance=tx.balance,
        raw_text=HUMO_SAMPLE,
    )
    second_id, second_created = await engine.save_transaction_once(
        source_bot=tx.source_bot,
        direction=tx.direction,
        amount=tx.amount,
        merchant=tx.merchant,
        card_suffix=tx.card_suffix,
        tx_time=tx.tx_time,
        balance=tx.balance,
        raw_text=HUMO_SAMPLE,
    )

    assert (first_created, second_created) == (True, False)
    assert first_id == second_id
    rows = await temp_db.execute("SELECT COUNT(*) AS cnt FROM hisobchi_transactions")
    assert rows[0]["cnt"] == 1


@pytest.mark.asyncio
async def test_two_real_messages_with_same_payment_fields_are_kept(temp_db) -> None:
    engine = HisobchiEngine(temp_db)
    tx = parse_card_notification("humocardbot", HUMO_SAMPLE)
    assert tx is not None
    base = dict(
        source_bot=tx.source_bot,
        direction=tx.direction,
        amount=tx.amount,
        merchant=tx.merchant,
        card_suffix=tx.card_suffix,
        tx_time=tx.tx_time,
        balance=tx.balance,
        raw_text=HUMO_SAMPLE,
    )

    first_id, first_created = await engine.save_transaction_once(
        **base, source_message_id=100
    )
    replay_id, replay_created = await engine.save_transaction_once(
        **base, source_message_id=100
    )
    second_id, second_created = await engine.save_transaction_once(
        **base, source_message_id=101
    )

    assert (first_created, replay_created, second_created) == (True, False, True)
    assert first_id == replay_id
    assert second_id != first_id


@pytest.mark.asyncio
async def test_learning_is_bound_to_exact_transaction_context(temp_db) -> None:
    engine = HisobchiEngine(temp_db)
    await engine.learn_rule(
        merchant="PAYNET",
        card_suffix="6224",
        direction="out",
        amount=4_000,
        category="Ofis interneti",
        ownership="business",
    )

    exact = await engine.get_known_rule("PAYNET", "6224", "out", 4_000)
    other_amount = await engine.get_known_rule("PAYNET", "6224", "out", 8_000)
    other_card = await engine.get_known_rule("PAYNET", "1393", "out", 4_000)

    assert exact == {"category": "Ofis interneti", "ownership": "business"}
    assert other_amount is None
    assert other_card is None


class _DialogsClient:
    async def get_dialogs(self, limit=500):
        return [
            SimpleNamespace(id=-1001, name="Haftalik hisobot"),
            SimpleNamespace(id=-1002, name="Jon Branding Moliya"),
        ]


@pytest.mark.asyncio
async def test_finance_group_is_discovered_by_title(monkeypatch) -> None:
    from src.context import app_ctx
    from src.services.core.finance.handlers import engine_utils as hisobchi_handlers, card_bot_handler, manual_handler

    app_ctx.finance_group_cache = None
    hisobchi_handlers._topic_cache.clear()
    monkeypatch.setattr(
        hisobchi_handlers,
        "_get_finance_config",
        lambda: (None, 11, 22),
    )
    monkeypatch.setattr(hisobchi_handlers.settings, "TEAM_GROUP_ID", -1999)

    assert await resolve_finance_destination(_DialogsClient()) == (-1002, 11, 22)


class _NoFinanceClient:
    async def get_dialogs(self, limit=500):
        return [SimpleNamespace(id=-1001, name="Haftalik hisobot")]

    async def __call__(self, request):
        return SimpleNamespace(topics=[])


@pytest.mark.asyncio
async def test_finance_data_is_not_sent_to_plain_team_group(monkeypatch) -> None:
    from src.context import app_ctx
    from src.services.core.finance.handlers import engine_utils as hisobchi_handlers, card_bot_handler, manual_handler

    app_ctx.finance_group_cache = None
    hisobchi_handlers._topic_cache.clear()
    monkeypatch.setattr(
        hisobchi_handlers,
        "_get_finance_config",
        lambda: (None, None, None),
    )
    monkeypatch.setattr(hisobchi_handlers.settings, "TEAM_GROUP_ID", -1999)

    assert await resolve_finance_destination(_NoFinanceClient()) == (None, None, None)


class _BackfillMessage:
    def __init__(self, msg_id: int, text: str, username: str):
        self.id = msg_id
        self.message = text
        self.text = text
        self.out = False
        self.date = None
        self._sender = SimpleNamespace(username=username)

    async def get_sender(self):
        return self._sender


class _BackfillClient:
    def __init__(self):
        self.sent = []
        self.messages = {
            "humocardbot": [_BackfillMessage(10, HUMO_SAMPLE, "HUMOcardbot")],
            "cardxabarbot": [_BackfillMessage(20, UZCARD_SAMPLE, "CardXabarBot")],
        }

    def is_connected(self):
        return True

    async def get_dialogs(self, limit=500):
        return []

    async def get_entity(self, username):
        return SimpleNamespace(username=username.lower().lstrip("@"))

    async def iter_messages(self, entity, limit=50):
        for message in self.messages[entity.username]:
            yield message

    async def send_message(self, chat_id, text, **kwargs):
        sent = SimpleNamespace(id=100 + len(self.sent))
        self.sent.append((chat_id, text, kwargs))
        return sent


@pytest.mark.asyncio
async def test_backfill_replays_once_and_deduplicates(monkeypatch, temp_db) -> None:
    from src.context import app_ctx
    from src.services.core.finance.handlers import engine_utils as hisobchi_handlers, card_bot_handler, manual_handler

    app_ctx.finance_group_cache = None
    hisobchi_handlers._topic_cache.clear()
    client = _BackfillClient()
    engine = HisobchiEngine(temp_db)
    from src.settings import settings
    monkeypatch.setattr(settings, "OWNER_ID", None)
    monkeypatch.setattr(
        hisobchi_handlers,
        "resolve_finance_destination",
        lambda _client: _async_value((-1002, None, None)),
    )
    monkeypatch.setattr(
        card_bot_handler,
        "resolve_finance_destination",
        lambda _client: _async_value((-1002, None, None)),
    )

    first = await backfill_card_bot_messages(client, engine, bot_client=client, max_age_hours=48)
    second = await backfill_card_bot_messages(client, engine, bot_client=client, max_age_hours=48)

    assert first["created"] == 2
    assert second["created"] == 0
    assert len(client.sent) == 2


async def _async_value(value):
    return value


class _FakeReplyTo:
    def __init__(self, reply_to_msg_id):
        self.reply_to_msg_id = reply_to_msg_id


class _FakeGroupMessage:
    def __init__(self, text, reply_to_msg_id, msg_id=999):
        self.message = text
        self.reply_to = _FakeReplyTo(reply_to_msg_id)
        self.id = msg_id


class _FakeGroupReplyEvent:
    def __init__(self, chat_id, text, reply_to_msg_id, sender_is_bot):
        self.chat_id = chat_id
        self.message = _FakeGroupMessage(text, reply_to_msg_id)
        self._sender_is_bot = sender_is_bot

    async def get_sender(self):
        return SimpleNamespace(bot=self._sender_is_bot)


class _FakeBotClient:
    def __init__(self):
        self.sent = []

    def is_connected(self):
        return True

    async def send_message(self, chat_id, text, **kwargs):
        self.sent.append((chat_id, text, kwargs))
        return SimpleNamespace(id=1)


class _FakeAiogramBot:
    def __init__(self):
        self.sent = []

    async def send_message(self, **kwargs):
        self.sent.append(kwargs)
        return SimpleNamespace(message_id=2)


async def _seed_pending_tx(engine, *, finance_chat_id, finance_msg_id):
    tx = parse_card_notification("humocardbot", HUMO_SAMPLE)
    assert tx is not None
    tx_id = await engine.save_transaction(
        source_bot=tx.source_bot,
        direction=tx.direction,
        amount=tx.amount,
        merchant=tx.merchant,
        card_suffix=tx.card_suffix,
        tx_time=tx.tx_time,
        balance=tx.balance,
        raw_text=HUMO_SAMPLE,
    )
    await engine.update_finance_msg(tx_id, finance_msg_id=finance_msg_id, finance_chat_id=finance_chat_id)
    return tx_id


@pytest.mark.asyncio
async def test_bot_sender_reply_is_ignored_in_finance_group(monkeypatch, temp_db) -> None:
    """A bot's own message (e.g. @jonairobot's question replying to the
    topic root) must never be treated as a human answering the question —
    this was the root cause of transactions self-categorizing as garbage."""
    from src.services.core.finance.handlers import engine_utils as hisobchi_handlers, card_bot_handler, manual_handler

    monkeypatch.setattr(
        hisobchi_handlers, "resolve_finance_destination",
        lambda _client: _async_value((-1002, None, None)),
    )
    engine = HisobchiEngine(temp_db)
    tx_id = await _seed_pending_tx(engine, finance_chat_id=-1002, finance_msg_id=555)
    bot_client = _FakeBotClient()

    event = _FakeGroupReplyEvent(
        chat_id=-1002,
        text="💳 Yangi to'lov #1\n\n➖ Chiqim: 4 000 UZS\n\n❓ Bu to'lov nima uchun ketdi?\nJavob bering yoki /skip 1",
        reply_to_msg_id=555,
        sender_is_bot=True,
    )

    handled = await handle_finance_group_reply(event, client=None, engine=engine, bot_client=bot_client)

    assert handled is False
    assert bot_client.sent == []
    tx = await engine.get_pending_by_finance_msg(finance_chat_id=-1002, finance_msg_id=555)
    assert tx is not None and tx["id"] == tx_id  # still pending, untouched


@pytest.mark.asyncio
async def test_human_reply_quoting_bot_template_is_ignored(monkeypatch, temp_db) -> None:
    """Defense in depth: even from a genuine human, text that's just the
    bot's own question template (e.g. accidentally forwarded) must not be
    accepted as a real category."""
    from src.services.core.finance.handlers import engine_utils as hisobchi_handlers, card_bot_handler, manual_handler

    monkeypatch.setattr(
        hisobchi_handlers, "resolve_finance_destination",
        lambda _client: _async_value((-1002, None, None)),
    )
    engine = HisobchiEngine(temp_db)
    await _seed_pending_tx(engine, finance_chat_id=-1002, finance_msg_id=555)
    bot_client = _FakeBotClient()

    event = _FakeGroupReplyEvent(
        chat_id=-1002,
        text="💳 Yangi to'lov #1 — Javob bering yoki /skip 1",
        reply_to_msg_id=555,
        sender_is_bot=False,
    )

    handled = await handle_finance_group_reply(event, client=None, engine=engine, bot_client=bot_client)

    assert handled is False
    assert bot_client.sent == []


@pytest.mark.asyncio
async def test_human_reply_saves_category_via_bot_client(monkeypatch, temp_db) -> None:
    """The normal, correct path: a real human's category answer is saved
    and the confirmation is sent via bot_client (@jonairobot), never the
    userbot."""
    from src.services.core.finance.handlers import engine_utils as hisobchi_handlers, card_bot_handler, manual_handler

    monkeypatch.setattr(
        manual_handler, "resolve_finance_destination",
        lambda _client: _async_value((-1002, None, None)),
    )
    engine = HisobchiEngine(temp_db)
    tx_id = await _seed_pending_tx(engine, finance_chat_id=-1002, finance_msg_id=555)
    bot_client = _FakeBotClient()

    event = _FakeGroupReplyEvent(
        chat_id=-1002,
        text="Ofis xarajati",
        reply_to_msg_id=555,
        sender_is_bot=False,
    )

    handled = await handle_finance_group_reply(event, client=None, engine=engine, bot_client=bot_client)

    assert handled is True
    assert len(bot_client.sent) == 1
    _, sent_text, _ = bot_client.sent[0]
    assert "Ofis xarajati" in sent_text
    tx = await engine.get_pending_by_finance_msg(finance_chat_id=-1002, finance_msg_id=555)
    assert tx is None  # no longer pending — categorized


@pytest.mark.asyncio
async def test_human_reply_saves_category_via_aiogram_runtime(monkeypatch, temp_db) -> None:
    from src.services.core.finance.handlers import engine_utils as hisobchi_handlers, card_bot_handler, manual_handler

    monkeypatch.setattr(
        manual_handler, "resolve_finance_destination",
        lambda _client: _async_value((-1002, None, None)),
    )
    engine = HisobchiEngine(temp_db)
    await _seed_pending_tx(engine, finance_chat_id=-1002, finance_msg_id=555)
    aiogram_bot = _FakeAiogramBot()

    event = _FakeGroupReplyEvent(
        chat_id=-1002,
        text="Ofis xarajati",
        reply_to_msg_id=555,
        sender_is_bot=False,
    )

    handled = await handle_finance_group_reply(
        event,
        client=None,
        engine=engine,
        bot_client=AiogramBotRuntime(aiogram_bot),
    )

    assert handled is True
    assert len(aiogram_bot.sent) == 1
    assert aiogram_bot.sent[0]["chat_id"] == -1002
    assert aiogram_bot.sent[0]["reply_to_message_id"] == 999
    assert aiogram_bot.sent[0]["parse_mode"] == "HTML"


def test_boot_registers_primary_message_handler_and_initializes_schema() -> None:
    source = ("src/boot.py")
    text = open(source, encoding="utf-8").read()
    assert "init_hisobchi_tables" in text
    assert "m.handle_new_message" in text


@pytest.mark.asyncio
async def test_reset_learning_and_transactions_clears_everything(temp_db) -> None:
    engine = HisobchiEngine(temp_db)
    tx = parse_card_notification("humocardbot", HUMO_SAMPLE)
    assert tx is not None
    await engine.save_transaction(
        source_bot=tx.source_bot, direction=tx.direction, amount=tx.amount,
        merchant=tx.merchant, card_suffix=tx.card_suffix, tx_time=tx.tx_time,
        balance=tx.balance, raw_text=HUMO_SAMPLE,
    )
    await engine.learn_category(tx.merchant, "Ofis xarajati")
    await engine.learn_rule(
        merchant=tx.merchant, card_suffix=tx.card_suffix, direction=tx.direction,
        amount=tx.amount, category="Ofis xarajati", ownership="business",
    )

    rows = await temp_db.execute("SELECT COUNT(*) AS cnt FROM hisobchi_transactions")
    assert rows[0]["cnt"] == 1
    rows = await temp_db.execute("SELECT COUNT(*) AS cnt FROM hisobchi_merchant_memory")
    assert rows[0]["cnt"] == 1
    rows = await temp_db.execute("SELECT COUNT(*) AS cnt FROM hisobchi_category_rules")
    assert rows[0]["cnt"] == 1

    await engine.reset_learning_and_transactions()

    for table in ("hisobchi_transactions", "hisobchi_merchant_memory", "hisobchi_category_rules"):
        rows = await temp_db.execute(f"SELECT COUNT(*) AS cnt FROM {table}")
        assert rows[0]["cnt"] == 0, f"{table} should be empty after reset"


class _FakeUserbotClient:
    """Minimal stand-in — backfill_card_bot_messages is stubbed out, so this
    never actually needs to iterate real Telegram messages in these tests."""


@pytest.mark.asyncio
async def test_one_time_reset_resync_runs_only_once(monkeypatch, temp_db) -> None:
    from src.services.core.finance import hisobchi_schema

    engine = HisobchiEngine(temp_db)
    reset_calls = []
    resync_calls = []

    async def _fake_reset():
        reset_calls.append(1)

    async def _fake_resync(client, engine, *, bot_client=None, since=None, limit=5000, poll_interval_sec=5.0, max_wait_sec=3600.0):
        resync_calls.append(since)
        return {"scanned": 0, "created": 0, "duplicates": 0, "errors": 0, "timed_out": 0}

    monkeypatch.setattr(engine, "reset_learning_and_transactions", _fake_reset)
    monkeypatch.setattr(
        "src.services.core.finance.handlers.resync_since_sequential",
        _fake_resync,
    )

    first = await run_one_time_reset_and_resync(
        db=temp_db.db, engine=engine, client=_FakeUserbotClient(), since_date="2026-07-01",
    )
    second = await run_one_time_reset_and_resync(
        db=temp_db.db, engine=engine, client=_FakeUserbotClient(), since_date="2026-07-01",
    )

    assert first is not None
    assert second is None  # guarded — did nothing the second time
    assert len(reset_calls) == 1
    assert len(resync_calls) == 1


@pytest.mark.asyncio
async def test_resync_sequential_waits_for_answer_before_next(monkeypatch, temp_db) -> None:
    from src.services.core.finance.handlers import engine_utils as hisobchi_handlers, card_bot_handler, manual_handler
    from datetime import datetime, timezone

    hisobchi_handlers._topic_cache.clear()
    client = _BackfillClient()
    engine = HisobchiEngine(temp_db)
    monkeypatch.setattr(
        hisobchi_handlers, "resolve_finance_destination",
        lambda _client: _async_value((-1002, None, None)),
    )

    async def _answer_both_shortly():
        for tx_id in (1, 2):
            for _ in range(100):
                if await engine.get_transaction_status(tx_id) == "pending":
                    await engine.categorize(tx_id, "Ofis xarajati", "business")
                    break
                await asyncio.sleep(0.01)

    answer_task = asyncio.create_task(_answer_both_shortly())
    stats = await resync_since_sequential(
        client, engine, bot_client=client,
        since=datetime(2020, 1, 1, tzinfo=timezone.utc),
        limit=50, poll_interval_sec=0.01, max_wait_sec=2.0,
    )
    await answer_task

    assert stats["created"] == 2
    assert stats["timed_out"] == 0


@pytest.mark.asyncio
async def test_resync_sequential_times_out_and_moves_on(monkeypatch, temp_db) -> None:
    from src.services.core.finance.handlers import engine_utils as hisobchi_handlers, card_bot_handler, manual_handler
    from datetime import datetime, timezone

    hisobchi_handlers._topic_cache.clear()
    client = _BackfillClient()
    engine = HisobchiEngine(temp_db)
    monkeypatch.setattr(
        hisobchi_handlers, "resolve_finance_destination",
        lambda _client: _async_value((-1002, None, None)),
    )

    stats = await resync_since_sequential(
        client, engine, bot_client=client,
        since=datetime(2020, 1, 1, tzinfo=timezone.utc),
        limit=50, poll_interval_sec=0.01, max_wait_sec=0.03,
    )

    assert stats["created"] == 2
    assert stats["timed_out"] == 2  # neither ever answered — still moved on


@pytest.mark.asyncio
async def test_hisobchi_approval_callbacks_across_restart(temp_db) -> None:
    from src.services.core.hisobchi_approval import handle_callback, _pending
    from src.services.core.finance.hisobchi_card_parser import parse_card_notification

    engine = HisobchiEngine(temp_db)
    parsed = parse_card_notification("CardXabarBot", UZCARD_SAMPLE)
    tx_id, _ = await engine.save_transaction_once(
        source_bot=parsed.source_bot,
        direction=parsed.direction,
        amount=parsed.amount,
        merchant=parsed.merchant,
        card_suffix=parsed.card_suffix,
        tx_time=parsed.tx_time,
        balance=parsed.balance,
        raw_text=UZCARD_SAMPLE,
    )

    # Simulate server restart by clearing in-memory cache
    _pending.clear()

    class _MockEvent:
        def __init__(self):
            self.answers = []
            self.edits = []

        async def answer(self, text=""):
            self.answers.append(text)

        async def edit(self, text=None, *, parse_mode=None, buttons=None):
            self.edits.append((text, parse_mode, buttons))

    # 1. Toggle ownership on fresh restart
    event1 = _MockEvent()
    handled = await handle_callback(f"howner:{tx_id}:personal", event1, engine)
    assert handled is True
    assert "Shaxsiy" in event1.answers[0]
    assert len(event1.edits) == 1

    # 2. Edit category
    event2 = _MockEvent()
    handled = await handle_callback(f"hedit:{tx_id}", event2, engine)
    assert handled is True
    assert "Kategoriyani tanlang" in event2.answers[0]

    # 3. Select category
    event3 = _MockEvent()
    handled = await handle_callback(f"hcat:{tx_id}:🚕 Taksi", event3, engine)
    assert handled is True
    assert "Taksi" in event3.answers[0]

    # 4. Approve
    event4 = _MockEvent()
    handled = await handle_callback(f"happrove:{tx_id}:personal", event4, engine)
    assert handled is True
    assert "Tasdiqlandi" in event4.answers[0]

    # Verify status in database
    status = await engine.get_transaction_status(tx_id)
    assert status == "categorized"
    tx_row = await engine.get_transaction(tx_id)
    assert tx_row["ownership"] == "personal"
    assert tx_row["category"] == "🚕 Taksi"

