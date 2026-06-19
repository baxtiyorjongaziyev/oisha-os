from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.database import Database
from src.services.core.card_transaction_accountant import (
    CardTransactionAccountant,
    parse_card_transaction,
)


HUMO_EXPENSE = """💸 To'lov
➖ 4.000,00 UZS
📍 AO PAYNET QR DLYA S
💳 HUMOCARD *6224
🕓 22:26 18.06.2026
💰 2.135,00 UZS"""

UZCARD_EXPENSE = """🔴 Platezh
➖ 8 000.00 UZS
💳 ***1393
📍 PAYNET AJ QR DLYA SAMOZANYATIX UZKARD, UZ
🕓 18.06.26 22:26
💵 700.00 UZS"""

HUMO_INCOME = """💸 Kirim
➕ 1.500.000,00 UZS
📍 PEREVOD S KARTY
💳 HUMOCARD *6224
🕓 09:15 19.06.2026
💰 1.502.135,00 UZS"""


def test_parses_humo_expense_without_confusing_balance_for_amount():
    tx = parse_card_transaction(HUMO_EXPENSE, "HUMOcardbot")

    assert tx is not None
    assert tx.direction == "expense"
    assert tx.amount_uzs == 4_000
    assert tx.balance_uzs == 2_135
    assert tx.card_last4 == "6224"
    assert tx.merchant == "AO PAYNET QR DLYA S"
    assert tx.occurred_at == "2026-06-18T22:26:00+05:00"


def test_parses_uzcard_expense_date_and_decimal_format():
    tx = parse_card_transaction(UZCARD_EXPENSE, "CardXabarBot")

    assert tx is not None
    assert tx.direction == "expense"
    assert tx.amount_uzs == 8_000
    assert tx.balance_uzs == 700
    assert tx.card_last4 == "1393"
    assert tx.occurred_at == "2026-06-18T22:26:00+05:00"


def test_parses_income_notification():
    tx = parse_card_transaction(HUMO_INCOME, "HUMOcardbot")

    assert tx is not None
    assert tx.direction == "income"
    assert tx.amount_uzs == 1_500_000
    assert tx.balance_uzs == 1_502_135


def test_rejects_non_transaction_message():
    assert parse_card_transaction("Assalomu alaykum", "HUMOcardbot") is None


class FakeTelegramClient:
    def __init__(self):
        self.sent = []
        self._next_id = 500

    async def send_message(self, chat_id, text, **kwargs):
        self._next_id += 1
        self.sent.append((chat_id, text, kwargs))
        return SimpleNamespace(id=self._next_id)

    async def get_dialogs(self, limit=500):
        return []

    async def iter_messages(self, entity, limit=50):
        if False:
            yield entity


def bank_event(text: str, username: str, message_id: int):
    sender = SimpleNamespace(username=username, bot=True)
    return SimpleNamespace(
        id=message_id,
        chat_id=9000,
        raw_text=text,
        text=text,
        is_private=True,
        get_sender=AsyncMock(return_value=sender),
    )


async def fetch_one(db: Database, sql: str, params=()):
    conn = await db.get_connection()
    async with conn.execute(sql, params) as cursor:
        return await cursor.fetchone()


@pytest.fixture
async def accountant(tmp_path):
    db = Database(str(tmp_path / "finance.db"))
    await db.init_instance()
    client = FakeTelegramClient()
    service = CardTransactionAccountant(
        db=db,
        user_client=client,
        finance_group_id=-100777,
        finance_topic_id=42,
        allowed_bots={"humocardbot", "cardxabarbot"},
    )
    await service.initialize()
    try:
        yield service, db, client
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_unknown_transaction_is_saved_and_asks_finance_group(accountant):
    service, db, client = accountant

    result = await service.handle_bank_message(
        bank_event(HUMO_EXPENSE, "HUMOcardbot", 101)
    )

    assert result["status"] == "awaiting_reason"
    assert len(client.sent) == 1
    chat_id, text, kwargs = client.sent[0]
    assert chat_id == -100777
    assert "4 000 UZS" in text
    assert "nima uchun" in text.lower()
    assert kwargs["reply_to"] == 42
    row = await fetch_one(
        db,
        "SELECT status, question_message_id FROM card_transactions WHERE fingerprint = ?",
        (result["fingerprint"],),
    )
    assert row == ("awaiting_reason", 501)


@pytest.mark.asyncio
async def test_same_notification_is_deduplicated(accountant):
    service, _db, client = accountant
    event = bank_event(UZCARD_EXPENSE, "CardXabarBot", 102)

    first = await service.handle_bank_message(event)
    second = await service.handle_bank_message(event)

    assert first["status"] == "awaiting_reason"
    assert second["status"] == "duplicate"
    assert len(client.sent) == 1


@pytest.mark.asyncio
async def test_message_from_unapproved_bot_is_ignored(accountant):
    service, _db, client = accountant

    result = await service.handle_bank_message(
        bank_event(HUMO_EXPENSE, "NotMyBankBot", 103)
    )

    assert result["status"] == "ignored_sender"
    assert client.sent == []


