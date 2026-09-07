import re
from types import SimpleNamespace

import pytest

from src.services.core.dispatcher.inline_search import (
    PHONE_RE,
    register_inline_search_handlers,
)


class _Dispatcher:
    def __init__(self):
        self.inline_handlers = []
        self.message_handlers = []

    def inline_query(self, *filters):
        def deco(fn):
            self.inline_handlers.append((filters, fn))
            return fn

        return deco

    def message(self, *filters):
        def deco(fn):
            self.message_handlers.append((filters, fn))
            return fn

        return deco


class _InlineQuery:
    def __init__(self, text):
        self.query = text
        self.text = text
        self.from_user = SimpleNamespace(id=150074828)
        self.answered = []

    async def answer(self, results, **kwargs):
        self.answered.append((results, kwargs))


class _Message:
    def __init__(self, text):
        self.text = text
        self.from_user = SimpleNamespace(id=150074828)
        self.replies = []

    async def answer(self, text, **kwargs):
        self.replies.append(text)
        return SimpleNamespace(edit_text=self._edit)

    async def _edit(self, text, **kwargs):
        self.replies.append(("edit", text))


@pytest.mark.asyncio
async def test_inline_query_name_returns_article_results():
    dp = _Dispatcher()

    async def fake_lookup(phone):
        return None

    class _DB:
        def get_connection(self):
            raise AssertionError("name path must not hit the DB in this fake")

    register_inline_search_handlers(
        dp, is_admin=lambda uid: True, perform_global_lookup=fake_lookup, db=_DB()
    )
    assert dp.inline_handlers, "inline_query handler not registered"
    _filters, handler = dp.inline_handlers[0]

    q = _InlineQuery("Kamila")
    await handler(q)
    assert q.answered, "handler must call inline_query.answer"
    results, _ = q.answered[0]
    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_inline_query_phone_returns_contact_result():
    dp = _Dispatcher()

    async def fake_lookup(phone):
        return {
            "first_name": "Ali",
            "last_name": "V",
            "username": "aliv",
            "user_id": 42,
        }

    register_inline_search_handlers(
        dp, is_admin=lambda uid: True, perform_global_lookup=fake_lookup, db=object()
    )
    _filters, handler = dp.inline_handlers[0]
    q = _InlineQuery("+998901234567")
    await handler(q)
    results, _ = q.answered[0]
    assert len(results) == 1
    assert getattr(results[0], "id", None) is not None


@pytest.mark.asyncio
async def test_phone_message_triggers_lookup():
    dp = _Dispatcher()
    calls = []

    async def fake_lookup(phone):
        calls.append(phone)
        return None

    register_inline_search_handlers(
        dp, is_admin=lambda uid: True, perform_global_lookup=fake_lookup, db=object()
    )
    assert dp.message_handlers, "phone-search message handler not registered"
    _filters, handler = dp.message_handlers[0]
    await handler(_Message("+998 90 123 45 67"))
    assert calls == ["+998 90 123 45 67"]


@pytest.mark.asyncio
async def test_phone_message_ignored_for_non_admin():
    dp = _Dispatcher()
    calls = []

    async def fake_lookup(phone):
        calls.append(phone)
        return None

    register_inline_search_handlers(
        dp, is_admin=lambda uid: False, perform_global_lookup=fake_lookup, db=object()
    )
    _filters, handler = dp.message_handlers[0]
    await handler(_Message("+998 90 123 45 67"))
    assert calls == []


def test_phone_re_matches_uz_numbers_only():
    assert re.search(PHONE_RE, "+998901234567")
    assert re.search(PHONE_RE, "call me on 90 123 45 67 please")
    assert not re.search(PHONE_RE, "hello world no digits here")
