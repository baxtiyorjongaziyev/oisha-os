from src.api.rbac import (
    Permission,
    Principal,
    Role,
    has_permission,
    require_any_permission,
    scope_owned_rows,
)


def principal(role: Role, *, subject: str = "user-1", scopes=()) -> Principal:
    return Principal(
        subject=subject,
        role=role,
        auth_type="session",
        scopes=frozenset(scopes),
    )


def test_owner_has_every_permission():
    assert all(has_permission(principal(Role.OWNER), permission) for permission in Permission)


def test_role_matrix_enforces_admin_seller_and_viewer_boundaries():
    assert not has_permission(principal(Role.ADMIN), Permission.SECRETS_MANAGE)
    assert not has_permission(principal(Role.ADMIN), Permission.SYSTEM_DEPLOY)
    assert has_permission(principal(Role.SELLER), Permission.LEAD_READ_ASSIGNED)
    assert has_permission(principal(Role.SELLER), Permission.CALL_READ_OWN)
    assert not has_permission(principal(Role.SELLER), Permission.FINANCE_READ)
    assert has_permission(principal(Role.VIEWER), Permission.DASHBOARD_READ)
    assert not has_permission(principal(Role.VIEWER), Permission.LEAD_WRITE)


def test_service_requires_exact_scope():
    service = principal(Role.SERVICE, scopes={"finance:read"})
    assert has_permission(service, Permission.FINANCE_READ)
    assert not has_permission(service, Permission.FINANCE_WRITE)


def test_seller_rows_are_filtered_by_canonical_owner_field():
    rows = [
        {"id": "a", "responsible_user_id": "seller-a"},
        {"id": "b", "responsible_user_id": "seller-b"},
    ]
    assert scope_owned_rows(
        principal(Role.SELLER, subject="seller-a"),
        rows,
        owner_field="responsible_user_id",
    ) == [rows[0]]
    assert scope_owned_rows(principal(Role.ADMIN), rows, owner_field="responsible_user_id") == rows


def test_missing_owner_field_fails_closed_for_seller():
    assert scope_owned_rows(
        principal(Role.SELLER),
        [{"id": "unassigned"}],
        owner_field="responsible_user_id",
    ) == []


def test_any_permission_dependency_exposes_auditable_metadata():
    dependency = require_any_permission(
        Permission.LEAD_READ_ALL,
        Permission.LEAD_READ_ASSIGNED,
    )
    assert dependency.dependency.__oisha_permissions__ == (
        "lead:read:all",
        "lead:read:assigned",
    )
    assert dependency.dependency.__oisha_permission_mode__ == "any"
