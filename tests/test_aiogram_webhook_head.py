import pytest

from src.services.core.telegram.aiogram_webhook_head import (
    AiogramWebhookHead,
    DatabaseUpdateReceiptStore,
    InMemoryUpdateReceiptStore,
)


class _Session:
    def __init__(self):
        self.closed = False

    async def close(self):
        self.closed = True


class _Bot:
    def __init__(self):
        self.session = _Session()
        self.webhook_kwargs = None

    async def set_webhook(self, **kwargs):
        self.webhook_kwargs = kwargs


class _Dispatcher:
    def __init__(self):
        self.payloads = []
        self.fail = False

    async def feed_webhook_update(self, bot, payload):
        if self.fail:
            raise RuntimeError("handler failed")
        self.payloads.append(payload)


class _Database:
    def __init__(self):
        self.values = {}

    async def get_state(self, key, default=None):
        return self.values.get(key, default)

    async def set_state(self, key, value):
        self.values[key] = value


@pytest.mark.asyncio
async def test_webhook_head_registers_and_deduplicates_updates():
    bot = _Bot()
    dispatcher = _Dispatcher()
    head = AiogramWebhookHead(
        bot=bot,
        dispatcher=dispatcher,
        receipt_store=InMemoryUpdateReceiptStore(),
        webhook_url="https://oisha.example/telegram/webhook",
        webhook_secret="secret-value",
        allowed_updates=["message", "callback_query"],
    )

    await head.start()
    first = await head.receive({"update_id": 42, "message": {"text": "/start"}})
    duplicate = await head.receive({"update_id": 42, "message": {"text": "/start"}})

    assert bot.webhook_kwargs == {
        "url": "https://oisha.example/telegram/webhook",
        "secret_token": "secret-value",
        "allowed_updates": ["message", "callback_query"],
        "drop_pending_updates": False,
    }
    assert first["duplicate"] is False
    assert duplicate["duplicate"] is True
    assert len(dispatcher.payloads) == 1
    assert head.health()["userbot_enabled"] is False
    assert head.health()["webhook_registered"] is True

    await head.stop()
    assert bot.session.closed is True


@pytest.mark.asyncio
async def test_failed_update_is_not_marked_processed():
    dispatcher = _Dispatcher()
    store = InMemoryUpdateReceiptStore()
    head = AiogramWebhookHead(
        bot=_Bot(),
        dispatcher=dispatcher,
        receipt_store=store,
        webhook_url="https://oisha.example/telegram/webhook",
        webhook_secret="secret-value",
    )
    dispatcher.fail = True

    with pytest.raises(RuntimeError, match="handler failed"):
        await head.receive({"update_id": 7})

    assert await store.contains(7) is False


@pytest.mark.asyncio
async def test_database_receipts_are_bounded_and_persistent():
    database = _Database()
    first = DatabaseUpdateReceiptStore(database, capacity=2)
    await first.add(1)
    await first.add(2)
    await first.add(3)

    second = DatabaseUpdateReceiptStore(database, capacity=2)
    assert await second.contains(1) is False
    assert await second.contains(2) is True
    assert await second.contains(3) is True


@pytest.mark.asyncio
@pytest.mark.parametrize("update_id", [None, True, -1, "12"])
async def test_webhook_head_rejects_invalid_update_id(update_id):
    head = AiogramWebhookHead(
        bot=_Bot(),
        dispatcher=_Dispatcher(),
        receipt_store=InMemoryUpdateReceiptStore(),
        webhook_secret="secret-value",
    )

    with pytest.raises(ValueError, match="update_id"):
        await head.receive({"update_id": update_id})


@pytest.mark.asyncio
async def test_first_deploy_can_start_before_public_url_is_known():
    head = AiogramWebhookHead(
        bot=_Bot(),
        dispatcher=_Dispatcher(),
        receipt_store=InMemoryUpdateReceiptStore(),
        webhook_secret="secret-value",
    )

    await head.start()

    assert head.health()["status"] == "degraded"
    assert head.health()["webhook_registered"] is False
