"""Jamoa ritmi va Hamroh: jadval, xotira, AI zaxira matnlari, mention va handler oqimi."""
from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from src.handlers.jamoa_hamroh import (
    EMPTY_MENTION_REPLY,
    HamrohService,
    register_jamoa_hamroh_handlers,
)
from src.schedulers import jamoa_ritm_scheduler as sched
from src.services.core.jamoa_ritm import (
    ROLE_HAMROH,
    ROLE_MEMBER,
    ROLE_RITM,
    HamrohBrain,
    JamoaConfig,
    JamoaStore,
    ReplyLimiter,
    extract_question,
    format_transcript,
    is_addressed,
    load_config,
)
from src.services.core.jamoa_ritm.brain import ANSWER_FALLBACK
from src.services.core.jamoa_ritm.texts import RETRO_FALLBACK

TZ = ZoneInfo("Asia/Tashkent")
MONDAY = date(2026, 1, 5)  # Dushanba
GROUP = -1001234567890
OWNER = 555


def at(day_offset: int, hour: int, minute: int) -> datetime:
    d = MONDAY + timedelta(days=day_offset)
    return datetime(d.year, d.month, d.day, hour, minute, tzinfo=TZ)


class FakeDB:
    def __init__(self):
        self.conn = sqlite3.connect(":memory:")

    async def execute(self, query, params=None):
        cur = self.conn.execute(query, params or [])
        cols = [c[0] for c in cur.description] if cur.description else []
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    async def commit(self):
        self.conn.commit()


class TelegramBadRequest(Exception):
    """aiogram'dagi shu nomli xato o'rnida: Telegram so'rovni aniq rad etdi."""


class TelegramNetworkError(Exception):
    """aiogram'dagi shu nomli xato o'rnida: natija noaniq."""


class FakeBot:
    def __init__(self, fail: type[Exception] | None = None, deliver_then_fail: bool = False):
        self.sent: list[tuple] = []
        self.fail = fail
        self.deliver_then_fail = deliver_then_fail

    async def send_message(self, chat_id, text, **kwargs):
        if self.deliver_then_fail:  # Telegram qabul qildi, lekin javob yo'qoldi
            self.sent.append((chat_id, text))
            raise TelegramNetworkError("timeout")
        if self.fail:
            raise self.fail("telegram error")
        self.sent.append((chat_id, text))


def make_cfg(**overrides) -> JamoaConfig:
    base = dict(group_id=GROUP, owner_id=OWNER, ritm_enabled=True, hamroh_enabled=True)
    base.update(overrides)
    return JamoaConfig(**base)


def make_brain(reply: str = "AI javobi", calls: list | None = None, fail: bool = False) -> HamrohBrain:
    async def generate(prompt, *, system, max_tokens, temperature):
        if calls is not None:
            calls.append(prompt)
        if fail:
            raise RuntimeError("provider down")
        return reply

    return HamrohBrain(generate=generate, tz=TZ)


# ─── config ──────────────────────────────────────────────────────────────────

def test_load_config_from_env(monkeypatch):
    for key in ("JAMOA_GROUP_ID", "JAMOA_OWNER_ID", "JAMOA_RITM_ENABLED",
                "JAMOA_HAMROH_ENABLED", "DISABLE_UNSOLICITED_REPORTS"):
        monkeypatch.delenv(key, raising=False)
    settings_obj = SimpleNamespace(OWNER_ID=7)

    off = load_config(settings_obj)
    assert off.group_id is None and not off.ritm_active and not off.hamroh_active
    assert off.owner_id == 7

    monkeypatch.setenv("JAMOA_GROUP_ID", str(GROUP))
    monkeypatch.setenv("JAMOA_OWNER_ID", "99")
    on = load_config(settings_obj)
    assert on.group_id == GROUP and on.owner_id == 99 and on.ritm_active and on.hamroh_active

    monkeypatch.setenv("DISABLE_UNSOLICITED_REPORTS", "1")
    monkeypatch.setenv("JAMOA_HAMROH_ENABLED", "off")
    muted = load_config(settings_obj)
    assert not muted.ritm_active and not muted.hamroh_active

    monkeypatch.setenv("JAMOA_GROUP_ID", "not-a-number")
    assert load_config(settings_obj).group_id is None


# ─── jadval ──────────────────────────────────────────────────────────────────

def _due(now: datetime) -> list[str]:
    return [s.key for s in sched.SLOTS if sched.slot_due(s, now)]


