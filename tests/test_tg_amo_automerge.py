"""Tests for Telegram <-> Phone amoCRM chat linking and deal auto-merge."""
from __future__ import annotations

import json
import sqlite3
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.services.core.crm.amocrm.chats import AmoCRMChatsMixin
from src.services.core.crm.amocrm_pipeline_config import (
    FARMER_PIPELINE_ID,
    SALES_CONTACT_STATUS_ID,
    SALES_NEW_STATUS_ID,
    SALES_PIPELINE_ID,
    STATUS_LOST,
    STATUS_WON,
)
from src.services.core.crm.tg_amo_bridge import accounts, inbound
from src.services.core.crm.tg_amo_bridge.amojo_client import AmoJoClient
from src.services.core.crm.tg_amo_bridge.analyzer import (
    LeadProfile,
    analyze_lead_pair,
    extract_phone_from_text,
    normalize_uz_phone,
    pick_best_pair,
)
from src.services.core.crm.tg_amo_bridge.automerge import (
    MERGED_SOURCE_TAG,
    MERGED_TARGET_TAG,
    REVIEW_CONFLICT_TAG,
    TelegramDealAutoMerger,
)
from src.services.core.crm.tg_amo_bridge.reconciler import scan_and_merge_existing
from src.services.core.crm.tg_amo_bridge.store import MessageStore


class FakePool:
    def __init__(self):
        self.c = sqlite3.connect(":memory:")

    async def execute(self, q, params=None):
        cur = self.c.execute(q, params or [])
        rows = cur.fetchall()
        self.c.commit()
        return rows


def _phone_contact(cid: int, name: str, phone: str, lead_ids: list[int], created_at: int = 1000):
    return {
        "id": cid,
        "name": name,
        "created_at": created_at,
        "custom_fields_values": [
            {"field_code": "PHONE", "values": [{"value": phone}]}
        ] if phone else [],
        "_embedded": {"leads": [{"id": lid} for lid in lead_ids]},
    }


def _lead(
    lid: int,
    name: str,
    *,
    status_id: int = SALES_CONTACT_STATUS_ID,
    pipeline_id: int = SALES_PIPELINE_ID,
    price: int = 0,
    created_at: int = 1000,
    contact_id: int = 10,
    tags: list[str] | None = None,
):
    return {
        "id": lid,
        "name": name,
        "status_id": status_id,
        "pipeline_id": pipeline_id,
        "price": price,
        "created_at": created_at,
        "updated_at": created_at + 10,
        "_embedded": {
            "contacts": [{"id": contact_id}],
            "tags": [{"name": t} for t in (tags or [])],
        },
    }


