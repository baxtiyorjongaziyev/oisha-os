"""Tests for amoCRM Enterprise capabilities (Digital Pipeline, Targets, Loss Analytics, RBAC)."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.services.core.crm.digital_pipeline import DigitalPipelineEngine
from src.services.core.crm.sales_targets import SalesTargetsEngine
from src.services.core.crm.loss_analytics import LossAnalyticsEngine
from src.services.core.crm.crm_rbac import CrmRbacGuard
from src.services.core.crm.dialer_store import DialerStore
from src.api.routes.crm_enterprise_routes import router as enterprise_router


@pytest.fixture
def temp_db(tmp_path):
    return str(tmp_path / "test_enterprise_crm.db")


def test_digital_pipeline_automation(temp_db):
    # Initialize store and lead
    store = DialerStore(db_path=temp_db)
    lead_id = store.create_or_update_lead({
        "id": 9901,
        "pipeline_id": 11162698,
        "name": "Bekzod Savdo MChJ",
        "contact_name": "Bekzod",
        "phone": "+998901112233",
        "price": 25000000.0,
        "status_slug": "yangi",
    })

    dp = DigitalPipelineEngine(db_path=temp_db)
    rules = dp.get_pipeline_rules(11162698)
    assert len(rules) >= 4

    # Add custom rule
    rule_id = dp.add_rule(
        pipeline_id=11162698,
        stage_slug="kp",
        name="Test KP Auto Task",
        trigger_type="stage_enter",
        action_type="create_task",
        action_payload={"title": "Avtomat: KP tekshiruvi", "delay_days": 2},
    )
    assert rule_id > 0

    # Toggle rule
    assert dp.toggle_rule(rule_id, False) is True
    assert dp.toggle_rule(rule_id, True) is True


@pytest.mark.asyncio
async def test_digital_pipeline_trigger_execution(temp_db):
    store = DialerStore(db_path=temp_db)
    store.create_or_update_lead({
        "id": 9902,
        "pipeline_id": 11162698,
        "name": "Alisher Korporativ",
        "contact_name": "Alisher",
        "phone": "+998905554433",
        "price": 30000000.0,
        "status_slug": "yangi",
    })

    dp = DigitalPipelineEngine(db_path=temp_db)
    executed = await dp.execute_stage_enter_triggers(
        lead_id=9902,
        pipeline_id=11162698,
        new_stage_slug="kp",
        seller_name="Shahnoza Abdijabborova",
    )
    assert len(executed) >= 1
    assert any("create_task" in str(x) for x in executed)

    # Verify task was created in crm_tasks table
    with dp._get_conn() as conn:
        task_row = conn.execute("SELECT * FROM crm_tasks WHERE lead_id = 9902").fetchone()
        assert task_row is not None
        assert "KP" in task_row["title"]


def test_sales_targets_pacing_and_forecast(temp_db):
    store = DialerStore(db_path=temp_db)
    # Add won leads and active leads
    store.create_or_update_lead({
        "id": 9903,
        "pipeline_id": 11162698,
        "name": "Won Deal 1",
        "price": 40000000.0,
        "status_slug": "sotuv",
        "responsible_name": "Shahnoza Abdijabborova",
        "is_active": False,
    })
    store.create_or_update_lead({
        "id": 9904,
        "pipeline_id": 11162698,
        "name": "Active Deal 1 (KP)",
        "price": 50000000.0,
        "status_slug": "kp",
        "responsible_name": "Shahnoza Abdijabborova",
        "is_active": True,
    })

    engine = SalesTargetsEngine(db_path=temp_db)
    overview = engine.get_plan_fact_overview()
    assert overview["totals"]["target_revenue"] >= 450000000.0
    assert overview["totals"]["fact_revenue"] >= 40000000.0
    assert overview["totals"]["forecast_revenue"] > overview["totals"]["fact_revenue"]

    # Set new target
    ok = engine.set_seller_target("Shahnoza Abdijabborova", "2026-10", 250000000.0, 20)
    assert ok is True


def test_loss_reasons_and_velocity(temp_db):
    store = DialerStore(db_path=temp_db)
    store.create_or_update_lead({
        "id": 9905,
        "pipeline_id": 11162698,
        "name": "Lost Deal 1",
        "price": 12000000.0,
        "status_slug": "yangi",
    })

    loss_eng = LossAnalyticsEngine(db_path=temp_db)
    ok = loss_eng.record_loss(
        lead_id=9905,
        reason="Qimmat / Byudjet yetmadi",
        note="Mijoz byudjetini tasdiqlamadi",
        lost_amount=12000000.0,
        seller_name="Shahnoza",
    )
    assert ok is True

    rep = loss_eng.get_loss_reasons_report()
    assert rep["total_lost_deals"] >= 1
    assert any(r["reason"] == "Qimmat / Byudjet yetmadi" for r in rep["reasons"])

    vel_rep = loss_eng.get_cycle_time_velocity_report()
    assert "avg_cycle_days_total" in vel_rep
    assert len(vel_rep["stages_velocity"]) == 7


def test_crm_rbac_guard():
    guard = CrmRbacGuard()
    # Admin
    assert guard.can_perform("admin", "delete_leads") is True
    assert guard.can_perform("admin", "manage_automations") is True

    # Seller
    assert guard.can_perform("seller", "delete_leads") is False
    assert guard.can_perform("seller", "export_data") is False

    # Lead editing permission
    assert guard.can_edit_lead("seller", "Shahnoza Abdijabborova", "Shahnoza Abdijabborova") is True
    assert guard.can_edit_lead("seller", "Shahnoza Abdijabborova", "Rayxona") is False
    assert guard.can_edit_lead("admin", "Baxtiyorjon Gaziyev", "Rayxona") is True

    # Action validation
    res_del = guard.validate_action("Shahnoza Abdijabborova", "delete_leads")
    assert res_del["allowed"] is False
    assert "faqat Administrator" in res_del["reason"]


def test_enterprise_api_routes(temp_db, monkeypatch):
    import src.api.routes.crm_enterprise_routes as routes_mod

    routes_mod.dp_engine = DigitalPipelineEngine(db_path=temp_db)
    routes_mod.target_engine = SalesTargetsEngine(db_path=temp_db)
    routes_mod.loss_engine = LossAnalyticsEngine(db_path=temp_db)

    app = FastAPI()
    app.include_router(enterprise_router)
    client = TestClient(app)

    # 1. Digital pipeline rules
    r_rules = client.get("/api/crm/dialer/digital-pipeline/rules")
    assert r_rules.status_code == 200
    assert len(r_rules.json()["rules"]) >= 4

    # 2. Targets overview
    r_targets = client.get("/api/crm/dialer/targets/overview")
    assert r_targets.status_code == 200
    assert "totals" in r_targets.json()

    # 3. Loss analytics
    r_loss = client.get("/api/crm/dialer/loss-analytics")
    assert r_loss.status_code == 200
    assert "loss_reasons" in r_loss.json()
    assert "cycle_time_velocity" in r_loss.json()

    # 4. RBAC users
    r_rbac = client.get("/api/crm/dialer/rbac/users")
    assert r_rbac.status_code == 200
    assert len(r_rbac.json()["users"]) >= 4
