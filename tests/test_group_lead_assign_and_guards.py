"""Tests for Sotuv Bolim group lead assignment, Hermes mention guards, and 04:47 regression fixes."""
from __future__ import annotations

import re
from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from scripts.hermes_env_guard import (
    HERMES_TELEGRAM_GUARD_VARS,
    enforce_hermes_telegram_guards,
    ensure_amina_soul_guards,
)
from src.handlers.group_lead_assign import (
    GroupLeadContextCache,
    execute_group_lead_assignment,
    extract_contact_from_message,
    is_group_lead_assign_request,
    register_group_lead_assign_handlers,
    select_seller_for_lead,
)
from src.handlers.jamoa_hamroh import _text_of
from src.services.core.crm.amocrm_pipeline_config import FARMER_PIPELINE_ID, SALES_PIPELINE_ID
from src.services.core.crm.team_roster import find_staff
from src.services.core.daily_priority.ownership import resolve_seller_key
from src.services.core.jamoa_ritm.config import load_config

TZ = ZoneInfo("Asia/Tashkent")
SALES_GROUP = -1003854308552
OWNER_ID = 150074828


class FakeAmoCRM:
    subdomain = "jonbranding"
    base_url = "https://jonbranding.amocrm.ru"

    def __init__(
        self,
        existing_lead: dict | None = None,
        contact_leads: list[dict] | None = None,
        pipeline_leads: list | None = None,
    ):
        self.existing_lead = existing_lead
        self.contact_leads = contact_leads if contact_leads is not None else ([existing_lead] if existing_lead else [])
        self.pipeline_leads = pipeline_leads or []
        self.tags_added: list[tuple[int, str]] = []
        self.notes_added: list[tuple[int, str]] = []
        self.tasks_created: list[tuple[int, str, int]] = []
        self.created_leads: list[dict] = []
        self.patched_payloads: list[tuple[int, dict]] = []

    def get_contact_by_phone(self, phone: str):
        return {"id": 60635583} if self.contact_leads else None

    def get_active_leads_for_contact(self, contact_id: int):
        return list(self.contact_leads)

    async def create_lead(self, **kwargs):
        self.created_leads.append(kwargs)
        return 777001

    async def get_lead(self, lead_id: int):
        for ld in self.contact_leads:
            if ld and int(ld.get("id") or 0) == int(lead_id):
                return ld
        return self.existing_lead or {"id": lead_id, "name": "Test"}

    async def get_leads(self, limit: int = 250, page: int = 1, **kwargs):
        return self.pipeline_leads if page == 1 else []

    async def add_lead_tag(self, lead_id: int, tag: str):
        self.tags_added.append((lead_id, tag))
        return True

    def add_lead_note(self, lead_id: int, text: str):
        self.notes_added.append((lead_id, text))
        return {"ok": True}

    async def create_task(self, element_id: int, text: str, complete_till: int, responsible_user_id=None):
        self.tasks_created.append((element_id, text, complete_till))
        return {"ok": True}


def test_trigger_and_slash_contact_extraction():
    assert is_group_lead_assign_request(
        "Odiljon aka Tez Natijada vip tarifda oʻqiyapti 2 ta yoʻnalishlari bor spes texnika va apteka ehtiyoj bor.\n\nQaysi sotuv menejeri oladi"
    )
    assert is_group_lead_assign_request(
        "Oisha javob bermayapti sotuv menejerlarini belgilab leadni topshir darsdan keyin aloqaga chiqish kerak"
    )
    assert is_group_lead_assign_request("/lid_topshir +998909197680")
    assert not is_group_lead_assign_request(
        "Qizlar bugunga kimlar toʻlov qilaman degan shularni roʻyxatini qilib beringlar @jonbranding_assistant @RayxonMenejer @MumtozmaxalJonbranding"
    )
    assert not is_group_lead_assign_request("Amina, qaysi sotuv menejeri oladi?")
    assert not is_group_lead_assign_request("Aminа, qaysi sotuv menejeri oladi?")

    # Slash command must NEVER become customer display name
    slash_msg = SimpleNamespace(contact=None, text="/lid_topshir +998909197680", caption=None)
    assert extract_contact_from_message(slash_msg) == ("+998909197680", "+998909197680")