class FakeCRM:
    """In-memory amoCRM facade matching AmoCRMSync + AmoCRMChatsMixin."""

    def __init__(self):
        self.contacts: dict[int, dict] = {}
        self.leads: dict[int, dict] = {}
        self.call_counts: dict[int, int] = {}
        self.chat_links: list[dict] = []  # [{"contact_id": int, "chat_id": str}]
        self.lead_notes: dict[int, list[dict]] = {}
        self.lead_tasks: dict[int, list[dict]] = {}
        self.linked_contacts: list[tuple[int, int]] = []
        self.added_notes: list[tuple[int, str]] = []
        self.added_tags: list[tuple[int, str]] = []
        self.reassigned_tasks: list[tuple[int, int]] = []
        self.closed_leads: list[tuple[int, int | None]] = []
        self.fail_chat_link = False
        self.fail_contact_link = False
        self.fail_task_reassign = False

    async def find_contacts_by_phone_async(self, phone: str):
        tail = normalize_uz_phone(phone)[-9:]
        out = []
        for c in self.contacts.values():
            for f in c.get("custom_fields_values") or []:
                if f.get("field_code") == "PHONE":
                    for v in f.get("values") or []:
                        if normalize_uz_phone(v.get("value"))[-9:] == tail:
                            out.append(c)
        return out

    async def find_contacts_by_query_async(self, query: str):
        q = query.lower()
        return [c for c in self.contacts.values() if q in json.dumps(c).lower()]

    async def get_contact_details_async(self, contact_id: int):
        return self.contacts.get(int(contact_id))

    async def get_contact_linked_leads(self, contact_id: int):
        c = self.contacts.get(int(contact_id)) or {}
        return (c.get("_embedded") or {}).get("leads") or []

    async def get_contact_call_notes_count(self, contact_id: int) -> int:
        return self.call_counts.get(int(contact_id), 0)

    async def get_contact_chats(self, *, contact_id=None, chat_id=None):
        if contact_id is not None:
            return [r for r in self.chat_links if r["contact_id"] == int(contact_id)]
        return [r for r in self.chat_links if r["chat_id"] == str(chat_id)]

    async def link_chat_to_contact(self, contact_id: int, chat_id: str) -> bool:
        if self.fail_chat_link:
            return False
        self.chat_links = [r for r in self.chat_links if r["chat_id"] != chat_id]
        self.chat_links.append({"contact_id": int(contact_id), "chat_id": str(chat_id)})
        return True

    async def link_contact_to_lead_async(self, lead_id: int, contact_id: int) -> bool:
        if self.fail_contact_link:
            return False
        self.linked_contacts.append((int(lead_id), int(contact_id)))
        return True

    async def get_lead(self, lead_id: int):
        return self.leads.get(int(lead_id))

    async def get_leads(self, limit: int = 100, with_contacts: bool = True):
        return list(self.leads.values())[:limit]

    async def get_lead_notes(self, lead_id: int):
        return list(self.lead_notes.get(int(lead_id), []))

    async def get_lead_open_tasks(self, lead_id: int):
        return list(self.lead_tasks.get(int(lead_id), []))

    async def reassign_task_to_lead(self, task_id: int, target_lead_id: int) -> bool:
        if self.fail_task_reassign:
            return False
        self.reassigned_tasks.append((int(task_id), int(target_lead_id)))
        return True

    async def add_lead_note_async(self, lead_id: int, text: str) -> bool:
        self.added_notes.append((int(lead_id), text))
        self.lead_notes.setdefault(int(lead_id), []).append({"params": {"text": text}})
        return True

    async def add_lead_tag(self, lead_id: int, tag_name: str) -> bool:
        self.added_tags.append((int(lead_id), tag_name))
        return True

    async def close_duplicate_lead(self, lead_id: int, *, loss_reason_id=None) -> bool:
        self.closed_leads.append((int(lead_id), loss_reason_id))
        if int(lead_id) in self.leads:
            self.leads[int(lead_id)]["status_id"] = STATUS_LOST
        return True


def _amojo_mock(chat_uuid: str = "amo-chat-uuid-1"):
    m = AsyncMock()
    m.scope_id = "scope-1"
    m.build_message_event = AmoJoClient("a", "c", "x", "scope-1").build_message_event
    m.create_chat.return_value = chat_uuid
    m.send_event.return_value = {"new_message": {"msgid": "1"}}
    m.send_status.return_value = True
    return m


# ---- 1. Phone normalization & extraction --------------------------------


def test_phone_normalization_and_text_extraction():
    assert normalize_uz_phone("+998 (90) 123-45-67") == "998901234567"
    assert normalize_uz_phone("90 123 45 67") == "998901234567"
    assert normalize_uz_phone("12345") == ""
    assert extract_phone_from_text("Salom, mening raqamim +998 99 555-44-33 ga telefon qiling") == "998995554433"
    assert extract_phone_from_text("Raqamim 93 777 88 99") == "998937778899"
    assert extract_phone_from_text("Narxi 15000000 soʻm") == ""


# ---- 2. Analyzer safety & conflict rules --------------------------------


def test_analyzer_merges_telegram_only_into_prior_phone_deal():
    phone_deal = LeadProfile(
        lead_id=101, contact_id=10, name="Sardor +998901234567",
        status_id=SALES_CONTACT_STATUS_ID, pipeline_id=SALES_PIPELINE_ID,
        price=15_000_000, created_at=1000, call_count=2, has_chat=False,
        phones=("998901234567",),
    )
    tg_deal = LeadProfile(
        lead_id=202, contact_id=20, name="Telegram chat Sardor",
        status_id=SALES_NEW_STATUS_ID, pipeline_id=SALES_PIPELINE_ID,
        price=0, created_at=2000, call_count=0, has_chat=True,
        phones=(),
    )
    decision = pick_best_pair([tg_deal, phone_deal])
    assert decision is not None
    assert decision.action == "merge"
    assert decision.target_lead_id == 101
    assert decision.source_lead_id == 202
    assert decision.confidence == "high"