def test_schedule_matches_jadval():
    assert MONDAY.weekday() == 0
    assert _due(at(0, 9, 0)) == ["haftalik_start"]
    assert _due(at(1, 9, 10)) == ["ertalabki_start"]
    assert _due(at(1, 9, 30)) == []  # 30 daqiqalik oyna tugadi
    assert _due(at(0, 17, 30)) == ["kun_yakuni"]
    assert _due(at(3, 17, 45)) == ["kun_yakuni"]
    assert _due(at(4, 17, 10)) == ["ozini_tahlil"]
    assert _due(at(4, 17, 35)) == []  # juma: kun yakuni yo'q
    assert _due(at(4, 16, 5)) == ["haftalik_retro"]
    assert _due(at(4, 9, 0)) == ["ertalabki_start"]
    assert _due(at(5, 9, 0)) == [] and _due(at(6, 17, 30)) == []


async def test_slot_sent_once_and_recorded():
    store, bot = JamoaStore(FakeDB()), FakeBot()
    kwargs = dict(cfg=make_cfg(), store=store, brain=make_brain(), bot=bot, bot_username="jonairobot")

    assert await sched.run_due_slots(at(0, 9, 1), **kwargs) == ["haftalik_start"]
    assert await sched.run_due_slots(at(0, 9, 5), **kwargs) == []
    assert len(bot.sent) == 1
    chat_id, text = bot.sent[0]
    assert chat_id == GROUP and "@jonairobot" in text and "maqsad" in text

    saved = await store.recent_messages(GROUP, 0)
    assert [m["role"] for m in saved] == [ROLE_RITM]


async def test_rejected_send_is_retried_later():
    store = JamoaStore(FakeDB())
    kwargs = dict(cfg=make_cfg(), store=store, brain=make_brain())
    assert await sched.run_due_slots(at(1, 9, 0), bot=FakeBot(fail=TelegramBadRequest), **kwargs) == []
    assert not await store.was_sent("ertalabki_start", at(1, 9, 0).date().isoformat())
    assert await sched.run_due_slots(at(1, 9, 2), bot=FakeBot(), **kwargs) == ["ertalabki_start"]


async def test_uncertain_send_is_not_repeated():
    store, bot = JamoaStore(FakeDB()), FakeBot(deliver_then_fail=True)
    kwargs = dict(cfg=make_cfg(), store=store, brain=make_brain(), bot=bot)
    assert await sched.run_due_slots(at(1, 9, 0), **kwargs) == []
    assert await sched.run_due_slots(at(1, 9, 1), **kwargs) == []
    assert len(bot.sent) == 1
    assert await store.slot_status("ertalabki_start", at(1, 9, 0).date().isoformat()) == "uncertain"


async def test_log_write_failure_after_delivery_does_not_resend():
    """Codex review: Telegram qabul qilib, jurnal yozilmasa — qayta yuborilmasligi kerak."""
    store, bot = JamoaStore(FakeDB()), FakeBot()

    async def broken_status(*args, **kwargs):
        raise RuntimeError("db write failed")

    store.set_slot_status = broken_status
    kwargs = dict(cfg=make_cfg(), store=store, brain=make_brain(), bot=bot)
    for minute in (0, 1, 2):
        await sched.run_due_slots(at(1, 9, minute), **kwargs)
    assert len(bot.sent) == 1


async def test_weekly_review_counts_whole_week_beyond_transcript_limit():
    """Codex review: 400 dan ko'p xabarda statistika to'liq hafta bo'yicha bo'lishi kerak."""
    store, bot = JamoaStore(FakeDB()), FakeBot()
    friday = at(4, 17, 0)
    base = int(friday.timestamp()) - 3 * 24 * 3600
    for i in range(500):
        await store.save_message(chat_id=GROUP, text=f"xabar {i}", user_name="Ali", ts=base + i)
    await sched.run_due_slots(friday, cfg=make_cfg(), store=store, brain=make_brain(fail=True), bot=bot)
    review = bot.sent[0][1]
    assert "(butun hafta): kuzatilgan xabarlar — 500" in review
    assert "faqat oxirgi" not in review


