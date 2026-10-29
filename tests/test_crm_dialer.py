"""Unit and integration tests for Jon CRM (9-Pipeline Kanban, Drag-and-Drop, Full Deal Card, BANT/SPIN, Files & AI Analysis)."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes.crm_dialer import router
from src.services.core.crm.dialer_service import DialerService
from src.services.core.crm.dialer_store import DialerStore


@pytest.fixture
def temp_store(tmp_path):
    db_file = tmp_path / "test_dialer.db"
    return DialerStore(db_path=str(db_file))


def test_dialer_store_lifecycle(temp_store):
    # 1. Upsert with BANT/SPIN custom fields, tags, and company
    temp_store.upsert_lead({
        "id": 9001,
        "pipeline_id": 11162698,
        "name": "Alisher Navoiy",
        "contact_name": "Alisher",
        "company_name": "Navoiy Brend",
        "phone": "+998901234567",
        "price": 15000000.0,
        "status_id": 89067962,
        "status_slug": "yangi",
        "responsible_user_id": 13021974,
        "responsible_name": "Shahnoza Abdijabborova",
        "source": "Meta",
        "tags": ["VIP", "Patent"],
        "custom_fields": {
            "brand_name": "Navoiy Brend",
            "pain_point": "Logotip va nomni patentlash kerak",
            "service_type": ["Brendbuk", "Patentlash"],
        },
        "is_active": True,
    })

    # 2. Get Lead & Queue
    lead = temp_store.get_lead(9001)
    assert lead is not None
    assert lead["name"] == "Alisher Navoiy"
    assert lead["company_name"] == "Navoiy Brend"
    assert lead["phone"] == "+998901234567"
    assert lead["status_slug"] == "yangi"
    assert "VIP" in lead["tags"]
    assert lead["custom_fields"]["brand_name"] == "Navoiy Brend"

    queue = temp_store.get_queue(pipeline_id=11162698)
    assert len(queue) == 1
    assert queue[0]["id"] == 9001

    # 3. Record Call Action
    temp_store.record_call_action(
        lead_id=9001,
        new_status_slug="kotarmadi",
        new_status_id=87609518,
        seller_name="Shahnoza",
        note="Qo'ng'iroq qildim, ko'tarmadi",
    )

    updated = temp_store.get_lead(9001)
    assert updated["status_slug"] == "kotarmadi"
    assert updated["calls_count"] == 1
    assert any("ko'tarmadi" in n.get("text", "") for n in updated["notes"])

    # 4. Attach File & Note
    assert temp_store.add_lead_file(
        lead_id=9001,
        name="Tijoriy Taklif PDF",
        url="https://drive.google.com/kp123",
        file_type="kp",
        uploaded_by="Shahnoza",
    )
    detail = temp_store.get_lead_detail(9001)
    assert len(detail["files"]) == 1
    assert detail["files"][0]["name"] == "Tijoriy Taklif PDF"

    # 5. Stats
    stats = temp_store.get_stats()
    assert stats["total_active_leads"] == 1
    assert stats["calls_today"] == 1
    assert stats["by_status"].get("kotarmadi") == 1
    assert stats["by_pipeline"].get(11162698) == 1

    # 6. Attach Call Recording
    lead_id = temp_store.attach_call_recording(
        phone="+998901234567",
        audio_url="https://moizvonki.ru/rec/call123.mp3",
        duration=75,
        manager="Shahnoza",
    )
    assert lead_id == 9001
    updated_lead = temp_store.get_lead(9001)
    assert updated_lead["last_audio_url"] == "https://moizvonki.ru/rec/call123.mp3"
    assert updated_lead["last_audio_duration"] == 75


@pytest.mark.asyncio
async def test_dialer_service_multi_pipeline_and_ai(temp_store):
    service = DialerService(store=temp_store)

    # Catalog has all 9 pipelines & 20+ custom fields
    catalog = service.get_catalog()
    assert len(catalog["pipelines"]) == 9
    assert len(catalog["custom_fields_schema"]) >= 20

    # Insert leads into Sotuv (11162698) and Farmer (10123318)
    temp_store.upsert_lead({
        "id": 101,
        "pipeline_id": 11162698,
        "name": "Mijoz Sotuv",
        "phone": "+998901111111",
        "price": 25000000,
        "status_slug": "yangi",
        "status_id": 89067962,
        "custom_fields": {"pain_point": "Bozorda tanilish"},
    })
    temp_store.upsert_lead({
        "id": 102,
        "pipeline_id": 10123318,
        "name": "Mijoz Farmer",
        "phone": "+998902222222",
        "price": 40000000,
        "status_slug": "ish_jarayonida",
        "status_id": 80215338,
    })

    # Submit action on lead 101 (Drag-and-drop to uchrashuv)
    result = await service.submit_action(
        lead_id=101,
        action_slug="uchrashuv",
        seller_name="Shahnoza",
        note="Uchrashuv belgilandi",
        pipeline_id=11162698,
    )
    assert result["success"] is True
    assert result["new_status"] == "uchrashuv"
    assert result["new_status_id"] == 87609526

    # Check Farmer pipeline Kanban
    farmer_board = service.get_kanban_board(pipeline_id=10123318)
    assert farmer_board["pipeline_id"] == 10123318
    assert farmer_board["total_leads"] == 1
    assert farmer_board["total_sum"] == 40000000

    # AI analysis generation
    ai_res = service.generate_ai_deal_analysis(101)
    assert ai_res["bant_score"] >= 75
    assert "recommendations" in ai_res
    assert len(ai_res["recommendations"]) == 3


def test_dialer_api_routes(temp_store, monkeypatch):
    import src.api.routes.crm_dialer as crm_routes
    from src.services.core.crm.uzbek_crm_hub import UzbekCrmHub

    monkeypatch.setattr(crm_routes, "dialer_service", DialerService(store=temp_store))
    monkeypatch.setattr(crm_routes, "crm_hub", UzbekCrmHub(store=temp_store))

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    # 1. Catalog endpoint
    res_cat = client.get("/api/crm/dialer/catalog")
    assert res_cat.status_code == 200
    assert len(res_cat.json()["pipelines"]) == 9

    # 2. Create/Update lead with BANT/SPIN fields & tags
    res_create = client.post(
        "/api/crm/dialer/lead",
        json={
            "id": 201,
            "pipeline_id": 11162698,
            "name": "Test Client Brend",
            "company_name": "Brend MChJ",
            "phone": "+998933333333",
            "price": 18000000,
            "status_slug": "yangi",
            "tags": ["VIP", "Meta"],
            "custom_fields": {"brand_name": "Brend MChJ", "pain_point": "Rebrending"},
        },
    )
    assert res_create.status_code == 200
    assert res_create.json()["success"] is True

    # 3. Attach file & note
    res_file = client.post(
        "/api/crm/dialer/lead/201/file",
        json={"name": "KP.pdf", "url": "https://jonbranding.uz/kp.pdf", "file_type": "kp"},
    )
    assert res_file.status_code == 200
    assert res_file.json()["success"] is True

    res_note = client.post(
        "/api/crm/dialer/lead/201/note",
        json={"text": "Mijoz KP ni ma'qulladi", "author": "Shahnoza"},
    )
    assert res_note.status_code == 200
    assert res_note.json()["success"] is True

    # 4. AI analysis endpoint
    res_ai = client.post("/api/crm/dialer/lead/201/ai-analyze")
    assert res_ai.status_code == 200
    assert res_ai.json()["success"] is True
    assert "bant_score" in res_ai.json()["analysis"]

    # 5. Kanban endpoint across pipelines
    res_kb = client.get("/api/crm/dialer/kanban?pipeline_id=11162698")
    assert res_kb.status_code == 200
    assert "stages" in res_kb.json()
    assert res_kb.json().get("backend_engine") == "twenty-crm"

    # 6. 7-module Uzbek amoCRM Hub endpoints: Dashboard, Tasks, Directory, Inbox, SaaS
    res_dash = client.get("/api/crm/dialer/dashboard?pipeline_id=11162698")
    assert res_dash.status_code == 200
    assert "kpis" in res_dash.json()
    assert "funnel" in res_dash.json()

    res_task_create = client.post(
        "/api/crm/dialer/tasks",
        json={"lead_id": 201, "title": "Tijoriy taklif yuborish", "task_type": "Tijoriy taklif (KP)"},
    )
    assert res_task_create.status_code == 200
    task_id = res_task_create.json()["task_id"]

    res_tasks = client.get("/api/crm/dialer/tasks?status=open")
    assert res_tasks.status_code == 200
    assert len(res_tasks.json()["tasks"]) >= 1

    res_task_done = client.post(f"/api/crm/dialer/tasks/{task_id}/complete", json={"result_text": "Yuborildi"})
    assert res_task_done.status_code == 200
    assert res_task_done.json()["success"] is True

    res_dir_contacts = client.get("/api/crm/dialer/directory?entity_type=contacts")
    assert res_dir_contacts.status_code == 200
    assert res_dir_contacts.json()["total"] >= 1

    res_dir_comp = client.get("/api/crm/dialer/directory?entity_type=companies")
    assert res_dir_comp.status_code == 200
    assert res_dir_comp.json()["total"] >= 1

    res_inbox = client.get("/api/crm/dialer/inbox")
    assert res_inbox.status_code == 200
    assert len(res_inbox.json()["threads"]) >= 1

    res_chat_send = client.post(
        "/api/crm/dialer/inbox/send",
        json={"lead_id": 201, "text": "Assalomu alaykum, brifni yubordik", "channel": "Telegram"},
    )
    assert res_chat_send.status_code == 200
    assert res_chat_send.json()["success"] is True

    res_saas = client.get("/api/crm/dialer/saas")
    assert res_saas.status_code == 200
    assert len(res_saas.json()["tenants"]) >= 1

    # 7. Single-request bootstrap endpoint (<15ms startup)
    res_boot = client.get("/api/crm/dialer/bootstrap?pipeline_id=11162698")
    assert res_boot.status_code == 200
    boot_data = res_boot.json()
    assert "catalog" in boot_data and "kanban" in boot_data and "queue" in boot_data


def test_twenty_client_payload_roundtrip():
    from src.services.core.crm.twenty_client import TwentyClient

    lead = {
        "id": 53875559,
        "pipeline_id": 11162698,
        "name": "Saidjamol Textil",
        "contact_name": "Saidjamol",
        "company_name": "Saidjamol Textil MChJ",
        "phone": "+998909313735",
        "price": 35000000.0,
        "status_id": 89067962,
        "status_slug": "yangi",
        "responsible_user_id": 13021974,
        "responsible_name": "Shahnoza Abdijabborova",
        "tags": ["PCG_TOSHKENT7_PERSONAL", "VIP"],
        "custom_fields": {"brand_name": "Saidjamol Textil", "pain_point": "Eksport brendingi"},
        "files": [{"name": "KP.pdf", "url": "https://jonbranding.uz/kp.pdf", "type": "kp"}],
        "ai_analysis": {"bant_score": 85, "summary": "Issiq mijoz"},
        "last_audio_url": "https://moizvonki.ru/rec1.mp3",
        "last_audio_duration": 120,
        "calls_count": 2,
    }
    payload = TwentyClient.build_opportunity_payload(lead, twenty_stage="NEW")
    assert payload["amoId"] == 53875559
    assert payload["pipelineId"] == 11162698
    assert payload["statusSlug"] == "yangi"
    assert payload["amount"]["amountMicros"] == 35000000000000

    restored = TwentyClient.opportunity_to_lead_dict({"id": "uuid-123", **payload})
    assert restored["id"] == 53875559
    assert restored["twenty_id"] == "uuid-123"
    assert restored["company_name"] == "Saidjamol Textil MChJ"
    assert restored["price"] == 35000000.0
    assert "PCG_TOSHKENT7_PERSONAL" in restored["tags"]
    assert restored["custom_fields"]["pain_point"] == "Eksport brendingi"
    assert len(restored["files"]) == 1
    assert restored["ai_analysis"]["bant_score"] == 85


def test_amocrm_webhook_lead_event_sync(temp_store, monkeypatch):
    from src.services.core.crm.amocrm_dialer_syncer import apply_amocrm_webhook_lead_event
    import src.services.core.crm.amocrm_dialer_syncer as syncer_mod

    # Patch DialerStore to use temp_store
    monkeypatch.setattr(syncer_mod, "DialerStore", lambda *args, **kwargs: temp_store)

    # Initial lead
    temp_store.upsert_lead({
        "id": 778899,
        "name": "Sinxron Test Lead",
        "pipeline_id": 11162698,
        "status_slug": "yangi",
        "status_id": 89067962,
    })

    # Webhook payload from amoCRM when lead moves to 'uchrashuv' (87609526)
    webhook_data = {
        "leads[status][0][id]": "778899",
        "leads[status][0][status_id]": "87609526",
        "leads[status][0][pipeline_id]": "11162698",
    }
    apply_amocrm_webhook_lead_event(webhook_data)

    lead = temp_store.get_lead(778899)
    assert lead is not None
    assert lead["status_id"] == 87609526
    assert lead["status_slug"] == "uchrashuv"
    assert lead["name"] == "Sinxron Test Lead"


def test_omnichannel_chat_inbox_and_drawer(temp_store, monkeypatch):
    import src.api.routes.crm_dialer as route_mod
    monkeypatch.setattr(route_mod.dialer_service, "store", temp_store)

    temp_store.upsert_lead({
        "id": 888111,
        "name": "Javohir Telegram Mijoz",
        "contact_name": "Javohir",
        "phone": "+998909998877",
        "pipeline_id": 11162698,
        "status_slug": "yangi",
        "custom_fields": {"telegram_username": "javohir_tg"},
    })

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    # 1. Send via Telegram
    res_tg = client.post("/api/crm/dialer/inbox/send", json={
        "lead_id": 888111,
        "text": "Assalomu alaykum Javohir aka! Jon Branding dan Shahnozaman.",
        "channel": "Telegram",
        "sender_name": "Shahnoza Abdijabborova"
    })
    assert res_tg.status_code == 200
    data_tg = res_tg.json()
    assert data_tg["success"] is True

    # 2. Send Internal Note
    res_note = client.post("/api/crm/dialer/inbox/send", json={
        "lead_id": 888111,
        "text": "Mijoz ertaga soat 15:00 da qo'ng'iroq qilishni so'radi.",
        "channel": "note",
        "sender_name": "Shahnoza Abdijabborova"
    })
    assert res_note.status_code == 200

    # 3. Verify lead timeline has both entries
    lead = temp_store.get_lead(888111)
    notes = lead.get("notes") or []
    assert len(notes) >= 2
    assert any("[Telegram]" in n["text"] for n in notes)
    assert any("[Izoh]" in n["text"] for n in notes)



