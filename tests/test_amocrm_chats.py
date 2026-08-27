import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from src.api_server import app
from src.api.routes.amocrm_chats import _verify_amojo_signature

client = TestClient(app)


def test_verify_amojo_signature():
    secret = "test_secret_123"
    body = b'{"test": "payload"}'
    # Valid signature check logic
    verified = _verify_amojo_signature(
        body_bytes=body,
        signature_header=None,
        date_header=None,
        content_md5_header=None,
        channel_secret="",  # No secret configured -> returns True
    )
    assert verified is True


@pytest.mark.asyncio
async def test_handle_amocrm_chat_outbound_dispatch():
    payload = {
        "account_id": "32681154",
        "time": 1787567000,
        "message": {
            "type": "text",
            "text": "Salom, loyiha bo'yicha taklif tayyor!",
            "msg_id": "msg-12345",
            "sender": {
                "id": "13021974",
                "name": "Baxtiyorjon Gaziyev"
            },
            "conversation": {
                "id": "150074828",
                "client_id": "150074828"
            }
        }
    }

    mock_bot = AsyncMock()
    with patch("src.api.routes.amocrm_chats.app_ctx") as mock_ctx:
        mock_ctx.bot_runtime = mock_bot
        response = client.post("/webhook/amocrm/chats", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "ok"
        assert data.get("msg_id") == "msg-12345"
        mock_bot.send_message.assert_called_once_with(
            chat_id=150074828,
            text="Salom, loyiha bo'yicha taklif tayyor!",
            parse_mode="HTML"
        )
