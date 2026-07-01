from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.database import Database
from src.database_pool import SmartRow
from src.services.core.hisobchi_card_parser import parse_card_notification
from src.services.core.hisobchi_engine import HisobchiEngine, _normalize_merchant
from src.services.core.hisobchi_handlers import (
    backfill_card_bot_messages,
    resolve_finance_destination,
)
from src.services.core.hisobchi_schema import init_hisobchi_tables
from src.services.core.hisobchi_schema import ensure_hisobchi_db


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
    from src.services.core import hisobchi_handlers

    hisobchi_handlers._finance_group_cache = None
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
    from src.services.core import hisobchi_handlers

    hisobchi_handlers._finance_group_cache = None
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
    from src.services.core import hisobchi_handlers

    client = _BackfillClient()
    engine = HisobchiEngine(temp_db)
    monkeypatch.setattr(
        hisobchi_handlers,
        "resolve_finance_destination",
        lambda _client: _async_value((-1002, None, None)),
    )

    first = await backfill_card_bot_messages(client, engine, max_age_hours=48)
    second = await backfill_card_bot_messages(client, engine, max_age_hours=48)

    assert first["created"] == 2
    assert second["created"] == 0
    assert len(client.sent) == 2


async def _async_value(value):
    return value


def test_boot_registers_primary_message_handler_and_initializes_schema() -> None:
    source = ("src/boot.py")
    text = open(source, encoding="utf-8").read()
    assert "init_hisobchi_tables" in text
    assert "m.handle_new_message" in text
