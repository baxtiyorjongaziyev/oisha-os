"""
Unit tests for Meta Instagram Webhook & Agent integration
"""
import pytest
import hmac
import hashlib
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient

from src.api_server import app
from src.services.core.instagram_agent import verify_signature, notify_crm

client = TestClient(app)


def test_verify_signature():
    payload = b"test_payload"
    secret = "test_secret"
    expected_sig = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

    # Valid signature
    assert verify_signature(payload, expected_sig, secret) is True

    # Invalid signature
    assert verify_signature(payload, "invalid_sig", secret) is False

    # Empty secret (skipped verify)
    assert verify_signature(payload, expected_sig, "") is True


@patch.dict("os.environ", {"META_VERIFY_TOKEN": "correct_token"})
def test_webhook_verification_success():
    response = client.get(
        "/api/instagram/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "correct_token",
            "hub.challenge": "12345challenge"
        }
    )
    assert response.status_code == 200
    assert response.text == "12345challenge"


@patch.dict("os.environ", {"META_VERIFY_TOKEN": "correct_token"})
def test_webhook_verification_failure():
    response = client.get(
        "/api/instagram/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong_token",
            "hub.challenge": "12345challenge"
        }
    )
    assert response.status_code == 403
    assert "Verification token mismatch" in response.text


@pytest.mark.asyncio
@patch("src.services.core.instagram_agent.requests.post")
async def test_notify_crm(mock_post):
    mock_post.return_value.status_code = 200

    with patch("src.services.core.instagram_agent.settings") as mock_settings:
        mock_settings.CRM_GROUP_ID = -100123456
        mock_settings.CRM_TOPIC_ID = 5
        mock_settings.BOT_TOKEN.get_secret_value.return_value = "fake_bot_token"

        notify_crm(
            source="Instagram DM",
            user_name="Botir",
            user_id="ig_12345",
            message="Salom, narxlarni bering",
            reply="[LEAD_REPORT: QUALITY=sifatli] Assalomu alaykum! Narxlarimiz..."
        )

        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert "fake_bot_token" in args[0]
        assert kwargs["json"]["chat_id"] == -100123456
        assert kwargs["json"]["message_thread_id"] == 5
        assert "Sifatli 💎" in kwargs["json"]["text"]
        assert "Botir" in kwargs["json"]["text"]


@pytest.mark.asyncio
@patch("src.services.core.instagram_agent.send_ig_reply")
@patch("src.services.core.instagram_agent.notify_crm")
@patch("src.services.core.instagram_agent.AutonomousSalesAgent")
async def test_process_instagram_webhook_dm(mock_agent_class, mock_notify, mock_send_reply):
    # Mock database
    mock_db = AsyncMock()
    mock_db.log_message = AsyncMock()
    mock_db.upsert_user = AsyncMock()

    # Mock AutonomousSalesAgent
    mock_agent_instance = MagicMock()
    mock_agent_instance.handle_incoming = AsyncMock(return_value={
        "response": "[SAVE_INFO: phone=+998991234567] Salom, xabarni qabul qildim"
    })
    mock_agent_class.return_value = mock_agent_instance

    payload = {
        "object": "instagram",
        "entry": [
            {
                "id": "entry_1",
                "messaging": [
                    {
                        "sender": {"id": "112233"},
                        "message": {"text": "Qalay ishlar?"}
                    }
                ]
            }
        ]
    }

    from src.services.core.instagram_agent import process_instagram_webhook
    await process_instagram_webhook(payload, mock_db)

    # Verify database logging calls
    mock_db.log_message.assert_any_call("ig_112233", "Qalay ishlar?", is_ai=False)
    mock_db.log_message.assert_any_call("ig_112233", "Salom, xabarni qabul qildim", is_ai=True)

    # Verify info upsert
    mock_db.upsert_user.assert_called_once_with("ig_112233", "Foydalanuvchi", phone="+998991234567")

    # Verify Instagram API send call
    mock_send_reply.assert_called_once_with("112233", "Salom, xabarni qabul qildim", "")

    # Verify CRM notify call
    mock_notify.assert_called_once_with("Instagram DM", "Foydalanuvchi", "112233", "Qalay ishlar?", "[SAVE_INFO: phone=+998991234567] Salom, xabarni qabul qildim")
