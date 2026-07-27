from src.api.rbac import Principal, Role
from src.api.routes.crm_dashboard import _lead_query
from src.api.routes.sales_quality import _build_sales_quality_payload


def seller(subject: str) -> Principal:
    return Principal(subject=subject, role=Role.SELLER, auth_type="session")


def test_seller_lead_query_applies_assignment_predicate():
    sql, params = _lead_query(seller("42"))
    assert "WHERE assigned_to = ?" in sql
    assert params == ("42",)


def test_owner_lead_query_has_no_assignment_predicate():
    sql, params = _lead_query(
        Principal(subject="1", role=Role.OWNER, auth_type="session")
    )
    assert "WHERE assigned_to = ?" not in sql
    assert params == ()


def test_seller_sales_quality_contains_only_own_calls():
    rows = [
        {
            "call_id": "own",
            "manager_id": "seller-a",
            "manager_name": "A",
            "overall_score": 90,
        },
        {
            "call_id": "other",
            "manager_id": "seller-b",
            "manager_name": "B",
            "overall_score": 80,
        },
    ]
    payload = _build_sales_quality_payload(rows, principal=seller("seller-a"))
    assert [call["call_id"] for call in payload["calls"]] == ["own"]


def test_viewer_sales_quality_is_redacted():
    viewer = Principal(subject="viewer", role=Role.VIEWER, auth_type="session")
    payload = _build_sales_quality_payload(
        [
            {
                "call_id": "call-1",
                "manager_id": "seller-a",
                "manager_name": "A",
                "client_name": "Sensitive Client",
                "overall_score": 90,
                "summary": "Private notes",
            }
        ],
        principal=viewer,
    )
    call = payload["calls"][0]
    assert "client" not in call
    assert "summary" not in call
