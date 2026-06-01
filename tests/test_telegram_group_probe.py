from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src import api_server


@pytest.mark.asyncio
async def test_group_access_endpoint_refreshes_snapshot_read_only(monkeypatch):
    refresh = AsyncMock(return_value={"status": "ok", "groups": {}, "topics": {}})
    monkeypatch.setattr(api_server, "refresh_userbot_group_access_snapshot", refresh)

    snapshot = await api_server.telegram_group_access(refresh=True)

    assert snapshot["status"] == "ok"
    refresh.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_userbot_group_probe_reads_configured_groups_and_topics(monkeypatch):
    monkeypatch.setattr(api_server.settings, "CRM_GROUP_ID", -100111, raising=False)
    monkeypatch.setattr(api_server.settings, "TEAM_GROUP_ID", -100222, raising=False)
    monkeypatch.setattr(api_server.settings, "PROJECTS_GROUP_ID", None, raising=False)
    monkeypatch.setattr(api_server.settings, "TASKS_GROUP_ID", None, raising=False)
    monkeypatch.setattr(api_server.settings, "CRM_TOPIC_ID", 7, raising=False)
    monkeypatch.setattr(api_server.settings, "TOPIC_CRM_ID", None, raising=False)
    monkeypatch.setattr(api_server.settings, "TOPIC_REPORTS_ID", None, raising=False)
    monkeypatch.setattr(api_server.settings, "TOPIC_TASKS_ID", None, raising=False)
    monkeypatch.setattr(api_server.settings, "TOPIC_GENERAL_ID", None, raising=False)
    monkeypatch.setattr(api_server.settings, "TOPIC_KIRIM_ID", 168, raising=False)

    client = MagicMock()
    client.get_entity = AsyncMock()
    client.get_messages = AsyncMock(return_value=[])

    snapshot = await api_server.refresh_userbot_group_access_snapshot(client)

    assert snapshot["status"] == "ok"
    assert snapshot["groups"]["crm_group"]["readable"] is True
    assert snapshot["groups"]["team_group"]["readable"] is True
    assert snapshot["topics"]["crm"]["readable"] is True
    assert snapshot["topics"]["kirim"]["readable"] is True
    assert client.get_entity.await_count == 2
    assert client.get_messages.await_count == 2


@pytest.mark.asyncio
async def test_userbot_group_probe_reports_access_error_without_raising(monkeypatch):
    monkeypatch.setattr(api_server.settings, "CRM_GROUP_ID", -100111, raising=False)
    monkeypatch.setattr(api_server.settings, "TEAM_GROUP_ID", None, raising=False)
    monkeypatch.setattr(api_server.settings, "PROJECTS_GROUP_ID", None, raising=False)
    monkeypatch.setattr(api_server.settings, "TASKS_GROUP_ID", None, raising=False)
    monkeypatch.setattr(api_server.settings, "CRM_TOPIC_ID", None, raising=False)
    monkeypatch.setattr(api_server.settings, "TOPIC_CRM_ID", None, raising=False)
    monkeypatch.setattr(api_server.settings, "TOPIC_REPORTS_ID", None, raising=False)
    monkeypatch.setattr(api_server.settings, "TOPIC_TASKS_ID", None, raising=False)
    monkeypatch.setattr(api_server.settings, "TOPIC_GENERAL_ID", None, raising=False)
    monkeypatch.setattr(api_server.settings, "TOPIC_KIRIM_ID", None, raising=False)

    client = MagicMock()
    client.get_entity = AsyncMock(side_effect=ValueError("not found"))
    client.get_dialogs = AsyncMock(return_value=[])

    snapshot = await api_server.refresh_userbot_group_access_snapshot(client)

    assert snapshot["status"] == "degraded"
    assert snapshot["groups"]["crm_group"]["readable"] is False
    assert snapshot["groups"]["crm_group"]["error"] == "ValueError"
    assert snapshot["groups"]["crm_group"]["reason"] == "not_in_userbot_dialogs"


