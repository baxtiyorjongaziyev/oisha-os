"""Regression proof for Instagram webhook security and CRM compatibility."""

import hashlib
import hmac
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from src.api_server import app
from src.services.core.instagram.lead_qualifier import sync_lead_to_amocrm
from src.services.core.instagram_agent import process_instagram_webhook


client = TestClient(app)


def test_webhook_signature_uses_exact_raw_body():
    raw_body = b'{"object": "instagram", "entry": []}'
    secret = "test-secret"
    signature = "sha256=" + hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()

    with patch("src.services.core.instagram_agent.settings.META_APP_SECRET", SecretStr(secret)):
        response = client.post(
            "/api/instagram/webhook",
            content=raw_body,
            headers={"content-type": "application/json", "x-hub-signature-256": signature},
        )

    assert response.status_code == 200


def test_webhook_rejects_unsigned_request_without_app_secret():
    with patch("src.services.core.instagram_agent.settings.META_APP_SECRET", None):
        response = client.post("/api/instagram/webhook", json={"object": "instagram"})

    assert response.status_code == 403


@pytest.mark.asyncio
@patch("src.services.core.instagram_agent.reply_to_comment", return_value=True)
@patch("src.services.core.instagram_agent.like_comment", return_value=True)
@patch("src.services.core.instagram_agent.generate_comment_reply", new_callable=AsyncMock)
@patch("src.services.core.instagram_agent.notify_crm")
async def test_mention_event_is_processed(mock_notify, mock_reply, _mock_like, _mock_reply_api):
    mock_reply.return_value = "Rahmat!"
    payload = {
        "object": "instagram",
        "entry": [{
            "id": "page-id",
            "changes": [{
                "field": "mentions",
                "value": {
                    "id": "mention-id",
                    "text": "@oisha branding kerak",
                    "verb": "add",
                    "from": {"id": "user-id", "username": "client"},
                },
            }],
        }],
    }

    await process_instagram_webhook(payload, AsyncMock())

    assert mock_notify.call_args.args[0] == "Instagram Mention"


@patch("src.services.core.crm.amocrm.sync.AmoCRMSync")
def test_crm_sync_uses_supported_amocrm_contract(mock_cls):
    instance = MagicMock()
    instance.create_contact.return_value = 11
    instance.create_lead_for_contact.return_value = 22
    mock_cls.return_value = instance

    result = sync_lead_to_amocrm("Ali", "+998901234567", details="Branding")

    assert result == 22
    assert "redirect_url" in mock_cls.call_args.kwargs
    assert "redirect_uri" not in mock_cls.call_args.kwargs
    instance.create_contact.assert_called_once_with(name="Ali", phone="+998901234567")
    instance.add_lead_note.assert_called_once()

