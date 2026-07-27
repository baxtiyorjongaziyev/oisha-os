"""Product suite route."""
from __future__ import annotations

from fastapi import APIRouter
from src.api.rbac import Permission, require_permissions

router = APIRouter(
    prefix="/api/oisha",
    tags=["product"],
    dependencies=[require_permissions(Permission.DASHBOARD_READ)],
)


@router.get("/product-suite")
async def oisha_product_suite():
    """Unified DeepSales + Metasell + Reportagram capability contract."""
    from src.services.core.oisha_product_suite import build_oisha_sales_os_suite
    return build_oisha_sales_os_suite()
