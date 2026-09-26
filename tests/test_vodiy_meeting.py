from types import SimpleNamespace

import pytest

from src.handlers.vodiy_meeting import _menu, _rich_card, register_vodiy_meeting_handlers


class FakeDispatcher:
    def __init__(self):
        self.messages = {}
        self.callbacks = {}

    def message(self, *filters):
        def register(fn):
            self.messages[fn.__name__] = fn
            return fn

        return register

    def callback_query(self, *filters):
        def register(fn):
            self.callbacks[fn.__name__] = fn
            return fn

        return register


class FakeState:
    def __init__(self):
        self.data = {}
        self.current = None

    async def set_state(self, value):
        self.current = value

    async def update_data(self, **kwargs):
        self.data.update(kwargs)

    async def get_data(self):
        return self.data

    async def clear(self):
        self.data = {}
        self.current = None


class FakeMessage:
    def __init__(self, text=""):
        self.text = text
        self.chat = SimpleNamespace(type="private", id=123)
        self.from_user = SimpleNamespace(id=123)
        self.answers = []
        self.sent_to_owner = []

        async def send_message(chat_id, content):
            self.sent_to_owner.append((chat_id, content))

        async def get_me():
            return SimpleNamespace(username="jonairobot")

        async def call_bot(method):
            self.rich_method = method

        class FakeBot:
            async def __call__(self, method):
                await call_bot(method)

        self.bot = FakeBot()
        self.bot.send_message = send_message
        self.bot.get_me = get_me

    async def answer(self, text, **kwargs):
        self.answers.append((text, kwargs))


@pytest.mark.asyncio
async def test_meeting_menu_and_registration():
    dispatcher = FakeDispatcher()
    register_vodiy_meeting_handlers(dispatcher, owner_id=999)
    state = FakeState()
    message = FakeMessage()

    await dispatcher.messages["show_meeting"](message, state)
    assert message.rich_method.__api_method__ == "sendRichMessage"
    assert message.rich_method.chat_id == 123
    assert len(_menu().inline_keyboard) == 2
    rows = [block for block in _rich_card("jonairobot")["blocks"] if block["type"] == "buttons"]
    assert len(rows) == 2 and all(len(row["buttons"]) == 2 for row in rows)
    assert rows[0]["buttons"][0]["url"].endswith("qoshtepa_register")

    async def answer_callback(*args, **kwargs):
        return None

    callback = SimpleNamespace(answer=answer_callback, message=message)
    await dispatcher.callbacks["show_place"](callback)
    await dispatcher.callbacks["start_registration"](callback, state)
    message.text = "Ali Valiyev"
    await dispatcher.messages["receive_name"](message, state)
    message.text = "xato"
    await dispatcher.messages["receive_phone"](message, state)
    assert not message.sent_to_owner
    message.text = "+998901234567"
    await dispatcher.messages["receive_phone"](message, state)
    assert message.sent_to_owner[0][0] == 999
    assert "Ali Valiyev" in message.sent_to_owner[0][1]
    assert state.current is None


@pytest.mark.asyncio
async def test_post_is_owner_only_and_deep_link_starts_form():
    dispatcher = FakeDispatcher()
    register_vodiy_meeting_handlers(dispatcher, owner_id=999)
    message = FakeMessage("/qoshtepa_post -1001234567890")
    await dispatcher.messages["publish_meeting"](message)
    assert not hasattr(message, "rich_method")

    message.from_user.id = 999
    await dispatcher.messages["publish_meeting"](message)
    assert message.rich_method.chat_id == -1001234567890

    state = FakeState()
    await dispatcher.messages["register_from_link"](message, state)
    assert state.current is not None
