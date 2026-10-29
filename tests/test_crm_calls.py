"""Tests for Jon CRM MoiZvonki 1-Click Callback and Deal Audio History + Whisper STT & Call Intel."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.services.core.crm.callback_service import CrmCallService, normalize_uz_phone
from src.services.core.crm.call_intel_service import CallIntelService
from src.services.core.crm.dialer_store import DialerStore
from src.services.core.crm.seller_auth import SellerAuthService
from src.api.routes.crm_call_routes import router as crm_call_router


@pytest.fixture
def temp_crm_db(tmp_path):
    db_file = str(tmp_path / "test_calls_dialer.db")
    store = DialerStore(db_path=db_file)
    store.create_or_update_lead({
        "name": "Test Klient Callback",
        "phone": "+998901234567",
        "price": 15000000,
        "status_slug": "aloqa",
        "responsible_name": "Shahnoza Abdijabborova",
        "last_audio_url": "https://storage.jonbranding.uz/calls/rec_test123.mp3",
        "last_audio_duration": 145,
    })
    return db_file


def test_normalize_uz_phone():
    assert normalize_uz_phone("90 123 45 67") == "+998901234567"
    assert normalize_uz_phone("+998 77 322 00 42") == "+998773220042"
    assert normalize_uz_phone("89012345678") == "+79012345678"
    assert normalize_uz_phone("") == ""


def test_callback_service_flow(temp_crm_db):
    service = CrmCallService(db_path=temp_crm_db)
    lead = service.store.find_lead_by_phone("+998901234567")
    assert lead is not None
    lead_id = lead["id"]

    # 1. 1-Click Callback chaqirish
    res = service.initiate_callback(
        lead_id=lead_id,
        seller_slug="shahnoza",
        client_phone="+998901234567",
    )
    assert res["success"] is True
    assert res["client_phone"] == "+998901234567"
    assert res["seller_phone"] == "+998773220042"
    assert "tel:+998901234567" in res["tel_url"]

    # 2. Qo'ng'iroqlar tarixi va audio pleyer ro'yxati
    calls = service.get_lead_call_history(lead_id)
    assert len(calls) >= 1
    assert calls[0]["audio_url"] == "https://storage.jonbranding.uz/calls/rec_test123.mp3"
    assert calls[0]["duration"] == 145
    assert calls[0]["duration_formatted"] == "2m 25s"


@pytest.mark.asyncio
async def test_call_intel_service_flow(temp_crm_db):
    intel_service = CallIntelService(db_path=temp_crm_db)
    store = DialerStore(db_path=temp_crm_db)
    lead = store.find_lead_by_phone("+998901234567")
    assert lead is not None
    lead_id = lead["id"]

    sample_transcript = (
        "[00:02] Menejer: Assalomu alaykum, Jon Branding agentligi!\n"
        "[00:08] Mijoz: Vaalaykum assalom, yangi qandolat brendimiz uchun nom va patent kerak.\n"
        "[00:15] Menejer: Juda yaxshi, byudjetingiz 15 mln atrofidami?\n"
        "[00:20] Mijoz: Ha, sifatli bo'lsa shunday byudjet ajratamiz."
    )

    res = await intel_service.process_lead_call_intelligence(
        lead_id=lead_id,
        transcript_override=sample_transcript,
    )
    assert res["success"] is True
    assert "Menejer:" in res["transcript"]
    assert "bant_score" in res["analysis"]
    assert res["analysis"]["bant_score"] >= 65

    # Bitim xulosasi tekshiruvi
    holistic = await intel_service.run_holistic_deal_analysis(lead_id)
    assert holistic["success"] is True
    assert "analysis" in holistic


def test_crm_call_api_routes(temp_crm_db, monkeypatch):
    from src.api.routes import crm_call_routes

    # Test DB va xizmatlarni bog'lash
    test_auth_service = SellerAuthService(db_path=temp_crm_db)
    test_call_service = CrmCallService(db_path=temp_crm_db)
    test_intel_service = CallIntelService(db_path=temp_crm_db)

    monkeypatch.setattr("src.services.core.crm.seller_auth.seller_auth_service", test_auth_service)
    monkeypatch.setattr(crm_call_routes, "call_service", test_call_service)
    monkeypatch.setattr(crm_call_routes, "call_intel_service", test_intel_service)

    app = FastAPI()
    app.include_router(crm_call_router)
    client = TestClient(app)

    lead = test_call_service.store.find_lead_by_phone("+998901234567")
    lead_id = lead["id"]

    # Sessiya tokenini olish (Shahnoza uchun)
    session = test_auth_service.authenticate_seller("shahnoza", "1302")
    token = session["token"]
    headers = {"X-CRM-Session-Token": token}

    # 1. POST /api/crm/dialer/calls/callback
    resp = client.post(
        "/api/crm/dialer/calls/callback",
        json={"lead_id": lead_id, "client_phone": "+998901234567", "seller_slug": "shahnoza"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["seller_phone"] == "+998773220042"

    # 2. GET /api/crm/dialer/calls/history/{lead_id}
    resp_hist = client.get(f"/api/crm/dialer/calls/history/{lead_id}", headers=headers)
    assert resp_hist.status_code == 200
    hist_data = resp_hist.json()
    assert hist_data["success"] is True
    assert hist_data["total_calls"] >= 1

    # 3. POST /api/crm/dialer/calls/log-manual
    resp_log = client.post(
        "/api/crm/dialer/calls/log-manual",
        json={"lead_id": lead_id, "duration_seconds": 65, "outcome": "answered", "note": "Mijoz bilan gaplashildi"},
        headers=headers,
    )
    assert resp_log.status_code == 200
    assert resp_log.json()["success"] is True

    # 4. POST /api/crm/dialer/calls/transcribe
    resp_tr = client.post(
        "/api/crm/dialer/calls/transcribe",
        json={"lead_id": lead_id, "transcript_override": "[00:05] Menejer: Assalomu alaykum. [00:10] Mijoz: Rahmat."},
        headers=headers,
    )
    assert resp_tr.status_code == 200
    assert resp_tr.json()["success"] is True
    assert "analysis" in resp_tr.json()

    # 5. POST /api/crm/dialer/calls/ai-analyze-lead/{lead_id}
    resp_ai = client.post(
        f"/api/crm/dialer/calls/ai-analyze-lead/{lead_id}",
        headers=headers,
    )
    assert resp_ai.status_code == 200
    assert resp_ai.json()["success"] is True

    # 6. GET /api/crm/dialer/calls/stats/shahnoza
    resp_stats = client.get("/api/crm/dialer/calls/stats/shahnoza", headers=headers)
    assert resp_stats.status_code == 200
