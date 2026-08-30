import hashlib
import hmac
import json
import os
import stat
from email.utils import formatdate

import pytest
from pydantic import SecretStr
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from src.api_server import app
from src.api.routes.amocrm_chats import _verify_amojo_signature
from src.services.core.crm.amocrm.auth import AmoCRMAuthMixin

client = TestClient(app)


def _signed_headers(payload, secret="test_secret_123"):
    body = json.dumps(payload, separators=(",", ":")).encode()
    content_md5 = hashlib.md5(body, usedforsecurity=False).hexdigest().lower()
    date = formatdate(usegmt=True)
    signature_input = (
        f"POST\n{content_md5}\napplication/json\n{date}\n/webhook/amocrm/chats"
    )
    signature = hmac.new(
        secret.encode(), signature_input.encode(), hashlib.sha1
    ).hexdigest()
    return body, {
        "Content-Type": "application/json",
        "Content-MD5": content_md5,
        "Date": date,
        "X-Signature": signature,
    }


def test_verify_amojo_signature():
    secret = "test_secret_123"
    body = b'{"test": "payload"}'
    verified = _verify_amojo_signature(
        body_bytes=body,
        signature_header=None,
        date_header=None,
        content_md5_header=None,
        channel_secret="",
    )
    assert verified is False


def test_amocrm_chat_fails_closed_without_secret(monkeypatch):
    monkeypatch.setattr(
        "src.api.routes.amocrm_chats.settings.AMOCRM_CHAT_CHANNEL_SECRET",
        None,
    )
    response = client.post("/webhook/amocrm/chats", json={"message": {}})
    assert response.status_code == 503


def test_amocrm_chat_rejects_invalid_signature(monkeypatch):
    monkeypatch.setattr(
        "src.api.routes.amocrm_chats.settings.AMOCRM_CHAT_CHANNEL_SECRET",
        SecretStr("test_secret_123"),
    )
    response = client.post(
        "/webhook/amocrm/chats",
        content=b'{"message":{}}',
        headers={
            "Content-Type": "application/json",
            "Content-MD5": "0" * 32,
            "Date": formatdate(usegmt=True),
            "X-Signature": "0" * 40,
        },
    )
    assert response.status_code == 401


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

    body, headers = _signed_headers(payload)
    mock_bot = AsyncMock()
    with patch("src.api.routes.amocrm_chats.app_ctx") as mock_ctx:
        mock_ctx.bot_runtime = mock_bot
        with patch(
            "src.api.routes.amocrm_chats.settings.AMOCRM_CHAT_CHANNEL_SECRET",
            SecretStr("test_secret_123"),
        ):
            response = client.post(
                "/webhook/amocrm/chats", content=body, headers=headers
            )
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "ok"
        assert data.get("msg_id") == "msg-12345"
        mock_bot.send_message.assert_called_once_with(
            chat_id=150074828,
            text="Salom, loyiha bo'yicha taklif tayyor!",
            parse_mode=None,
        )


def test_legacy_unsigned_amocrm_chat_route_is_retired():
    response = client.post("/webhook/amocrm_chat", json={"message": {}})
    assert response.status_code == 410


def test_amocrm_token_save_is_atomic_and_owner_only(tmp_path):
    token_path = tmp_path / "amocrm_token.json"

    class Client(AmoCRMAuthMixin):
        token_file = str(token_path)
        token_data = {}
        access_token = None
        auth_blocked_until = 1.0
        auth_block_reason = "old"
        last_error = None

    token_data = {
        "access_token": "access-value",
        "refresh_token": "refresh-value",
        "expires_in": 86400,
    }
    client_instance = Client()
    client_instance._save_token(token_data)

    assert json.loads(token_path.read_text(encoding="utf-8")) == token_data
    if os.name != "nt":
        assert stat.S_IMODE(token_path.stat().st_mode) & 0o077 == 0
    assert not list(tmp_path.glob(".amocrm-token-*"))
