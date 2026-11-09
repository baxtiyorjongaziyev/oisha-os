"""Tests for Native Oisha CRM Engine and Routes."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes.oisha_crm_routes import router
from src.services.core.crm.engine import (
    CrmAiCoach,
    CrmAutomationEngine,
    DealCreate,
    DealUpdate,
    IntakeLeadPayload,
    LeadIntakeService,
    OishaCrmStore,
    TaskCreate,
    TimelineEventCreate,
    normalize_phone_number,
)


@pytest.fixture
def test_store(tmp_path):
    db_file = tmp_path / "test_oisha_crm.db"
    return OishaCrmStore(db_path=str(db_file))


def test_normalize_phone():
    assert normalize_phone_number("998901234567") == "+998901234567"
    assert normalize_phone_number("+998 90 123-45-67") == "+998901234567"
    assert normalize_phone_number("901234567") == "+998901234567"
    assert normalize_phone_number("89012345678") == "+79012345678"


def test_store_pipelines_and_stages(test_store):
    pipelines = test_store.get_pipelines()
    assert len(pipelines) >= 1
    main_pipe = pipelines[0]
    assert main_pipe.name == "Sotuv Boʻlimi"
    assert len(main_pipe.stages) == 8
    stage_names = [s.name for s in main_pipe.stages]
    assert "Saralanmaganlar" in stage_names
    assert "Muvaffaqiyatli yopildi" in stage_names


def test_deal_crud_and_timeline(test_store):
    deal = test_store.create_deal(
        DealCreate(
            name="Smart Brand Loyihasi",
            price=15000000.0,
            phone="+998901234567",
            source="Instagram",
            tags=["brending", "rebranding"],
        )
    )
    assert deal.id > 0
    assert deal.name == "Smart Brand Loyihasi"
    assert deal.price == 15000000.0

    # Get deal
    fetched = test_store.get_deal(deal.id)
    assert fetched is not None
    assert fetched.id == deal.id

    # Update deal
    updated = test_store.update_deal(
        deal.id,
        DealUpdate(price=18000000.0, stage_id=2),
    )
    assert updated.price == 18000000.0
    assert updated.stage_id == 2

    # Timeline check
    timeline = test_store.get_timeline(deal.id)
    assert len(timeline) >= 2
    events = [e.event_type for e in timeline]
    assert "deal_created" in events
    assert "stage_change" in events


def test_tasks_lifecycle(test_store):
    deal = test_store.create_deal(
        DealCreate(name="Vazifa Testi", phone="+998991112233")
    )
    task = test_store.create_task(
        TaskCreate(
            deal_id=deal.id,
            title="Taqdimot yuborish",
            due_at="2026-11-10 12:00",
        )
    )
    assert task.id > 0
    assert not task.is_completed

    success = test_store.complete_task(task.id, "Taqdimot yuborildi va qabul qilindi")
    assert success is True


def test_lead_intake_and_deduplication(test_store):
    automation = CrmAutomationEngine(test_store)
    intake = LeadIntakeService(test_store, automation)

    # First incoming lead
    res1 = intake.process_incoming_lead(
        IntakeLeadPayload(
            name="Alisher Usmonov",
            phone="90 123 45 67",
            comment="Yangi brend logotipi kerak",
            source="Sayt formasi",
        )
    )
    assert res1["status"] == "created"
    assert res1["deal_id"] > 0
    assert res1["task_id"] is not None

    # Duplicate incoming lead with same phone
    res2 = intake.process_incoming_lead(
        IntakeLeadPayload(
            name="Alisher Usmonov",
            phone="+998901234567",
            comment="Qayta yozmoqdaman, narxini bilmoqchi edim",
        )
    )
    assert res2["status"] == "duplicate_merged"
    assert res2["deal_id"] == res1["deal_id"]


def test_ai_coach_surgical_mission(test_store):
    deal = test_store.create_deal(
        DealCreate(
            name="AI Coach Test Deal",
            phone="+998909876543",
            price=25000000.0,
            custom_fields={"pain_point": "Eski dizayn savdoni tushirib yubordi"},
        )
    )
    coach = CrmAiCoach(test_store)
    mission_res = coach.generate_surgical_mission(deal.id)
    assert mission_res["success"] is True
    assert "step_1" in mission_res["mission"]
    assert "step_2" in mission_res["mission"]
    assert "step_3" in mission_res["mission"]

    timeline = test_store.get_timeline(deal.id)
    ai_events = [e for e in timeline if e.event_type == "ai_mission"]
    assert len(ai_events) == 1


def test_oisha_crm_fastapi_endpoints():
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    # 1. Pipelines
    res = client.get("/api/crm/native/pipelines")
    assert res.status_code == 200
    assert "pipelines" in res.json()

    # 2. Create Deal
    create_res = client.post(
        "/api/crm/native/deal",
        json={"name": "FastAPI Route Deal", "price": 5000000.0, "phone": "+998901112233"},
    )
    assert create_res.status_code == 200
    deal_id = create_res.json()["deal"]["id"]

    # 3. Get Deal
    get_res = client.get(f"/api/crm/native/deal/{deal_id}")
    assert get_res.status_code == 200

    # 4. Patch Deal
    patch_res = client.patch(
        f"/api/crm/native/deal/{deal_id}",
        json={"price": 7500000.0, "stage_id": 2},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["deal"]["price"] == 7500000.0

    # 5. Public Intake
    import time
    unique_phone = f"+99893{int(time.time() * 1000) % 10000000:07d}"
    intake_res = client.post(
        "/api/crm/native/intake",
        json={"name": "Web Form Lead", "phone": unique_phone, "comment": "Audit kerak"},
    )
    assert intake_res.status_code == 200
    assert intake_res.json()["status"] == "created"

    # 6. Surgical Mission
    mission_res = client.post(f"/api/crm/native/deal/{deal_id}/surgical-mission")
    assert mission_res.status_code == 200
    assert mission_res.json()["success"] is True