@pytest.mark.asyncio
async def test_tn7_networking_lead_routes_to_shahnoza_and_sets_after_class_task():
    amo = FakeAmoCRM(existing_lead={"id": 54908005, "name": "Odiljon TN7 Gr", "pipeline_id": SALES_PIPELINE_ID})
    now = datetime(2026, 11, 27, 9, 49, tzinfo=TZ)
    reply = await execute_group_lead_assignment(
        amocrm=amo,
        phone="+998909197680",
        contact_name="Odiljon TN7 Gr",
        instruction_text="Sotuv menejerlarini belgilab leadni topshir darsdan keyin aloqaga chiqish kerak",
        contact_context="Tez Natijada vip tarifda oʻqiyapti, spes texnika va apteka ehtiyoj bor",
        now=now,
    )
    assert "Shahnoza" in reply and "@jonbranding_assistant" in reply
    assert "54908005" in reply and "18:30" in reply
    assert len(amo.notes_added) == 1
    assert len(amo.tasks_created) == 1
    expected_due = int(datetime(2026, 11, 27, 18, 30, tzinfo=TZ).timestamp())
    assert amo.tasks_created[0][2] == expected_due


@pytest.mark.asyncio
async def test_client_named_shahnoza_does_not_override_explicit_seller_rayxona():
    amo = FakeAmoCRM()
    seller, reason = await select_seller_for_lead(
        "Rayxonaga lidni topshir",
        contact_context="Shahnoza opa Gul doʻkoni TN7",
        amocrm=amo,
    )
    assert seller.slug == "rayxona"
    assert reason == "rahbar koʻrsatmasi"


@pytest.mark.asyncio
async def test_reassignment_replaces_old_seller_tags_and_ignores_farmer_deals(monkeypatch):
    import requests
    from src.handlers.group_lead_crm import _build_ownership_patch

    old_lead = {
        "id": 54908005,
        "name": "Сделка #54908005",
        "pipeline_id": SALES_PIPELINE_ID,
        "_embedded": {"tags": [{"name": "Rayxona"}, {"name": "sotuvchi:Rayxona"}, {"name": "TN7"}]},
        "custom_fields_values": [{"field_id": 991, "field_name": "Sotuvchi", "values": [{"value": "Rayxona"}]}],
    }
    patch = _build_ownership_patch(old_lead, "Mumtozmaxal", "Odiljon (+998909197680)")
    assert patch["name"] == "Odiljon (+998909197680)"
    updated_lead = {
        "id": 54908005,
        "_embedded": patch["_embedded"],
        "custom_fields_values": patch["custom_fields_values"],
    }
    sellers = [
        {"key": "shahnoza", "name": "Shahnoza"},
        {"key": "rayxona", "name": "Rayxona"},
        {"key": "mumtozmaxal", "name": "Mumtozmaxal"},
    ]
    assert resolve_seller_key(updated_lead, sellers) == "mumtozmaxal"
    assert {"name": "TN7"} in patch["_embedded"]["tags"]

    # Farmer deal must NOT be mutated; a fresh Sales deal must be created instead
    farmer_only = FakeAmoCRM(
        contact_leads=[{"id": 111, "name": "Loyiha", "pipeline_id": FARMER_PIPELINE_ID, "status_id": 80215334}]
    )
    monkeypatch.setattr(requests, "patch", lambda *a, **kw: SimpleNamespace(status_code=200))
    reply = await execute_group_lead_assignment(
        amocrm=farmer_only,
        phone="+998901112233",
        contact_name="Yangi Mijoz",
        instruction_text="Rayxonaga lidni topshir",
    )
    assert len(farmer_only.created_leads) == 1
    assert farmer_only.created_leads[0]["pipeline_id"] == SALES_PIPELINE_ID
    assert "777001" in reply
    assert len(farmer_only.notes_added) == 1  # no duplicate notes


