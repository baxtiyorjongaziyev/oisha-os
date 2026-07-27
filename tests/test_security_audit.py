import json

from src.api.rbac import Permission, Principal, Role
from src.api.security_audit import SecurityAuditEvent, hash_resource_id


def test_denial_event_contains_only_sanitized_fields():
    principal = Principal(
        subject="seller-a",
        role=Role.SELLER,
        auth_type="session",
    )
    event = SecurityAuditEvent.denied(
        principal=principal,
        route="/api/finance/dashboard?token=secret",
        method="GET",
        permissions=(Permission.FINANCE_READ,),
        resource_type="lead",
        resource_id="998877",
    )

    payload = event.as_dict()
    serialized = json.dumps(payload)

    assert payload["route"] == "/api/finance/dashboard"
    assert payload["permissions"] == ["finance:read"]
    assert payload["resource_id_hash"] == hash_resource_id("998877")
    for forbidden in (
        "secret",
        "authorization",
        "cookie",
        "phone",
        "email",
        "transcript",
        "message_body",
        "finance_value",
    ):
        assert forbidden not in serialized.lower()


def test_resource_hash_is_stable_and_does_not_expose_identifier():
    digest = hash_resource_id("customer-123")
    assert digest == hash_resource_id("customer-123")
    assert digest != hash_resource_id("customer-124")
    assert "customer-123" not in digest
    assert len(digest) == 64
