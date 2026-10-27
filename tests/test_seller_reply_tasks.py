import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from src.handlers.seller_reply import is_checkin_text, register_seller_reply_handlers
from src.services.core.seller_reply_tasks import (
    ApplyResult,
    SellerAction,
    apply_actions,
    extract_actions,
    format_summary,
    parse_actions,
)

TZ = timezone(timedelta(hours=5))
NOW = datetime(2026, 10, 27, 11, 28, tzinfo=TZ)

LLM_JSON = """Mana:
[{"client": "Shaxboz aka", "phone": "+998 (99) 533-19-98", "action": "callback", "due": "2026-10-27 16:00", "note": "band edi"},
 {"client": "Farrux aka", "phone": null, "action": "payment", "due": "2026-10-29 10:00", "note": "ekspert tekshiruvi"},
 {"client": "2 ta raqam", "phone": null, "action": "wrong_number", "due": null, "note": ""},
 {"client": "", "action": "callback"},
 {"client": "X", "action": "dance"}]"""


def run(coro):
    return asyncio.run(coro)


class FakeAmo:
    def __init__(self, leads):
        self.leads = leads
        self.tasks = []

    async def search_leads(self, query, limit=5):
        return self.leads.get(query, [])

    async def create_task(self, element_id, text, complete_till, responsible_user_id=None):
        self.tasks.append((element_id, text, complete_till))
        return True


def test_parse_actions_filters_invalid_items():
    actions = parse_actions(LLM_JSON)
    assert [a.action for a in actions] == ["callback", "payment", "wrong_number"]
    assert actions[0].due == datetime(2026, 10, 27, 16, 0)


def test_parse_actions_handles_garbage():
    assert parse_actions("uzr, bilmadim") == []
    assert parse_actions("[not json") == []


def test_extract_actions_attaches_timezone():
    async def fake_generate(prompt, **kwargs):
        assert "Farrux" not in kwargs["system"]
        assert "2026-10-27 11:28" in prompt
        return LLM_JSON

    actions = run(extract_actions("javob", "check-in", NOW, generate=fake_generate))
    assert actions[0].due.tzinfo == TZ


def test_extract_actions_survives_llm_error():
    async def boom(prompt, **kwargs):
        raise RuntimeError("down")

    assert run(extract_actions("javob", "check-in", NOW, generate=boom)) == []


def test_apply_actions_creates_task_for_unique_lead_only():
    amo = FakeAmo({"995331998": [{"id": 101}], "Farrux aka": [{"id": 1}, {"id": 2}]})
    actions = [
        SellerAction("Shaxboz aka", "callback", phone="+998 (99) 533-19-98",
                     due=datetime(2026, 10, 27, 16, 0, tzinfo=TZ)),
        SellerAction("Farrux aka", "payment"),
        SellerAction("2 ta raqam", "wrong_number"),
    ]
    result = run(apply_actions(amo, actions, NOW))
    assert [a.client for a in result.created] == ["Shaxboz aka"]
    assert [a.client for a in result.unresolved] == ["Farrux aka"]
    assert [a.client for a in result.skipped] == ["2 ta raqam"]
    lead_id, text, due_ts = amo.tasks[0]
    assert lead_id == 101 and "Qayta qo'ng'iroq" in text
    assert due_ts == int(datetime(2026, 10, 27, 16, 0, tzinfo=TZ).timestamp())


def test_apply_actions_defaults_due_two_hours():
    amo = FakeAmo({"Ali": [{"id": 7}]})
    run(apply_actions(amo, [SellerAction("Ali", "followup")], NOW))
    assert amo.tasks[0][2] == int((NOW + timedelta(hours=2)).timestamp())


def test_format_summary_is_friendly_and_asks_for_missing_phone():
    result = ApplyResult(
        created=[SellerAction("Shaxboz aka", "callback", due=datetime(2026, 10, 27, 16, 0))],
        unresolved=[SellerAction("Farrux aka", "payment")],
        skipped=[SellerAction("2 ta raqam", "wrong_number")],
    )
    text = format_summary("Rayxon", result)
    assert text.startswith("Rahmat, Rayxon!")
    assert "Qayta qo'ng'iroq — Shaxboz aka (27.10 16:00)" in text
    assert "Farrux aka — amoCRM'da lidini aniq topa olmadim" in text
    assert "raqam ishlamaydi" in text


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


def _message(chat_id, reply_from_id, reply_text, is_bot=False):
    async def me():
        return SimpleNamespace(id=999)

    reply = SimpleNamespace(from_user=SimpleNamespace(id=reply_from_id), text=reply_text, caption=None)
    return SimpleNamespace(
        chat=SimpleNamespace(id=chat_id),
        from_user=SimpleNamespace(id=5, is_bot=is_bot, first_name="Rayxona"),
        reply_to_message=reply,
        bot=SimpleNamespace(me=me),
        text="Shaxboz aka band",
        caption=None,
    )


def test_filter_only_catches_replies_to_bot_checkin():
    disp = FakeDispatcher()
    register_seller_reply_handlers(disp, amocrm_getter=lambda: None, group_id_getter=lambda: -100)
    _, (flt,) = disp.handlers[0]
    checkin = "Assalomu alaykum, Rayxon! Oxirgi soatda 7 ta raqam terdingiz"
    assert run(flt(_message(-100, 999, checkin)))
    assert not run(flt(_message(-200, 999, checkin)))
    assert not run(flt(_message(-100, 42, checkin)))
    assert not run(flt(_message(-100, 999, "Bugungi hisobot")))
    assert not run(flt(_message(-100, 999, checkin, is_bot=True)))
