"""
ServiceConfigurator implementation.
"""
from __future__ import annotations

import hashlib
import time
from typing import Any, Dict, List

from src.context import app_ctx
from src.services.core.service_config.models import ServiceModule, ServiceType
from src.services.core.service_config.modules import (
    get_default_modules,
    get_recommended_packages_list,
)


class ServiceConfigurator:
    """Xizmatlarni sozlash va kombinatsiya qilish tizimi."""

    def __init__(self):
        self.modules: Dict[ServiceType, ServiceModule] = get_default_modules()

    def _setup_default_modules(self):
        self.modules = get_default_modules()

    def configure_project(
        self,
        client_name: str,
        selected_services: List[ServiceType],
        custom_requirements: Dict = None,
    ) -> Dict[str, Any]:
        if not selected_services:
            raise ValueError("Kamida bitta xizmat tanlanishi kerak")

        services = []
        total_price = 0
        total_days = 0
        total_steps = 0
        all_phases = []
        all_deliverables = []

        for service_type in selected_services:
            module = self.modules.get(service_type)
            if not module:
                continue

            services.append(module.to_dict())
            total_price += module.base_price
            total_days += module.estimated_days
            total_steps += module.total_steps
            all_phases.extend(module.includes_phases)
            all_deliverables.extend(module.deliverables)

        if len(selected_services) >= 3:
            total_price = int(total_price * 0.9)

        project_id = f"JB-{int(time.time())}-{hashlib.md5(client_name.encode(), usedforsecurity=False).hexdigest()[:6].upper()}"

        return {
            "project_id": project_id,
            "client_name": client_name,
            "services": services,
            "service_types": [s.value for s in selected_services],
            "total_price": total_price,
            "total_days": total_days,
            "total_steps": total_steps,
            "phases": all_phases,
            "deliverables": list(set(all_deliverables)),
            "discount_applied": len(selected_services) >= 3,
            "custom_requirements": custom_requirements or {},
        }

    def get_service_options(self) -> List[Dict]:
        return [module.to_dict() for module in self.modules.values()]

    def get_recommended_packages(self) -> List[Dict]:
        return get_recommended_packages_list()

    def validate_configuration(self, selected_services: List[ServiceType]) -> Dict:
        warnings = []
        errors = []

        if ServiceType.BRANDBOOK in selected_services:
            if ServiceType.LOGO not in selected_services:
                errors.append("Brandbook uchun Logo xizmati majburiy")
            if ServiceType.VISUAL_IDENTITY not in selected_services:
                warnings.append("Brandbook Visual Identity bilan yaxshiroq bo'ladi")

        if ServiceType.NAMING in selected_services:
            if ServiceType.NAMING_CHECK not in selected_services:
                warnings.append("Naming Check Naming bilan birga tavsiya etiladi")

        service_order = [
            ServiceType.BRAND_AUDIT,
            ServiceType.NAMING_CHECK,
            ServiceType.NAMING,
            ServiceType.LOGO,
            ServiceType.VISUAL_IDENTITY,
            ServiceType.BRANDBOOK,
            ServiceType.PACKAGING,
            ServiceType.PATENT_SUPPORT,
        ]

        current_indices = [
            service_order.index(s) for s in selected_services if s in service_order
        ]
        if current_indices != sorted(current_indices):
            warnings.append("Xizmatlarni logik tartibda olish tavsiya etiladi")

        return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}


def get_service_configurator() -> ServiceConfigurator:
    if getattr(app_ctx, "configurator", None) is None:
        app_ctx.configurator = ServiceConfigurator()
    return app_ctx.configurator
