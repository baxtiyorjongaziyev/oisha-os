"""Jon Branding agentligi haqidagi rasmiy bilimlar va manbalarni yuklovchi modul.

Ushbu modul rasmiy hujjatlar (docs/) va konfiguratsiyalar (config/moizvonki_roster.json)
asosida jamoa, xizmatlar va operatsion yoʻriqnomalarni jamlaydi.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

from src.services.core.onboarding.models import (
    CompanyServicePackage,
    TeamMember,
    WorkflowPlaybook,
)

logger = logging.getLogger(__name__)


def get_official_services() -> List[CompanyServicePackage]:
    """Rasmiy xizmatlar va ularning tasdiqlangan narxlarini qaytaradi."""
    return [
        CompanyServicePackage(
            name="Brend-strategiya va platforma",
            price_usd=4750,
            deliverables=["Bozor tahlili", "Auditoriya portreti", "Brend arxitekturasi"],
        ),
        CompanyServicePackage(
            name="Kommunikatsiya strategiyasi",
            price_usd=3950,
            deliverables=["Tonality qoʻllanmasi", "Xabarlar xaritasi", "6 oylik PR reja"],
        ),
        CompanyServicePackage(
            name="Naming VIP",
            price_usd=1450,
            deliverables=["30+ variant", "Huquqiy tekshiruv"],
        ),
        CompanyServicePackage(
            name="Naming Premium",
            price_usd=980,
            deliverables=["15 ta variant"],
        ),
        CompanyServicePackage(
            name="Naming Standart",
            price_usd=650,
            deliverables=["5 ta variant"],
        ),
        CompanyServicePackage(
            name="Logo + Firma uslubi + Brandbook (VIP)",
            price_usd=2950,
            deliverables=["Toʻliq vizual tizim", "Guideline", "Merchendayzing"],
        ),
        CompanyServicePackage(
            name="Logo + Korporativ firma uslubi",
            price_usd=1550,
            deliverables=["Asosiy vizual elementlar", "Vizitka va blank", "Ranglar"],
        ),
        CompanyServicePackage(
            name="Logo Standart",
            price_usd=780,
            deliverables=["Logotip va ranglar palitrasi"],
        ),
        CompanyServicePackage(
            name="Qadoq dizayni",
            price_usd=1150,
            deliverables=["Bitta liniya uchun toʻliq qadoq dizayni"],
        ),
    ]


def _load_moizvonki_roster(config_path: Optional[Path] = None) -> Dict[str, str]:
    """Moizvonki konfiguratsiya faylidan sotuvchilar roʻyxatini oʻqiydi."""
    path = config_path or Path("config/moizvonki_roster.json")
    if not path.exists():
        logger.debug("[ONBOARDING] Moizvonki roster fayli topilmadi: %s", path)
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("reps", {})
    except Exception as exc:
        logger.warning("[ONBOARDING] Moizvonki roster oʻqishda xato: %s", exc)
        return {}


def get_core_team(config_path: Optional[Path] = None) -> Dict[str, TeamMember]:
    """Jamoa aʼzolari va ularning rollarini qaytaradi."""
    team: Dict[str, TeamMember] = {
        "baxtiyorjon": TeamMember(
            id="baxtiyorjon",
            name="Baxtiyorjon Gaziyev",
            role="Asoschi va Rahbar (CEO)",
            telegram="@baxtiyorjon",
            authority="owner",
            responsibilities=[
                "Kompaniya strategiyasi va brending falsafasi",
                "Haftalik tahlil va asosiy qarorlarni qabul qilish",
                "VIP loyihalar va mijozlar bilan strategik sessiyalar",
            ],
            tone_guidance="hurmatli, aniq, strategik va xushmuomala",
        ),
        "dilbar": TeamMember(
            id="dilbar",
            name="Dilbar Akbarovna",
            role="Loyiha menejeri va Hisobchi (PM & Finance)",
            telegram="@jonbranding_finansist",
            authority="pm_finance",
            responsibilities=[
                "Mijozlar loyihalari muddatlari va ijrosini nazorat qilish",
                "Kunlik balans, tushumlar va xarajatlarni Airtableʼda yuritish",
                "Moliya guruhiga kunlik xulosa va hisobotlarni taqdim etish",
            ],
            tone_guidance="amaliy, professional, aniq va yordamga tayyor",
        ),
        "ahrorbek": TeamMember(
            id="ahrorbek",
            name="Ahrorbek",
            role="Dizayner va texnik ijrochi",
            authority="creative_tech",
            responsibilities=[
                "Brending vizual elementlari va logotip dizayni",
                "Veb-sayt va texnik vositalarni amalga oshirish",
            ],
            tone_guidance="samimiy, doʻstona va ijodiy",
        ),
    }

    # Sotuv jamoasini dinamik konfiguratsiyadan toʻldirish
    reps = _load_moizvonki_roster(config_path)
    sales_map = {
        "rayxona@jonbranding.uz": (
            "rayxon",
            "Rayxon",
            "@RayxonJonbranding",
            "Sotuv menejeri (Hunter / Setter)",
        ),
        "mumtozmaxal@jonbranding.uz": (
            "mumtozmaxal",
            "Mumtozmaxal",
            None,
            "Sotuv menejeri (Setter / Closing)",
        ),
        "shahnoza@jonbranding.uz": (
            "shahnoza",
            "Shahnoza",
            None,
            "Sotuv menejeri (Lead Qualify / Calls)",
        ),
    }

    for email, (member_id, default_name, tg_handle, member_role) in sales_map.items():
        name = reps.get(email, default_name)
        team[member_id] = TeamMember(
            id=member_id,
            name=name,
            role=member_role,
            telegram=tg_handle,
            email=email,
            authority="sales",
            responsibilities=[
                "Lidlarni saralash va qoʻngʻiroq qilish (kunlik 30–50 ta)",
                "AmoCRMʼda bitimlarni intizom bilan yuritish",
                "Mijozlarni strategik sessiyaga yozib olish",
            ],
            tone_guidance="ragʻbatlantiruvchi, doʻstona va aniq maslahat beruvchi",
        )

    return team


def get_core_workflows() -> Dict[str, WorkflowPlaybook]:
    """Operatsion yoʻriqnomalar va taqiqlangan amallar roʻyxati."""
    return {
        "moliya": WorkflowPlaybook(
            id="moliya",
            title="Moliya va Kunlik Balans Tartibi",
            responsible_role="Dilbar Akbarovna (PM & Finance)",
            source_of_truth="Airtable (Tranzaksiyalar va Hisoblar jadvallari)",
            key_rules=[
                "Kunlik balans va kassa hisobotini Dilbar opa Airtable orqali yuritadi.",
                "Dilbar opa guruhga balans yozganda bot faqat tasdiqlaydi yoki jim turadi.",
                "Moliya boʻyicha maʼlumot soʻralganda Airtable yozuvlariga tayaniladi.",
            ],
            prohibited_actions=[
                "Dilbar opadan yoki jamoadan 'Kunlik balansni qayerdan olasiz?' deb soʻroq qilish qatʼiyan taqiqlanadi.",
                "Balans kiritilgandan keyin nima qilish kerakligi boʻyicha keraksiz savollar berish taqiqlanadi.",
                "Moliyaviy raqamlarni taxmin qilish yoki toʻqish taqiqlanadi.",
            ],
        ),
        "sales_discipline": WorkflowPlaybook(
            id="sales_discipline",
            title="Sotuv va AmoCRM Intizomi",
            responsible_role="Sotuv boʻlimi (Rayxon, Mumtozmaxal, Shahnoza)",
            source_of_truth="AmoCRM va Moizvonki",
            key_rules=[
                "AmoCRMʼda aktiv lidlar soni qatʼiy 500 tadan oshmasligi shart.",
                "Kunlik 30–50 ta qoʻngʻiroq normasi bajariladi; barcha qoʻngʻiroqlar Moizvonki orqali yoziladi.",
                "Hunter saralaydi, Setter yopadi, Farmer esa LTV oshiradi.",
            ],
            prohibited_actions=[
                "Ochiq lidlarni asossiz 'Lost' qilish yoki oʻchirib yuborish taqiqlanadi.",
            ],
        ),
        "jamoa_ritmi": WorkflowPlaybook(
            id="jamoa_ritmi",
            title="Jamoa Ish Ritmi va Muloqot Odobi",
            responsible_role="Barcha jamoa aʼzolari va Oisha",
            source_of_truth="Telegram jamoa forumi",
            key_rules=[
                "09:00 — Ertalabki start (bugungi 1–3 ta vazifa, toʻsiqlar, yordam).",
                "18:00–19:00 — Kun yakuni (nima tugadi va ertaga nima davom etadi).",
                "Shanba/Yakshanba — Hafta yakuni va retro tahlil.",
                "22:00–08:00 — Tinchlik rejimi (quiet hours), guruhga avtomatik xabar yuborilmaydi.",
                "Guruhda 'siz' bilan, doʻstona, qisqa (2–4 qator) muloqot qilinadi.",
            ],
            prohibited_actions=[
                "Guruhdagi har bir xabarga oʻzicha aralashish taqiqlanadi (faqat botga murojaatda javob beriladi).",
                "Tizim xatoliklarini ([The tool failed...], [NO TOOL CALL...]) guruhga chiqarish taqiqlanadi.",
                "Xato yuz berganda oʻzini oqlash yoki bahslashish taqiqlanadi.",
            ],
        ),
    }
