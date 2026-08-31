"""PR #475 review'ida topilgan to'rtta nuqson uchun regressiya testlari.

CodeRabbit merge paytida review qilayotgan edi (xuddi #473 dagidek) va
topilmalar merge'dan KEYIN keldi: 3 ta P1, 1 ta P2. Har biri prod'da jim
turib zarar keltirardi — huquq oshib ketishi yoki tarixiy backfill'ning
noto'g'ri ma'lumot yozishi. Bu fayl har birini alohida qamrab oladi.
"""

from src.api.rbac import Permission


# ── 1. `/api/sales-quality/conversion-overview` faqat DASHBOARD_READ    ─
#    bilan SELLER/VIEWER'ga boshqa sotuvchilarning ballari va jamoaviy  ─
#    pulini ochib qo'yardi.                                            ─


def test_conversion_overview_requires_call_and_finance_permissions():
    from src.api.routes.sales_quality import router

    route = next(
        r for r in router.routes if r.path == "/api/sales-quality/conversion-overview"
    )
    required = set()
    for dep in route.dependencies:
        perms = getattr(dep.dependency, "__oisha_permissions__", ())
        required.update(perms)

    assert Permission.DASHBOARD_READ.value in required
    assert Permission.CALL_READ_ALL.value in required
    assert Permission.FINANCE_READ.value in required


def test_conversion_dashboard_page_requires_same_permissions_as_its_data():
    """Sahifa ochiladi-yu ichidagi so'rov 403 olsa — bu buzuq UI."""
    from src.api.routes.sales_quality import router

    route = next(r for r in router.routes if r.path == "/dashboard/sales-quality")
    required = set()
    for dep in route.dependencies:
        perms = getattr(dep.dependency, "__oisha_permissions__", ())
        required.update(perms)

    assert Permission.CALL_READ_ALL.value in required
    assert Permission.FINANCE_READ.value in required


def test_seller_role_cannot_reach_call_read_all_or_finance_read():
    """SELLER/VIEWER'ning huquq to'plamida bu ikkisi bo'lmasligi kerak —
    aks holda yuqoridagi gate hech narsani himoya qilmaydi."""
    from src.api.rbac import ROLE_PERMISSIONS, Role

    for role in (Role.SELLER, Role.VIEWER):
        perms = ROLE_PERMISSIONS[role]
        assert Permission.CALL_READ_ALL not in perms
        assert Permission.FINANCE_READ not in perms


def test_money_bearing_ai_conversion_routes_require_finance_read():
    """`/api/ai/conversion/*` moliyaviy ma'lumot beradigan yo'llar ham
    router darajasidagi `CALL_READ_ALL`dan tashqari `FINANCE_READ`
    talab qilishi kerak."""
    from src.api.routes.ai_analytics import router

    money_paths = {
        "/conversion/overview",
        "/conversion/sync-revenue",
        "/conversion/seller-card",
    }

    def _iter_routes(r):
        for route in r.routes:
            original_router = getattr(route, "original_router", None)
            if original_router is not None:
                yield from _iter_routes(original_router)
            else:
                yield route

    for route in _iter_routes(router):
        if getattr(route, "path", None) not in money_paths:
            continue
        required = set()
        for dep in route.dependencies:
            perms = getattr(dep.dependency, "__oisha_permissions__", ())
            required.update(perms)
        assert Permission.FINANCE_READ.value in required, route.path
