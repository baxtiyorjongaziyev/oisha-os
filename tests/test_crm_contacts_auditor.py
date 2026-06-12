from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.services.core.crm_contacts_auditor import CRMContactsAuditor


def make_auditor(dialogs, get_permissions):
    auditor = object.__new__(CRMContactsAuditor)
    auditor.tg_client = SimpleNamespace(get_permissions=get_permissions)
    auditor._dialogs_cache = dialogs
    auditor._dialogs_cache_time = datetime.now()
    return auditor


def test_extract_keywords_excludes_shared_honorifics():
    auditor = make_auditor([], AsyncMock())

    keywords = auditor.extract_keywords("Saidazimxoja aka", "Saidazimxoja aka")

    assert "saidazimxoja" in keywords
    assert "aka" not in keywords


@pytest.mark.asyncio
async def test_group_context_is_not_used_without_verified_telegram_identity():
    dialogs = [
        SimpleNamespace(
            name="Farrux aka sendvich",
            entity=SimpleNamespace(id=101),
        )
    ]
    get_permissions = AsyncMock()
    auditor = make_auditor(dialogs, get_permissions)

    matched = await auditor.find_shared_group_chats(
        "Farrux aka",
        "Farrux aka",
        telegram_user_id=None,
    )

    assert matched == []
    get_permissions.assert_not_awaited()


@pytest.mark.asyncio
async def test_group_context_only_uses_exact_identity_keyword_and_membership():
    farrux_group = SimpleNamespace(
        name="Farrux aka sendvich",
        entity=SimpleNamespace(id=101),
    )
    saidazim_group = SimpleNamespace(
        name="Saidazimxoja aka loyiha",
        entity=SimpleNamespace(id=202),
    )
    get_permissions = AsyncMock(return_value=SimpleNamespace())
    auditor = make_auditor([farrux_group, saidazim_group], get_permissions)

    matched = await auditor.find_shared_group_chats(
        "Saidazimxoja aka",
        "Saidazimxoja aka",
        telegram_user_id=777,
    )

    assert matched == [(saidazim_group.entity, "Saidazimxoja aka loyiha")]
    get_permissions.assert_awaited_once_with(saidazim_group.entity, 777)


@pytest.mark.asyncio
async def test_group_context_fails_closed_when_membership_check_errors():
    group = SimpleNamespace(
        name="Saidazimxoja aka loyiha",
        entity=SimpleNamespace(id=202),
    )
    get_permissions = AsyncMock(side_effect=RuntimeError("temporary Telegram error"))
    auditor = make_auditor([group], get_permissions)

    matched = await auditor.find_shared_group_chats(
        "Saidazimxoja aka",
        "Saidazimxoja aka",
        telegram_user_id=777,
    )

    assert matched == []
