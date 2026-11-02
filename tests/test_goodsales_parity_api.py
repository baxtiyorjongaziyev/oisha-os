"""Unit tests for GoodSales Parity FastAPI Routes."""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes.goodsales_parity import router as goodsales_parity_router


def _get_client() -> TestClient:
    test_app = FastAPI()
    test_app.include_router(goodsales_parity_router)
    return TestClient(test_app)


def test_get_next_steps_payload():
    client = _get_client()
    resp = client.get("/api/next-steps")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    payload = data["data"]
    assert payload["plan"]["percent"] == 96
    assert payload["funnel"]["sales"] > 0
    assert len(payload["actions"]) >= 5
    assert len(payload["managers"]) >= 4
    assert "sales_process" in payload["lost"]
    assert len(payload["sources"]) >= 3


def test_send_daily_briefs():
    client = _get_client()
    resp = client.post("/api/next-steps/brief/send", json={"managerIds": ["mgr_51"]})
    assert resp.status_code == 200
    res = resp.json()["data"]
    assert res["sent"] == 1
    assert res["total"] == 1


def test_get_1on1_dossier_and_print():
    client = _get_client()
    resp = client.get("/api/next-steps/1on1/mgr_51")
    assert resp.status_code == 200
    dossier = resp.json()["data"]
    assert dossier["managerName"] == "Kamola Karimova"
    assert len(dossier["wins"]) >= 1

    print_resp = client.get("/api/next-steps/1on1/mgr_51/print")
    assert print_resp.status_code == 200
    assert "Kamola Karimova" in print_resp.text
    assert "window.print()" in print_resp.text


def test_voice_exam_lifecycle():
    client = _get_client()
    sc_resp = client.get("/api/voice-exam/scenarios")
    assert sc_resp.status_code == 200
    scenarios = sc_resp.json()["scenarios"]
    assert len(scenarios) >= 1

    start_resp = client.post("/api/voice-exam/start", json={"manager_id": "mgr_51", "scenario_id": "pre_sale_1"})
    assert start_resp.status_code == 200
    session_id = start_resp.json()["session_id"]

    turn_resp = client.post("/api/voice-exam/turn", json={"session_id": session_id, "manager_text": "Assalomu alaykum! Savol bersam maylimi?"})
    assert turn_resp.status_code == 200
    assert "client_response" in turn_resp.json()["data"]

    fin_resp = client.post("/api/voice-exam/finalize", json={"session_id": session_id})
    assert fin_resp.status_code == 200
    fin_data = fin_resp.json()["data"]
    assert "overall_score" in fin_data


def test_compensation_davomat_matrix():
    client = _get_client()
    resp = client.get("/api/compensation-davomat")
    assert resp.status_code == 200
    matrix = resp.json()["data"]
    assert len(matrix) >= 4
    kamola = next(m for m in matrix if m["managerId"] == "mgr_51")
    assert kamola["netSalary"] > 4_000_000
