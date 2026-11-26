"""Tests for Moizvonki SIM-card SMS client and missed-call auto-SMS."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.telephony.moizvonki_sms import (
    SMS_TEMPLATES,
    MissedCallAutoSms,
    MoizvonkiSmsClient,
)


def _fake_settings(**overrides):
    base = dict(
        MOIZVONKI_DOMAIN="jonbrandingagency.moizvonki.ru",
        MOIZVONKI_API_KEY="test-api-key",
        MOIZVONKI_EMAIL="default@jonbranding.uz",
        MOIZVONKI_AUTO_SMS_ENABLED=True,
        MOIZVONKI_AUTO_SMS_COOLDOWN_HOURS=24,
        EXCLUDED_PHONES=["+998701641197"],
        AMOCRM_CALL_ANALYSIS_EXCLUDED_PHONES="",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.mark.asyncio
async def test_send_sms_uses_manager_account_and_calls_send_sms_action():
    captured = {}

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, json=None, headers=None):
            captured["url"] = url
            captured["json"] = json
            return SimpleNamespace(status_code=200)

    client = MoizvonkiSmsClient(settings_obj=_fake_settings())
    with patch("src.services.telephony.moizvonki_sms.httpx.AsyncClient", FakeAsyncClient):
        res = await client.send_template(
            to_phone="+998901234567",
            template_key="missed_call",
            user_name="mumtozmaxal@jonbranding.uz",
        )

    assert res["sent"] is True
    assert captured["url"] == "https://jonbrandingagency.moizvonki.ru/api/v1"
    assert captured["json"]["action"] == "calls.send_sms"
    assert captured["json"]["user_name"] == "mumtozmaxal@jonbranding.uz"
    assert captured["json"]["to"] == "+998901234567"
    assert captured["json"]["text"] == SMS_TEMPLATES["missed_call"]


@pytest.mark.asyncio
async def test_missed_call_auto_sms_sends_once_and_respects_cooldown(tmp_path):
    cfg = _fake_settings()
    sms_client = MagicMock()
    sms_client.send_template = AsyncMock(
        return_value={"sent": True, "sender": "rayxona@jonbranding.uz"}
    )
    auto = MissedCallAutoSms(
        client=sms_client,
        db_path=str(tmp_path / "sms.db"),
        settings_obj=cfg,
    )

    first = await auto.handle_call_finish(
        phone="+998901234567",
        status="missed",
        duration=0,
        user_account="rayxona@jonbranding.uz",
    )
    second = await auto.handle_call_finish(
        phone="+998901234567",
        status="missed",
        duration=0,
        user_account="rayxona@jonbranding.uz",
    )

    assert first["sent"] is True
    assert second["sent"] is False
    assert second["reason"] == "cooldown"
    assert sms_client.send_template.await_count == 1


@pytest.mark.asyncio
async def test_missed_call_auto_sms_skips_answered_blacklisted_and_team(tmp_path):
    cfg = _fake_settings()
    sms_client = MagicMock()
    sms_client.send_template = AsyncMock(return_value={"sent": True})
    auto = MissedCallAutoSms(
        client=sms_client,
        db_path=str(tmp_path / "sms.db"),
        settings_obj=cfg,
    )

    answered = await auto.handle_call_finish(
        phone="+998901234567", status="answered", duration=45, user_account="rayxona@jonbranding.uz"
    )
    blacklisted = await auto.handle_call_finish(
        phone="+998701641197", status="missed", duration=0, user_account="rayxona@jonbranding.uz"
    )
    team_member = await auto.handle_call_finish(
        phone="+998773220098", status="missed", duration=0, user_account="rayxona@jonbranding.uz"
    )

    assert answered["reason"] == "not_missed"
    assert blacklisted["reason"] == "blacklisted"
    assert team_member["reason"] == "internal_team"
    sms_client.send_template.assert_not_awaited()
