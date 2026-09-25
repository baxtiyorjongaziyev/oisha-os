"""Executive Google Sheets integration for Meta Lead Ads (Target Leads)."""
from __future__ import annotations

import datetime
import os
import re
from typing import Any, Dict, List, Optional
import structlog

logger = structlog.get_logger("MetaLeadgenSheets")

DEFAULT_GSHEET_ID = "1aWmfomtd2x4QoHQIWLPD88lHbepIRvuPhzuugM7-vEc"
OUTSOURCE_WORKSHEET_TITLE = "Gaplashilmagan Leadlar (UTC Outsource)"
OUTSOURCE_WORKSHEET_GID = 123739873
INHOUSE_WORKSHEET_TITLE = "Target Leads Inhouse (Sentabr)"
INHOUSE_WORKSHEET_GID = 307647876
LEGACY_TARGET_WORKSHEET_TITLE = "Target Leads (Sentabr)"
DEFAULT_WORKSHEET_TITLE = OUTSOURCE_WORKSHEET_TITLE

HEADERS = [
    "№",
    "Sana va Vaqt",
    "Mijoz Ismi",
    "Telefon raqami",
    "Faoliyat sohasi",
    "Tadbirkorlik holati",
    "Asosiy maqsad",
    "Brend nomi",
    "AmoCRM Bitimi",
    "Forma / Kampaniya",
    "Barcha savol-javoblar",
    "Meta Lead ID",
]

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def clean_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw or "")
    if digits.startswith("998") and len(digits) == 12:
        return f"'+{digits[0:3]} ({digits[3:5]}) {digits[5:8]}-{digits[8:10]}-{digits[10:12]}"
    if len(digits) == 9:
        return f"'+998 ({digits[0:2]}) {digits[2:5]}-{digits[5:7]}-{digits[7:9]}"
    val = (raw or "").strip()
    return f"'{val}" if val.startswith("+") else val


def humanize_stage(raw: str) -> str:
    val = (raw or "").lower().replace("_", " ").strip()
    if "mahsulot" in val:
        return "Mahsulot bor (brend ochiq)"
    if "yangi" in val:
        return "Yangi biznes boshlash"
    if "rebrend" in val:
        return "Rebrending qilish"
    if "rivoj" in val:
        return "Brendni rivojlantirish"
    return raw.replace("_", " ").title() if raw else "—"


def humanize_goal(raw: str) -> str:
    val = (raw or "").lower().replace("_", " ").strip()
    if "himoya" in val or "patent" in val:
        return "Patentlash va Himoya"
    if "nom" in val or "naming" in val:
        return "Naming tekshiruvi"
    if "savdo" in val or "kengay" in val:
        return "Savdoni oshirish"
    if "imij" in val or "premium" in val:
        return "Premium imij"
    if "rebrend" in val:
        return "Rebrending"
    return raw.replace("_", " ").title() if raw else "—"


def humanize_sector(raw: str) -> str:
    val = (raw or "").lower().replace("_", " ").strip()
    if "savdo" in val or "magazin" in val or "do'kon" in val:
        return "Savdo"
    if "ishlab" in val or "zavod" in val or "fabrika" in val:
        return "Ishlab chiqarish"
    if "xizmat" in val or "servis" in val:
        return "Xizmat ko'rsatish"
    if "ta'lim" in val or "talim" in val or "maktab" in val:
        return "Ta'lim"
    if "boshqa" in val:
        return "Boshqa soha"
    return raw.replace("_", " ").title() if raw else "—"


def humanize_form(raw: str) -> str:
    val = (raw or "").lower()
    if "patent" in val:
        return "Patent Brend (12.09)"
    if "jakhongir" in val:
        return "Lead Form 1"
    return raw.split("|")[0].strip() if "|" in raw else (raw or "").strip()