@pytest.mark.asyncio
async def test_aiogram_middleware_caches_shared_contact_for_followup_assignment():
    from aiogram import Dispatcher

    dp = Dispatcher()
    amo = FakeAmoCRM(existing_lead={"id": 54908005, "name": "Odiljon TN7 Gr", "pipeline_id": SALES_PIPELINE_ID})
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
    assert _text_of(contact_msg) == "[Kontakt: Odiljon TN7 Gr 998909197680]"

    async def _noop(ev, d):
        return None

    await dp.message.outer_middleware[0](_noop, contact_msg, {})
    replies: list[str] = []

    async def fake_reply(text: str, **kwargs):
        replies.append(text)

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
    assert len(replies) == 1 and "Shahnoza" in replies[0]


def test_jamoa_config_fallback_never_enables_scheduled_ritm(monkeypatch):
    for key in ("JAMOA_GROUP_ID", "JAMOA_HAMROH_ENABLED", "DISABLE_UNSOLICITED_REPORTS"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("JAMOA_RITM_ENABLED", "true")
    cfg = load_config(SimpleNamespace(OWNER_ID=OWNER_ID, TEAM_GROUP_ID=SALES_GROUP))
    assert cfg.group_id == SALES_GROUP
    assert cfg.hamroh_active is True
    assert cfg.ritm_active is False


def test_hermes_env_and_soul_guards_including_mixed_script_amina(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "TELEGRAM_BOT_TOKEN=secret_bot_token_123\n"
        "TELEGRAM_FREE_RESPONSE_TOPICS=-1003854308552:1\n",
        encoding="utf-8",
    )
    assert enforce_hermes_telegram_guards(env_file, owner_user=None) is True
    content = env_file.read_text(encoding="utf-8")
    assert "TELEGRAM_BOT_TOKEN=secret_bot_token_123" in content
    assert "TELEGRAM_FREE_RESPONSE_TOPICS=\n" in content

    import json

    pat = re.compile(json.loads(HERMES_TELEGRAM_GUARD_VARS["TELEGRAM_MENTION_PATTERNS"])[0])
    assert pat.search("Amina, buni qanday qilaman?")
    assert pat.search("Aminа, yordam bering")  # mixed Latin + Cyrillic 'а'
    assert pat.search("Амина, салом")

    soul_file = tmp_path / "SOUL.md"
    soul_file.write_text("# Amina\n\n## Qachon javob berasan\n- Test\n", encoding="utf-8")
    assert ensure_amina_soul_guards(soul_file) is True
    assert "(Jim turadi)" in soul_file.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_auditor_and_enricher_wiring_persists_classification(tmp_path):
    import aiosqlite
    from src.services.core.crm.crm_contacts_auditor import CRMContactsAuditor

    db_file = tmp_path / "audit.db"

    class LocalDB:
        async def get_connection(self):
            return await aiosqlite.connect(db_file)

    auditor = CRMContactsAuditor(amocrm=FakeAmoCRM(), db=LocalDB(), tg_client=None)
    await auditor.init_db()
    assert await auditor.is_lead_audited(54908005) is False
    await auditor.save_audit_result(
        lead_id=54908005,
        lead_name="Odiljon",
        contact_id=60635583,
        contact_name="Odiljon TN7 Gr",
        phone="+998909197680",
        username="odiljon_17",
        telegram_user_id=340778223,
        call_summary="",
        telegram_history="",
        category="Mijoz",
        explanation="TN7 VIP",
    )
    assert await auditor.is_lead_audited(54908005) is True


def test_roster_resolves_live_rayxonmenejer_and_dilbar_handles():
    assert find_staff("@RayxonMenejer").slug == "rayxona"
    assert find_staff("@jonbranding_finansist").slug == "dilbar"
