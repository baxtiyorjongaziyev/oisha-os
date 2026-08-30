"""
Default modules and package definitions for Service Configurator.
"""
from __future__ import annotations

from typing import Dict, List

from src.services.core.service_config.models import ServiceModule, ServiceType


def get_default_modules() -> Dict[ServiceType, ServiceModule]:
    modules = {}

    modules[ServiceType.BRAND_AUDIT] = ServiceModule(
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
        includes_phases=["D1", "D2", "D3", "D4", "D5", "D6"],
        total_steps=6,
    )

    modules[ServiceType.NAMING_CHECK] = ServiceModule(
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
        includes_phases=["N2", "N4"],
        total_steps=2,
    )

    modules[ServiceType.NAMING] = ServiceModule(
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
        includes_phases=["N1", "N2", "N3", "N4", "N5", "N6"],
        total_steps=6,
    )

    modules[ServiceType.LOGO] = ServiceModule(
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
        includes_phases=["L1", "L2", "L3", "L4", "L5", "L6", "L7"],
        total_steps=7,
    )

    modules[ServiceType.VISUAL_IDENTITY] = ServiceModule(
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
        includes_phases=["V1", "V2", "V3", "V4", "V5", "V6", "V7"],
        total_steps=7,
    )

    modules[ServiceType.BRANDBOOK] = ServiceModule(
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
            "B9",
        ],
        total_steps=9,
    )

    modules[ServiceType.PACKAGING] = ServiceModule(
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
            "Q7",
        ],
        total_steps=7,
    )

    modules[ServiceType.PATENT_SUPPORT] = ServiceModule(
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
        includes_phases=["PT1", "PT2", "PT3"],
        total_steps=3,
    )

    return modules


def get_recommended_packages_list() -> List[Dict]:
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
            "price": 3150,
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
            "price": 5850,
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
            "price": 8550,
            "days": 42,
            "description": "Kompleks yechim - auditdan topshirishgacha",
        },
    ]