async def test_friday_retro_to_group_and_review_to_owner():
    store, bot, calls = JamoaStore(FakeDB()), FakeBot(), []
    friday = at(4, 16, 0)
    await store.save_message(chat_id=GROUP, text="Logotip tayyor", user_name="Ali",
                             ts=int(friday.timestamp()) - 3600)
    kwargs = dict(cfg=make_cfg(), store=store, brain=make_brain("Hafta yakuni 🔁 ...", calls), bot=bot)

    assert await sched.run_due_slots(friday, **kwargs) == ["haftalik_retro"]
    assert await sched.run_due_slots(at(4, 17, 0), **kwargs) == ["ozini_tahlil"]
    assert bot.sent[0] == (GROUP, "Hafta yakuni 🔁 ...")
    assert bot.sent[1][0] == OWNER
    assert bot.sent[1][1].startswith(("Hamroh: haftalik oʻz-oʻzini tahlil", "Hamroh: haftalik o'z-o'zini tahlil"))
    assert "Logotip tayyor" in calls[0]


async def test_owner_slot_skipped_without_owner():
    bot = FakeBot()
    sent = await sched.run_due_slots(at(4, 17, 0), cfg=make_cfg(owner_id=None),
                                     store=JamoaStore(FakeDB()), brain=make_brain(), bot=bot)
    assert sent == [] and bot.sent == []


# ─── xotira ──────────────────────────────────────────────────────────────────

async def test_store_order_limit_and_prune():
    store = JamoaStore(FakeDB())
    for i in range(5):
        await store.save_message(chat_id=GROUP, text=f"xabar {i}", user_name="Ali", ts=1000 + i)
    await store.save_message(chat_id=GROUP, text="   ", ts=2000)  # bo'sh matn yozilmaydi
    await store.save_message(chat_id=-1, text="boshqa guruh", ts=1003)

    last_two = await store.recent_messages(GROUP, 0, limit=2)
    assert [m["text"] for m in last_two] == ["xabar 3", "xabar 4"]
    await store.prune(1003)
    assert [m["text"] for m in await store.recent_messages(GROUP, 0)] == ["xabar 3", "xabar 4"]


# ─── AI ──────────────────────────────────────────────────────────────────────

async def test_brain_fallbacks_when_ai_fails_or_no_data():
    failing = make_brain(fail=True)
    assert await failing.answer("Savol?", []) == ANSWER_FALLBACK
    calls: list = []
    assert await make_brain(calls=calls).weekly_retro([]) == RETRO_FALLBACK
    assert calls == []
    review = await failing.self_review([{"role": ROLE_MEMBER, "text": "x", "created_at": 1}])
    assert "kuzatilgan xabarlar — 1" in review


def test_transcript_keeps_newest_lines():
    msgs = [{"user_name": "Ali", "text": f"matn {i}", "role": ROLE_MEMBER, "created_at": 1700000000 + i}
            for i in range(50)]
    msgs.append({"text": "javob", "role": ROLE_HAMROH, "created_at": 1700000100})
    out = format_transcript(msgs, max_chars=120, tz=TZ)
    assert out.endswith("Hamroh: javob") and "matn 0" not in out and len(out) <= 120


# ─── mention va tezlik ───────────────────────────────────────────────────────

@pytest.mark.parametrize("text,reply_to,expected", [
    ("@jonairobot hisobot qachon?", None, True),
    ("Salom @JonAiRobot", None, True),
    ("Oisha, bugungi hisobot qachon?", None, True),
    ("Oishaxon rahmat!", None, True),
    ("@jonairobot2 bu boshqa bot", None, False),
    ("/oisha_stats@jonairobot", None, False),
    ("yozing: a@jonairobot.uz", None, False),
    ("oddiy xabar", None, False),
    ("rahmat", 999, True),
    ("rahmat", 1, False),
    ("Amina, buni qanday qilaman?", None, False),
    ("Amina, buni qanday qilaman?", 999, False),
    ("Mr.Jon narx diapazoni qancha?", 999, False),
    ("@jon_clawbot salom", 999, False),
    ("Amina, Oishaga yozing", None, False),
    ("Amina, Oishaga yozing", 999, False),
    ("Mr.Jon, Oishaga yubor", 999, False),
    ("Amina, @jonairobot ga yoz", None, True),
    ("Oisha va Amina, eshiting", None, True),
])
def test_is_addressed(text, reply_to, expected):
    assert is_addressed(text, bot_username="jonairobot", bot_id=999, reply_to_user_id=reply_to) is expected