def test_analyzer_blocks_unsafe_merges():
    base = LeadProfile(
        lead_id=1, contact_id=10, name="Phone", status_id=SALES_CONTACT_STATUS_ID,
        pipeline_id=SALES_PIPELINE_ID, price=10_000_000, created_at=100, call_count=1, phones=("998901234567",),
    )
    both_priced = LeadProfile(
        lead_id=2, contact_id=20, name="Telegram", status_id=SALES_NEW_STATUS_ID,
        pipeline_id=SALES_PIPELINE_ID, price=5_000_000, created_at=200, call_count=0, has_chat=True,
    )
    assert analyze_lead_pair(base, both_priced).action == "conflict"

    both_calls = LeadProfile(
        lead_id=3, contact_id=21, name="Telegram", status_id=SALES_NEW_STATUS_ID,
        pipeline_id=SALES_PIPELINE_ID, price=0, created_at=200, call_count=1, has_chat=True,
    )
    assert analyze_lead_pair(base, both_calls).action == "conflict"

    in_farmer = LeadProfile(
        lead_id=4, contact_id=22, name="Telegram", status_id=80215334,
        pipeline_id=FARMER_PIPELINE_ID, price=0, created_at=200, call_count=0, has_chat=True,
    )
    assert analyze_lead_pair(base, in_farmer).action == "conflict"

    closed_target = LeadProfile(
        lead_id=5, contact_id=10, name="Old Won", status_id=STATUS_WON,
        pipeline_id=SALES_PIPELINE_ID, price=20_000_000, created_at=100, call_count=3, phones=("998901234567",),
    )
    active_tg = LeadProfile(
        lead_id=6, contact_id=23, name="New Telegram", status_id=SALES_NEW_STATUS_ID,
        pipeline_id=SALES_PIPELINE_ID, price=0, created_at=300, call_count=0, has_chat=True,
    )
    assert analyze_lead_pair(closed_target, active_tg).action == "link_only"


# ---- 3. Proactive chat linking before send_event ------------------------


@pytest.mark.asyncio
async def test_proactive_link_attaches_chat_to_existing_phone_contact_before_send():
    crm = FakeCRM()
    crm.contacts[10] = _phone_contact(10, "Ali", "+998901112233", [101])
    crm.leads[101] = _lead(101, "Ali brending", contact_id=10, price=12_000_000)
    crm.call_counts[10] = 2

    store = MessageStore(FakePool())
    amojo = _amojo_mock("chat-uuid-777")
    merger = TelegramDealAutoMerger(crm=crm, amojo=amojo, store=store)

    sender = SimpleNamespace(first_name="Ali", last_name=None, username="ali_uz", phone="998901112233", bot=False)
    ev = SimpleNamespace(
        is_private=True, out=False, chat_id=555001,
        message=SimpleNamespace(id=11, raw_text="Assalomu alaykum", voice=None, photo=None, document=None, media=None),
        get_sender=AsyncMock(return_value=sender),
    )
    acc = accounts.Account("owner", "Owner", "oisha-tg-owner", lambda: None)

    assert await inbound.handle_message(ev, acc, amojo, store, merger=merger)
    amojo.create_chat.assert_awaited_once()
    assert crm.chat_links == [{"contact_id": 10, "chat_id": "chat-uuid-777"}]
    assert crm.added_notes and crm.added_notes[0][0] == 101
    assert "AUTO-LINK" in crm.added_notes[0][1]
    assert not crm.closed_leads  # no duplicate deal existed
    # Cached on 2nd message: no duplicate link call
    amojo.create_chat.reset_mock()
    ev.message.id = 12
    assert await inbound.handle_message(ev, acc, amojo, store, merger=merger)
    amojo.create_chat.assert_not_awaited()


# ---- 4. Reactive auto-merge when phone arrives later in chat text -------


