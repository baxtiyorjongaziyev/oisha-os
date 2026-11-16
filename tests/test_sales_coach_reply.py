import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from src.handlers.seller_reply import is_checkin_text, register_seller_reply_handlers
from src.services.core.checkin_composer import load_context
from src.services.core.sales_coach_reply import COACH_SYSTEM, coach_reply
from src.services.utils.free_ai_router import ProviderResult


def run(coro):
    return asyncio.run(coro)


def test_coach_reply_passes_context_and_returns_ai_text():
    seen = {}

    async def fake(prompt, **kwargs):
        seen["prompt"], seen["system"] = prompt, kwargs["system"]
        return "Zo'r, Rayxon! Farrux akaga bugun hisob-fakturani yuboring: \"Farrux aka, hujjatni tashladim\" 💪"

    text = run(coach_reply("Rayxon", "Фаррух ака 2 кунда тулов", "check-in matni", generate=fake))
    assert text.startswith("Zo'r, Rayxon!")
    assert "Фаррух ака 2 кунда тулов" in seen["prompt"] and "check-in matni" in seen["prompt"]
    assert "konversiya" in seen["system"]


def test_coach_reply_never_promises_crm_actions():
    assert "vazifa qo'ydim" in COACH_SYSTEM and "dema" in COACH_SYSTEM


def test_coach_reply_falls_back_on_error_or_bad_length():
    async def boom(prompt, **kwargs):
        raise RuntimeError("down")

    async def tiny(prompt, **kwargs):
        return "ok"

    for gen in (boom, tiny):
        text = run(coach_reply("Rayxon", "javob", "check-in", generate=gen))
        assert text.startswith("Rahmat, Rayxon!")


def test_is_checkin_text():
    assert is_checkin_text("Assalomu alaykum, Rayxon! Oxirgi soatda 7 ta raqam terdingiz")
    assert not is_checkin_text("Bugungi reja: 5 ta lid")
    assert not is_checkin_text("Assalomu alaykum, xayrli tong!")


class FakeDispatcher:
    def __init__(self):
        self.message = SimpleNamespace(register=self._register)
        self.handlers = []

    def _register(self, handler, *filters):
        self.handlers.append((handler, filters))


def _message(chat_id, reply_from_id, reply_text, is_bot=False, username=None):
    async def me():
        return SimpleNamespace(id=999)

    reply = SimpleNamespace(from_user=SimpleNamespace(id=reply_from_id), text=reply_text, caption=None)
    return SimpleNamespace(
        chat=SimpleNamespace(id=chat_id),
        from_user=SimpleNamespace(id=5, is_bot=is_bot, first_name="Rayxona", username=username),
        reply_to_message=reply,
        bot=SimpleNamespace(me=me),
        text="Shaxboz aka band",
        caption=None,
    )


def _filter():
    disp = FakeDispatcher()
    register_seller_reply_handlers(disp, group_id_getter=lambda: -100)
    return disp.handlers[0][1][0]


def test_filter_only_catches_replies_to_bot_checkin():
    flt = _filter()
    checkin = "Assalomu alaykum, Rayxon! Oxirgi soatda 7 ta raqam terdingiz"
    assert run(flt(_message(-100, 999, checkin)))
    assert not run(flt(_message(-200, 999, checkin)))
    assert not run(flt(_message(-100, 42, checkin)))
    assert not run(flt(_message(-100, 999, "Bugungi hisobot")))
    assert not run(flt(_message(-100, 999, checkin, is_bot=True)))


def test_filter_catches_ai_checkin_that_mentions_replier():
    flt = _filter()
    ai_text = "Rayxon (@RayxonJonbranding), Shaxboz aka bilan gaplasha oldingizmi?"
    assert run(flt(_message(-100, 999, ai_text, username="RayxonJonbranding")))
    assert not run(flt(_message(-100, 999, ai_text, username="boshqa")))


def test_coach_reply_falls_back_on_truncated_or_leaked_output():
    async def dangling(prompt, **kwargs):
        return "Shahnoza, barakalla! Bir soat ichida ham uchrashuv o'tkazib,"

    text = run(coach_reply("Shahnoza", "javob", "check-in", generate=dangling))
    assert text.startswith("Rahmat, Shahnoza!")

    fake_router = AsyncMock()
    fake_router.generate_text = AsyncMock(
        return_value=ProviderResult(
            text="Shahnoza, barakalla! Bir soat ichida ham",
            provider="gemini",
            model="gemini-3.5-flash",
            finish_reason="length",
        )
    )
    with patch("src.services.utils.free_ai_router.get_free_ai_router", return_value=fake_router):
        text2 = run(coach_reply("Shahnoza", "javob", "check-in"))
        assert text2.startswith("Rahmat, Shahnoza!")


def test_seller_reply_catches_topic_ai_checkin_and_routes_context_per_rep(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()

    disp = FakeDispatcher()
    register_seller_reply_handlers(disp, group_id_getter=lambda: -100)
    handler, (flt,) = disp.handlers[0]

    msg = _message(-100, 999, "Shahnoza, tushlikdan keyin qo'ng'iroqlar qalay?")
    msg.message_thread_id = 122
    msg.reply_to_message.message_thread_id = 122
    msg.from_user.first_name = "Shahnoza"
    msg.text = "1 ta uchrashuv o'tkazdim!"
    msg.reply = AsyncMock()

    assert run(flt(msg))

    with patch(
        "src.services.core.sales_coach_reply.coach_reply",
        AsyncMock(return_value="Zo'r natija, Shahnoza! Keyingi qadamni kelishib oling."),
    ):
        run(handler(msg))

    assert load_context("data/checkin_context_shahnoza.json").get("last_reply") == "1 ta uchrashuv o'tkazdim!"
    assert load_context("data/checkin_context.json") == {}
