"""AI lead pushes reach AmoCRM through ensure_lead (audit 2026-11-07).

Both callers used to call create_lead with kwargs it does not accept
(note=/notes=/user_id=), so every push died with TypeError.
"""
from __future__ import annotations

import inspect
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.core.action_parser import ActionParser
from src.services.core.crm.amocrm.leads_create import AmoCRMLeadsCreateMixin


def _db(state: str = "") -> MagicMock:
    db = MagicMock()
    db.get_state = AsyncMock(return_value=state)
    db.set_state = AsyncMock()
    db.upsert_user = AsyncMock()
    return db


def test_ensure_lead_accepts_the_kwargs_callers_send():
    params = inspect.signature(AmoCRMLeadsCreateMixin.ensure_lead).parameters
    assert {"name", "phone", "note"} <= set(params)


@pytest.mark.asyncio
async def test_push_tag_creates_lead_once_and_remembers_it():
    amocrm = MagicMock(ensure_lead=AsyncMock(return_value=4242))
    db = _db()
    parser = ActionParser(db=db, amocrm=amocrm)

    await parser.parse_and_execute(
        "[PUSH_TO_AMOCRM: title=Ali brend|phone=+998901112233] Rahmat",
        sender_id=7, sender_name="Ali", username="ali",
    )

    amocrm.ensure_lead.assert_awaited_once()
    kwargs = amocrm.ensure_lead.await_args.kwargs
    assert kwargs["name"] == "Ali brend"
    assert kwargs["phone"] == "+998901112233"
    assert "AI Agent" in kwargs["note"]
    db.set_state.assert_awaited_once_with("crm:ai_push:7", "4242")


@pytest.mark.asyncio
async def test_repeat_sifatli_replies_do_not_push_again():
    amocrm = MagicMock(ensure_lead=AsyncMock(return_value=4242))
    parser = ActionParser(db=_db(state="4242"), amocrm=amocrm)

    await parser.parse_and_execute(
        "[LEAD_REPORT: QUALITY=sifatli] Rahmat",
        sender_id=7, sender_name="Ali", username="ali", saved_phone="+998901112233",
    )

    amocrm.ensure_lead.assert_not_awaited()


@pytest.mark.asyncio
async def test_push_without_phone_is_skipped():
    amocrm = MagicMock(ensure_lead=AsyncMock(return_value=1))
    parser = ActionParser(db=_db(), amocrm=amocrm)

    await parser.parse_and_execute(
        "[LEAD_REPORT: QUALITY=sifatli] ok", sender_id=7, sender_name="Ali", username="ali",
    )

    amocrm.ensure_lead.assert_not_awaited()


@pytest.mark.asyncio
async def test_save_lead_info_pushes_through_ensure_lead():
    from src.agents.agent_tools.crm_actions import CrmActionsMixin

    tool = CrmActionsMixin.__new__(CrmActionsMixin)
    tool.db = _db()
    tool.gsheet = MagicMock()
    tool.amocrm = MagicMock(ensure_lead=AsyncMock(return_value=99))
    tool._log_action = AsyncMock()

    result = await tool._save_lead_info(5, name="Ali", phone="+998901112233", region="Toshkent")

    tool.amocrm.ensure_lead.assert_awaited_once()
    assert tool.amocrm.ensure_lead.await_args.kwargs["phone"] == "+998901112233"
    assert "AmoCRM" in result["message"]


@pytest.mark.asyncio
async def test_save_lead_info_does_not_claim_amocrm_when_no_lead_id():
    from src.agents.agent_tools.crm_actions import CrmActionsMixin

    tool = CrmActionsMixin.__new__(CrmActionsMixin)
    tool.db = _db()
    tool.gsheet = MagicMock()
    tool.amocrm = MagicMock(ensure_lead=AsyncMock(return_value=None))
    tool._log_action = AsyncMock()

    result = await tool._save_lead_info(5, name="Ali", phone="+998901112233")

    assert "AmoCRM" not in result["message"]