@pytest.mark.asyncio
async def test_reactive_automerge_when_client_shares_phone_in_telegram_chat():
    crm = FakeCRM()
    # Existing phone deal (with prior call)
    crm.contacts[10] = _phone_contact(10, "Javohir", "+998931234567", [101], created_at=1000)
    crm.leads[101] = _lead(101, "Javohir telefon", contact_id=10, created_at=1000, price=8_000_000)
    crm.call_counts[10] = 1
    # Separate Telegram-only contact & deal already created when phone was hidden
    crm.contacts[20] = _phone_contact(20, "Javohir TG", "", [202], created_at=2000)
    crm.leads[202] = _lead(202, "Telegram chat Javohir", status_id=SALES_NEW_STATUS_ID, contact_id=20, created_at=2000)
    crm.chat_links.append({"contact_id": 20, "chat_id": "chat-uuid-split"})
    crm.lead_notes[202] = [{"params": {"text": "Logo narxini soʻradi"}}]
    crm.lead_tasks[202] = [{"id": 9001, "text": "KP yuborish", "complete_till": 1799999999, "responsible_user_id": 7}]

    store = MessageStore(FakePool())
    amojo = _amojo_mock("chat-uuid-split")
    merger = TelegramDealAutoMerger(crm=crm, amojo=amojo, store=store)

    # Client writes their phone number inside the Telegram message
    outcome = await merger.ensure_chat_linked_before_send(
        peer_id=777001,
        client_name="Javohir",
        sender_phone=None,
        message_text="Mening nomerim 93 123 45 67",
        username="javohir_tg",
    )
    assert outcome.status == "merged"
    assert outcome.target_lead_id == 101
    assert outcome.merged_source_lead_id == 202
    assert {"contact_id": 10, "chat_id": "chat-uuid-split"} in crm.chat_links
    assert (101, 20) in crm.linked_contacts
    assert (202, None) in crm.closed_leads
    assert (101, MERGED_TARGET_TAG) in crm.added_tags
    assert (202, MERGED_SOURCE_TAG) in crm.added_tags
    assert crm.reassigned_tasks == [(9001, 101)]
    assert any("Logo narxini" in text for lid, text in crm.added_notes if lid == 101)

    # Idempotency: re-running does not double-close or duplicate notes
    notes_before = len(crm.added_notes)
    status_again = await merger.execute_decision(
        analyze_lead_pair(
            LeadProfile(101, 10, "Javohir", SALES_CONTACT_STATUS_ID, SALES_PIPELINE_ID, 8_000_000, 1000, 1010, 1, False, False, 0, (), ("998931234567",)),
            LeadProfile(202, 20, "Telegram", SALES_NEW_STATUS_ID, SALES_PIPELINE_ID, 0, 2000, 2010, 0, True, True, 1, (), ()),
        ),
        phone="998931234567",
    )
    assert status_again == "merged"
    assert len(crm.added_notes) == notes_before


# ---- 5. Manager outgoing uses get_chat (not manager's own phone) --------


@pytest.mark.asyncio
async def test_outgoing_manager_message_resolves_client_from_get_chat(monkeypatch):
    monkeypatch.setattr(inbound, "_ECHO_GRACE_SECONDS", 0)
    store, amojo = MessageStore(FakePool()), _amojo_mock()
    manager_entity = SimpleNamespace(first_name="Baxtiyorjon", last_name=None, username="owner", phone="998909999999", bot=False)
    client_entity = SimpleNamespace(first_name="Dilshod", last_name=None, username="dilshod", phone="998901234567", bot=False)
    ev = SimpleNamespace(
        is_private=True, out=True, chat_id=888,
        message=SimpleNamespace(id=30, raw_text="Salom Dilshod", voice=None, photo=None, document=None, media=None),
        get_sender=AsyncMock(return_value=manager_entity),
        get_chat=AsyncMock(return_value=client_entity),
    )
    acc = accounts.Account("owner", "Owner", "oisha-tg-owner", lambda: None)
    assert await inbound.handle_message(ev, acc, amojo, store)
    payload = amojo.send_event.await_args.args[0]["payload"]
    assert payload["receiver"]["name"] == "Dilshod"
    assert payload["receiver"]["profile"]["phone"] == "998901234567"


# ---- 6. Background reconciler scan & dry-run ----------------------------


