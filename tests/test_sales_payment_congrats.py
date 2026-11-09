import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from src.handlers import sales_payment_congrats as spc

CASH_CARD = """💰 TO{a}LOV TASDIQLASH

📅 Sana: 07.11.2026
💵 Summa (so{a}m): 6.760.000
👤 Mijoz / Loyiha:Patent OOMAR
🧾 To{a}lov turi: Naqd
🙋 Sotuvchi: Rayxona
📎 Chek: Tasdiqlang @jonbranding_finansist
@BaxtiyorjonGaziyev""".format(a=chr(39))


class FakeDb:
    def __init__(self):
        self.state = {}

    async def get_state(self, key):
        return self.state.get(key)

    async def set_state(self, key, value):
        self.state[key] = value


def _event(text=CASH_CARD, sender=None):
    sender = sender or SimpleNamespace(bot=False, username="RayxonJonbranding", first_name="Rayxona")
    return SimpleNamespace(
        message=SimpleNamespace(message=text),
        chat_id=-1003854308552,
        id=77,
        get_sender=AsyncMock(return_value=sender),
    )


def _run(event, env, db=None, quiet=False):
    """Run the handler; returns (oisha bot mock, Bot API mock, db)."""
    db = db or FakeDb()
    bot = SimpleNamespace(send_message=AsyncMock())
    ctx = SimpleNamespace(bot_client=bot, client=None, msg_controller=SimpleNamespace(db=db))
    bot_api = AsyncMock()
    with (
        patch.object(spc, "app_ctx", ctx),
        patch.object(spc, "_send_via_bot_api", bot_api),
        patch.object(spc, "_send_typing_via_bot_api", AsyncMock()),
        patch.object(spc.asyncio, "sleep", AsyncMock()),
        patch.object(spc, "is_quiet_hours", return_value=quiet),
        patch.dict(spc.os.environ, env),
    ):
        asyncio.run(spc.sales_payment_congrats_handler(event))
    return bot, bot_api, db


TOKENS = {"AMINA_BOT_TOKEN": "amina-token", "MRJON_BOT_TOKEN": "mrjon-token"}


def test_parses_real_card_variants():
    card = spc.parse_payment_card(CASH_CARD)
    assert card["amount"] == "6.760.000 soʻm"
    assert card["project"] == "Patent OOMAR"
    assert card["seller"] == "Rayxona"

    curly = spc.parse_payment_card("TOʻLOV TASDIQLASH\nSumma (soʻm): 880.000\nMijoz / Loyiha: USTARA")
    assert curly["amount"] == "880.000 soʻm"


def test_ignores_non_cards_and_blank_template():
    assert spc.parse_payment_card("Bugun 5 mln toʻlov keldi") is None
    assert spc.parse_payment_card("💰 TO'LOV TASDIQLASH\n💵 Summa (so'm):\n🙋 Sotuvchi:") is None


def test_all_three_bots_congratulate_separately():
    bot, bot_api, _ = _run(_event(), TOKENS)

    oisha_text = bot.send_message.await_args.args[1]
    assert bot.send_message.await_args.kwargs["reply_to"] == 77
    assert "@RayxonJonbranding" in oisha_text and "6.760.000" in oisha_text

    assert [call.args[0] for call in bot_api.await_args_list] == ["amina-token", "mrjon-token"]
    texts = [oisha_text] + [call.args[3] for call in bot_api.await_args_list]
    assert len(set(texts)) == 3


def test_missing_token_skips_only_that_bot():
    bot, bot_api, _ = _run(_event(), {"AMINA_BOT_TOKEN": "", "MRJON_BOT_TOKEN": "mrjon-token"})
    bot.send_message.assert_awaited_once()
    assert [call.args[0] for call in bot_api.await_args_list] == ["mrjon-token"]


def test_one_bot_failure_does_not_stop_others():
    db = FakeDb()
    bot = SimpleNamespace(send_message=AsyncMock(side_effect=RuntimeError("boom")))
    ctx = SimpleNamespace(bot_client=bot, client=None, msg_controller=SimpleNamespace(db=db))
    bot_api = AsyncMock()
    with (
        patch.object(spc, "app_ctx", ctx),
        patch.object(spc, "_send_via_bot_api", bot_api),
        patch.object(spc, "_send_typing_via_bot_api", AsyncMock()),
        patch.object(spc.asyncio, "sleep", AsyncMock()),
        patch.object(spc, "is_quiet_hours", return_value=False),
        patch.dict(spc.os.environ, TOKENS),
    ):
        asyncio.run(spc.sales_payment_congrats_handler(_event()))
    assert bot_api.await_count == 2


def test_same_card_is_congratulated_once():
    db = FakeDb()
    _run(_event(), TOKENS, db=db)
    bot, bot_api, _ = _run(_event(), TOKENS, db=db)
    bot.send_message.assert_not_awaited()
    bot_api.assert_not_awaited()


def test_bot_sender_and_quiet_hours_are_silent():
    bot, bot_api, _ = _run(_event(sender=SimpleNamespace(bot=True)), TOKENS)
    bot.send_message.assert_not_awaited()
    bot_api.assert_not_awaited()

    bot, bot_api, _ = _run(_event(), TOKENS, quiet=True)
    bot.send_message.assert_not_awaited()
    bot_api.assert_not_awaited()


def test_logs_card_detection_and_success(capsys):
    _run(_event(), TOKENS)
    out = capsys.readouterr().out
    assert "[SALES_CONGRATS]" in out
    assert "kartasi aniqlandi" in out
    assert "[SALES_CONGRATS] oisha (Oisha-OS Surgical COO) tabrik yubordi" in out
    assert "[SALES_CONGRATS] amina (Hermes Sales Coach) tabrik yubordi" in out
    assert "[SALES_CONGRATS] mrjon (OpenClaw Master Closer) tabrik yubordi" in out
    assert "[SALES_CONGRATS] Tabrik yakunlandi" in out


def test_oisha_falls_back_to_userbot_when_bot_client_fails():
    bot = SimpleNamespace(send_message=AsyncMock(side_effect=RuntimeError("Unauthorized")))
    userbot = SimpleNamespace(send_message=AsyncMock())
    ctx = SimpleNamespace(bot_client=bot, client=userbot, msg_controller=SimpleNamespace(db=FakeDb()))
    with (
        patch.object(spc, "app_ctx", ctx),
        patch.object(spc, "_send_via_bot_api", AsyncMock()),
        patch.object(spc, "_send_typing_via_bot_api", AsyncMock()),
        patch.object(spc.asyncio, "sleep", AsyncMock()),
        patch.object(spc, "is_quiet_hours", return_value=False),
        patch.dict(spc.os.environ, TOKENS),
    ):
        asyncio.run(spc.sales_payment_congrats_handler(_event()))
    userbot.send_message.assert_awaited_once()


def test_warm_seller_name_variants():
    assert spc._warm_seller_name("Rayxona") == "Rayxonaxon"
    assert spc._warm_seller_name("@Shahnoza") == "Shahnozaxon"
    assert spc._warm_seller_name("Mumtozmaxal") == "Mumtozaxon"
    assert spc._warm_seller_name("Hasanboy") == "Hasanboy"
    assert spc._warm_seller_name("Baxtiyorjon") == "Baxtiyor aka"