@pytest.mark.asyncio
async def test_userbot_group_probe_resolves_uncached_group_from_dialogs(monkeypatch):
    monkeypatch.setattr(api_server.settings, "CRM_GROUP_ID", -100111, raising=False)
    monkeypatch.setattr(api_server.settings, "TEAM_GROUP_ID", None, raising=False)
    monkeypatch.setattr(api_server.settings, "PROJECTS_GROUP_ID", None, raising=False)
    monkeypatch.setattr(api_server.settings, "TASKS_GROUP_ID", None, raising=False)
    monkeypatch.setattr(api_server.settings, "CRM_TOPIC_ID", None, raising=False)
    monkeypatch.setattr(api_server.settings, "TOPIC_CRM_ID", None, raising=False)
    monkeypatch.setattr(api_server.settings, "TOPIC_REPORTS_ID", None, raising=False)
    monkeypatch.setattr(api_server.settings, "TOPIC_TASKS_ID", None, raising=False)
    monkeypatch.setattr(api_server.settings, "TOPIC_GENERAL_ID", None, raising=False)
    monkeypatch.setattr(api_server.settings, "TOPIC_KIRIM_ID", None, raising=False)

    entity = SimpleNamespace(forum=True)
    client = MagicMock()
    client.get_entity = AsyncMock(side_effect=ValueError("not cached"))
    client.get_dialogs = AsyncMock(
        return_value=[SimpleNamespace(id=-100111, entity=entity)]
    )

    snapshot = await api_server.refresh_userbot_group_access_snapshot(client)

    assert snapshot["status"] == "ok"
    assert snapshot["groups"]["crm_group"]["readable"] is True
    assert snapshot["groups"]["crm_group"]["source"] == "dialogs"
    assert snapshot["groups"]["crm_group"]["forum"] is True


@pytest.mark.asyncio
async def test_userbot_group_probe_classifies_invalid_topic(monkeypatch):
    class BadRequestError(Exception):
        pass

    monkeypatch.setattr(api_server.settings, "CRM_GROUP_ID", -100111, raising=False)
    monkeypatch.setattr(api_server.settings, "TEAM_GROUP_ID", None, raising=False)
    monkeypatch.setattr(api_server.settings, "PROJECTS_GROUP_ID", None, raising=False)
    monkeypatch.setattr(api_server.settings, "TASKS_GROUP_ID", None, raising=False)
    monkeypatch.setattr(api_server.settings, "CRM_TOPIC_ID", 7, raising=False)
    monkeypatch.setattr(api_server.settings, "TOPIC_CRM_ID", None, raising=False)
    monkeypatch.setattr(api_server.settings, "TOPIC_REPORTS_ID", None, raising=False)
    monkeypatch.setattr(api_server.settings, "TOPIC_TASKS_ID", None, raising=False)
    monkeypatch.setattr(api_server.settings, "TOPIC_GENERAL_ID", None, raising=False)
    monkeypatch.setattr(api_server.settings, "TOPIC_KIRIM_ID", None, raising=False)

    client = MagicMock()
    client.get_entity = AsyncMock(return_value=SimpleNamespace(forum=True))
    client.get_messages = AsyncMock(side_effect=BadRequestError("invalid topic"))

    snapshot = await api_server.refresh_userbot_group_access_snapshot(client)

    assert snapshot["status"] == "degraded"
    assert snapshot["topics"]["crm"]["readable"] is False
    assert snapshot["topics"]["crm"]["reason"] == "invalid_or_deleted_topic"


@pytest.mark.asyncio
async def test_userbot_group_probe_reads_tasks_topic_from_crm_group_by_default(
    monkeypatch,
):
    monkeypatch.setattr(api_server.settings, "CRM_GROUP_ID", -100111, raising=False)
    monkeypatch.setattr(api_server.settings, "TEAM_GROUP_ID", None, raising=False)
    monkeypatch.setattr(api_server.settings, "PROJECTS_GROUP_ID", -100333, raising=False)
    monkeypatch.setattr(api_server.settings, "TASKS_GROUP_ID", None, raising=False)
    monkeypatch.setattr(api_server.settings, "CRM_TOPIC_ID", None, raising=False)
    monkeypatch.setattr(api_server.settings, "TOPIC_CRM_ID", None, raising=False)
    monkeypatch.setattr(api_server.settings, "TOPIC_REPORTS_ID", None, raising=False)
    monkeypatch.setattr(api_server.settings, "TOPIC_TASKS_ID", 607, raising=False)
    monkeypatch.setattr(api_server.settings, "TOPIC_GENERAL_ID", None, raising=False)
    monkeypatch.setattr(api_server.settings, "TOPIC_KIRIM_ID", None, raising=False)

    client = MagicMock()
    client.get_entity = AsyncMock(return_value=SimpleNamespace(forum=True))
    client.get_messages = AsyncMock(return_value=[])

    snapshot = await api_server.refresh_userbot_group_access_snapshot(client)

    assert snapshot["status"] == "ok"
    assert snapshot["topics"]["tasks"]["group"] == "crm_group"
    assert snapshot["topics"]["tasks"]["readable"] is True
