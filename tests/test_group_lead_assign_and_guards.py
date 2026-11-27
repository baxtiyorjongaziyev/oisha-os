"""Tests for Sotuv Bolim group lead assignment, Hermes mention guards, and 04:47 regression fixes."""
from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from scripts.hermes_env_guard import enforce_hermes_telegram_guards
from src.handlers.group_lead_assign import (
    GroupLeadContextCache,
    execute_group_lead_assignment,
    extract_contact_from_message,
    is_group_lead_assign_request,
    register_group_lead_assign_handlers,
    select_seller_for_lead,
)
from src.handlers.jamoa_hamroh import _text_of
from src.services.core.crm.team_roster import find_staff
from src.services.core.jamoa_ritm.config import load_config

TZ = ZoneInfo("Asia/Tashkent")
SALES_GROUP = -1003854308552
OWNER_ID = 150074828


class FakeAmoCRM:
    subdomain = "jonbranding"
    base_url = "https://jonbranding.amocrm.ru"

    def __init__(self, existing_lead: dict | None = None, pipeline_leads: list | None = None):
        self.existing_lead = existing_lead
        self.pipeline_leads = pipeline_leads or []
        self.tags_added: list[tuple[int, str]] = []
        self.notes_added: list[tuple[int, str]] = []
        self.tasks_created: list[tuple[int, str, int]] = []
        self.ensured: list[dict] = []

    def find_active_lead_by_phone(self, phone: str):
        return self.existing_lead

    async def ensure_lead(self, **kwargs):
        self.ensured.append(kwargs)
        return 777001

    async def get_lead(self, lead_id: int):
        return self.existing_lead or {"id": lead_id, "name": "Test"}

    async def get_leads(self, limit: int = 250, **kwargs):
        return self.pipeline_leads

    async def add_lead_tag(self, lead_id: int, tag: str):
        self.tags_added.append((lead_id, tag))
        return True

    def add_lead_note(self, lead_id: int, text: str):
        self.notes_added.append((lead_id, text))
        return {"ok": True}

    async def create_task(self, element_id: int, text: str, complete_till: int, responsible_user_id=None):
        self.tasks_created.append((element_id, text, complete_till))
        return {"ok": True}


def test_trigger_matching_covers_owner_phrases_and_ignores_other_chatter():
    assert is_group_lead_assign_request(
        "Odiljon aka Tez Natijada vip tarifda oʻqiyapti 2 ta yoʻnalishlari bor spes texnika va apteka ehtiyoj bor.\n\nQaysi sotuv menejeri oladi"
    )
    assert is_group_lead_assign_request(
        "Oisha javob bermayapti sotuv menejerlarini belgilab leadni topshir darsdan keyin aloqaga chiqish kerak"
    )
    assert is_group_lead_assign_request("/lid_topshir +998909197680")
    # Dilbar PM asking the human sales girls for payment lists must NOT trigger lead assignment
    assert not is_group_lead_assign_request(
        "Qizlar bugunga kimlar toʻlov qilaman degan shularni roʻyxatini qilib beringlar @jonbranding_assistant @RayxonMenejer @MumtozmaxalJonbranding"
    )
    # Message explicitly starting with Amina without naming Oisha stays ignored
    assert not is_group_lead_assign_request("Amina, qaysi sotuv menejeri oladi?")


@pytest.mark.asyncio
async def test_tn7_networking_lead_routes_to_shahnoza_and_sets_after_class_task():
    amo = FakeAmoCRM(existing_lead={"id": 54908005, "name": "Odiljon TN7 Gr"})
    now = datetime(2026, 11, 27, 9, 49, tzinfo=TZ)
    reply = await execute_group_lead_assignment(
        amocrm=amo,
        phone="+998909197680",
        contact_name="Odiljon TN7 Gr",
        instruction_text=(
            "Odiljon aka Tez Natijada vip tarifda oʻqiyapti, spes texnika va apteka ehtiyoj bor. "
            "Sotuv menejerlarini belgilab leadni topshir darsdan keyin aloqaga chiqish kerak"
        ),
        now=now,
    )
    assert "Shahnoza" in reply
    assert "@jonbranding_assistant" in reply
    assert "54908005" in reply
    assert "18:30" in reply
    assert (54908005, "Shahnoza") in amo.tags_added
    assert (54908005, "sotuvchi:Shahnoza") in amo.tags_added
    assert len(amo.notes_added) == 1
    assert len(amo.tasks_created) == 1
    expected_due = int(datetime(2026, 11, 27, 18, 30, tzinfo=TZ).timestamp())
    assert amo.tasks_created[0][2] == expected_due


@pytest.mark.asyncio
async def test_commercial_lead_routes_to_least_loaded_closer_or_explicit_seller():
    amo = FakeAmoCRM(
        pipeline_leads=[
            {"id": 1, "status_id": 89067962, "_embedded": {"tags": [{"name": "Mumtozmaxal"}]}},
            {"id": 2, "status_id": 89067962, "_embedded": {"tags": [{"name": "Mumtozmaxal"}]}},
            {"id": 3, "status_id": 89067962, "_embedded": {"tags": [{"name": "Rayxona"}]}},
        ]
    )
    seller, reason = await select_seller_for_lead("Yangi mijoz logotip boʻyicha, kimga biriktiramiz?", amocrm=amo)
    assert seller.slug == "rayxona"
    assert "Rayxona=1" in reason and "Mumtozmaxal=2" in reason

    explicit, exp_reason = await select_seller_for_lead("Mumtozmaxalga lidni topshir", amocrm=amo)
    assert explicit.slug == "mumtozmaxal"
    assert exp_reason == "rahbar koʻrsatmasi"


