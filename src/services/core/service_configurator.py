"""
Service Configurator - Xizmatlarni sozlash tizimi
Jon.Branding - Mijoz qaysi xizmatlarni olganiga qarab checklist yaratadi
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum


class ServiceType(Enum):
    """Jon.Branding xizmat turlari"""

    BRAND_AUDIT = "brand_audit"
    NAMING_CHECK = "naming_check"
    NAMING = "naming"
    LOGO = "logo"
    VISUAL_IDENTITY = "visual_identity"
    BRANDBOOK = "brandbook"
    PACKAGING = "packaging"
    PATENT_SUPPORT = "patent_support"


@dataclass
class ServiceModule:
    """Xizmat moduli"""

    id: str
    name: str
    name_uz: str
    service_type: ServiceType
    base_price: int  # USD
    estimated_days: int

    # Modul tarkibi
    deliverables: List[str] = field(default_factory=list)
    includes_phases: List[str] = field(default_factory=list)

    # Majburiy qadamlar soni
    total_steps: int = 0

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "name_uz": self.name_uz,
            "type": self.service_type.value,
            "price": self.base_price,
            "days": self.estimated_days,
            "deliverables": self.deliverables,
            "total_steps": self.total_steps,
        }


class ServiceConfigurator:
    """
    Xizmatlarni sozlash va kombinatsiya qilish tizimi

    Mijoz tanlagan xizmatlarga qarab:
    - Narx hisoblash
    - Muddat aniqlash
    - Checklist yaratish
    """

    def __init__(self):
        self.modules: Dict[ServiceType, ServiceModule] = {}
        self._setup_default_modules()

    def _setup_default_modules(self):
        """Standart xizmat modullari"""

        self.modules[ServiceType.BRAND_AUDIT] = ServiceModule(
            id="brand_audit",
            name="Brand Audit",
            name_uz="Brand audit",
            service_type=ServiceType.BRAND_AUDIT,
            base_price=500,
            estimated_days=5,
            deliverables=[
                "Brand audit hisoboti (PDF)",
                "SWOT analiz",
                "Raqobat tahlili",
                "Tavsiyalar ro'yxati",
            ],
            includes_phases=["D1", "D2", "D3", "D4", "D5", "D6"],  # Brand audit phases
            total_steps=6,
        )

        self.modules[ServiceType.NAMING_CHECK] = ServiceModule(
            id="naming_check",
            name="Naming Check",
            name_uz="Naming tekshiruvi",
            service_type=ServiceType.NAMING_CHECK,
            base_price=200,
            estimated_days=2,
            deliverables=[
                "Mavjud nomlarni tekshirish",
                "Trademark tekshiruvi",
                "Domen tekshiruvi",
                "Xulosa hisoboti",
            ],
            includes_phases=["N2", "N4"],  # Research va trademark check
            total_steps=2,
        )

        self.modules[ServiceType.NAMING] = ServiceModule(
            id="naming",
            name="Naming",
            name_uz="Nom yaratish",
            service_type=ServiceType.NAMING,
            base_price=800,
            estimated_days=7,
            deliverables=[
                "30 ta nom varianti",
                "3 ta eng yaxshisi",
                "Trademark tekshiruvi",
                "Domen tekshiruvi",
                "Nom ma'nosi tushuntiruvi",
            ],
            includes_phases=["N1", "N2", "N3", "N4", "N5", "N6"],  # Full naming
            total_steps=6,
        )

        self.modules[ServiceType.LOGO] = ServiceModule(
            id="logo",
            name="Logo Design",
            name_uz="Logo dizayn",
            service_type=ServiceType.LOGO,
            base_price=1500,
            estimated_days=10,
            deliverables=[
                "3 ta logo konsepsiyasi",
                "Yakuniy logo (tasdiqlangan)",
                "Logo variantlari (RGB, CMYK, mono)",
                "Logo qo'llanmasi (usage guide)",
                "Source fayllar (AI, EPS, PDF, SVG, PNG)",
            ],
            includes_phases=["L1", "L2", "L3", "L4", "L5", "L6", "L7"],  # Full logo
            total_steps=7,
        )

        self.modules[ServiceType.VISUAL_IDENTITY] = ServiceModule(
            id="visual_identity",
            name="Visual Identity",
            name_uz="Vizual identitet",
            service_type=ServiceType.VISUAL_IDENTITY,
            base_price=2000,
            estimated_days=10,
            deliverables=[
                "Rang palitrasu",
                "Typography sistemasi",
                "Grafik elementlar (pattern, shapes)",
                "Icon set (20 ta)",
                "Photography style guide",
                "Visual identity qoidalari",
            ],
            includes_phases=["V1", "V2", "V3", "V4", "V5", "V6", "V7"],  # Full visual
            total_steps=7,
        )

        self.modules[ServiceType.BRANDBOOK] = ServiceModule(
            id="brandbook",
            name="Brandbook",
            name_uz="Brandbook",
            service_type=ServiceType.BRANDBOOK,
            base_price=3000,
            estimated_days=14,
            deliverables=[
                "Brand strategy bo'limi",
                "Logo usage guidelines",
                "Color system qoidalari",
                "Typography qoidalari",
                "Visual applications",
                "Mockup'lar to'plami",
                "Print-ready brandbook (PDF)",
            ],
            includes_phases=[
                "B1",
                "B2",
                "B3",
                "B4",
                "B5",
                "B6",
                "B7",
                "B8",
                "B9",  # Full brandbook
            ],
            total_steps=9,
        )

        self.modules[ServiceType.PACKAGING] = ServiceModule(
            id="packaging",
            name="Packaging Design",
            name_uz="Qadoq dizayni",
            service_type=ServiceType.PACKAGING,
            base_price=1500,
            estimated_days=10,
            deliverables=[
                "3 ta qadoq konsepsiyasi",
                "Dieline (texnik chizma)",
                "3D mockup",
                "Print-ready fayllar",
                "Qadoq qo'llanmasi",
            ],
            includes_phases=[
                "Q1",
                "Q2",
                "Q3",
                "Q4",
                "Q5",
                "Q6",
                "Q7",  # Full packaging
            ],
            total_steps=7,
        )

        self.modules[ServiceType.PATENT_SUPPORT] = ServiceModule(
            id="patent_support",
            name="Patent Support",
            name_uz="Patentlash yordami",
            service_type=ServiceType.PATENT_SUPPORT,
            base_price=300,
            estimated_days=3,
            deliverables=[
                "Logo va elementlar dokumentatsiyasi",
                "Patent uchun fayllar tayyorlash",
                "Uzpatent yo'naltiruvi",
                "Qo'llab-quvvatlash hujjatlari",
            ],
            includes_phases=["PT1", "PT2", "PT3"],  # Patent phases
            total_steps=3,
        )

    def configure_project(
        self,
        client_name: str,
        selected_services: List[ServiceType],
        custom_requirements: Dict = None,
    ) -> Dict[str, Any]:
        """
        Loyihani sozlash

        Returns:
            {
                "project_id": str,
                "client_name": str,
                "services": [...],
                "total_price": int,
                "total_days": int,
                "total_steps": int,
                "phases": [...],
                "deliverables": [...]
            }
        """

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

        # Package discount
        if len(selected_services) >= 3:
            total_price = int(total_price * 0.9)  # 10% chegirma

        # Generate project ID
        import hashlib
        import time

        project_id = f"JB-{int(time.time())}-{hashlib.md5(client_name.encode()).hexdigest()[:6].upper()}"

        return {
            "project_id": project_id,
            "client_name": client_name,
            "services": services,
            "service_types": [s.value for s in selected_services],
            "total_price": total_price,
            "total_days": total_days,
            "total_steps": total_steps,
            "phases": all_phases,
            "deliverables": list(set(all_deliverables)),  # Remove duplicates
            "discount_applied": len(selected_services) >= 3,
            "custom_requirements": custom_requirements or {},
        }

    def get_service_options(self) -> List[Dict]:
        """Mavjud xizmatlar ro'yxati"""
        return [module.to_dict() for module in self.modules.values()]

    def get_recommended_packages(self) -> List[Dict]:
        """Tavsiya etilgan paketlar"""

        return [
            {
                "id": "starter",
                "name": "Starter",
                "name_uz": "Boshlang'ich",
                "services": [ServiceType.LOGO],
                "price": 1500,
                "days": 10,
                "description": "Yangi biznes uchun oddiy logo",
            },
            {
                "id": "essential",
                "name": "Essential",
                "name_uz": "Asosiy",
                "services": [ServiceType.LOGO, ServiceType.VISUAL_IDENTITY],
                "price": 3150,  # 3500 - 10%
                "days": 18,
                "description": "Logo va vizual identitet",
            },
            {
                "id": "professional",
                "name": "Professional",
                "name_uz": "Professional",
                "services": [
                    ServiceType.LOGO,
                    ServiceType.VISUAL_IDENTITY,
                    ServiceType.BRANDBOOK,
                ],
                "price": 5850,  # 6500 - 10%
                "days": 28,
                "description": "To'liq brand identity",
            },
            {
                "id": "enterprise",
                "name": "Enterprise",
                "name_uz": "Korporativ",
                "services": [
                    ServiceType.BRAND_AUDIT,
                    ServiceType.NAMING,
                    ServiceType.LOGO,
                    ServiceType.VISUAL_IDENTITY,
                    ServiceType.BRANDBOOK,
                    ServiceType.PACKAGING,
                ],
                "price": 8550,  # 9500 - 10%
                "days": 42,
                "description": "Kompleks yechim - auditdan topshirishgacha",
            },
        ]

    def validate_configuration(self, selected_services: List[ServiceType]) -> Dict:
        """Konfiguratsiyani tekshirish"""

        warnings = []
        errors = []

        # Check dependencies
        if ServiceType.BRANDBOOK in selected_services:
            if ServiceType.LOGO not in selected_services:
                errors.append("Brandbook uchun Logo xizmati majburiy")
            if ServiceType.VISUAL_IDENTITY not in selected_services:
                warnings.append("Brandbook Visual Identity bilan yaxshiroq bo'ladi")

        if ServiceType.NAMING in selected_services:
            if ServiceType.NAMING_CHECK not in selected_services:
                warnings.append("Naming Check Naming bilan birga tavsiya etiladi")

        # Check logical order
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