def _get_creds_path() -> str:
    from pathlib import Path
    from src.settings import settings

    configured = getattr(settings, "GSHEET_CREDS_FILE", None) or os.getenv("GSHEET_CREDS_FILE")
    if configured and os.path.exists(configured):
        return configured
    candidate = Path(__file__).resolve().parents[4] / "data" / "service_account.json"
    if candidate.exists():
        return str(candidate)
    for c in ("data/service_account.json", "service_account.json", "/home/ubuntu/oisha-os/data/service_account.json"):
        if os.path.exists(c):
            return c
    return str(candidate)


def get_leadgen_spreadsheet(spreadsheet_id: Optional[str] = None):
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError as e:
        logger.warning("[GSHEET] gspread or google-auth not installed", error=str(e))
        return None

    from src.settings import settings

    sheet_id = (
        spreadsheet_id
        or getattr(settings, "TARGET_LEADS_GSHEET_ID", None)
        or os.getenv("TARGET_LEADS_GSHEET_ID")
        or DEFAULT_GSHEET_ID
    )
    creds_path = _get_creds_path()

    if not os.path.exists(creds_path):
        logger.warning("[GSHEET] Service account credentials not found", path=creds_path)
        return None

    try:
        creds = Credentials.from_service_account_file(creds_path, scopes=_SCOPES)
        client = gspread.authorize(creds)
        return client.open_by_key(sheet_id)
    except Exception as exc:
        logger.error("[GSHEET] Failed to open spreadsheet", error=str(exc), sheet_id=sheet_id)
        return None


def ensure_leadgen_worksheet(sh, title: str = DEFAULT_WORKSHEET_TITLE):
    try:
        return sh.worksheet(title)
    except Exception:
        pass

    try:
        t_low = title.lower()
        worksheets = sh.worksheets()

        # Pass 1: exact GID match wins outright, so a legacy tab that merely
        # shares words with the target title (e.g. "Target Leads (Sentabr)")
        # can never shadow the dedicated in-house/outsource destination.
        for ws in worksheets:
            ws_id = str(getattr(ws, "id", ""))
            if ws_id == str(OUTSOURCE_WORKSHEET_GID) and ("outsource" in t_low or "gaplashilmagan" in t_low):
                return ws
            if ws_id == str(INHOUSE_WORKSHEET_GID) and ("inhouse" in t_low or "target" in t_low):
                return ws

        # Pass 2: fall back to fuzzy title matching only if no GID matched.
        for ws in worksheets:
            ws_title = ws.title.lower()
            if title.lower() in ws_title or ws_title in title.lower():
                return ws
            if "inhouse" in t_low and "inhouse" in ws_title:
                return ws
            if "target leads" in ws_title and "target leads" in t_low:
                return ws
    except Exception:
        pass

    try:
        ws = sh.add_worksheet(title=title, rows=2000, cols=len(HEADERS) + 2)
        ws.append_row(HEADERS)
        try:
            ws.format("A1:L1", {"textFormat": {"bold": True}})
            ws.freeze(rows=1)
        except Exception:
            pass
        return ws
    except Exception as exc:
        logger.error("[GSHEET] Failed to create worksheet", title=title, error=str(exc))
        try:
            return sh.get_worksheet(0)
        except Exception:
            return None


def _extract_summary_fields(fields: Dict[str, str]) -> Dict[str, str]:
    from src.services.core.instagram.leadgen_router import (
        _pick_name,
        _pick_phone,
        _is_name_field,
        _is_phone_field,
    )

    name = _pick_name(fields)
    phone = _pick_phone(fields)

    sector, stage, goal, brand = "", "", "", ""
    qa_list: List[str] = []

    for k, v in fields.items():
        k_lower = k.lower()
        if not name and _is_name_field(k):
            name = v
        elif not phone and _is_phone_field(k):
            phone = v

        if any(w in k_lower for w in ("soha", "faoliyat")):
            sector = v
        elif any(w in k_lower for w in ("tadbirkorlik", "holat", "biznes_holati")):
            stage = v
        elif any(w in k_lower for w in ("maqsad", "patentlashdan")):
            goal = v
        elif any(w in k_lower for w in ("nomi", "brendingiz", "biznesingiz")):
            brand = v

        qa_list.append(f"{k}: {v}")

    return {
        "name": name,
        "phone": phone,
        "sector": sector,
        "stage": stage,
        "goal": goal,
        "brand": brand,
        "qa": " | ".join(qa_list),
    }


