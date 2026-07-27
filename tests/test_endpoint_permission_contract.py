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
)


def test_every_business_route_declares_explicit_permissions():
    def permission_metadata(dependant):
        current = getattr(dependant.call, "__oisha_permissions__", ())
        nested = [
            permission
            for child in getattr(dependant, "dependencies", ())
            for permission in permission_metadata(child)
        ]
        return list(current) + nested

    missing = []
    for router in PRIVATE_ROUTERS:
        for route in router.routes:
            path = getattr(route, "path", "")
            if path.endswith("/webhook"):
                continue
            if not permission_metadata(route.dependant):
                missing.append(path)
    assert missing == []
