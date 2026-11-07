"""Remaining AmoCRM lead creators no longer pass kwargs create_lead rejects (audit 2026-11-07)."""
from __future__ import annotations

import ast
import inspect
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.core.crm.amocrm.leads_create import AmoCRMLeadsCreateMixin
from src.services.core.leads.scraper.dialog_sync import DialogSyncMixin

ROOT = Path(__file__).resolve().parents[1]


def _call_kwargs(rel_path: str, method: str) -> list[set[str]]:
    tree = ast.parse((ROOT / rel_path).read_text(encoding="utf-8"))
    return [
        {kw.arg for kw in node.keywords if kw.arg}
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == method
    ]


@pytest.mark.parametrize(
    "rel_path",
    [
        "src/commands/sync.py",
        "src/services/core/leads/scraper/dialog_sync.py",
        "src/services/core/action_parser.py",
        "src/agents/agent_tools/crm_actions.py",
    ],
)
@pytest.mark.parametrize("method", ["create_lead", "ensure_lead", "create_standalone_lead"])
def test_lead_calls_only_use_accepted_kwargs(rel_path, method):
    accepted = set(inspect.signature(getattr(AmoCRMLeadsCreateMixin, method)).parameters) - {"self"}
    for kwargs in _call_kwargs(rel_path, method):
        assert kwargs <= accepted, f"{rel_path}: {method}() got {sorted(kwargs - accepted)}"


def _dm_syncer(amocrm) -> DialogSyncMixin:
    syncer = DialogSyncMixin.__new__(DialogSyncMixin)
    syncer.amocrm = amocrm
    syncer.message_controller = None
    syncer.db = MagicMock(set_crm_synced=AsyncMock())
    return syncer


DIALOG = SimpleNamespace(id=11, name="Ali", entity=SimpleNamespace(username="ali"))


@pytest.mark.asyncio
async def test_dm_lead_with_phone_uses_ensure_lead():
    amocrm = MagicMock(ensure_lead=AsyncMock(return_value=5), create_standalone_lead=AsyncMock())
    syncer = _dm_syncer(amocrm)

    assert await syncer._dm_save_to_crm(DIALOG, "998901112233", "HOT", {"summary": "x"}) is True

    assert amocrm.ensure_lead.await_args.kwargs["phone"] == "998901112233"
    amocrm.create_standalone_lead.assert_not_awaited()
    syncer.db.set_crm_synced.assert_awaited_once_with(11)


@pytest.mark.asyncio
async def test_dm_lead_without_phone_creates_tagged_standalone_deal():
    amocrm = MagicMock(ensure_lead=AsyncMock(), create_standalone_lead=AsyncMock(return_value=6))
    syncer = _dm_syncer(amocrm)

    assert await syncer._dm_save_to_crm(DIALOG, "Unknown", "HOT", {"summary": "x"}) is True

    amocrm.ensure_lead.assert_not_awaited()
    assert amocrm.create_standalone_lead.await_args.kwargs["tags"] == ["TELEGRAM_DM_LEAD"]


@pytest.mark.asyncio
async def test_dm_lead_failure_is_not_marked_synced():
    amocrm = MagicMock(ensure_lead=AsyncMock(return_value=None))
    syncer = _dm_syncer(amocrm)

    assert await syncer._dm_save_to_crm(DIALOG, "+998901112233", "HOT", {}) is False
    syncer.db.set_crm_synced.assert_not_awaited()
