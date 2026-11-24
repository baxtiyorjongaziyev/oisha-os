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
        self.contacts = []

    async def answer(self, text, **kwargs):
        self.replies.append((text, kwargs.get("reply_markup")))
        return SimpleNamespace()

    async def answer_contact(self, **kwargs):
        self.contacts.append(kwargs)


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
    msg = _Message("90 123 45 67")
    await handler(msg)
    assert calls == ["+998901234567"]
    # Topilmasa ham kontakt kartasi yuboriladi (GET-LID xulqi).
    assert msg.contacts[0]["phone_number"] == "+998901234567"
    assert "topilmadi" in msg.replies[-1][0]


@pytest.mark.asyncio
async def test_phone_message_sends_contact_card_and_username_button():
    dp = _Dispatcher()

    async def fake_lookup(phone):
        return {"first_name": "Diyora", "last_name": "", "username": "S_S_Diyora", "user_id": 7}

    register_inline_search_handlers(
        dp, is_admin=lambda uid: True, perform_global_lookup=fake_lookup, db=object()
    )
    _filters, handler = dp.message_handlers[0]
    msg = _Message("+998930036373")
    await handler(msg)
    assert msg.contacts == [
        {"phone_number": "+998930036373", "first_name": "Diyora", "last_name": ""}
    ]
    text, markup = msg.replies[-1]
    assert "Raqam topildi" in text and "+998 93 003 63 73" in text
    button = markup.inline_keyboard[0][0]
    assert button.url == "https://t.me/S_S_Diyora"


def test_normalize_uz_phone_variants():
    from src.services.core.dispatcher.inline_search import normalize_uz_phone

    for raw in ("974900606", "998974900606", "+998 97 490 06 06", "8 97 490-06-06"):
        assert normalize_uz_phone(raw) == "+998974900606"


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


@pytest.mark.asyncio
async def test_inline_query_ignored_for_non_admin():
    dp = _Dispatcher()
    lookup_calls = []

    async def fake_lookup(phone):
        lookup_calls.append(phone)
        return {"first_name": "Secret", "last_name": "Lead", "user_id": 99}

    class _DB:
        def get_connection(self):
            raise AssertionError("non-admin inline query must not touch DB")

    register_inline_search_handlers(
        dp, is_admin=lambda uid: False, perform_global_lookup=fake_lookup, db=_DB()
    )
    _filters, handler = dp.inline_handlers[0]

    q_phone = _InlineQuery("+998901234567")
    await handler(q_phone)
    assert lookup_calls == []
    assert q_phone.answered[0][0] == []

    q_name = _InlineQuery("Kamila")
    await handler(q_name)
    assert q_name.answered[0][0] == []


def test_phone_re_matches_uz_numbers_only():
    assert re.search(PHONE_RE, "+998901234567")
    assert re.search(PHONE_RE, "call me on 90 123 45 67 please")
    assert not re.search(PHONE_RE, "hello world no digits here")
