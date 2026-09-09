from src.api import admin
from src.api.routes import (
    callmaster_routes,
    crm_dashboard,
    finance_dashboard,
    sales_quality,
    system_dashboard,
    telegram_mcp,
    telegram_routes,
)


PRIVATE_ROUTERS = (
    crm_dashboard.router,
    finance_dashboard.router,
    sales_quality.router,
    system_dashboard.router,
    telegram_routes.router,
    telegram_mcp.router,
    callmaster_routes.router,
    admin.router,
)


def _permission_metadata(dependant):
    current = getattr(dependant.call, "__oisha_permissions__", ())
    nested = [
        permission
        for child in getattr(dependant, "dependencies", ())
        for permission in _permission_metadata(child)
    ]
    return list(current) + nested


def test_every_business_route_declares_explicit_permissions():
    missing = []
    for router in PRIVATE_ROUTERS:
        for route in router.routes:
            path = getattr(route, "path", "")
            if path.endswith("/webhook"):
                continue
            if not _permission_metadata(route.dependant):
                missing.append(path)
    assert missing == []


def test_admin_mutating_action_requires_system_deploy():
    """The admin POST action endpoint has real side effects (it can fire an
    owner briefing), so it must demand SYSTEM_DEPLOY on top of the router's
    SYSTEM_READ — keeping it OWNER-only. Read endpoints keep SYSTEM_READ."""
    routes_by_path = {r.path: r for r in admin.router.routes}
    action_route = routes_by_path["/api/v1/admin/actions/{action_type}"]
    perms = _permission_metadata(action_route.dependant)

    assert "system:deploy" in perms
    # Router-level SYSTEM_READ still applies to every admin route.
    assert "system:read" in perms

    stats_route = routes_by_path["/api/v1/admin/dashboard/stats"]
    stats_perms = _permission_metadata(stats_route.dependant)
    assert stats_perms == ["system:read"]