# Singleton
_configurator: Optional[ServiceConfigurator] = None


def get_service_configurator() -> ServiceConfigurator:
    """Global configurator instance"""
    global _configurator
    if _configurator is None:
        _configurator = ServiceConfigurator()
    return _configurator


# Quick test
if __name__ == "__main__":
    config = get_service_configurator()

    print("📋 MAVJUD XIZMATLAR:")
    for svc in config.get_service_options():
        print(f"   • {svc['name_uz']}: ${svc['price']} ({svc['days']} kun)")

    print("\n📦 TAVSIYA ETILGAN PAKETLAR:")
    for pkg in config.get_recommended_packages():
        services = ", ".join([s.name for s in pkg["services"]])
        print(f"   • {pkg['name_uz']}: ${pkg['price']} - {services}")

    print("\n🎯 LOYIHA CONFIGURATSIYASI (Professional):")
    project = config.configure_project(
        client_name="Test Company",
        selected_services=[
            ServiceType.LOGO,
            ServiceType.VISUAL_IDENTITY,
            ServiceType.BRANDBOOK,
        ],
    )
    print(f"   ID: {project['project_id']}")
    print(f"   Narx: ${project['total_price']}")
    print(f"   Muddat: {project['total_days']} kun")
    print(f"   Qadamlar: {project['total_steps']}")
    print(f"   Chegirma: {'Ha' if project['discount_applied'] else 'Yoq'}")
