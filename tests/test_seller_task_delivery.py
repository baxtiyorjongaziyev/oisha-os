"""Synthetic CRM tasks; no production data or network calls."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.core.crm.task_notifier.routing import resolve_seller, SELLERS
from src.services.core.crm.task_notifier.delivery import deliver, _SENT
from src.services.core.crm.task_notifier.notifier import AmoCrmTaskNotifier
from src.services.core.crm.amocrm.task_reader import read_tasks
from src.services.core.crm.task_notifier.formatter import _format_timestamp


def lead(field=None, tags=()):
    return {"name": "Synthetic test lead", "_embedded": {"tags": [{"name": t} for t in tags]},
            "custom_fields_values": [] if field is None else [
                {"field_id": 1559389, "values": [{"value": field}]}]}


@pytest.mark.parametrize("field,tags,expected", [
    ("Rayxon", (), "Rayxon"), (None, ("Rayxona",), "Rayxon"),
    ("Shahnoza", ("Shahnoza", "Target"), "Shahnoza"),
    (None, ("Mumtozmahal",), "Mumtozmaxal"),
    (None, (), None), ("Unknown", ("Rayxon",), None),
    ("Shahnoza", ("Rayxon",), None),
    (None, ("Rayxon", "Shahnoza"), None),
])
def test_resolve(field, tags, expected):
    seller = resolve_seller(lead(field, tags))
    assert (seller.name if seller else None) == expected


class ReceiptDB:
    def __init__(self):
        self.claims, self.states = set(), {}

    async def get_state(self, key):
        return self.states.get(key)

    async def set_state(self, key, value):
        self.states[key] = value

    async def claim_job_run(self, key, date):
        if key in self.claims:
            return False
        self.claims.add(key)
        return True

    async def release_job_run(self, key, date):
        self.claims.discard(key)


@pytest.mark.asyncio
async def test_concurrent_delivery_restart_reschedule_and_reassignment():
    _SENT.clear()
    db, bot = ReceiptDB(), SimpleNamespace(send_message=AsyncMock(return_value=SimpleNamespace(message_id=123)))
    task = {"id": 10001, "complete_till": 1000}
    send = lambda seller=SELLERS["rayxon"]: deliver(bot, db, task, seller, "due", "Synthetic", None)
    assert sum(await asyncio.gather(send(), send())) == 1
    _SENT.clear()
    assert not await send()
    task["complete_till"] = 2000
    assert await send()
    assert await send(SELLERS["shahnoza"])
    assert bot.send_message.call_count == 3
    assert all("message_thread_id" not in call.kwargs for call in bot.send_message.call_args_list)


@pytest.mark.asyncio
async def test_ambiguous_transport_failure_is_not_replayed():
    _SENT.clear()
    db, bot = ReceiptDB(), SimpleNamespace(send_message=AsyncMock(side_effect=TimeoutError))
    task = {"id": 10002}
    assert not await deliver(bot, db, task, SELLERS["rayxon"], "due", "Synthetic", None)
    assert not await deliver(bot, db, task, SELLERS["rayxon"], "due", "Synthetic", None)
    assert bot.send_message.call_count == 1


@pytest.mark.asyncio
async def test_storage_failure_blocks_send():
    db = SimpleNamespace(get_state=AsyncMock(side_effect=RuntimeError))
    bot = SimpleNamespace(send_message=AsyncMock())
    assert not await deliver(bot, db, {"id": 10003}, SELLERS["rayxon"], "due", "Synthetic", None)
    bot.send_message.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("entity_type,completed,tags,expected", [
    ("leads", False, ("Rayxon",), True),
    ("2", False, ("Shahnoza",), True),
    ("contacts", False, ("Rayxon",), False),
    ("leads", True, ("Rayxon",), False),
    ("leads", False, ("Rayxon", "Shahnoza"), False),
    ("leads", False, (), False),
])
async def test_notifier_private_routing(entity_type, completed, tags, expected):
    _SENT.clear()
    crm = MagicMock()
    crm.get_lead = AsyncMock(return_value=lead(tags=tags))
    crm.subdomain = "jonbranding"
    crm.get_lead_phone.return_value = None
    bot = SimpleNamespace(send_message=AsyncMock())
    notifier = AmoCrmTaskNotifier(crm, ReceiptDB(), bot)
    task = {"id": 10004, "text": "Synthetic", "entity_id": 1,
            "element_type": entity_type, "is_completed": completed}
    assert await notifier.send_task_alert(task, "new") == expected
    if expected:
        assert bot.send_message.call_args.kwargs["chat_id"] == resolve_seller(lead(tags=tags)).chat_id


def response(status, ids=(), more=False):
    return SimpleNamespace(status_code=status, json=lambda: {
        "_embedded": {"tasks": [{"id": i} for i in ids]},
        "_links": {"next": {"href": "next"}} if more else {},
    })


@pytest.mark.asyncio
async def test_task_reader_all_pages_and_failure():
    crm = SimpleNamespace(access_token=True, base_url="https://synthetic.invalid", last_error=None,
                          _request_with_auth=AsyncMock(side_effect=[response(200, (1, 2), True), response(200, (3,))]))
    assert [t["id"] for t in await read_tasks(crm)] == [1, 2, 3]
    assert crm._request_with_auth.call_args.kwargs["params"]["page"] == 2
    crm._request_with_auth.side_effect = [response(200, (1,), True), response(503)]
    with pytest.raises(RuntimeError, match="get_tasks_http_503"):
        await read_tasks(crm)


def test_tashkent_timestamp_is_host_independent():
    assert _format_timestamp(0)
    assert _format_timestamp(1767225600) == "01.01.2026 05:00"
