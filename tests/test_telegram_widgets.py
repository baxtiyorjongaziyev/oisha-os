import asyncio

import pytest

from src.services.core.telegram.ai_features.bot_api_client import TelegramBotAPI10Client
from src.services.core.telegram.widgets import (
    WidgetClient,
    WidgetLimitError,
    WidgetQueryRouter,
    render_widget,
    send_widget_or_text,
    validate_html,
    widgets_enabled,
)
from src.services.core.telegram.widgets import templates as t
from src.services.core.telegram.widgets.router import (
    DENIED_ANSWER,
    TIMEOUT_ANSWER,
    UNKNOWN_ANSWER,
    parse_widget_update,
)


class FakeTransport:
    def __init__(self, result=None, fail=None):
        self.calls = []
        self.result = {"message_id": 7} if result is None else result
        self.fail = fail

    async def __call__(self, method, payload):
        self.calls.append((method, payload))
        if self.fail and method in self.fail:
            return {"ok": False, "error_code": 400, "description": "Bad Request"}
        return {"ok": True, "result": self.result}


def make_client(**kw):
    transport = FakeTransport(**kw)
    api = TelegramBotAPI10Client("123:TEST", transport=transport)
    return WidgetClient(api), transport


def run(coro):
    return asyncio.run(coro)


# --- limits ---------------------------------------------------------------

def test_validate_html_rejects_empty_nul_and_oversize():
    with pytest.raises(WidgetLimitError):
        validate_html("")
    with pytest.raises(WidgetLimitError, match="NUL"):
        validate_html("a\x00b")
    with pytest.raises(WidgetLimitError):
        validate_html("x" * 40000)


def test_validate_html_rejects_poorly_compressible_content():
    import os

    with pytest.raises(WidgetLimitError, match="compressed"):
        validate_html(os.urandom(12000).hex())


# --- client ---------------------------------------------------------------

def test_send_widget_drops_unset_fields():
    client, transport = make_client()
    res = run(client.send_widget(42, "<b>x</b>", allow_queries=True))
    method, payload = transport.calls[0]
    assert method == "sendWidget"
    assert payload == {"chat_id": 42, "html": "<b>x</b>", "allow_queries": True}
    assert res == {"message_id": 7}


def test_send_widget_reply_parameters():
    client, transport = make_client()
    run(client.send_widget(1, "<p>x</p>", reply_to_message_id=5))
    assert transport.calls[0][1]["reply_parameters"] == {"message_id": 5}


def test_state_limit_enforced_before_request():
    client, transport = make_client()
    with pytest.raises(WidgetLimitError, match="chat_data"):
        run(client.send_widget(1, "<p>x</p>", chat_data="ф" * 600))
    assert transport.calls == []


def test_edit_requires_target():
    client, _ = make_client()
    with pytest.raises(ValueError):
        run(client.edit_message_widget_data(chat_data="{}"))


def test_shared_cache_time_bounds():
    client, transport = make_client(result=True)
    with pytest.raises(WidgetLimitError):
        run(client.edit_shared_widget_data("w1", cache_time=2))
    run(client.edit_shared_widget_data("w1", public_data="{}", cache_time=9999))
    assert transport.calls[-1][1]["cache_time"] == 3600


# --- templates ------------------------------------------------------------

def test_render_widget_fits_limits_with_all_components():
    html = render_widget(
        t.header("Kunlik hisobot", "12-noyabr"),
        t.kpi_row([("Lidlar", 14), ("Sotuv", "3.2 mln"), ("Konversiya", "21%")]),
        t.progress("Vazifalar", 7, 10),
        t.card_list([("Akmal", "Yangi lid"), ("Dilnoza", "Toʻlov kutilmoqda")], ["ok", "warn"]),
        t.table(["Menejer", "Lid"], [["Akmal", 5], ["Dilnoza", 9]], numeric=[1]),
        t.action_bar([("Tasdiqla", "crm:approve:1"), ("Rad et", "crm:reject:1")], secondary=[1]),
        interactive=True,
    )
    validate_html(html)
    assert "TelegramWidget.request" in html