async def test_hamroh_brain_loads_synced_oisha_soul(tmp_path, monkeypatch):
    from src.services.core.jamoa_ritm import texts as ritm_texts

    soul_file = tmp_path / "SOUL.md"
    soul_file.write_text("# Oisha Custom Yadro\nMaxsus sinov qoidasi.", encoding="utf-8")
    monkeypatch.setattr(ritm_texts, "_OISHA_SOUL_PATH", soul_file)
    seen_systems = []

    async def capture(prompt, *, system, max_tokens, temperature):
        seen_systems.append(system)
        return "Tayyor."

    brain = HamrohBrain(generate=capture, tz=TZ)
    await brain.answer("Hisobot qachon?", [], asker="Rayxon")
    assert "Maxsus sinov qoidasi." in seen_systems[0]


def test_extract_question_and_limiter():
    assert extract_question("@jonairobot , hisobot qachon?", "jonairobot") == "hisobot qachon?"
    assert extract_question("@jonairobot", "jonairobot") == ""
    assert extract_question("Oisha, hisobot qachon?", "jonairobot") == "hisobot qachon?"
    assert extract_question("Oisha", "jonairobot") == ""

    now = [0.0]
    limiter = ReplyLimiter(per_user_seconds=10, max_per_window=2, window_seconds=60, clock=lambda: now[0])
    assert limiter.allow(1) and not limiter.allow(1)
    assert limiter.allow(2) and not limiter.allow(3)  # daqiqalik chegara
    now[0] = 61
    assert limiter.allow(1)



# ─── handler ─────────────────────────────────────────────────────────────────

class FakeTgBot:
    async def me(self):
        return SimpleNamespace(id=999, username="jonairobot")


def make_message(text, *, chat_id=GROUP, user_id=1, is_bot=False, reply_to=None):
    replies: list = []

    async def reply(answer, **kwargs):
        replies.append(answer)

    msg = SimpleNamespace(
        chat=SimpleNamespace(id=chat_id), text=text, caption=None, message_id=10,
        from_user=SimpleNamespace(id=user_id, is_bot=is_bot, full_name="Ali Valiyev"),
        reply_to_message=reply_to, bot=FakeTgBot(), reply=reply,
    )
    return msg, replies


async def test_hamroh_observes_and_answers_mentions():
    store, calls = JamoaStore(FakeDB()), []
    service = HamrohService(make_cfg(), store, make_brain("Payshanba kuni.", calls), quiet_check=lambda: False)

    for text, kwargs in (("Hisobot payshanbaga ko'chdi", {}), ("begona", {"chat_id": -5}),
                         ("bot yozdi", {"is_bot": True})):
        await service.observe(make_message(text, **kwargs)[0])
    question, replies = make_message("@jonairobot hisobot qachon?")
    await service.observe(question)

    assert await service.is_for_me(question)
    assert not await service.is_for_me(make_message("oddiy gap")[0])
    assert await service.respond(question) == "Payshanba kuni."
    assert replies == ["Payshanba kuni."]
    assert "Hisobot payshanbaga ko'chdi" in calls[0] and "begona" not in calls[0]
    roles = [m["role"] for m in await store.recent_messages(GROUP, 0)]
    assert roles == [ROLE_MEMBER, ROLE_MEMBER, ROLE_HAMROH]


async def test_hamroh_quiet_hours_and_empty_mention():
    calls: list = []
    quiet = HamrohService(make_cfg(), JamoaStore(FakeDB()), make_brain(calls=calls), quiet_check=lambda: True)
    msg, replies = make_message("@jonairobot salom")
    assert await quiet.respond(msg) is None and replies == []

    awake = HamrohService(make_cfg(), JamoaStore(FakeDB()), make_brain(calls=calls), quiet_check=lambda: False)
    msg, replies = make_message("@jonairobot")
    assert await awake.respond(msg) == EMPTY_MENTION_REPLY and calls == []


def test_register_wires_dispatcher_only_when_configured():
    from aiogram import Dispatcher

    dp = Dispatcher()
    assert register_jamoa_hamroh_handlers(dp, config_loader=lambda: make_cfg(group_id=None)) is None
    assert len(dp.message.handlers) == 0

    service = register_jamoa_hamroh_handlers(dp, config_loader=make_cfg, store=JamoaStore(FakeDB()),
                                             brain=make_brain())
    assert isinstance(service, HamrohService)
    assert len(dp.message.handlers) == 1
    assert len(dp.message.outer_middleware) == 1