@pytest.mark.asyncio
async def test_finance_reply_categorizes_and_teaches_exact_repeat(accountant):
    service, db, client = accountant
    first = await service.handle_bank_message(
        bank_event(HUMO_EXPENSE, "HUMOcardbot", 104)
    )
    question_id = client.sent[0][2].get("reply_to")
    assert question_id == 42

    reply = SimpleNamespace(
        chat_id=-100777,
        reply_to_msg_id=501,
        raw_text="Kategoriya: Ofis xarajati\nSabab: ofis uchun mayda xarid",
        text="Kategoriya: Ofis xarajati\nSabab: ofis uchun mayda xarid",
        reply=AsyncMock(),
    )
    handled = await service.handle_finance_reply(reply)

    assert handled is True
    row = await fetch_one(
        db,
        "SELECT status, category, reason FROM card_transactions WHERE fingerprint = ?",
        (first["fingerprint"],),
    )
    assert row == ("categorized", "Ofis xarajati", "ofis uchun mayda xarid")
    reply.reply.assert_awaited_once()

    repeated_text = HUMO_EXPENSE.replace("18.06.2026", "19.06.2026")
    repeated = await service.handle_bank_message(
        bank_event(repeated_text, "HUMOcardbot", 105)
    )

    assert repeated["status"] == "auto_categorized"
    assert repeated["category"] == "Ofis xarajati"
    assert "Avtomatik kategoriya" in client.sent[-1][1]
    assert "nima uchun" not in client.sent[-1][1].lower()


@pytest.mark.asyncio
async def test_unrelated_group_reply_cannot_categorize(accountant):
    service, _db, _client = accountant
    reply = SimpleNamespace(
        chat_id=-100999,
        reply_to_msg_id=501,
        raw_text="Kategoriya: Marketing",
        text="Kategoriya: Marketing",
        reply=AsyncMock(),
    )

    assert await service.handle_finance_reply(reply) is False


@pytest.mark.asyncio
async def test_discovers_named_finance_group_when_id_is_not_configured(tmp_path):
    db = Database(str(tmp_path / "discover.db"))
    await db.init_instance()
    client = FakeTelegramClient()
    client.get_dialogs = AsyncMock(
        return_value=[SimpleNamespace(id=-100555, name="Jon Branding Moliya")]
    )
    service = CardTransactionAccountant(
        db=db,
        user_client=client,
        allowed_bots={"humocardbot"},
    )
    await service.initialize()

    result = await service.handle_bank_message(
        bank_event(HUMO_EXPENSE, "HUMOcardbot", 110)
    )

    assert result["status"] == "awaiting_reason"
    assert service.finance_group_id == -100555
    assert client.sent[0][0] == -100555
    await db.close()


@pytest.mark.asyncio
async def test_uses_team_fallback_when_named_finance_group_is_missing(tmp_path):
    db = Database(str(tmp_path / "fallback.db"))
    await db.init_instance()
    client = FakeTelegramClient()
    service = CardTransactionAccountant(
        db=db,
        user_client=client,
        fallback_group_id=-100888,
        fallback_topic_id=77,
        allowed_bots={"cardxabarbot"},
    )
    await service.initialize()

    result = await service.handle_bank_message(
        bank_event(UZCARD_EXPENSE, "CardXabarBot", 111)
    )

    assert result["status"] == "awaiting_reason"
    assert client.sent[0][0] == -100888
    assert client.sent[0][2]["reply_to"] == 77
    await db.close()


@pytest.mark.asyncio
async def test_backfill_processes_recent_bank_bot_history_once(tmp_path):
    db = Database(str(tmp_path / "backfill.db"))
    await db.init_instance()
    client = FakeTelegramClient()
    historical = bank_event(HUMO_EXPENSE, "HUMOcardbot", 120)

    async def iter_messages(entity, limit=50):
        if entity.casefold() == "@humocardbot":
            yield historical

    client.iter_messages = iter_messages
    service = CardTransactionAccountant(
        db=db,
        user_client=client,
        finance_group_id=-100777,
        allowed_bots={"humocardbot", "cardxabarbot"},
    )
    await service.initialize()

    first = await service.backfill_recent(limit_per_bot=10)
    second = await service.backfill_recent(limit_per_bot=10)

    assert first == {"processed": 1, "duplicates": 0, "errors": 0, "stale": 0}
    assert second == {"processed": 0, "duplicates": 1, "errors": 0, "stale": 0}
    assert len(client.sent) == 1
    await db.close()


@pytest.mark.asyncio
async def test_backfill_skips_old_transactions(tmp_path):
    db = Database(str(tmp_path / "old-backfill.db"))
    await db.init_instance()
    client = FakeTelegramClient()
    old_text = HUMO_EXPENSE.replace("18.06.2026", "01.01.2020")
    historical = bank_event(old_text, "HUMOcardbot", 121)

    async def iter_messages(entity, limit=50):
        yield historical

    client.iter_messages = iter_messages
    service = CardTransactionAccountant(
        db=db,
        user_client=client,
        finance_group_id=-100777,
        allowed_bots={"humocardbot"},
    )
    await service.initialize()

    result = await service.backfill_recent(limit_per_bot=10, max_age_hours=48)

    assert result == {"processed": 0, "duplicates": 0, "errors": 0, "stale": 1}
    assert client.sent == []
    await db.close()