def test_templates_escape_user_text():
    html = render_widget(t.header("<script>alert(1)</script>"))
    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html


def test_action_query_over_64_bytes_rejected():
    with pytest.raises(WidgetLimitError):
        t.action_bar([("X", "a" * 65)])


# --- flags ----------------------------------------------------------------

def test_flags(monkeypatch):
    monkeypatch.delenv("WIDGETS_ENABLED", raising=False)
    assert widgets_enabled("reports") is False
    monkeypatch.setenv("WIDGETS_ENABLED", "1")
    monkeypatch.setenv("WIDGETS_MODULES", "reports, approvals")
    assert widgets_enabled("reports") is True
    assert widgets_enabled("crm") is False
    monkeypatch.setenv("WIDGETS_MODULES", "*")
    assert widgets_enabled("crm") is True


# --- router ---------------------------------------------------------------

def widget_update(data, user_id=100, key="widget_query"):
    return {
        "update_id": 1,
        key: {
            "id": "q1",
            "from": {"id": user_id},
            "chat": {"id": user_id, "type": "private"},
            "message_id": 10,
            "data": data,
        },
    }


def test_parse_widget_update():
    q = parse_widget_update(widget_update("CRM:Approve:42:x"))
    assert (q.module, q.action, q.arg) == ("crm", "approve", "42:x")
    assert q.chat_id == 100 and q.message_id == 10 and not q.shared
    assert parse_widget_update({"message": {}}) is None
    assert parse_widget_update(widget_update("a", key="shared_widget_query")).shared


def answers(transport):
    return [p.get("data") for m, p in transport.calls if m == "answerWidgetQuery"]


def test_router_dispatches_and_answers():
    client, transport = make_client(result=True)
    router = WidgetQueryRouter(client, allowed_user_ids=[100])

    async def crm(q):
        return f"ok {q.action} {q.arg}"

    router.register("crm", crm)
    res = run(router.handle_update(widget_update("crm:approve:42")))
    assert res["reason"] == "ok" and res["answered"]
    assert answers(transport) == ["ok approve 42"]


def test_router_denies_unknown_user_and_module():
    client, transport = make_client(result=True)
    router = WidgetQueryRouter(client, allowed_user_ids=[100])
    run(router.handle_update(widget_update("crm:x", user_id=999)))
    run(router.handle_update(widget_update("nope:x")))
    assert answers(transport) == [DENIED_ANSWER, UNKNOWN_ANSWER]


def test_router_policy_denial():
    client, transport = make_client(result=True)

    async def deny(q):
        return False

    router = WidgetQueryRouter(client, authorizer=deny)
    router.register("crm", lambda q: asyncio.sleep(0, "x"))
    res = run(router.handle_update(widget_update("crm:x")))
    assert res["reason"] == "policy_denied"
    assert answers(transport) == [DENIED_ANSWER]


def test_router_timeout_still_answers():
    client, transport = make_client(result=True)
    router = WidgetQueryRouter(client, timeout=0.01)

    async def slow(q):
        await asyncio.sleep(1)
        return "late"

    router.register("crm", slow)
    res = run(router.handle_update(widget_update("crm:x")))
    assert res["reason"] == "timeout"
    assert answers(transport) == [TIMEOUT_ANSWER]


def test_router_ignores_non_widget_updates():
    client, transport = make_client()
    res = run(WidgetQueryRouter(client).handle_update({"message": {"text": "hi"}}))
    assert res == {"handled": False, "reason": "not_widget_query"}
    assert transport.calls == []


# --- sender ---------------------------------------------------------------