def format_lead_row(
    leadgen_id: str,
    lead_id: Optional[int],
    fields: Dict[str, str],
    form_name: str = "",
    created_time: str = "",
    is_outsource: bool = False,
    ad_name: Optional[str] = None,
    creative_url: Optional[str] = None,
) -> List[str]:
    summary = _extract_summary_fields(fields)
    if lead_id:
        amocrm_cell = f'=HYPERLINK("https://jonbranding.amocrm.ru/leads/detail/{lead_id}"; "🔗 #{lead_id}")'
    else:
        amocrm_cell = "—"

    if not created_time:
        created_time = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
    elif "-" in created_time:
        try:
            dt = datetime.datetime.strptime(created_time[:19], "%Y-%m-%d %H:%M:%S")
            created_time = dt.strftime("%d.%m.%Y %H:%M")
        except Exception:
            pass

    client_name = summary["name"].strip().title() if summary["name"] else "—"
    phone_clean = clean_phone(summary["phone"])
    soha = humanize_sector(summary["sector"])
    holat = humanize_stage(summary["stage"])
    maqsad = humanize_goal(summary["goal"])
    brand = summary["brand"].strip() if summary["brand"] and summary["brand"].strip().lower() not in ["yoq", "yo'q", "-", "a"] else "—"
    forma = humanize_form(form_name)

    if not creative_url and ad_name:
        from src.services.core.marketing.meta_ads_client import get_creative_url
        creative_url = get_creative_url(ad_name)

    if ad_name and creative_url:
        forma = f'=HYPERLINK("{creative_url}"; "🎬 {ad_name} | {forma}")'
    elif ad_name:
        forma = f"{ad_name} | {forma}"

    row = [
        "=ROW()-1",
        str(created_time),
        client_name,
        phone_clean,
        soha,
        holat,
        maqsad,
        brand,
        amocrm_cell,
        forma,
    ]
    if is_outsource:
        row.append("0 ta qo'ng'iroq")
    row.extend([summary["qa"], str(leadgen_id)])
    return row


def append_lead_to_sheet(
    leadgen_id: str,
    lead_id: Optional[int],
    fields: Dict[str, str],
    form_name: str = "",
    created_time: str = "",
    spreadsheet_id: Optional[str] = None,
    worksheet_title: Optional[str] = None,
    ad_name: Optional[str] = None,
    creative_url: Optional[str] = None,
    destination: str = "utc",
) -> bool:
    try:
        sh = get_leadgen_spreadsheet(spreadsheet_id)
        if not sh:
            return False

        if destination == "inhouse":
            target_title = worksheet_title or INHOUSE_WORKSHEET_TITLE
            is_outsource = False
        elif destination == "utc":
            target_title = worksheet_title or OUTSOURCE_WORKSHEET_TITLE
            is_outsource = True
        else:
            target_title = worksheet_title or OUTSOURCE_WORKSHEET_TITLE
            is_outsource = "outsource" in target_title.lower() or "gaplashilmagan" in target_title.lower()

        ws = ensure_leadgen_worksheet(sh, target_title)
        if not ws:
            logger.warning("[GSHEET] Worksheet not found or could not be created", title=target_title)
            return False

        row = format_lead_row(
            leadgen_id,
            lead_id,
            fields,
            form_name,
            created_time,
            is_outsource=is_outsource,
            ad_name=ad_name,
            creative_url=creative_url,
        )
        ws.append_row(row, value_input_option="USER_ENTERED")
        logger.info(
            "[GSHEET] Lead appended successfully",
            destination=destination,
            target=target_title,
            leadgen_id=leadgen_id,
            lead_id=lead_id,
        )
        return True
    except Exception as exc:
        logger.warning("[GSHEET] Failed to append lead to sheet", error=str(exc), leadgen_id=leadgen_id)
        return False
