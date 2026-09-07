from types import SimpleNamespace

import pytest

from src.bootstrap.orchestration.bot_head import init_aiogram_bot_head


class _FakeCompat:
    instances = []

    def __init__(self, *, bot, dispatcher):
        self.bot = bot
        self.dispatcher = dispatcher
        self.attached = False
        _FakeCompat.instances.append(self)

    def attach(self):
        self.attached = True


class _FakeHead:
    instances = []

    def __init__(
        self, *, bot, dispatcher, allowed_updates=None, raw_update_handler=None
    ):
        self.bot = bot
        self.dispatcher = dispatcher
        self.allowed_updates = allowed_updates
        self.raw_update_handler = raw_update_handler
        self.started = False
        _FakeHead.instances.append(self)

    def start(self):
        self.started = True
        return SimpleNamespace(done=lambda: False)


class _AdminBot:
    def __init__(self):
        self.bot_client = object()
        self.start_calls = 0

    async def start(self):
        self.start_calls += 1

    async def _perform_global_lookup(self, phone):
        return None


class _ApiModule:
    def __init__(self):
        self.ingress = None
        self.cached_crm_audit = {}

    async def process_telegram_ai_update(self, update):
        return None

    def set_telegram_ai_ingress_status(self, *, mode, active):
        self.ingress = (mode, active)


class _AppCtx:
    def __init__(self):
        self.aiogram_bot_head = None
        self.admin_aiogram_dispatcher = None


def _access():
    return SimpleNamespace(
        owner_id=1,
        get_role=lambda uid: None,
        get_role_name=lambda r: "GUEST",
        is_admin=lambda uid: True,
    )


async def _today_stats():
    return {}


def _db():
    return SimpleNamespace(get_today_stats=_today_stats)


def _msg_controller():
    return SimpleNamespace(
        crm=SimpleNamespace(amocrm=object(), airtable=object()), db=_db()
    )


@pytest.fixture
def patched(monkeypatch):
    _FakeCompat.instances.clear()
    _FakeHead.instances.clear()
    monkeypatch.setattr(
        "src.bootstrap.orchestration.bot_head.AiogramTelethonCompatClient", _FakeCompat
    )
    monkeypatch.setattr(
        "src.bootstrap.orchestration.bot_head.AiogramBotHead", _FakeHead
    )
    built = {}

    def fake_maybe_build(**kwargs):
        built.update(kwargs)
        return SimpleNamespace(name="dispatcher")

    monkeypatch.setattr(
        "src.bootstrap.orchestration.bot_head.maybe_build_admin_aiogram_dispatcher",
        fake_maybe_build,
    )
    hisobchi_calls = []
    salescoach_calls = []
    monkeypatch.setattr(
        "src.bootstrap.orchestration.bot_head.register_hisobchi_aiogram_callbacks",
        lambda dp, *, engine: hisobchi_calls.append(engine),
    )
    monkeypatch.setattr(
        "src.bootstrap.orchestration.bot_head.register_salescoach_aiogram_callbacks",
        lambda dp, *, context: salescoach_calls.append(context),
    )
    return SimpleNamespace(
        built=built,
        hisobchi_calls=hisobchi_calls,
        salescoach_calls=salescoach_calls,
    )


@pytest.mark.asyncio
async def test_aiogram_path_builds_starts_and_registers_once(patched):
    admin_bot = _AdminBot()
    api_module = _ApiModule()
    app_ctx = _AppCtx()
    bot_runtime = SimpleNamespace(backend="aiogram", bot=SimpleNamespace(tag="bot"))
    msg_controller = _msg_controller()

    head = await init_aiogram_bot_head(
        bot_runtime=bot_runtime,
        bot_ingress_mode="polling",
        admin_bot=admin_bot,
        access_manager=_access(),
        msg_controller=msg_controller,
        db=msg_controller.db,
        hisobchi_engine=SimpleNamespace(tag="engine"),
        api_module=api_module,
        app_ctx=app_ctx,
    )

    assert head is not None
    assert head.started is True
    assert admin_bot.start_calls == 1
    assert _FakeCompat.instances[0].attached is True
    assert admin_bot.bot_client is _FakeCompat.instances[0]
    assert app_ctx.aiogram_bot_head is head
    assert app_ctx.admin_aiogram_dispatcher is not None
    assert api_module.ingress == ("aiogram", True)
    assert len(patched.hisobchi_calls) == 1
    assert len(patched.salescoach_calls) == 1
    assert callable(patched.built.get("perform_global_lookup"))
    assert patched.built.get("enabled") is True


@pytest.mark.asyncio
async def test_telethon_backend_is_noop(patched):
    admin_bot = _AdminBot()
    app_ctx = _AppCtx()
    head = await init_aiogram_bot_head(
        bot_runtime=SimpleNamespace(backend="telethon", bot=None),
        bot_ingress_mode="polling",
        admin_bot=admin_bot,
        access_manager=_access(),
        msg_controller=_msg_controller(),
        db=_db(),
        hisobchi_engine=None,
        api_module=_ApiModule(),
        app_ctx=app_ctx,
    )
    assert head is None
    assert admin_bot.start_calls == 0
    assert app_ctx.aiogram_bot_head is None


@pytest.mark.asyncio
async def test_non_polling_ingress_is_noop(patched):
    admin_bot = _AdminBot()
    head = await init_aiogram_bot_head(
        bot_runtime=SimpleNamespace(backend="aiogram", bot=SimpleNamespace()),
        bot_ingress_mode="webhook",
        admin_bot=admin_bot,
        access_manager=_access(),
        msg_controller=_msg_controller(),
        db=_db(),
        hisobchi_engine=None,
        api_module=_ApiModule(),
        app_ctx=_AppCtx(),
    )
    assert head is None
    assert admin_bot.start_calls == 0


@pytest.mark.asyncio
async def test_aiogram_path_skips_hisobchi_when_engine_none(patched):
    admin_bot = _AdminBot()
    head = await init_aiogram_bot_head(
        bot_runtime=SimpleNamespace(backend="aiogram", bot=SimpleNamespace()),
        bot_ingress_mode="polling",
        admin_bot=admin_bot,
        access_manager=_access(),
        msg_controller=_msg_controller(),
        db=_db(),
        hisobchi_engine=None,
        api_module=_ApiModule(),
        app_ctx=_AppCtx(),
    )
    assert head is not None
    assert admin_bot.start_calls == 1
    assert len(patched.hisobchi_calls) == 0
    assert len(patched.salescoach_calls) == 1