def test_sender_uses_text_when_disabled(monkeypatch):
    monkeypatch.setenv("WIDGETS_ENABLED", "0")
    client, transport = make_client()
    sent = []

    async def send_text(chat_id, text):
        sent.append((chat_id, text))

    res = run(send_widget_or_text(
        client=client, chat_id=1, module="reports",
        build_html=lambda: render_widget(t.header("x")),
        fallback_text="matn", send_text=send_text,
    ))
    assert sent == [(1, "matn")] and transport.calls == []
    assert res.metadata["mode"] == "text" and res.reason == "widgets_disabled"


def test_sender_sends_widget_when_enabled(monkeypatch):
    monkeypatch.setenv("WIDGETS_ENABLED", "1")
    monkeypatch.delenv("WIDGETS_MODULES", raising=False)
    client, transport = make_client()

    async def send_text(chat_id, text):
        raise AssertionError("text must not be sent")

    res = run(send_widget_or_text(
        client=client, chat_id=1, module="reports",
        build_html=lambda: render_widget(t.header("x")),
        fallback_text="matn", send_text=send_text,
    ))
    assert res.success and res.metadata["mode"] == "widget"
    assert res.direct_message_ids == [7]


def test_sender_falls_back_on_api_error(monkeypatch):
    monkeypatch.setenv("WIDGETS_ENABLED", "1")
    client, _ = make_client(fail={"sendWidget"})
    sent = []

    async def send_text(chat_id, text):
        sent.append(text)

    res = run(send_widget_or_text(
        client=client, chat_id=1, module="reports",
        build_html=lambda: render_widget(t.header("x")),
        fallback_text="matn", send_text=send_text,
    ))
    assert sent == ["matn"]
    assert res.reason.startswith("widget_failed")


# --- wiring ---------------------------------------------------------------

def test_widget_updates_are_allowed_and_passed_through():
    from src.services.core.telegram.ai_features.models import (
        BOT_API_10_ALLOWED_UPDATES,
        classify_update,
    )
    from src.services.core.telegram.aiogram_head import AiogramBotHead

    for key in ("widget_query", "shared_widget_query"):
        assert key in BOT_API_10_ALLOWED_UPDATES
        assert key in AiogramBotHead._RAW_PASSTHROUGH_KEYS
    assert classify_update(widget_update("ping:x")) == "widget_query"


def test_polling_keeps_widget_updates_in_allowed_list():
    from tests.test_aiogram_head import _Bot, _Dispatcher
    from src.services.core.telegram.aiogram_head import AiogramBotHead

    async def scenario():
        dispatcher = _Dispatcher()
        head = AiogramBotHead(
            bot=_Bot(), dispatcher=dispatcher,
            allowed_updates=["message", "widget_query", "shared_widget_query"],
        )
        head.start()
        await dispatcher.started.wait()
        allowed = dispatcher.kwargs["allowed_updates"]
        await head.stop()
        return allowed

    assert run(scenario()) == ["message", "widget_query", "shared_widget_query"]


def test_aiogram_update_keeps_widget_query_in_dump():
    from aiogram.types import Update

    upd = Update.model_validate(widget_update("ping:x"))
    assert "widget_query" in upd.model_dump(exclude_none=True)


def test_process_telegram_ai_update_routes_widget_query(monkeypatch):
    from src.services.api_server import webhooks
    from src.services.core.telegram.widgets import runtime

    client, transport = make_client(result=True)
    router = WidgetQueryRouter(client, allowed_user_ids=[100])
    router.register("ping", runtime._ping)
    monkeypatch.setattr(runtime, "_router", router)

    res = run(webhooks.process_telegram_ai_update(widget_update("ping:go")))
    assert res["update_type"] == "widget_query" and res["answered"]
    assert answers(transport)[0].startswith("pong ")


def test_runtime_router_fails_closed_without_owner(monkeypatch):
    from src.services.core.telegram.widgets import runtime

    monkeypatch.setattr(runtime, "_allowed_ids", lambda: [])
    monkeypatch.setattr(runtime, "_bot_token", lambda: "123:TEST")
    runtime.reset_widget_router()
    try:
        router = runtime.get_widget_router()
        assert router.allowed_user_ids == {-1}
    finally:
        runtime.reset_widget_router()
