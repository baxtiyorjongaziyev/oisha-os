"""Unit tests for Unified Telephony and SMS Gateway."""
import pytest

from src.services.telephony.unified_gateway import (
    UnifiedTelephonyGateway,
    UtelWebhookAdapter,
    OnlinePBXWebhookAdapter,
    NativeVoiceGateway,
    NativeSmsGateway,
    CanonicalCallEvent,
    CanonicalSmsMessage,
)


def test_utel_webhook_parsing():
    adapter = UtelWebhookAdapter()
    payload = {
        "event": "call_end",
        "call_id": "utel_123456",
        "caller": "+998901234567",
        "callee": "+998712001122",
        "duration": 45,
        "record_url": "https://records.utel.uz/rec_123.mp3",
        "ext": "101",
    }
    event: CanonicalCallEvent = adapter.parse_webhook(payload)
    assert event.call_id == "utel_123456"
    assert event.provider == "utel"
    assert event.event_type == "ended"
    assert event.caller_phone == "+998901234567"
    assert event.duration_seconds == 45
    assert event.record_url == "https://records.utel.uz/rec_123.mp3"
    assert event.manager_id == "101"


def test_onlinepbx_webhook_parsing():
    adapter = OnlinePBXWebhookAdapter()
    payload = {
        "uuid": "opbx_abc_789",
        "status": "completed",
        "caller_id": "+998977654321",
        "destination": "+998781501122",
        "duration": 120,
        "download_url": "https://onlinepbx.uz/audio/abc.wav",
        "user": "operator_5",
    }
    event: CanonicalCallEvent = adapter.parse_webhook(payload)
    assert event.call_id == "opbx_abc_789"
    assert event.provider == "onlinepbx"
    assert event.event_type == "ended"
    assert event.duration_seconds == 120
    assert event.record_url == "https://onlinepbx.uz/audio/abc.wav"
    assert event.manager_id == "operator_5"


def test_native_voice_webrtc_session():
    voice_gw = NativeVoiceGateway(sip_server_host="109.199.100.137")
    session = voice_gw.create_webrtc_dialer_session(
        manager_id="mgr_aziz",
        manager_extension="201",
    )
    assert session["manager_id"] == "mgr_aziz"
    assert session["extension"] == "201"
    assert "wss://109.199.100.137:8089/ws" in session["websocket_url"]
    assert "webrtc_tok_" in session["session_token"]
    assert session["codec"] == "opus,pcmu"


@pytest.mark.asyncio
async def test_native_sms_with_failover():
    native_sms = NativeSmsGateway()
    
    # 1. Native GSM modem online -> 0 so'm xarajat
    native_sms.gsm_modem_online = True
    msg_gsm: CanonicalSmsMessage = await native_sms.send_sms_with_failover(
        phone="+998901234567",
        message="Hurmatli mijoz, sizning arizangiz qabul qilindi.",
    )
    assert msg_gsm.provider == "oisha_gsm"
    assert msg_gsm.status == "delivered"
    assert msg_gsm.cost_uzs == 0.0

    # 2. Native GSM modem offline -> Eskiz fallback (~120 so'm)
    native_sms.gsm_modem_online = False
    msg_eskiz: CanonicalSmsMessage = await native_sms.send_sms_with_failover(
        phone="+998901234567",
        message="Hurmatli mijoz, sizning arizangiz qabul qilindi.",
    )
    assert msg_eskiz.provider == "eskiz"
    assert msg_eskiz.status == "sent"
    assert msg_eskiz.cost_uzs == 120.0


@pytest.mark.asyncio
async def test_unified_gateway_routing():
    gateway = UnifiedTelephonyGateway()

    # Route Utel webhook
    utel_call = gateway.process_incoming_call_webhook(
        provider="utel",
        payload={"event": "call_start", "caller": "+998991112233", "call_id": "u1"},
    )
    assert utel_call.provider == "utel"
    assert utel_call.event_type == "ringing"

    # Route Native SIP event
    native_call = gateway.process_incoming_call_webhook(
        provider="oisha_native",
        payload={
            "uniqueid": "sip_999",
            "event": "answered",
            "caller_num": "+998909998877",
            "connected_line_num": "201",
            "billable_seconds": 35,
        },
    )
    assert native_call.provider == "oisha_native"
    assert native_call.event_type == "answered"
    assert native_call.duration_seconds == 35

    # Dispatch SMS
    sms_res = await gateway.dispatch_customer_sms("+998901112233", "Test SMS")
    assert sms_res.provider in ["oisha_gsm", "eskiz"]