@pytest.mark.asyncio
async def test_background_reconciler_merges_existing_split_deals_and_respects_dry_run():
    crm = FakeCRM()
    crm.contacts[10] = _phone_contact(10, "Nodir", "+998905551122", [101], created_at=1000)
    crm.leads[101] = _lead(101, "Nodir qoʻngʻiroq", contact_id=10, created_at=1000)
    crm.call_counts[10] = 3

    crm.contacts[20] = _phone_contact(20, "Nodir TG", "+998905551122", [202], created_at=2000)
    crm.leads[202] = _lead(202, "Telegram Nodir", status_id=SALES_NEW_STATUS_ID, contact_id=20, created_at=2000)
    crm.chat_links.append({"contact_id": 20, "chat_id": "chat-nodir"})

    # Dry-run: zero mutations
    dry_merger = TelegramDealAutoMerger(crm=crm, amojo=_amojo_mock(), store=MessageStore(FakePool()), dry_run=True)
    dry_report = await scan_and_merge_existing(dry_merger, limit=50)
    assert dry_report.merged == 1
    assert not crm.closed_leads
    assert not crm.added_notes

    # Live run: merges & relinks chat
    live_merger = TelegramDealAutoMerger(crm=crm, amojo=_amojo_mock(), store=MessageStore(FakePool()), dry_run=False)
    live_report = await scan_and_merge_existing(live_merger, limit=50)
    assert live_report.merged == 1
    assert (202, None) in crm.closed_leads
    assert {"contact_id": 10, "chat_id": "chat-nodir"} in crm.chat_links


@pytest.mark.asyncio
async def test_conflict_tags_without_closing():
    crm = FakeCRM()
    crm.contacts[10] = _phone_contact(10, "Aziz", "+998907776655", [101], created_at=1000)
    crm.leads[101] = _lead(101, "Aziz 1", contact_id=10, created_at=1000, price=10_000_000)
    crm.contacts[20] = _phone_contact(20, "Aziz TG", "+998907776655", [202], created_at=2000)
    crm.leads[202] = _lead(202, "Telegram Aziz 2", status_id=SALES_NEW_STATUS_ID, contact_id=20, created_at=2000, price=5_000_000)
    crm.chat_links.append({"contact_id": 20, "chat_id": "chat-aziz"})

    merger = TelegramDealAutoMerger(crm=crm, amojo=_amojo_mock(), store=MessageStore(FakePool()))
    report = await scan_and_merge_existing(merger, limit=50)
    assert report.conflicts == 1
    assert not crm.closed_leads
    assert (202, REVIEW_CONFLICT_TAG) in crm.added_tags


# ---- 7. AmoCRMChatsMixin unit tests -------------------------------------


@pytest.mark.asyncio
async def test_amocrm_chats_mixin_exact_phone_filter_and_single_param_guard():
    class DummyCRM(AmoCRMChatsMixin):
        base_url = "https://x.amocrm.ru"
        def _load_token(self): pass
        def refresh_token(self): return False

        async def _request_with_auth(self, fn, url, **kwargs):
            self.last_call = (url, kwargs)
            if url.endswith("/api/v4/contacts"):
                return SimpleNamespace(
                    status_code=200,
                    json=lambda: {
                        "_embedded": {
                            "contacts": [
                                _phone_contact(1, "Match", "+998901234567", [11]),
                                _phone_contact(2, "FalsePositive", "+998909999999", [22]),
                            ]
                        }
                    },
                )
            return SimpleNamespace(status_code=200, json=lambda: {"_embedded": {"chats": [{"contact_id": 1, "chat_id": "u1"}]}})

    c = DummyCRM()
    found = await c.find_contacts_by_phone_async("90 123-45-67")
    assert [x["id"] for x in found] == [1]

    with pytest.raises(ValueError):
        await c.get_contact_chats(contact_id=1, chat_id="u1")

    chats = await c.get_contact_chats(chat_id="u1")
    assert chats == [{"contact_id": 1, "chat_id": "u1"}]
    assert c.last_call[1]["params"] == {"chat_id": "u1"}


@pytest.mark.asyncio
async def test_amojo_create_chat_sends_signed_post(monkeypatch):
    captured = []

    class FakeResp:
        status_code = 200
        content = b'{"id":"amo-uuid-42"}'
        def json(self): return {"id": "amo-uuid-42"}

    class FakeHttp:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, content, headers):
            captured.append((url, json.loads(content), headers))
            return FakeResp()

    monkeypatch.setattr("src.services.core.crm.tg_amo_bridge.amojo_client.httpx.AsyncClient", FakeHttp)
    client = AmoJoClient("amojo-1", "chan-1", "secret-1", scope_id="scope-1")
    chat_id = await client.create_chat(
        conversation_id="12345",
        user_id="12345",
        user_name="Ali",
        phone="+998901234567",
        profile_link="https://t.me/ali",
    )
    assert chat_id == "amo-uuid-42"
    assert captured[0][0].endswith("/v2/origin/custom/scope-1/chats")
    assert captured[0][1]["user"]["profile"]["phone"] == "+998901234567"
    assert "source" not in captured[0][1]


