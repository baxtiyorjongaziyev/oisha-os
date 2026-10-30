"""Synthetic authorization, provenance and review rejection regressions."""
import time

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.rbac import Principal, Role
from src.services.sales_quality import kpi_routes as routes
from src.services.sales_quality.reviews import QualityReviews


def test_simulation_uses_current_approved_reviews_and_never_writes_payment(tmp_path, monkeypatch):
    store = QualityReviews(tmp_path / "synthetic.sqlite3")
    evaluation = {"review_ready": True, "score": 100, "sales_quality": True, "call_type": "discovery"}
    for index in range(21):
        call = str(index)
        revision = store.save(call, index, "7", evaluation)
        store.review(call, revision, "rop", "approved", "synthetic", 80)
    # Latest decision invalidates approval and removes this call from the sample.
    store.review("20", store.get("20")["revision"], "rop", "rejected", "synthetic")
    other = store.save("other", 99, "8", evaluation)
    store.review("other", other, "rop", "approved", "synthetic", 0)
    monkeypatch.setattr(routes, "QualityReviews", lambda: store)
    app = FastAPI()
    app.include_router(routes.router)
    principal = Principal("owner", Role.OWNER, "test")
    app.dependency_overrides[routes.ACCESS.dependency] = lambda: principal
    body = {"manager_id": "7", "review_window_start": 0, "review_window_end": int(time.time()) + 10,
            "actual": 80, "target": 100, "completed_on_time": 9, "tasks_due": 10,
            "bonus_pool": 1000000, "currency": "UZS"}
    with TestClient(app) as client:
        result = client.post("/api/sales-quality/kpi-simulation", json=body)
        assert result.status_code == 200
        data = result.json()
        assert data["total_score"] == 82.5
        assert data["quality"]["reviewed_calls"] == 20
        assert data["projected_bonus"] == "825000.00"
        assert data["input_provenance"] == "owner_supplied_simulation_values_not_ledger_verified"
        assert not data["payroll_enabled"] and not data["payment_created"]
        assert client.post("/api/sales-quality/kpi-simulation", json={**body, "quality": {"score": 100}}).status_code == 422
        assert client.post("/api/sales-quality/kpi-simulation", json={**body, "review_window_end": 0}).status_code == 422
        principal = Principal("7", Role.SELLER, "test")
        assert client.post("/api/sales-quality/kpi-simulation", json=body).status_code == 403
    assert len(store.get("0")["reviews"]) == 1


def test_scoped_window_is_not_limited_by_unrelated_latest_evaluations(tmp_path):
    store = QualityReviews(tmp_path / "synthetic.sqlite3")
    evaluation = {"review_ready": True, "score": 80, "sales_quality": True}
    revision = store.save("mine", 1, "7", evaluation)
    store.review("mine", revision, "rop", "approved", "synthetic")
    for index in range(501):
        store.save(f"other-{index}", index, "8", evaluation)
    assert [r["call_id"] for r in store.manager_window("7", 0, int(time.time()) + 10)] == ["mine"]
    assert store.manager_window("7", 0, 1) == []
    # A new snapshot must be reviewed again.
    store.save("mine", 1, "7", {**evaluation, "score": 90})
    assert store.manager_window("7", 0, int(time.time()) + 10) == []


def test_real_rbac_denies_seller_before_store_access(monkeypatch):
    from src.api import security
    app = FastAPI()
    app.include_router(routes.router)
    monkeypatch.setattr(security, "authorize_connection", lambda _: Principal("7", Role.SELLER, "test"))
    with TestClient(app) as client:
        assert client.get("/api/sales-quality/kpi-policy").status_code == 403
