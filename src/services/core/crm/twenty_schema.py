"""Twenty CRM maydonlar sxemasi — branding agentlik sotuv bo'limi uchun.

Manba: BANT kvalifikatsiya modeli (Budget, Authority, Need, Timeline) va
agentlik CRM amaliyoti (HubSpot agency deal properties). Sxema deklarativ:
`ensure_schema()` yetishmagan maydonlarni Twenty metadata REST API orqali
yaratadi, mavjudlarini o'zgartirmaydi (idempotent).
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

import httpx

from src.services.core.crm.twenty_client import TwentyClient

logger = logging.getLogger(__name__)

_COLORS = ["blue", "green", "orange", "purple", "red", "turquoise", "yellow", "pink", "sky", "gray"]


def _opts(*labels: str) -> List[Dict[str, Any]]:
    out = []
    for i, label in enumerate(labels):
        value = re.sub(r"[^A-Z0-9]+", "_", label.upper().replace("'", "")).strip("_")
        if not value or value[0].isdigit():
            value = f"OPT_{value}"
        out.append({"label": label, "value": value, "color": _COLORS[i % len(_COLORS)], "position": i})
    return out


def _f(name: str, label: str, ftype: str, options: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    field: Dict[str, Any] = {"name": name, "label": label, "type": ftype}
    if options:
        field["options"] = options
    return field


TAGS = _opts("VIP", "Issiq", "Qayta mijoz", "Tavsiya orqali", "Xalqaro", "Tender", "Shoshilinch", "Sovuq")

OPPORTUNITY_FIELDS: List[Dict[str, Any]] = [
    # Xizmat
    _f("serviceType", "Xizmat turi", "MULTI_SELECT", _opts(
        "Brend strategiya", "Neyming", "Logotip", "Brendbuk", "Firma uslubi", "Qadoq dizayni",
        "Rebrending", "Veb-sayt", "SMM", "Reklama kampaniyasi", "Brend audit")),
    _f("tags", "Teglar", "MULTI_SELECT", TAGS),
    # BANT
    _f("budgetRange", "Byudjet oralig'i", "SELECT", _opts(
        "5 mln gacha", "5-15 mln", "15-50 mln", "50-150 mln", "150 mln+", "Noma'lum")),
    _f("decisionRole", "Suhbatdosh roli", "SELECT", _opts(
        "Qaror qabul qiluvchi", "Ta'sir qiluvchi", "Tavsiyachi", "Noma'lum")),
    _f("painPoint", "Mijoz muammosi", "TEXT"),
    _f("deadline", "Mijoz muddati", "DATE"),
    _f("qualification", "BANT bahosi", "RATING"),
    # Manba
    _f("leadSource", "Lid manbasi", "SELECT", _opts(
        "Instagram", "Telegram", "Meta Ads", "Sayt", "Tavsiya", "Networking", "Qayta mijoz",
        "Qo'ng'iroq", "Tender", "Boshqa")),
    _f("utmCampaign", "UTM kampaniya", "TEXT"),
    # Jarayon
    _f("nextStep", "Keyingi qadam", "TEXT"),
    _f("nextStepDate", "Keyingi qadam sanasi", "DATE"),
    _f("briefReceived", "Brif olindi", "BOOLEAN"),
    _f("proposalSentAt", "KP yuborilgan sana", "DATE"),
    _f("proposalLink", "Tijoriy taklif", "LINKS"),
    _f("contractSignedAt", "Shartnoma sanasi", "DATE"),
    _f("prepaymentPercent", "Oldindan to'lov %", "NUMBER"),
    _f("paymentStatus", "To'lov holati", "SELECT", _opts(
        "To'lanmagan", "Avans to'landi", "Qisman", "To'liq to'landi")),
    _f("lostReason", "Yo'qotish sababi", "SELECT", _opts(
        "Narx qimmat", "Raqobatchi tanlandi", "Javob bermadi", "Loyiha bekor", "Muddat to'g'ri kelmadi",
        "Byudjet yo'q", "Sifatsiz lid", "Boshqa")),
    _f("competitor", "Raqobatchi", "TEXT"),
    _f("driveFolder", "Google Drive papka", "LINKS"),
    # Jon CRM (amoCRM 1:1 Frontend <-> Twenty Backend Bridge Fields)
    _f("pipelineId", "Voronka ID", "NUMBER"),
    _f("amoStatusId", "amoCRM Status ID", "NUMBER"),
    _f("statusSlug", "Bosqich Slug", "TEXT"),
    _f("responsibleUserId", "Masul Xodim ID", "NUMBER"),
    _f("responsibleName", "Masul Xodim Ismi", "TEXT"),
    _f("contactName", "Kontakt Ismi", "TEXT"),
    _f("companyName", "Kompaniya Nomi", "TEXT"),
    _f("contactPhone", "Telefon Raqami", "TEXT"),
    _f("tagsJson", "Teglar JSON", "TEXT"),
    _f("customFieldsJson", "BANT SPIN JSON", "TEXT"),
    _f("filesJson", "Fayllar JSON", "TEXT"),
    _f("aiAnalysisJson", "AI Tahlil JSON", "TEXT"),
    _f("lastAudioUrl", "Oxirgi Audio Havolasi", "TEXT"),
    _f("lastAudioDuration", "Audio Davomiyligi", "NUMBER"),
    _f("callsCount", "Qongiroqlar Soni", "NUMBER"),
]

COMPANY_FIELDS: List[Dict[str, Any]] = [
    _f("industry", "Soha", "SELECT", _opts(
        "Oziq-ovqat", "Restoran / HoReCa", "Chakana savdo", "Qurilish / Ko'chmas mulk", "Ta'lim",
        "Tibbiyot", "IT", "Ishlab chiqarish", "Moliya", "Go'zallik", "Logistika", "Boshqa")),
    _f("stir", "STIR (INN)", "TEXT"),
    _f("region", "Hudud", "TEXT"),
    _f("instagram", "Instagram", "LINKS"),
    _f("telegram", "Telegram", "LINKS"),
    _f("brandStage", "Brend holati", "SELECT", _opts(
        "Yangi biznes", "Brend yangilash", "Rivojlangan brend")),
    _f("tags", "Teglar", "MULTI_SELECT", TAGS),
]

PERSON_FIELDS: List[Dict[str, Any]] = [
    _f("position", "Lavozim", "TEXT"),
    _f("telegramUsername", "Telegram", "TEXT"),
    _f("preferredChannel", "Afzal kanal", "SELECT", _opts(
        "Telegram", "Qo'ng'iroq", "Instagram", "WhatsApp", "Email")),
    _f("birthday", "Tug'ilgan kun", "DATE"),
    _f("tags", "Teglar", "MULTI_SELECT", TAGS),
]

SCHEMA: Dict[str, List[Dict[str, Any]]] = {
    "opportunity": OPPORTUNITY_FIELDS,
    "company": COMPANY_FIELDS,
    "person": PERSON_FIELDS,
}


async def _get_objects(client: httpx.AsyncClient, twenty: TwentyClient) -> List[Dict[str, Any]]:
    res = await client.get(f"{twenty.base_url}/rest/metadata/objects", headers=twenty._headers())
    res.raise_for_status()
    data = res.json().get("data", [])
    if isinstance(data, dict):
        data = data.get("objects", [])
    return data if isinstance(data, list) else []


def _existing_field_names(obj: Dict[str, Any]) -> set:
    fields = obj.get("fields") or []
    if isinstance(fields, dict):  # GraphQL-style edges
        fields = [e.get("node", {}) for e in fields.get("edges", [])]
    return {f.get("name") for f in fields}


async def ensure_schema(twenty: TwentyClient, dry_run: bool = True) -> List[Tuple[str, str, str]]:
    """Yetishmagan maydonlarni yaratadi. Natija: (object, field, status) ro'yxati."""
    report: List[Tuple[str, str, str]] = []
    async with httpx.AsyncClient(timeout=twenty.timeout) as client:
        objects = {o.get("nameSingular"): o for o in await _get_objects(client, twenty)}
        for obj_name, fields in SCHEMA.items():
            obj = objects.get(obj_name)
            if not obj:
                report.append((obj_name, "*", "object topilmadi"))
                continue
            existing = _existing_field_names(obj)
            for field in fields:
                if field["name"] in existing:
                    report.append((obj_name, field["name"], "bor"))
                    continue
                if dry_run:
                    report.append((obj_name, field["name"], "yaratiladi"))
                    continue
                body = {**field, "objectMetadataId": obj["id"]}
                res = await client.post(
                    f"{twenty.base_url}/rest/metadata/fields", headers=twenty._headers(), json=body
                )
                status = "yaratildi" if res.status_code < 300 else f"xato {res.status_code}: {res.text[:160]}"
                report.append((obj_name, field["name"], status))
    return report