@pytest.mark.asyncio
async def test_closed_target_preserves_active_telegram_deal_link_only():
    crm = FakeCRM()
    crm.contacts[10] = _phone_contact(10, "Old Client", "+998901234567", [101], created_at=1000)
    crm.leads[101] = _lead(101, "Old Won Deal", status_id=STATUS_WON, contact_id=10, created_at=1000, price=25_000_000)
    crm.call_counts[10] = 4

    crm.contacts[20] = _phone_contact(20, "Returning TG", "", [202], created_at=3000)
    crm.leads[202] = _lead(202, "Telegram chat Returning", status_id=SALES_NEW_STATUS_ID, contact_id=20, created_at=3000)
    crm.chat_links.append({"contact_id": 20, "chat_id": "chat-returning"})

    merger = TelegramDealAutoMerger(crm=crm, amojo=_amojo_mock("chat-returning"), store=MessageStore(FakePool()))
    outcome = await merger.ensure_chat_linked_before_send(
        peer_id=999001, client_name="Returning", sender_phone="+998901234567", username="ret_client"
    )
    assert outcome.status == "linked_only"
    assert not crm.closed_leads
    assert (202, 10) in crm.linked_contacts
    assert any("TARIX" in txt for lid, txt in crm.added_notes if lid == 202)


@pytest.mark.asyncio
async def test_username_resolution_finds_phone_when_tg_phone_hidden():
    crm = FakeCRM()
    crm.contacts[10] = {
        "id": 10,
        "name": "Malika (@malika_brand)",
        "created_at": 1000,
        "custom_fields_values": [{"field_code": "PHONE", "values": [{"value": "+998911112233"}]}],
        "_embedded": {"leads": [{"id": 101}]},
    }
    crm.leads[101] = _lead(101, "Malika telefon", contact_id=10, created_at=1000)
    crm.call_counts[10] = 1

    merger = TelegramDealAutoMerger(crm=crm, amojo=_amojo_mock("chat-malika"), store=MessageStore(FakePool()))
    outcome = await merger.ensure_chat_linked_before_send(
        peer_id=333001, client_name="Malika", sender_phone=None, message_text="Salom!", username="malika_brand"
    )
    assert outcome.status == "proactive_linked"
    assert outcome.phone == "998911112233"
    assert outcome.phone_source == "amocrm_username"
    assert crm.chat_links == [{"contact_id": 10, "chat_id": "chat-malika"}]


@pytest.mark.asyncio
async def test_internal_team_phone_never_resolves_as_client_phone():
    from src.services.core.crm.team_roster import CANONICAL_STAFF
    from src.services.core.crm.tg_amo_bridge.analyzer import is_internal_team_phone

    staff_phone = next(m.phone for m in CANONICAL_STAFF if m.phone)
    assert is_internal_team_phone(staff_phone) is True
    assert is_internal_team_phone("+998901234567") is False
    merger = TelegramDealAutoMerger(crm=FakeCRM(), amojo=_amojo_mock(), store=MessageStore(FakePool()))
    phone, source = await merger.resolve_client_phone(
        peer_id=444001, sender_phone=staff_phone, message_text=f"Mening raqamim {staff_phone}"
    )
    assert phone == "" and source == ""


@pytest.mark.asyncio
async def test_same_contact_two_unpriced_deals_not_closed_without_deal_provenance():
    crm = FakeCRM()
    crm.contacts[10] = _phone_contact(10, "Sherzod", "+998901112244", [101, 102], created_at=1000)
    crm.leads[101] = _lead(101, "Sherzod brending", contact_id=10, created_at=1000, price=0)
    crm.leads[102] = _lead(102, "Sherzod qadoq dizayn", status_id=SALES_NEW_STATUS_ID, contact_id=10, created_at=2000, price=0)
    crm.chat_links.append({"contact_id": 10, "chat_id": "chat-sherzod"})

    merger = TelegramDealAutoMerger(crm=crm, amojo=_amojo_mock("chat-sherzod"), store=MessageStore(FakePool()))
    report = await scan_and_merge_existing(merger, limit=50)
    assert report.merged == 0
    assert not crm.closed_leads


