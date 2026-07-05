import pytest

from src.services.core.sms_gateway_client import (
    SmsGatewayClient,
    SmsGatewayConfig,
    SmsGatewayError,
    parse_sms_webhook,
)


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text="OK"):
        self.status_code = status_code
        self._payload = payload if payload is not None else {"messageId": "sms-1"}
        self.text = text

    def json(self):
        return self._payload


class FakeAsyncClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    async def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


@pytest.mark.asyncio
async def test_sms_gateway_disabled_is_safe_noop():
    client = SmsGatewayClient(config=SmsGatewayConfig(enabled=False))

    result = await client.send_sms("+998901234567", "Salom")

    assert result.ok is False
    assert result.status_code is None
    assert result.raw == {"disabled": True}


@pytest.mark.asyncio
async def test_send_sms_posts_cloud_payload_with_basic_auth():
    fake = FakeAsyncClient(FakeResponse(payload={"messageId": "abc"}))
    config = SmsGatewayConfig(
        enabled=True,
        base_url="https://api.sms-gate.app/3rdparty/v1",
        username="user",
        password="pass",
    )
    client = SmsGatewayClient(config=config, client=fake)

    result = await client.send_sms(["+998901234567"], "Uchrashuv eslatmasi")

    assert result.ok is True
    assert result.message_id == "abc"
    assert fake.calls[0][0] == "https://api.sms-gate.app/3rdparty/v1/message"
    assert fake.calls[0][1]["auth"] == ("user", "pass")
    assert fake.calls[0][1]["json"] == {
        "textMessage": {"text": "Uchrashuv eslatmasi"},
        "phoneNumbers": ["+998901234567"],
    }


@pytest.mark.asyncio
async def test_send_sms_rejects_invalid_phone_before_network():
    fake = FakeAsyncClient(FakeResponse())
    client = SmsGatewayClient(
        config=SmsGatewayConfig(enabled=True, username="user", password="pass"),
        client=fake,
    )

    with pytest.raises(ValueError):
        await client.send_sms("998901234567", "Salom")

    assert fake.calls == []


@pytest.mark.asyncio
async def test_send_sms_raises_for_gateway_error():
    fake = FakeAsyncClient(FakeResponse(status_code=401, payload={"error": "unauthorized"}))
    client = SmsGatewayClient(
        config=SmsGatewayConfig(enabled=True, username="user", password="bad"),
        client=fake,
    )

    with pytest.raises(SmsGatewayError):
        await client.send_sms("+998901234567", "Salom")


def test_parse_sms_webhook_normalizes_incoming_sms():
    normalized = parse_sms_webhook(
        {
            "event": "sms:received",
            "payload": {
                "messageId": "msg-1",
                "message": "Ha, keldim",
                "phoneNumber": "+998901234567",
                "simNumber": 1,
                "receivedAt": "2026-07-05T10:00:00+05:00",
            },
        }
    )

    assert normalized["event"] == "sms:received"
    assert normalized["message_id"] == "msg-1"
    assert normalized["phone_number"] == "+998901234567"
    assert normalized["text"] == "Ha, keldim"
    assert normalized["sim_number"] == 1