@pytest.mark.asyncio
async def test_aiogram_middleware_caches_shared_contact_for_followup_assignment():
    from aiogram import Dispatcher

    dp = Dispatcher()
    amo = FakeAmoCRM(existing_lead={"id": 54908005, "name": "Odiljon TN7 Gr"})
    cache = GroupLeadContextCache()
    register_group_lead_assign_handlers(
        dp,
        is_admin=lambda uid: uid == OWNER_ID,
        get_amocrm_client=lambda: amo,
        cache=cache,
        group_ids_getter=lambda: {SALES_GROUP},
    )

    contact_msg = SimpleNamespace(
        chat=SimpleNamespace(id=SALES_GROUP),
        from_user=SimpleNamespace(id=OWNER_ID, is_bot=False),
        contact=SimpleNamespace(phone_number="998909197680", first_name="Odiljon TN7 Gr", last_name=""),
        text=None,
        caption=None,
    )
    extracted = extract_contact_from_message(contact_msg)
    assert extracted == ("+998909197680", "Odiljon TN7 Gr")
    assert _text_of(contact_msg) == "[Kontakt: Odiljon TN7 Gr 998909197680]"

    # Simulate outer_middleware observing the contact card first
    async def _noop(ev, d):
        return None

    mw = dp.message.outer_middleware[0]
    await mw(_noop, contact_msg, {})
    assert cache.latest(SALES_GROUP) is not None

    replies: list[str] = []

    async def fake_reply(text: str, **kwargs):
        replies.append(text)

    # Owner replies to Amina's message (no contact in reply_to_message), asking who takes the lead
    followup_msg = SimpleNamespace(
        chat=SimpleNamespace(id=SALES_GROUP),
        from_user=SimpleNamespace(id=OWNER_ID, is_bot=False),
        contact=None,
        text="Odiljon aka Tez Natijada vip tarifda oʻqiyapti. Qaysi sotuv menejeri oladi",
        caption=None,
        reply_to_message=SimpleNamespace(
            from_user=SimpleNamespace(id=9256147208, is_bot=True),
            text="Assalomu alaykum, Odiljon! Jamoamizga xush kelibsiz.",
            contact=None,
            caption=None,
        ),
        reply=fake_reply,
    )
    handler_obj = dp.message.handlers[0]
    assert await handler_obj.check(followup_msg)
    await handler_obj.call(followup_msg)
    assert len(replies) == 1
    assert "Shahnoza" in replies[0] and "54908005" in replies[0]


def test_jamoa_config_falls_back_to_team_group_for_hamroh_only(monkeypatch):
    for key in ("JAMOA_GROUP_ID", "JAMOA_RITM_ENABLED", "JAMOA_HAMROH_ENABLED", "DISABLE_UNSOLICITED_REPORTS"):
        monkeypatch.delenv(key, raising=False)
    cfg = load_config(SimpleNamespace(OWNER_ID=OWNER_ID, TEAM_GROUP_ID=SALES_GROUP))
    assert cfg.group_id == SALES_GROUP
    assert cfg.hamroh_active is True
    assert cfg.ritm_active is False


def test_hermes_env_guard_clears_free_response_topics_and_preserves_secrets(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "TELEGRAM_BOT_TOKEN=secret_bot_token_123\n"
        "GEMINI_API_KEY=secret_gemini_key\n"
        "TELEGRAM_HOME_CHANNEL=-1003854308552\n"
        "TELEGRAM_FREE_RESPONSE_TOPICS=-1003854308552:1\n"
        "TELEGRAM_REQUIRE_MENTION=false\n",
        encoding="utf-8",
    )
    assert enforce_hermes_telegram_guards(env_file, owner_user=None) is True
    content = env_file.read_text(encoding="utf-8")
    assert "TELEGRAM_BOT_TOKEN=secret_bot_token_123" in content
    assert "GEMINI_API_KEY=secret_gemini_key" in content
    assert "TELEGRAM_FREE_RESPONSE_TOPICS=\n" in content
    assert "TELEGRAM_REQUIRE_MENTION=true\n" in content
    assert "TELEGRAM_BOTS_REQUIRE_MENTION=true\n" in content
    assert "TELEGRAM_OBSERVE_UNMENTIONED_GROUP_MESSAGES=true\n" in content


def test_roster_resolves_live_rayxonmenejer_and_dilbar_handles():
    assert find_staff("@RayxonMenejer").slug == "rayxona"
    assert find_staff("@jonbranding_finansist").slug == "dilbar"


@pytest.mark.asyncio
async def test_elite_intake_handles_missing_auto_lead_agent_gracefully(monkeypatch):
    from src.handlers.msg_pipeline import lead_intake
    from src.services.core.crm import non_client_filter

    monkeypatch.setattr(
        non_client_filter,
        "is_sender_marked_as_non_client",
        lambda *a, **kw: _async_val((False, "")),
    )

    class DummyDB:
        async def is_crm_synced(self, uid):
            return True

    event = SimpleNamespace(sender_id=123, message=SimpleNamespace(text="+998909197680"))
    sender = SimpleNamespace(id=123, phone="998909197680", username="odiljon_17")
    msg_controller = SimpleNamespace(db=DummyDB(), crm=SimpleNamespace(amocrm=None))

    await lead_intake.process_elite_intake(
        event,
        sender=sender,
        message_text="+998909197680",
        sender_name="Odiljon",
        msg_controller=msg_controller,
        auto_lead_agent=None,
        folder_manager=None,
        admin_bot=None,
        bot_client=None,
        welcome_manager=None,
        TN5_GROUP_ID=None,
    )


async def _async_val(v):
    return v