@pytest.mark.asyncio
async def test_failed_transfer_blocks_source_close_and_retry_completes_without_duplicate_note():
    crm = FakeCRM()
    crm.contacts[10] = _phone_contact(10, "Kamol", "+998905556677", [101], created_at=1000)
    crm.leads[101] = _lead(101, "Kamol telefon", contact_id=10, created_at=1000)
    crm.call_counts[10] = 2
    crm.contacts[20] = _phone_contact(20, "Kamol TG", "", [202], created_at=2000)
    crm.leads[202] = _lead(202, "Telegram Kamol", status_id=SALES_NEW_STATUS_ID, contact_id=20, created_at=2000)
    crm.chat_links.append({"contact_id": 20, "chat_id": "chat-kamol"})
    crm.fail_chat_link = True

    store = MessageStore(FakePool())
    merger = TelegramDealAutoMerger(crm=crm, amojo=_amojo_mock("chat-kamol"), store=store)
    decision = analyze_lead_pair(
        LeadProfile(101, 10, "Kamol telefon", SALES_CONTACT_STATUS_ID, SALES_PIPELINE_ID, 0, 1000, 1010, 2, False, False, 0, (), ("998905556677",)),
        LeadProfile(202, 20, "Telegram Kamol", SALES_NEW_STATUS_ID, SALES_PIPELINE_ID, 0, 2000, 2010, 0, True, True, 0, (), ()),
    )

    first = await merger.execute_decision(decision, phone="998905556677", amo_chat_id="chat-kamol")
    assert first == "incomplete"
    assert not crm.closed_leads
    target_notes_after_fail = [t for lid, t in crm.added_notes if lid == 101]
    assert len(target_notes_after_fail) == 1

    crm.fail_chat_link = False
    second = await merger.execute_decision(decision, phone="998905556677", amo_chat_id="chat-kamol")
    assert second == "merged"
    assert (202, None) in crm.closed_leads
    assert len([t for lid, t in crm.added_notes if lid == 101]) == 1  # no duplicate merge note


@pytest.mark.asyncio
async def test_dry_run_does_not_call_amojo_create_chat():
    crm = FakeCRM()
    crm.contacts[10] = _phone_contact(10, "Anvar", "+998901231234", [101], created_at=1000)
    crm.leads[101] = _lead(101, "Anvar", contact_id=10, created_at=1000)
    amojo = _amojo_mock("should-not-be-created")
    merger = TelegramDealAutoMerger(crm=crm, amojo=amojo, store=MessageStore(FakePool()), dry_run=True)

    outcome = await merger.ensure_chat_linked_before_send(
        peer_id=612345, client_name="Anvar", sender_phone="+998901231234"
    )
    assert outcome.status == "proactive_linked"
    amojo.create_chat.assert_not_awaited()
    assert not crm.chat_links


@pytest.mark.asyncio
async def test_concurrent_merge_claims_prevent_duplicate_writes():
    import asyncio

    crm = FakeCRM()
    crm.contacts[10] = _phone_contact(10, "Rustam", "+998901119988", [101], created_at=1000)
    crm.leads[101] = _lead(101, "Rustam telefon", contact_id=10, created_at=1000)
    crm.contacts[20] = _phone_contact(20, "Rustam TG", "", [202], created_at=2000)
    crm.leads[202] = _lead(202, "Telegram Rustam", status_id=SALES_NEW_STATUS_ID, contact_id=20, created_at=2000)
    crm.lead_tasks[202] = [{"id": 7701, "text": "Follow up", "complete_till": 1799999999}]

    store = MessageStore(FakePool())
    merger = TelegramDealAutoMerger(crm=crm, amojo=_amojo_mock("chat-r"), store=store)
    decision = analyze_lead_pair(
        LeadProfile(101, 10, "Rustam telefon", SALES_CONTACT_STATUS_ID, SALES_PIPELINE_ID, 0, 1000, 1010, 1, False, False, 0, (), ("998901119988",)),
        LeadProfile(202, 20, "Telegram Rustam", SALES_NEW_STATUS_ID, SALES_PIPELINE_ID, 0, 2000, 2010, 0, True, True, 0, (), ()),
    )
    r1, r2 = await asyncio.gather(
        merger.execute_decision(decision, phone="998901119988", amo_chat_id="chat-r"),
        merger.execute_decision(decision, phone="998901119988", amo_chat_id="chat-r"),
    )
    assert r1 == "merged" and r2 == "merged"
    assert crm.reassigned_tasks == [(7701, 101)]
    assert len(crm.closed_leads) == 1


