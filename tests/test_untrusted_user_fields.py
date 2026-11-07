"""LLM [SAVE_INFO]/[CALENDAR_EVENT] tags reach the users table safely (audit 2026-11-07).

upsert_user interpolates kwargs keys as SQL identifiers, and the keys come
from LLM output fed by client messages, so they are allow-listed twice: the
repository drops non-columns, the tag parsers keep only profile fields.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.db.repositories.users import UserRepository, filter_untrusted_profile_fields
from src.services.core.action_parser import ActionParser


def _repo(existing: bool) -> UserRepository:
    repo = UserRepository.__new__(UserRepository)
    repo._fetch_one = AsyncMock(return_value={"user_id": 1} if existing else None)
    repo._execute = AsyncMock()
    return repo


@pytest.mark.asyncio
@pytest.mark.parametrize("existing", [True, False])
async def test_upsert_user_drops_non_column_keys(existing):
    repo = _repo(existing)
    hostile = "role) VALUES (1); --"
    await repo.upsert_user(1, first_name="Ali", position="PM", **{hostile: "x", "source_group": "g"})

    sql, params = repo._execute.await_args.args
    assert "position" in sql
    assert "source_group" not in sql
    assert "--" not in sql
    assert "PM" in params and "x" not in params


def test_untrusted_filter_keeps_profile_fields_only():
    data = {"phone": "+998901112233", "region": "Toshkent", "role": "admin", "assigned_to": "x", "crm_synced": 1}
    assert filter_untrusted_profile_fields(data) == {"phone": "+998901112233", "region": "Toshkent"}


@pytest.mark.asyncio
async def test_save_info_is_awaited_and_privileged_keys_dropped():
    db = MagicMock()
    db.upsert_user = AsyncMock()
    parser = ActionParser(db=db)

    text = await parser.parse_and_execute(
        "[SAVE_INFO: phone=+998901112233] [SAVE_INFO: role=admin] Rahmat",
        sender_id=7, sender_name="Ali", username="ali",
    )

    db.upsert_user.assert_awaited_once_with(7, "Ali", username="ali", phone="+998901112233")
    assert text == "Rahmat"


@pytest.mark.asyncio
async def test_calendar_event_saves_meeting_and_notifies_group():
    db = MagicMock()
    db.upsert_user = AsyncMock()
    parser = ActionParser(db=db, gcalendar=MagicMock())

    with patch.object(parser, "_notify_meeting_group") as notify:
        await parser.parse_and_execute(
            "[CALENDAR_EVENT: summary=Brif|start=2026-11-10T10:00] Kelishdik",
            sender_id=7, sender_name="Ali", username="ali",
        )

    db.upsert_user.assert_awaited_once_with(
        7, "Ali", username="ali", meeting_time="2026-11-10T10:00", meeting_status="scheduled",
    )
    notify.assert_called_once()


@pytest.mark.asyncio
async def test_calendar_notification_survives_db_failure():
    db = MagicMock()
    db.upsert_user = AsyncMock(side_effect=RuntimeError("db down"))
    parser = ActionParser(db=db, gcalendar=MagicMock())

    with patch.object(parser, "_notify_meeting_group") as notify:
        await parser.parse_and_execute(
            "[CALENDAR_EVENT: summary=Brif|start=2026-11-10T10:00] Ok",
            sender_id=7, sender_name="Ali", username="ali",
        )

    notify.assert_called_once()


@pytest.mark.asyncio
async def test_save_lead_info_awaits_db_and_reports_real_outcome():
    from src.agents.agent_tools.crm_actions import CrmActionsMixin

    tool = CrmActionsMixin.__new__(CrmActionsMixin)
    tool.db = MagicMock()
    tool.db.upsert_user = AsyncMock()
    tool.gsheet = MagicMock(sync_user=MagicMock(side_effect=RuntimeError("no sheets")))
    tool.amocrm = MagicMock()
    tool._log_action = AsyncMock()

    result = await tool._save_lead_info(5, name="Ali", region="Toshkent")

    tool.db.upsert_user.assert_awaited_once_with(5, "Ali", None, phone=None, region="Toshkent")
    assert result["success"] is True
    assert "SQLite DB" in result["message"]


@pytest.mark.asyncio
async def test_save_lead_info_reports_failure_when_nothing_saved():
    from src.agents.agent_tools.crm_actions import CrmActionsMixin

    tool = CrmActionsMixin.__new__(CrmActionsMixin)
    tool.db = MagicMock()
    tool.db.upsert_user = AsyncMock(side_effect=RuntimeError("db down"))
    tool.gsheet = MagicMock(sync_user=MagicMock(side_effect=RuntimeError("no sheets")))
    tool.amocrm = MagicMock()
    tool._log_action = AsyncMock()

    result = await tool._save_lead_info(5, name="Ali")

    assert result["success"] is False
