import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

from src.schedulers.remote_staff_checkin_scheduler import send_remote_checkin
from src.services.core.checkin_composer import compose_checkin, load_context, save_context

TZ = timezone(timedelta(hours=5))
NOW = datetime(2026, 10, 27, 12, 0, tzinfo=TZ)
ACTIVITY = {
    "total": 3, "answered": 3, "solid": 0, "total_talk_sec": 300,
    "answered_clients": [{"number": "+998914614535", "name": "", "duration": 42}],
}


def run(coro):
    return asyncio.run(coro)


def test_compose_follows_up_on_last_reply_same_day():
    seen = {}

    async def fake(prompt, **kwargs):
        seen["prompt"] = prompt
        seen["temperature"] = kwargs["temperature"]
        return "Shaxboz aka bilan qayta gaplasha oldingizmi? Farrux akaga eslatma qo'yib qo'ydim 🙂"

    ctx = {"date": "2026-10-27", "last_checkin": "eski xabar", "last_reply": "Шахбоз ака банд экан"}
    text = run(compose_checkin("Rayxon", NOW, ACTIVITY, context=ctx, generate=fake))
    assert text.startswith("Shaxboz aka")
    assert "Шахбоз ака банд экан" in seen["prompt"]
    assert "salomlashganmiz: ha" in seen["prompt"]
    assert seen["temperature"] > 0.5


def test_compose_ignores_yesterday_context():
    seen = {}

    async def fake(prompt, **kwargs):
        seen["prompt"] = prompt
        return "Xayrli kun! Bugun birinchi qo'ng'iroqlar qanday ketyapti?"

    ctx = {"date": "2026-10-26", "last_reply": "kechagi javob"}
    run(compose_checkin("Rayxon", NOW, None, context=ctx, generate=fake))
    assert "kechagi javob" not in seen["prompt"]
    assert "salomlashganmiz: yo`q" in seen["prompt"]


def test_compose_returns_none_on_failure_or_bad_length():
    async def boom(prompt, **kwargs):
        raise RuntimeError("down")

    async def tiny(prompt, **kwargs):
        return "ok"

    assert run(compose_checkin("Rayxon", NOW, None, context={}, generate=boom)) is None
    assert run(compose_checkin("Rayxon", NOW, None, context={}, generate=tiny)) is None


def test_context_roundtrip(tmp_path):
    path = str(tmp_path / "ctx.json")
    assert load_context(path) == {}
    save_context({"date": "2026-10-27", "last_reply": "a"}, path)
    save_context({"last_checkin": "b"}, path)
    assert load_context(path) == {"date": "2026-10-27", "last_reply": "a", "last_checkin": "b"}


def test_send_uses_ai_text_and_escapes_html(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    bot = AsyncMock()

    with patch(
        "src.schedulers.remote_staff_checkin_scheduler.fetch_recent_calls_for_rep", return_value=ACTIVITY
    ), patch(
        "src.services.core.checkin_composer.compose_checkin",
        AsyncMock(return_value="3 ta qo'ng'iroq <b>zo'r</b>! Qaysi biri qiziqdi?"),
    ):
        ok = run(send_remote_checkin(bot, now_fn=lambda: NOW, tg_handle="@RayxonJonbranding"))

    assert ok is True
    text = bot.send_message.call_args.args[1]
    assert text.startswith("Rayxon (@RayxonJonbranding), 3 ta")
    assert "&lt;b&gt;" in text and "Assalomu alaykum" not in text
    assert load_context()["last_checkin"] == text