@pytest.mark.asyncio
async def test_returning_customer_low_score_closed_phone_deal_preserves_active_tg_chat():
    crm = FakeCRM()
    # Closed old phone deal with zero calls, zero price, zero notes (score = 20)
    crm.contacts[10] = _phone_contact(10, "Umid Old", "+998908887766", [101], created_at=1000)
    crm.leads[101] = _lead(101, "Old Lost Deal", status_id=STATUS_LOST, contact_id=10, created_at=1000, price=0)
    # Active returning Telegram deal (higher score = 70)
    crm.contacts[20] = _phone_contact(20, "Umid TG", "", [202], created_at=3000)
    crm.leads[202] = _lead(202, "Telegram Umid", status_id=SALES_NEW_STATUS_ID, contact_id=20, created_at=3000, price=0)
    crm.chat_links.append({"contact_id": 20, "chat_id": "chat-umid"})

    merger = TelegramDealAutoMerger(crm=crm, amojo=_amojo_mock("chat-umid"), store=MessageStore(FakePool()))
    outcome = await merger.ensure_chat_linked_before_send(
        peer_id=888001, client_name="Umid", sender_phone="+998908887766"
    )
    assert outcome.status == "linked_only"
    assert not crm.closed_leads
    assert crm.chat_links == [{"contact_id": 20, "chat_id": "chat-umid"}]  # chat NOT moved off active deal
    assert (202, 10) in crm.linked_contacts


def test_automerge_cli_accepts_explicit_dry_run_flag():
    from src.services.core.crm.tg_amo_bridge.automerge_cli import build_parser

    args = build_parser().parse_args(["--dry-run", "--limit", "50"])
    assert args.apply is False and args.dry_run is True and args.limit == 50


@pytest.mark.asyncio
async def test_runtime_start_wires_merger_and_background_reconciler(monkeypatch):
    import asyncio
    from src.services.core.crm.tg_amo_bridge import runtime

    monkeypatch.setenv("TG_AMO_BRIDGE_ENABLED", "1")
    monkeypatch.setenv("TG_AMO_AUTOMERGE_ENABLED", "1")
    monkeypatch.setenv("TG_AMO_AUTOMERGE_INTERVAL_SECONDS", "60")
    monkeypatch.setenv("AMOCRM_AMOJO_ID", "amojo-test")

    fake_amojo = _amojo_mock()
    fake_store = MessageStore(FakePool())
    registered = []
    monkeypatch.setattr(runtime, "_amojo", fake_amojo)
    monkeypatch.setattr(runtime, "_store", fake_store)
    monkeypatch.setattr(runtime, "_reconciler_task", None)
    monkeypatch.setattr(runtime, "_merger", None)
    monkeypatch.setattr(runtime, "resolve_amojo_id", AsyncMock(return_value="amojo-test"))
    monkeypatch.setattr(runtime, "resolve_manager_ref_id", AsyncMock(return_value="mgr-ref"))
    monkeypatch.setattr(
        accounts, "all_accounts",
        lambda: [accounts.Account("owner", "O", "oisha-tg-owner", lambda: SimpleNamespace())],
    )
    monkeypatch.setattr(inbound, "register", lambda *a, **kw: registered.append(kw.get("merger")))
    started_loop = asyncio.Event()

    async def fake_loop(merger, *, interval_seconds=300, limit=100):
        started_loop.set()
        await asyncio.sleep(60)

    monkeypatch.setattr(runtime, "automerge_loop", fake_loop)
    ok = await runtime.start(crm_client=FakeCRM(), db=None)
    try:
        assert ok is True
        assert runtime.get_merger() is not None
        assert registered and registered[0] is runtime.get_merger()
        await asyncio.wait_for(started_loop.wait(), timeout=2.0)
    finally:
        if runtime._reconciler_task:
            runtime._reconciler_task.cancel()
            try:
                await runtime._reconciler_task
            except asyncio.CancelledError:
                pass
            runtime._reconciler_task = None

