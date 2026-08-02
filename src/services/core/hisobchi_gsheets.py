"""Hisobchi AI — Google Sheets storage backend."""

from __future__ import annotations

import asyncio
import datetime
import hashlib
import logging
import os
import re
from typing import Any, Optional

import gspread
from google.oauth2.service_account import Credentials

logger = logging.getLogger(__name__)

_GSHEET_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

SHEET_PUL_OQIMI = "Pul oqimi"
SHEET_SHAXSIY = "Shaxsiy"
SHEET_FOYDA_ZARAR = "Foyda/zarar"
SHEET_BALANS = "Balans"
SHEET_XOTIRA = "Xotira"
SHEET_QOIDALAR = "Qoidalar"
SHEET_QARZ = "Qarz"
SHEET_BYUDJET = "Byudjet"
SHEET_MAOSH = "Maosh"
SHEET_HISOBOT = "Hisobot"
SHEET_VALYUTA = "Valyuta"
SHEET_XODIMLAR = "Xodimlar"
SHEET_KASSA = "Kassa"

PUL_OQIMI_COLUMNS = [
    ("#", "id"),
    ("Sana", "date"),
    ("Yonalish", "direction"),
    ("Summa", "amount"),
    ("Valyuta", "currency"),
    ("Nomi", "merchant"),
    ("Kategoriya", "category"),
    ("Karta", "card_suffix"),
    ("Vaqt", "tx_time"),
    ("Qoldiq", "balance"),
    ("Izoh", "reason"),
    ("Holat", "status"),
    ("Manba", "source_bot"),
    ("Xabar", "raw_text"),
    ("Fingerprint", "fingerprint"),
    ("Xabar ID", "source_message_id"),
    ("Finansi chat ID", "finance_chat_id"),
    ("Finansi xabar ID", "finance_msg_id"),
]

SHAXSIY_COLUMNS = list(PUL_OQIMI_COLUMNS)

FOYDA_ZARAR_COLUMNS = [
    ("#", "id"),
    ("Davr", "period"),
    ("Biznes kirim", "business_income"),
    ("Biznes chiqim", "business_expense"),
    ("Biznes sof", "business_net"),
    ("Shaxsiy kirim", "personal_income"),
    ("Shaxsiy chiqim", "personal_expense"),
    ("Shaxsiy sof", "personal_net"),
    ("Yaratilgan", "created_at"),
]

BALANS_COLUMNS = [
    ("#", "id"),
    ("Karta raqami", "card_suffix"),
    ("Karta turi", "card_type"),
    ("Balans (UZS)", "balance"),
    ("Yangilangan", "updated_at"),
]

XOTIRA_COLUMNS = [
    ("#", "id"),
    ("Nomi", "merchant_pattern"),
    ("Kategoriya", "category"),
    ("Ishlatilgan", "use_count"),
    ("Yangilangan", "updated_at"),
]

QOIDALAR_COLUMNS = [
    ("#", "id"),
    ("Nomi", "merchant_pattern"),
    ("Karta", "card_suffix"),
    ("Yonalish", "direction"),
    ("Summa (UZS)", "amount"),
    ("Kategoriya", "category"),
    ("Tegishlilik", "ownership"),
    ("Tasdiqlar", "confirmations"),
    ("Ziddiyat", "conflicts"),
    ("Faol", "active"),
    ("Yangilangan", "updated_at"),
]

QARZ_COLUMNS = [
    ("#", "id"),
    ("Tur", "debt_type"),
    ("Kimdan/Kimga", "person"),
    ("Summa (UZS)", "amount"),
    ("Sana", "date"),
    ("Qaytgan (UZS)", "repaid"),
    ("Qoldiq (UZS)", "remaining"),
    ("Muddat", "due_date"),
    ("Izoh", "note"),
    ("Holat", "status"),
    ("Yangilangan", "updated_at"),
]

BYUDJET_COLUMNS = [
    ("#", "id"),
    ("Kategoriya", "category"),
    ("Oy", "period"),
    ("Limit (UZS)", "budget_limit"),
    ("Sarflangan (UZS)", "spent"),
    ("Qoldiq (UZS)", "remaining"),
    ("Holat", "status"),
    ("Yangilangan", "updated_at"),
]

MAOSH_COLUMNS = [
    ("#", "id"),
    ("Xodim", "employee_name"),
    ("Tur", "type"),
    ("Summa (UZS)", "amount"),
    ("Sana", "date"),
    ("Davr", "period"),
    ("Izoh", "note"),
    ("Holat", "status"),
    ("Yangilangan", "updated_at"),
]

VALYUTA_COLUMNS = [
    ("#", "id"),
    ("Valyuta", "currency"),
    ("Sotib olish", "buy_rate"),
    ("Sotish", "sell_rate"),
    ("Markaziy bank", "cb_rate"),
    ("Sana", "date"),
    ("Yangilangan", "updated_at"),
]

XODIMLAR_COLUMNS = [
    ("#", "id"),
    ("Ism", "name"),
    ("Rol", "role"),
    ("Telegram ID", "telegram_id"),
    ("Telefon", "phone"),
    ("Ruxsat", "permission"),
    ("Faol", "active"),
    ("Yangilangan", "updated_at"),
]

KASSA_COLUMNS = [
    ("#", "id"),
    ("Nomi", "name"),
    ("Valyuta", "currency"),
    ("Balans", "balance"),
    ("Turi", "type"),
    ("Izoh", "note"),
    ("Faol", "active"),
    ("Yangilangan", "updated_at"),
]

SHEET_CONFIG_DISPLAY = {
    SHEET_PUL_OQIMI: PUL_OQIMI_COLUMNS,
    SHEET_SHAXSIY: SHAXSIY_COLUMNS,
    SHEET_FOYDA_ZARAR: FOYDA_ZARAR_COLUMNS,
    SHEET_BALANS: BALANS_COLUMNS,
    SHEET_XOTIRA: XOTIRA_COLUMNS,
    SHEET_QOIDALAR: QOIDALAR_COLUMNS,
    SHEET_QARZ: QARZ_COLUMNS,
    SHEET_BYUDJET: BYUDJET_COLUMNS,
    SHEET_MAOSH: MAOSH_COLUMNS,
    SHEET_VALYUTA: VALYUTA_COLUMNS,
    SHEET_XODIMLAR: XODIMLAR_COLUMNS,
    SHEET_KASSA: KASSA_COLUMNS,
}

SHEET_HEADERS: dict[str, list[str]] = {}
SHEET_KEYS: dict[str, list[str]] = {}
SHEET_KEY_TO_HEADER: dict[str, dict[str, str]] = {}
SHEET_HEADER_TO_KEY: dict[str, dict[str, str]] = {}

for sheet_name, cols in SHEET_CONFIG_DISPLAY.items():
    headers = [c[0] for c in cols]
    keys = [c[1] for c in cols]
    SHEET_HEADERS[sheet_name] = headers
    SHEET_KEYS[sheet_name] = keys
    SHEET_KEY_TO_HEADER[sheet_name] = dict(cols)
    SHEET_HEADER_TO_KEY[sheet_name] = {h: k for h, k in cols}


def _normalize_card_suffix(card_suffix: str) -> str:
    digits = re.sub(r"\D", "", card_suffix or "")
    return digits[-4:]


def _normalize_merchant(merchant: str) -> str:
    cleaned = "".join(
        char if char.isalnum() or char in {" ", "'", "\u2018", "\u2019"} else " "
        for char in merchant.upper()
    )
    parts = cleaned.split()
    key_parts = [p for p in parts if len(p) > 2]
    if not key_parts:
        key_parts = parts
    return " ".join(key_parts[:3])


def _fingerprint(
    *,
    source_bot: str,
    direction: str,
    amount: int,
    merchant: str,
    card_suffix: str,
    tx_time: str,
    source_message_id: Optional[int] = None,
) -> str:
    if source_message_id is not None:
        canonical = (
            f"telegram-message|{source_bot.strip().lower()}|"
            f"{int(source_message_id)}"
        )
    else:
        canonical = "|".join(
            (
                source_bot.strip().lower(),
                direction.strip().lower(),
                str(int(amount)),
                _normalize_merchant(merchant),
                _normalize_card_suffix(card_suffix),
                " ".join((tx_time or "").split()),
            )
        )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _h2k(sheet: str, header: str) -> str:
    return SHEET_HEADER_TO_KEY[sheet].get(header, header)


def _k2h(sheet: str, key: str) -> str:
    return SHEET_KEY_TO_HEADER[sheet].get(key, key)


def _get(sheet: str, row: dict, key: str, default: Any = "") -> Any:
    h = _k2h(sheet, key)
    return row.get(h, default)


class HisobchiGsheetStore:
    def __init__(
        self,
        spreadsheet_id: str,
        credentials_path: str = "service_account.json",
    ):
        self.spreadsheet_id = spreadsheet_id
        self.credentials_path = credentials_path
        self.client: Optional[gspread.Client] = None
        self.spreadsheet: Optional[gspread.Spreadsheet] = None
        self._worksheets: dict[str, gspread.Worksheet] = {}
        self._next_ids: dict[str, int] = {}
        self._loaded = False

        self._cache_mm: dict[str, str] = {}
        self._cache_rules: list[dict[str, Any]] = []
        self._cache_fingerprints: set[str] = set()
        self._cache_transactions: dict[int, dict[str, Any]] = {}

        self._authenticate()
        self._ensure_worksheets()

    def _authenticate(self):
        if not os.path.exists(self.credentials_path):
            logger.warning(
                "[HISOBCHI-GS] Credentials fayli topilmadi: %s",
                self.credentials_path,
            )
            return
        try:
            creds = Credentials.from_service_account_file(
                self.credentials_path, scopes=_GSHEET_SCOPES
            )
            self.client = gspread.authorize(creds)
            if self.spreadsheet_id and self.client:
                self.spreadsheet = self.client.open_by_key(self.spreadsheet_id)
                logger.info(
                    "[HISOBCHI-GS] Spreadsheet ulandi: %s",
                    self.spreadsheet.title,
                )
        except Exception as exc:
            logger.error("[HISOBCHI-GS] Auth xatosi: %s", exc)

    def _ensure_worksheets(self):
        if not self.spreadsheet:
            return
        for title, headers in SHEET_HEADERS.items():
            try:
                ws = self.spreadsheet.worksheet(title)
            except gspread.exceptions.WorksheetNotFound:
                ws = self.spreadsheet.add_worksheet(
                    title=title, rows=1000, cols=len(headers)
                )
                ws.append_row(headers)
                logger.info("[HISOBCHI-GS] Sheet yaratildi: %s", title)
            else:
                existing = ws.row_values(1) or []
                if existing != headers:
                    if len(existing) < len(headers):
                        added = headers[len(existing):]
                        col_start = len(existing) + 1
                        for i, h in enumerate(added):
                            ws.update_cell(1, col_start + i, h)
                    else:
                        ws.clear()
                        ws.append_row(headers)
            self._worksheets[title] = ws
        self._ensure_hisobot()
        self._apply_formatting()

    def _ensure_hisobot(self):
        try:
            self._worksheets[SHEET_HISOBOT] = self.spreadsheet.worksheet(SHEET_HISOBOT)
            return
        except gspread.exceptions.WorksheetNotFound:
            pass
        ws = self.spreadsheet.add_worksheet(title=SHEET_HISOBOT, rows=50, cols=4)
        ws.update("A1:D1", [["📊 HISOBOT DASHBOARD", "", "", ""]])
        ws.merge_cells("A1:D1")
        ws.format("A1", {"textFormat": {"bold": True, "fontSize": 14}})
        ws.update("A3:D3", [["Joriy oy", '=TEXT(TODAY(),"YYYY-MM")', "", ""]])
        labels = [
            ("PUL OQIMI",),
            ("Biznes kirim", '=SUMIF(\'Pul oqimi\'!C:C,"Kirim",\'Pul oqimi\'!D:D)'),
            ("Biznes chiqim", '=SUMIF(\'Pul oqimi\'!C:C,"Chiqim",\'Pul oqimi\'!D:D)'),
            ("Biznes sof", '=IF(B5="","",B5-B6)'),
            ("Shaxsiy kirim", '=SUMIF(Shaxsiy!C:C,"Kirim",Shaxsiy!D:D)'),
            ("Shaxsiy chiqim", '=SUMIF(Shaxsiy!C:C,"Chiqim",Shaxsiy!D:D)'),
            ("Shaxsiy sof", '=IF(B8="","",B8-B9)'),
            ("",),
            ("QARZ & BYUDJET",),
            ("Faol qarz qoldig'i", '=SUMIF(Qarz!G:G,">0",Qarz!G:G)'),
            ("Byudjetdan oshgan", '=COUNTIF(Byudjet!G:G,"<0")'),
            ("Oylik maosh", '=SUMIF(Maosh!F:F,A3,Maosh!D:D)'),
        ]
        for i, row in enumerate(labels, start=5):
            if len(row) == 1:
                ws.update(f"A{i}:A{i}", [[row[0]]])
                ws.format(f"A{i}", {"textFormat": {"bold": True}})
            else:
                ws.update(f"A{i}:B{i}", [list(row)])
        ws.format("A5:B16", {"numberFormat": {"type": "NUMBER", "pattern": "#,##0"}})
        self._worksheets[SHEET_HISOBOT] = ws
        logger.info("[HISOBCHI-GS] Hisobot dashboard yaratildi")

    def _apply_formatting(self):
        if not self.spreadsheet:
            return
        try:
            requests = []
            for title in SHEET_HEADERS:
                ws = self._worksheets.get(title)
                if not ws:
                    continue
                sid = ws.id
                num_cols = len(SHEET_HEADERS[title])

                requests.append({
                    "updateSheetProperties": {
                        "properties": {
                            "sheetId": sid,
                            "gridProperties": {"frozenRowCount": 1}
                        },
                        "fields": "gridProperties.frozenRowCount"
                    }
                })

                requests.append({
                    "repeatCell": {
                        "range": {
                            "sheetId": sid, "startRowIndex": 0, "endRowIndex": 1,
                            "startColumnIndex": 0, "endColumnIndex": num_cols,
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "textFormat": {"bold": True, "fontSize": 10},
                                "backgroundColor": {"red": 0.18, "green": 0.2, "blue": 0.27},
                                "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
                                "horizontalAlignment": "CENTER",
                            }
                        },
                        "fields": "userEnteredFormat(textFormat,backgroundColor,horizontalAlignment)"
                    }
                })

                requests.append({
                    "addBanding": {
                        "bandedRange": {
                            "range": {
                                "sheetId": sid,
                                "startRowIndex": 1, "startColumnIndex": 0,
                                "endColumnIndex": num_cols,
                            },
                            "rowProperties": {
                                "firstBandColor": {"red": 0.97, "green": 0.97, "blue": 0.97},
                                "secondBandColor": {"red": 1, "green": 1, "blue": 1},
                                "headerColor": {"red": 0.9, "green": 0.9, "blue": 0.9},
                            }
                        }
                    }
                })

                requests.append({
                    "updateSheetProperties": {
                        "properties": {
                            "sheetId": sid,
                            "gridProperties": {"columnCount": num_cols}
                        },
                        "fields": "gridProperties.columnCount"
                    }
                })

                if title in (SHEET_PUL_OQIMI, SHEET_SHAXSIY):
                    requests.append({
                        "addConditionalFormatRule": {
                            "rule": {
                                "ranges": [{
                                    "sheetId": sid,
                                    "startRowIndex": 1, "startColumnIndex": 2, "endColumnIndex": 3,
                                }],
                                "booleanRule": {
                                    "condition": {
                                        "type": "TEXT_EQ",
                                        "values": [{"userEnteredValue": "Kirim"}]
                                    },
                                    "format": {
                                        "backgroundColor": {"red": 0.78, "green": 0.92, "blue": 0.78},
                                        "textFormat": {"bold": True, "foregroundColor": {"red": 0, "green": 0.4, "blue": 0}}
                                    }
                                }
                            }
                        }
                    })
                    requests.append({
                        "addConditionalFormatRule": {
                            "rule": {
                                "ranges": [{
                                    "sheetId": sid,
                                    "startRowIndex": 1, "startColumnIndex": 2, "endColumnIndex": 3,
                                }],
                                "booleanRule": {
                                    "condition": {
                                        "type": "TEXT_EQ",
                                        "values": [{"userEnteredValue": "Chiqim"}]
                                    },
                                    "format": {
                                        "backgroundColor": {"red": 0.95, "green": 0.78, "blue": 0.78},
                                        "textFormat": {"bold": True, "foregroundColor": {"red": 0.5, "green": 0, "blue": 0}}
                                    }
                                }
                            }
                        }
                    })
                    # Holat (col K=10): pending → yellow, categorized → green
                    requests.append({
                        "addConditionalFormatRule": {
                            "rule": {
                                "ranges": [{"sheetId": sid, "startRowIndex": 1, "startColumnIndex": 10, "endColumnIndex": 11}],
                                "booleanRule": {
                                    "condition": {"type": "TEXT_EQ", "values": [{"userEnteredValue": "pending"}]},
                                    "format": {"backgroundColor": {"red": 1, "green": 1, "blue": 0.7}}
                                }
                            }
                        }
                    })
                    requests.append({
                        "addConditionalFormatRule": {
                            "rule": {
                                "ranges": [{"sheetId": sid, "startRowIndex": 1, "startColumnIndex": 10, "endColumnIndex": 11}],
                                "booleanRule": {
                                    "condition": {"type": "TEXT_EQ", "values": [{"userEnteredValue": "categorized"}]},
                                    "format": {"backgroundColor": {"red": 0.78, "green": 0.92, "blue": 0.78}}
                                }
                            }
                        }
                    })
                    # Yonalish dropdown
                    requests.append({
                        "setDataValidation": {
                            "range": {"sheetId": sid, "startRowIndex": 1, "endRowIndex": 9999, "startColumnIndex": 2, "endColumnIndex": 3},
                            "rule": {
                                "condition": {"type": "ONE_OF_LIST", "values": [{"userEnteredValue": "Kirim"}, {"userEnteredValue": "Chiqim"}]},
                                "inputMessage": "Kirim yoki Chiqim", "showCustomUi": True,
                            }
                        }
                    })

                elif title == SHEET_QARZ:
                    # Qarz turi dropdown
                    requests.append({
                        "setDataValidation": {
                            "range": {"sheetId": sid, "startRowIndex": 1, "endRowIndex": 9999, "startColumnIndex": 1, "endColumnIndex": 2},
                            "rule": {
                                "condition": {"type": "ONE_OF_LIST", "values": [{"userEnteredValue": "Berilgan"}, {"userEnteredValue": "Olingan"}]},
                                "inputMessage": "Berilgan yoki Olingan", "showCustomUi": True,
                            }
                        }
                    })
                    # Qarz holati dropdown
                    requests.append({
                        "setDataValidation": {
                            "range": {"sheetId": sid, "startRowIndex": 1, "endRowIndex": 9999, "startColumnIndex": 9, "endColumnIndex": 10},
                            "rule": {
                                "condition": {"type": "ONE_OF_LIST", "values": [
                                    {"userEnteredValue": "faol"}, {"userEnteredValue": "yopilgan"}, {"userEnteredValue": "muddati o'tgan"}
                                ]},
                                "inputMessage": "Holatni tanlang", "showCustomUi": True,
                            }
                        }
                    })
                    # Conditional: remaining > 0 AND past due → red
                    requests.append({
                        "addConditionalFormatRule": {
                            "rule": {
                                "ranges": [{"sheetId": sid, "startRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": num_cols}],
                                "booleanRule": {
                                    "condition": {"type": "CUSTOM_FORMULA", "values": [{"userEnteredValue": "=AND(G2>0,H2<>\"\",H2<TODAY())"}]},
                                    "format": {"backgroundColor": {"red": 1, "green": 0.85, "blue": 0.85}}
                                }
                            }
                        }
                    })
                    # Qarz: to'langan → green highlight
                    requests.append({
                        "addConditionalFormatRule": {
                            "rule": {
                                "ranges": [{"sheetId": sid, "startRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": num_cols}],
                                "booleanRule": {
                                    "condition": {"type": "TEXT_EQ", "values": [{"userEnteredValue": "yopilgan"}]},
                                    "format": {"backgroundColor": {"red": 0.85, "green": 0.95, "blue": 0.85}}
                                }
                            }
                        }
                    })
                    # SPARKLINE for debt trend (use formula in a dedicated column header)
                    # Add "Trend" column as last col (M)
                    trend_col = num_cols + 1
                    try:
                        ws.update_cell(1, trend_col, "Trend (UZS)")
                    except Exception:
                        logger.error("Exception handled in %s", __name__, exc_info=True)

                elif title == SHEET_BYUDJET:
                    # Byudjet holati dropdown
                    requests.append({
                        "setDataValidation": {
                            "range": {"sheetId": sid, "startRowIndex": 1, "endRowIndex": 9999, "startColumnIndex": 6, "endColumnIndex": 7},
                            "rule": {
                                "condition": {"type": "ONE_OF_LIST", "values": [
                                    {"userEnteredValue": "yaxshi"}, {"userEnteredValue": "ogohlantirish"}, {"userEnteredValue": "yomon"}
                                ]},
                                "inputMessage": "Holatni tanlang", "showCustomUi": True,
                            }
                        }
                    })
                    # Conditional: yomon → red, ogohlantirish → yellow
                    requests.append({
                        "addConditionalFormatRule": {
                            "rule": {
                                "ranges": [{"sheetId": sid, "startRowIndex": 1, "startColumnIndex": 6, "endColumnIndex": 7}],
                                "booleanRule": {
                                    "condition": {"type": "TEXT_EQ", "values": [{"userEnteredValue": "yomon"}]},
                                    "format": {"backgroundColor": {"red": 1, "green": 0.8, "blue": 0.8}}
                                }
                            }
                        }
                    })
                    requests.append({
                        "addConditionalFormatRule": {
                            "rule": {
                                "ranges": [{"sheetId": sid, "startRowIndex": 1, "startColumnIndex": 6, "endColumnIndex": 7}],
                                "booleanRule": {
                                    "condition": {"type": "TEXT_EQ", "values": [{"userEnteredValue": "ogohlantirish"}]},
                                    "format": {"backgroundColor": {"red": 1, "green": 1, "blue": 0.7}}
                                }
                            }
                        }
                    })
                    # SPARKLINE for budget usage
                    try:
                        ws.update_cell(1, num_cols + 1, "Foyda %")
                        ws.update_cell(2, num_cols + 1, '=IF(E2>0,(D2/E2)*100,"")')
                    except Exception:
                        logger.error("Exception handled in %s", __name__, exc_info=True)

                elif title == SHEET_MAOSH:
                    requests.append({
                        "setDataValidation": {
                            "range": {"sheetId": sid, "startRowIndex": 1, "endRowIndex": 9999, "startColumnIndex": 2, "endColumnIndex": 3},
                            "rule": {
                                "condition": {"type": "ONE_OF_LIST", "values": [
                                    {"userEnteredValue": "Oylik"}, {"userEnteredValue": "Avans"}, {"userEnteredValue": "Bonus"}
                                ]},
                                "inputMessage": "Turini tanlang", "showCustomUi": True,
                            }
                        }
                    })
                    requests.append({
                        "setDataValidation": {
                            "range": {"sheetId": sid, "startRowIndex": 1, "endRowIndex": 9999, "startColumnIndex": 7, "endColumnIndex": 8},
                            "rule": {
                                "condition": {"type": "ONE_OF_LIST", "values": [
                                    {"userEnteredValue": "kutilmoqda"}, {"userEnteredValue": "to'langan"}, {"userEnteredValue": "bekor qilingan"}
                                ]},
                                "inputMessage": "Holatni tanlang", "showCustomUi": True,
                            }
                        }
                    })

                elif title == SHEET_VALYUTA:
                    requests.append({
                        "setDataValidation": {
                            "range": {"sheetId": sid, "startRowIndex": 1, "endRowIndex": 9999, "startColumnIndex": 1, "endColumnIndex": 2},
                            "rule": {
                                "condition": {"type": "ONE_OF_LIST", "values": [
                                    {"userEnteredValue": "USD"}, {"userEnteredValue": "EUR"},
                                    {"userEnteredValue": "RUB"}, {"userEnteredValue": "GBP"},
                                ]},
                                "inputMessage": "Valyutani tanlang", "showCustomUi": True,
                            }
                        }
                    })

                elif title == SHEET_XODIMLAR:
                    # Rol dropdown
                    requests.append({
                        "setDataValidation": {
                            "range": {"sheetId": sid, "startRowIndex": 1, "endRowIndex": 9999, "startColumnIndex": 2, "endColumnIndex": 3},
                            "rule": {
                                "condition": {"type": "ONE_OF_LIST", "values": [
                                    {"userEnteredValue": "Direktor"}, {"userEnteredValue": "Menejer"},
                                    {"userEnteredValue": "Dizayner"}, {"userEnteredValue": "SMM"},
                                    {"userEnteredValue": "Buxgalter"}, {"userEnteredValue": "Xodim"},
                                ]},
                                "inputMessage": "Rolni tanlang", "showCustomUi": True,
                            }
                        }
                    })
                    # Ruxsat dropdown
                    requests.append({
                        "setDataValidation": {
                            "range": {"sheetId": sid, "startRowIndex": 1, "endRowIndex": 9999, "startColumnIndex": 5, "endColumnIndex": 6},
                            "rule": {
                                "condition": {"type": "ONE_OF_LIST", "values": [
                                    {"userEnteredValue": "to'liq"}, {"userEnteredValue": "yozish"}, {"userEnteredValue": "kuzatish"}
                                ]},
                                "inputMessage": "Ruxsat darajasi", "showCustomUi": True,
                            }
                        }
                    })

                elif title == SHEET_KASSA:
                    # Wallet turi dropdown
                    requests.append({
                        "setDataValidation": {
                            "range": {"sheetId": sid, "startRowIndex": 1, "endRowIndex": 9999, "startColumnIndex": 4, "endColumnIndex": 5},
                            "rule": {
                                "condition": {"type": "ONE_OF_LIST", "values": [
                                    {"userEnteredValue": "Naqd"}, {"userEnteredValue": "Karta"},
                                    {"userEnteredValue": "Jamg'arma"}, {"userEnteredValue": "Valyuta"},
                                ]},
                                "inputMessage": "Turi", "showCustomUi": True,
                            }
                        }
                    })
                    # Conditional: balance < 0 → red
                    requests.append({
                        "addConditionalFormatRule": {
                            "rule": {
                                "ranges": [{"sheetId": sid, "startRowIndex": 1, "startColumnIndex": 2, "endColumnIndex": 4}],
                                "booleanRule": {
                                    "condition": {"type": "NUMBER_LESS", "values": [{"userEnteredValue": "0"}]},
                                    "format": {"backgroundColor": {"red": 1, "green": 0.8, "blue": 0.8}}
                                }
                            }
                        }
                    })

            aws = self._worksheets.get(SHEET_HISOBOT)
            if aws:
                aid = aws.id
                requests.append({
                    "updateSheetProperties": {
                        "properties": {"sheetId": aid, "gridProperties": {"frozenRowCount": 0}},
                        "fields": "gridProperties.frozenRowCount"
                    }
                })
                requests.append({
                    "addProtectedRange": {
                        "protectedRange": {
                            "range": {"sheetId": aid, "startRowIndex": 0, "endRowIndex": 50, "startColumnIndex": 0, "endColumnIndex": 4},
                            "description": "Hisobot — avtomatik formula maydoni",
                            "warningOnly": True,
                        }
                    }
                })

            if requests:
                try:
                    self.spreadsheet.batch_update({"requests": requests})
                    logger.info("[HISOBCHI-GS] Advanced formatting applied to %d sheets", len(requests))
                except Exception as batch_err:
                    logger.warning("[HISOBCHI-GS] Batch format error: %s — retrying individually", batch_err)
                    for req in requests:
                        try:
                            self.spreadsheet.batch_update({"requests": [req]})
                        except Exception:
                            logger.error("Exception handled in %s", __name__, exc_info=True)

            for title, ws in self._worksheets.items():
                if title == SHEET_QARZ:
                    try:
                        ws.format(f"1:{1}", {"textFormat": {"bold": True, "fontSize": 10}})
                    except Exception:
                        logger.error("Exception handled in %s", __name__, exc_info=True)
        except Exception as exc:
            logger.warning("[HISOBCHI-GS] Formatting skipped: %s", exc)

    def _load_cache(self):
        if self._loaded or not self.spreadsheet:
            return
        self._load_sheet_cache(SHEET_XOTIRA)
        self._load_sheet_cache(SHEET_QOIDALAR)
        self._load_sheet_cache(SHEET_PUL_OQIMI)
        self._load_sheet_cache(SHEET_SHAXSIY)
        for s in (SHEET_QARZ, SHEET_BYUDJET, SHEET_MAOSH, SHEET_FOYDA_ZARAR, SHEET_BALANS):
            self._load_sheet_cache(s)
        self._loaded = True

    def _load_sheet_cache(self, sheet_name: str):
        ws = self._worksheets.get(sheet_name)
        if not ws:
            return
        try:
            rows = ws.get_all_records()
        except Exception:
            logger.error("Exception handled in %s", __name__, exc_info=True)
            rows = []

        if sheet_name == SHEET_XOTIRA:
            self._cache_mm = {}
            for r in rows:
                pat = (_get(sheet_name, r, "merchant_pattern") or "").strip()
                cat = (_get(sheet_name, r, "category") or "").strip()
                if pat and cat:
                    self._cache_mm[pat] = cat
            self._next_ids[sheet_name] = len(rows) + 1

        elif sheet_name == SHEET_QOIDALAR:
            self._cache_rules = []
            for r in rows:
                self._cache_rules.append(r)
            self._next_ids[sheet_name] = len(rows) + 1

        elif sheet_name == SHEET_PUL_OQIMI:
            self._cache_fingerprints = set()
            self._cache_transactions = {}
            for r in rows:
                fp = (_get(sheet_name, r, "fingerprint") or "").strip()
                if fp:
                    self._cache_fingerprints.add(fp)
                rid = _get(sheet_name, r, "id")
                if rid:
                    try:
                        self._cache_transactions[int(rid)] = r
                    except (ValueError, TypeError):
                        pass
            self._next_ids[sheet_name] = len(rows) + 1

        elif sheet_name == SHEET_SHAXSIY:
            for r in rows:
                fp = (_get(sheet_name, r, "fingerprint") or "").strip()
                if fp:
                    self._cache_fingerprints.add(fp)
                rid = _get(sheet_name, r, "id")
                if rid:
                    try:
                        self._cache_transactions[int(rid)] = r
                    except (ValueError, TypeError):
                        pass
            self._next_ids[sheet_name] = len(rows) + 1

        elif sheet_name in (SHEET_FOYDA_ZARAR, SHEET_BALANS, SHEET_QARZ, SHEET_BYUDJET, SHEET_MAOSH):
            self._next_ids[sheet_name] = len(rows) + 1

    def _next_id(self, sheet_name: str) -> int:
        nid = self._next_ids.get(sheet_name, 1)
        self._next_ids[sheet_name] = nid + 1
        return nid

    def _append_row(self, sheet_name: str, values: dict) -> Optional[int]:
        ws = self._worksheets.get(sheet_name)
        if not ws:
            return None
        keys = SHEET_KEYS[sheet_name]
        row = [str(values.get(k, "")) for k in keys]
        try:
            ws.append_row(row, value_input_option="USER_ENTERED")
            return len(row)
        except Exception as exc:
            logger.error("[HISOBCHI-GS] Append error %s: %s", sheet_name, exc)
            return None

    def _find_row_by_col(
        self, ws: gspread.Worksheet, col_name: str, value: Any
    ) -> Optional[int]:
        headers = ws.row_values(1)
        if col_name not in headers:
            return None
        col_idx = headers.index(col_name) + 1
        try:
            cell = ws.find(str(value), in_column=col_idx)
            return cell.row if cell else None
        except Exception:
            logger.error("Exception handled in %s", __name__, exc_info=True)
            return None

    def _update_row(self, sheet_name: str, row_num: int, values: dict):
        ws = self._worksheets.get(sheet_name)
        if not ws:
            return
        headers = SHEET_HEADERS[sheet_name]
        keys = SHEET_KEYS[sheet_name]
        row = [str(values.get(k, "")) for k in keys]
        col_letter = chr(64 + min(len(headers), 26))
        try:
            ws.update(f"A{row_num}:{col_letter}{row_num}", [row])
        except Exception as exc:
            logger.error("[HISOBCHI-GS] Update error: %s", exc)

    # ── PUBLIC API ──────────────────────────────────────────────────────────

    async def init(self):
        await asyncio.to_thread(self._load_cache)

    async def reset_learning_and_transactions(self) -> None:
        """Full reset: clear Pul oqimi, Xotira, Qoidalar (keep headers only),
        then reload every in-memory cache from the now-cleared sheets."""
        if not self.spreadsheet:
            return
        for title in (SHEET_PUL_OQIMI, SHEET_XOTIRA, SHEET_QOIDALAR):
            ws = self._worksheets.get(title)
            if not ws:
                continue
            try:
                headers = ws.row_values(1)
                ws.clear()
                if headers:
                    ws.append_row(headers)
            except Exception as exc:
                logger.error("[HISOBCHI-GS] Failed to clear sheet %s: %s", title, exc)
        self._loaded = False
        self._load_cache()
        logger.info("[HISOBCHI-GS] Reset: Pul oqimi, Xotira, Qoidalar cleared.")

    # ── Merchant Memory ────────────────────────────────────────────────────

    async def get_known_category(self, merchant: str) -> Optional[str]:
        if not self._loaded:
            self._load_cache()
        return self._cache_mm.get(_normalize_merchant(merchant))

    async def learn_category(self, merchant: str, category: str) -> None:
        pat = _normalize_merchant(merchant)
        if pat in self._cache_mm:
            self._cache_mm[pat] = category
            ws = self._worksheets.get(SHEET_XOTIRA)
            if ws:
                row = self._find_row_by_col(
                    ws, _k2h(SHEET_XOTIRA, "merchant_pattern"), pat
                )
                if row:
                    self._update_row(SHEET_XOTIRA, row, {
                        "merchant_pattern": pat,
                        "category": category,
                    })
                    return
        self._cache_mm[pat] = category
        nid = self._next_id(SHEET_XOTIRA)
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._append_row(SHEET_XOTIRA, {
            "id": nid, "merchant_pattern": pat, "category": category,
            "use_count": 1, "updated_at": now,
        })

    # ── Category Rules ─────────────────────────────────────────────────────

    async def get_known_rule(
        self, merchant: str, card_suffix: str, direction: str, amount: int
    ) -> Optional[dict]:
        if not self._loaded:
            self._load_cache()
        pat = _normalize_merchant(merchant)
        suf = _normalize_card_suffix(card_suffix)
        for r in self._cache_rules:
            if (
                (_get(SHEET_QOIDALAR, r, "merchant_pattern") or "").strip() == pat
                and (_get(SHEET_QOIDALAR, r, "card_suffix") or "").strip() == suf
                and (_get(SHEET_QOIDALAR, r, "direction") or "").strip() == direction
                and str(_get(SHEET_QOIDALAR, r, "amount") or "0").strip() == str(amount)
                and str(_get(SHEET_QOIDALAR, r, "active") or "1").strip() == "1"
                and str(_get(SHEET_QOIDALAR, r, "conflicts") or "0").strip() == "0"
                and int(_get(SHEET_QOIDALAR, r, "confirmations") or 0) >= 1
            ):
                return {
                    "category": (_get(SHEET_QOIDALAR, r, "category") or "").strip(),
                    "ownership": (_get(SHEET_QOIDALAR, r, "ownership") or "business").strip(),
                }
        return None

    async def learn_rule(
        self,
        *,
        merchant: str,
        card_suffix: str,
        direction: str,
        amount: int,
        category: str,
        ownership: str,
    ) -> None:
        pat = _normalize_merchant(merchant)
        suf = _normalize_card_suffix(card_suffix)
        ws = self._worksheets.get(SHEET_QOIDALAR)
        if not ws:
            return

        rows = ws.get_all_records()
        found = None
        for i, r in enumerate(rows):
            if (
                (_get(SHEET_QOIDALAR, r, "merchant_pattern") or "").strip() == pat
                and (_get(SHEET_QOIDALAR, r, "card_suffix") or "").strip() == suf
                and (_get(SHEET_QOIDALAR, r, "direction") or "").strip() == direction
                and str(_get(SHEET_QOIDALAR, r, "amount") or "").strip() == str(amount)
            ):
                found = (i + 2, r)
                break

        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if found:
            row_num, existing = found
            existing_cat = (_get(SHEET_QOIDALAR, existing, "category") or "").strip()
            existing_own = (_get(SHEET_QOIDALAR, existing, "ownership") or "business").strip()
            if existing_cat != category or existing_own != ownership:
                conflicts = int(_get(SHEET_QOIDALAR, existing, "conflicts") or 0) + 1
                self._update_row(SHEET_QOIDALAR, row_num, {
                    "merchant_pattern": pat, "card_suffix": suf,
                    "direction": direction, "amount": int(amount),
                    "category": existing_cat, "ownership": existing_own,
                    "confirmations": int(_get(SHEET_QOIDALAR, existing, "confirmations") or 1),
                    "conflicts": conflicts, "active": 0, "updated_at": now,
                })
                for r in self._cache_rules:
                    if (
                        (_get(SHEET_QOIDALAR, r, "merchant_pattern") or "").strip() == pat
                        and (_get(SHEET_QOIDALAR, r, "card_suffix") or "").strip() == suf
                    ):
                        r[_k2h(SHEET_QOIDALAR, "conflicts")] = str(conflicts)
                        r[_k2h(SHEET_QOIDALAR, "active")] = "0"
            else:
                confirmations = int(_get(SHEET_QOIDALAR, existing, "confirmations") or 1) + 1
                self._update_row(SHEET_QOIDALAR, row_num, {
                    "merchant_pattern": pat, "card_suffix": suf,
                    "direction": direction, "amount": int(amount),
                    "category": category, "ownership": ownership,
                    "confirmations": confirmations, "conflicts": 0,
                    "active": 1, "updated_at": now,
                })
        else:
            nid = self._next_id(SHEET_QOIDALAR)
            self._append_row(SHEET_QOIDALAR, {
                "id": nid, "merchant_pattern": pat, "card_suffix": suf,
                "direction": direction, "amount": int(amount),
                "category": category, "ownership": ownership,
                "confirmations": 1, "conflicts": 0, "active": 1,
                "updated_at": now,
            })
            self._cache_rules.append({
                _k2h(SHEET_QOIDALAR, "merchant_pattern"): pat,
                _k2h(SHEET_QOIDALAR, "card_suffix"): suf,
                _k2h(SHEET_QOIDALAR, "direction"): direction,
                _k2h(SHEET_QOIDALAR, "amount"): str(amount),
                _k2h(SHEET_QOIDALAR, "category"): category,
                _k2h(SHEET_QOIDALAR, "ownership"): ownership,
                _k2h(SHEET_QOIDALAR, "confirmations"): "1",
                _k2h(SHEET_QOIDALAR, "conflicts"): "0",
                _k2h(SHEET_QOIDALAR, "active"): "1",
                _k2h(SHEET_QOIDALAR, "updated_at"): now,
            })

    # ── Fingerprint ────────────────────────────────────────────────────────

    def transaction_fingerprint(
        self,
        *,
        source_bot: str,
        direction: str,
        amount: int,
        merchant: str,
        card_suffix: str,
        tx_time: str,
        source_message_id: Optional[int] = None,
    ) -> str:
        return _fingerprint(
            source_bot=source_bot, direction=direction, amount=amount,
            merchant=merchant, card_suffix=card_suffix, tx_time=tx_time,
            source_message_id=source_message_id,
        )

    async def transaction_exists(self, fingerprint: str) -> bool:
        if not self._loaded:
            self._load_cache()
        return fingerprint in self._cache_fingerprints

    # ── Transactions ──────────────────────────────────────────────────────

    def _target_sheet(self, ownership: str) -> str:
        return SHEET_PUL_OQIMI if ownership == "business" else SHEET_SHAXSIY

    async def save_transaction(
        self,
        *,
        source_bot: str,
        direction: str,
        amount: int,
        merchant: str,
        card_suffix: str,
        tx_time: str,
        balance: Optional[int],
        raw_text: str,
        category: Optional[str] = None,
        ownership: str = "business",
        currency: str = "UZS",
        finance_msg_id: Optional[int] = None,
        finance_chat_id: Optional[int] = None,
        status: str = "pending",
        reason: Optional[str] = None,
        source_message_id: Optional[int] = None,
    ) -> int:
        tx_id, _ = await self.save_transaction_once(
            source_bot=source_bot, direction=direction, amount=amount,
            merchant=merchant, card_suffix=card_suffix, tx_time=tx_time,
            balance=balance, raw_text=raw_text, category=category,
            ownership=ownership, currency=currency,
            finance_msg_id=finance_msg_id,
            finance_chat_id=finance_chat_id, status=status,
            reason=reason, source_message_id=source_message_id,
        )
        return tx_id

    async def save_transaction_once(
        self,
        *,
        source_bot: str,
        direction: str,
        amount: int,
        merchant: str,
        card_suffix: str,
        tx_time: str,
        balance: Optional[int],
        raw_text: str,
        category: Optional[str] = None,
        ownership: str = "business",
        currency: str = "UZS",
        finance_msg_id: Optional[int] = None,
        finance_chat_id: Optional[int] = None,
        status: str = "pending",
        reason: Optional[str] = None,
        source_message_id: Optional[int] = None,
    ) -> tuple[int, bool]:
        fp = self.transaction_fingerprint(
            source_bot=source_bot, direction=direction, amount=amount,
            merchant=merchant, card_suffix=card_suffix, tx_time=tx_time,
            source_message_id=source_message_id,
        )

        if await self.transaction_exists(fp):
            return 0, False

        sheet = self._target_sheet(ownership)
        nid = self._next_id(sheet)
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        txn = {
            "id": nid,
            "date": now,
            "source_bot": source_bot,
            "direction": "Kirim" if direction == "in" else "Chiqim",
            "amount": int(amount),
            "currency": currency.upper(),
            "merchant": merchant,
            "card_suffix": card_suffix,
            "tx_time": tx_time,
            "balance": str(balance) if balance is not None else "",
            "category": category or "",
            "raw_text": raw_text,
            "status": status,
            "fingerprint": fp,
            "reason": reason or "",
            "source_message_id": str(source_message_id) if source_message_id else "",
        }
        self._append_row(sheet, txn)
        self._cache_fingerprints.add(fp)
        self._cache_transactions[nid] = txn

        # Auto-update budget spent
        if direction == "out" or direction == "Chiqim":
            cat = category or ""
            if cat:
                period_ = now[:7]  # "YYYY-MM" from "YYYY-MM-DD HH:MM:SS"
                total_spent = sum(
                    t.get("amount", 0) for t in self._cache_transactions.values()
                    if str(t.get("direction", "")).lower() in ("chiqim", "out")
                    and str(t.get("category", "")).lower() == cat.lower()
                    and str(t.get("date", "")).startswith(period_)
                )
                await self.update_budget_spent(period_, cat, total_spent)

        return nid, True

    async def update_finance_msg(
        self, tx_id: int, finance_msg_id: int, finance_chat_id: int
    ) -> None:
        pass

    async def categorize(
        self,
        tx_id: int,
        category: str,
        ownership: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> None:
        cached = self._cache_transactions.get(tx_id)
        if not cached:
            return
        sheet = self._target_sheet(cached.get("ownership", "business"))
        ws = self._worksheets.get(sheet)
        if not ws:
            return
        row = self._find_row_by_col(
            ws, _k2h(sheet, "id"), tx_id
        )
        if not row:
            return

        new_own = ownership or cached.get("ownership", "business")
        cached["category"] = category
        cached["ownership"] = new_own
        cached["status"] = "categorized"
        if reason:
            cached["reason"] = reason

        self._update_row(sheet, row, cached)

    async def skip(self, tx_id: int) -> None:
        cached = self._cache_transactions.get(tx_id)
        if not cached:
            return
        cached["status"] = "skipped"
        sheet = self._target_sheet(cached.get("ownership", "business"))
        ws = self._worksheets.get(sheet)
        if not ws:
            return
        row = self._find_row_by_col(
            ws, _k2h(sheet, "id"), tx_id
        )
        if not row:
            return
        self._update_row(sheet, row, cached)

    async def get_pending_by_finance_msg(
        self, finance_chat_id: int, finance_msg_id: int
    ) -> Optional[dict]:
        for tx in self._cache_transactions.values():
            if str(tx.get("status", "")) == "pending":
                return {
                    "id": tx["id"],
                    "merchant": tx["merchant"],
                    "card_suffix": tx.get("card_suffix", ""),
                    "direction": "out" if tx.get("direction") == "Chiqim" else "in",
                    "amount": tx.get("amount", 0),
                    "ownership": tx.get("ownership", "business"),
                    "category": tx.get("category", ""),
                    "reason": tx.get("reason", ""),
                    "status": tx["status"],
                }
        return None

    async def get_transaction_status(self, tx_id: int) -> Optional[str]:
        tx = self._cache_transactions.get(tx_id)
        return tx.get("status") if tx else None

    async def get_monthly_summary(self, period: str) -> dict:
        summary = {
            "business": {"income": 0, "expense": 0, "net": 0, "categories": {},
                         "usd_income": 0, "usd_expense": 0},
            "personal": {"income": 0, "expense": 0, "net": 0, "categories": {},
                         "usd_income": 0, "usd_expense": 0},
        }
        for tx in self._cache_transactions.values():
            tx_date = str(tx.get("date", ""))
            if not tx_date.startswith(period):
                continue
            own = tx.get("ownership", "business")
            if own not in summary:
                own = "business"
            direc = "in" if tx.get("direction") == "Kirim" else "out"
            try:
                total = int(tx.get("amount", 0))
            except (ValueError, TypeError):
                continue
            cur = str(tx.get("currency", "UZS")).upper()
            cat = tx.get("category") or "Nomalum"
            if direc == "in":
                summary[own]["income"] += total
                if cur == "USD":
                    summary[own]["usd_income"] += total
            else:
                summary[own]["expense"] += total
                if cur == "USD":
                    summary[own]["usd_expense"] += total
                summary[own]["categories"][cat] = (
                    summary[own]["categories"].get(cat, 0) + total
                )

        for own in ["business", "personal"]:
            summary[own]["net"] = summary[own]["income"] - summary[own]["expense"]
            summary[own]["categories"] = dict(
                sorted(summary[own]["categories"].items(), key=lambda x: -x[1])
            )
        return summary

    # ── P&L Sheet ──────────────────────────────────────────────────────────

    async def save_monthly_pnl(self, period: str, summary: dict) -> None:
        ws = self._worksheets.get(SHEET_FOYDA_ZARAR)
        if not ws:
            return
        b = summary.get("business", {})
        p = summary.get("personal", {})
        rows = ws.get_all_records()
        for i, r in enumerate(rows):
            if (_get(SHEET_FOYDA_ZARAR, r, "period") or "").strip() == period:
                row_num = i + 2
                self._update_row(SHEET_FOYDA_ZARAR, row_num, {
                    "id": _get(SHEET_FOYDA_ZARAR, r, "id"),
                    "period": period,
                    "business_income": b.get("income", 0),
                    "business_expense": b.get("expense", 0),
                    "business_net": b.get("net", 0),
                    "personal_income": p.get("income", 0),
                    "personal_expense": p.get("expense", 0),
                    "personal_net": p.get("net", 0),
                    "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                })
                return
        nid = self._next_id(SHEET_FOYDA_ZARAR)
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._append_row(SHEET_FOYDA_ZARAR, {
            "id": nid, "period": period,
            "business_income": b.get("income", 0),
            "business_expense": b.get("expense", 0),
            "business_net": b.get("net", 0),
            "personal_income": p.get("income", 0),
            "personal_expense": p.get("expense", 0),
            "personal_net": p.get("net", 0),
            "created_at": now,
        })

    # ── Balans Sheet ──────────────────────────────────────────────────────

    async def update_balance(
        self, card_suffix: str, card_type: str, balance: int
    ) -> None:
        ws = self._worksheets.get(SHEET_BALANS)
        if not ws:
            return
        rows = ws.get_all_records()
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for i, r in enumerate(rows):
            if (_get(SHEET_BALANS, r, "card_suffix") or "").strip() == card_suffix:
                row_num = i + 2
                self._update_row(SHEET_BALANS, row_num, {
                    "id": _get(SHEET_BALANS, r, "id"),
                    "card_suffix": card_suffix,
                    "card_type": card_type,
                    "balance": balance,
                    "updated_at": now,
                })
                return
        nid = self._next_id(SHEET_BALANS)
        self._append_row(SHEET_BALANS, {
            "id": nid, "card_suffix": card_suffix,
            "card_type": card_type, "balance": balance,
            "updated_at": now,
        })

    # ── Qarz (Debt) ──────────────────────────────────────────────────────────

    async def add_debt(
        self, debt_type: str, person: str, amount: int,
        date: str = "", due_date: str = "", note: str = "",
    ) -> int:
        ws = self._worksheets.get(SHEET_QARZ)
        if not ws:
            return 0
        nid = self._next_id(SHEET_QARZ)
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._append_row(SHEET_QARZ, {
            "id": nid, "debt_type": debt_type, "person": person,
            "amount": int(amount), "date": date or now,
            "repaid": 0, "remaining": int(amount),
            "due_date": due_date, "note": note,
            "status": "faol", "updated_at": now,
        })
        return nid

    async def get_debts(self, active_only: bool = True) -> list[dict]:
        ws = self._worksheets.get(SHEET_QARZ)
        if not ws:
            return []
        try:
            rows = ws.get_all_records()
        except Exception:
            logger.error("Exception handled in %s", __name__, exc_info=True)
            return []
        result = []
        for r in rows:
            status = _get(SHEET_QARZ, r, "status", "faol").strip().lower()
            if active_only and status not in ("faol", "muddati o'tgan"):
                continue
            result.append({
                "id": int(_get(SHEET_QARZ, r, "id", 0)),
                "debt_type": _get(SHEET_QARZ, r, "debt_type", ""),
                "person": _get(SHEET_QARZ, r, "person", ""),
                "amount": int(_get(SHEET_QARZ, r, "amount", 0)),
                "repaid": int(_get(SHEET_QARZ, r, "repaid", 0)),
                "remaining": int(_get(SHEET_QARZ, r, "remaining", 0)),
                "date": _get(SHEET_QARZ, r, "date", ""),
                "due_date": _get(SHEET_QARZ, r, "due_date", ""),
                "note": _get(SHEET_QARZ, r, "note", ""),
                "status": status,
            })
        return result

    async def repay_debt(self, debt_id: int, amount: int) -> Optional[dict]:
        ws = self._worksheets.get(SHEET_QARZ)
        if not ws:
            return None
        rows = ws.get_all_records()
        for i, r in enumerate(rows):
            rid = int(_get(SHEET_QARZ, r, "id", 0))
            if rid != debt_id:
                continue
            row_num = i + 2
            current_repaid = int(_get(SHEET_QARZ, r, "repaid", 0))
            total = int(_get(SHEET_QARZ, r, "amount", 0))
            new_repaid = current_repaid + int(amount)
            remaining = total - new_repaid
            status = "yopilgan" if remaining <= 0 else _get(SHEET_QARZ, r, "status", "faol")
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self._update_row(SHEET_QARZ, row_num, {
                "id": rid,
                "debt_type": _get(SHEET_QARZ, r, "debt_type", ""),
                "person": _get(SHEET_QARZ, r, "person", ""),
                "amount": total,
                "date": _get(SHEET_QARZ, r, "date", ""),
                "repaid": new_repaid,
                "remaining": max(0, remaining),
                "due_date": _get(SHEET_QARZ, r, "due_date", ""),
                "note": _get(SHEET_QARZ, r, "note", ""),
                "status": status,
                "updated_at": now,
            })
            return {"id": rid, "repaid": new_repaid, "remaining": max(0, remaining), "status": status}
        return None

    # ── Byudjet (Budget) ─────────────────────────────────────────────────────

    async def set_budget(
        self, category: str, period: str, budget_limit: int
    ) -> int:
        ws = self._worksheets.get(SHEET_BYUDJET)
        if not ws:
            return 0
        rows = ws.get_all_records()
        for i, r in enumerate(rows):
            if (_get(SHEET_BYUDJET, r, "category", "") == category
                and _get(SHEET_BYUDJET, r, "period", "") == period):
                row_num = i + 2
                now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self._update_row(SHEET_BYUDJET, row_num, {
                    "id": _get(SHEET_BYUDJET, r, "id"),
                    "category": category, "period": period,
                    "budget_limit": budget_limit,
                    "spent": _get(SHEET_BYUDJET, r, "spent", 0),
                    "remaining": budget_limit - int(_get(SHEET_BYUDJET, r, "spent", 0)),
                    "status": _get(SHEET_BYUDJET, r, "status", "yaxshi"),
                    "updated_at": now,
                })
                return int(_get(SHEET_BYUDJET, r, "id", 0))
        nid = self._next_id(SHEET_BYUDJET)
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._append_row(SHEET_BYUDJET, {
            "id": nid, "category": category, "period": period,
            "budget_limit": budget_limit, "spent": 0,
            "remaining": budget_limit, "status": "yaxshi",
            "updated_at": now,
        })
        return nid

    async def get_budget_status(self, period: str) -> list[dict]:
        ws = self._worksheets.get(SHEET_BYUDJET)
        if not ws:
            return []
        try:
            rows = ws.get_all_records()
        except Exception:
            logger.error("Exception handled in %s", __name__, exc_info=True)
            return []
        result = []
        for r in rows:
            if _get(SHEET_BYUDJET, r, "period", "") != period:
                continue
            result.append({
                "id": int(_get(SHEET_BYUDJET, r, "id", 0)),
                "category": _get(SHEET_BYUDJET, r, "category", ""),
                "period": _get(SHEET_BYUDJET, r, "period", ""),
                "budget_limit": int(_get(SHEET_BYUDJET, r, "budget_limit", 0)),
                "spent": int(_get(SHEET_BYUDJET, r, "spent", 0)),
                "remaining": int(_get(SHEET_BYUDJET, r, "remaining", 0)),
                "status": _get(SHEET_BYUDJET, r, "status", "yaxshi"),
            })
        return result

    async def update_budget_spent(self, period: str, category: str, spent: int) -> None:
        ws = self._worksheets.get(SHEET_BYUDJET)
        if not ws:
            return
        rows = ws.get_all_records()
        for i, r in enumerate(rows):
            if (_get(SHEET_BYUDJET, r, "category", "") == category
                and _get(SHEET_BYUDJET, r, "period", "") == period):
                row_num = i + 2
                limit = int(_get(SHEET_BYUDJET, r, "budget_limit", 0))
                remaining = limit - spent
                if remaining < 0:
                    status = "yomon"
                elif remaining < limit * 0.2:
                    status = "ogohlantirish"
                else:
                    status = "yaxshi"
                now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self._update_row(SHEET_BYUDJET, row_num, {
                    "id": _get(SHEET_BYUDJET, r, "id"),
                    "category": category, "period": period,
                    "budget_limit": limit, "spent": spent,
                    "remaining": max(0, remaining),
                    "status": status, "updated_at": now,
                })
                return

    # ── Maosh (Salary) ─────────────────────────────────────────────────────

    async def add_salary_entry(
        self, employee_name: str, entry_type: str, amount: int,
        period: str, note: str = "",
    ) -> int:
        ws = self._worksheets.get(SHEET_MAOSH)
        if not ws:
            return 0
        nid = self._next_id(SHEET_MAOSH)
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._append_row(SHEET_MAOSH, {
            "id": nid, "employee_name": employee_name,
            "type": entry_type, "amount": int(amount),
            "date": now, "period": period, "note": note,
            "status": "to'langan", "updated_at": now,
        })
        return nid

    async def get_salary_summary(self, period: str) -> dict:
        ws = self._worksheets.get(SHEET_MAOSH)
        if not ws:
            return {"total": 0, "oylik": 0, "avans": 0, "bonus": 0, "entries": []}
        try:
            rows = ws.get_all_records()
        except Exception:
            logger.error("Exception handled in %s", __name__, exc_info=True)
            return {"total": 0, "oylik": 0, "avans": 0, "bonus": 0, "entries": []}
        total = 0
        oylik = 0
        avans = 0
        bonus = 0
        entries = []
        for r in rows:
            if _get(SHEET_MAOSH, r, "period", "") != period:
                continue
            amt = int(_get(SHEET_MAOSH, r, "amount", 0))
            tp = _get(SHEET_MAOSH, r, "type", "").strip().lower()
            total += amt
            if tp == "oylik":
                oylik += amt
            elif tp == "avans":
                avans += amt
            elif tp == "bonus":
                bonus += amt
            entries.append({
                "id": int(_get(SHEET_MAOSH, r, "id", 0)),
                "employee": _get(SHEET_MAOSH, r, "employee_name", ""),
                "type": tp, "amount": amt,
                "note": _get(SHEET_MAOSH, r, "note", ""),
                "status": _get(SHEET_MAOSH, r, "status", ""),
            })
        return {"total": total, "oylik": oylik, "avans": avans, "bonus": bonus, "entries": entries}

    # ── VALYUTA (CURRENCY RATES) ────────────────────────────────────────────

    async def update_rate(
        self, currency: str, buy_rate: float, sell_rate: float, cb_rate: float = 0
    ) -> None:
        ws = self._worksheets.get(SHEET_VALYUTA)
        if not ws:
            return
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        rows = ws.get_all_records()
        for i, r in enumerate(rows):
            if _get(SHEET_VALYUTA, r, "currency", "").upper() == currency.upper():
                row_num = i + 2
                self._update_row(SHEET_VALYUTA, row_num, {
                    "id": _get(SHEET_VALYUTA, r, "id"),
                    "currency": currency.upper(),
                    "buy_rate": buy_rate,
                    "sell_rate": sell_rate,
                    "cb_rate": cb_rate,
                    "date": today,
                    "updated_at": now,
                })
                return
        nid = self._next_id(SHEET_VALYUTA)
        self._append_row(SHEET_VALYUTA, {
            "id": nid, "currency": currency.upper(),
            "buy_rate": buy_rate, "sell_rate": sell_rate,
            "cb_rate": cb_rate, "date": today, "updated_at": now,
        })

    async def get_rates(self) -> dict:
        ws = self._worksheets.get(SHEET_VALYUTA)
        if not ws:
            return {}
        try:
            rows = ws.get_all_records()
        except Exception:
            logger.error("Exception handled in %s", __name__, exc_info=True)
            return {}
        rates = {}
        for r in rows:
            cur = (_get(SHEET_VALYUTA, r, "currency") or "").upper()
            if cur:
                rates[cur] = {
                    "buy": float(_get(SHEET_VALYUTA, r, "buy_rate", 0)),
                    "sell": float(_get(SHEET_VALYUTA, r, "sell_rate", 0)),
                    "cb": float(_get(SHEET_VALYUTA, r, "cb_rate", 0)),
                    "date": _get(SHEET_VALYUTA, r, "date", ""),
                }
        return rates

    # ── XODIMLAR (EMPLOYEES / ROLES) ─────────────────────────────────────

    async def add_xodim(
        self, name: str, role: str, telegram_id: str = "", phone: str = "",
        permission: str = "kuzatish",
    ) -> int:
        ws = self._worksheets.get(SHEET_XODIMLAR)
        if not ws:
            return 0
        nid = self._next_id(SHEET_XODIMLAR)
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._append_row(SHEET_XODIMLAR, {
            "id": nid, "name": name, "role": role,
            "telegram_id": telegram_id, "phone": phone,
            "permission": permission, "active": "1", "updated_at": now,
        })
        return nid

    async def get_xodimlar(self, active_only: bool = True) -> list[dict]:
        ws = self._worksheets.get(SHEET_XODIMLAR)
        if not ws:
            return []
        try:
            rows = ws.get_all_records()
        except Exception:
            logger.error("Exception handled in %s", __name__, exc_info=True)
            return []
        result = []
        for r in rows:
            active = _get(SHEET_XODIMLAR, r, "active", "1")
            if active_only and str(active) != "1":
                continue
            result.append({
                "id": int(_get(SHEET_XODIMLAR, r, "id", 0)),
                "name": _get(SHEET_XODIMLAR, r, "name", ""),
                "role": _get(SHEET_XODIMLAR, r, "role", ""),
                "telegram_id": _get(SHEET_XODIMLAR, r, "telegram_id", ""),
                "phone": _get(SHEET_XODIMLAR, r, "phone", ""),
                "permission": _get(SHEET_XODIMLAR, r, "permission", "kuzatish"),
            })
        return result

    # ── KASSA (WALLETS / BALANCE TRANSFER) ───────────────────────────────

    async def add_kassa(
        self, name: str, currency: str = "UZS", balance: int = 0,
        wallet_type: str = "Naqd", note: str = "",
    ) -> int:
        ws = self._worksheets.get(SHEET_KASSA)
        if not ws:
            return 0
        nid = self._next_id(SHEET_KASSA)
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._append_row(SHEET_KASSA, {
            "id": nid, "name": name, "currency": currency.upper(),
            "balance": int(balance), "type": wallet_type,
            "note": note, "active": "1", "updated_at": now,
        })
        return nid

    async def get_kassa(self, active_only: bool = True) -> list[dict]:
        ws = self._worksheets.get(SHEET_KASSA)
        if not ws:
            return []
        try:
            rows = ws.get_all_records()
        except Exception:
            logger.error("Exception handled in %s", __name__, exc_info=True)
            return []
        result = []
        for r in rows:
            active = _get(SHEET_KASSA, r, "active", "1")
            if active_only and str(active) != "1":
                continue
            result.append({
                "id": int(_get(SHEET_KASSA, r, "id", 0)),
                "name": _get(SHEET_KASSA, r, "name", ""),
                "currency": _get(SHEET_KASSA, r, "currency", "UZS"),
                "balance": int(_get(SHEET_KASSA, r, "balance", 0)),
                "type": _get(SHEET_KASSA, r, "type", ""),
                "note": _get(SHEET_KASSA, r, "note", ""),
            })
        return result

    async def transfer_balance(
        self, from_kassa_id: int, to_kassa_id: int, amount: int, note: str = ""
    ) -> Optional[dict]:
        """Transfer between wallets (supports different currencies)."""
        wallets = await self.get_kassa(active_only=True)
        from_w = next((w for w in wallets if w["id"] == from_kassa_id), None)
        to_w = next((w for w in wallets if w["id"] == to_kassa_id), None)
        if not from_w or not to_w:
            return None

        rates = await self.get_rates()
        cur_from = from_w["currency"]
        cur_to = to_w["currency"]

        if cur_from == cur_to:
            converted = amount
        else:
            rate_info = rates.get(cur_to, {})
            rate = rate_info.get("buy", 0) or rate_info.get("cb", 0)
            if rate <= 0:
                # Try inverse
                inv_rate_info = rates.get(cur_from, {})
                inv_sell = inv_rate_info.get("sell", 0)
                if inv_sell > 0:
                    converted = int(amount * inv_sell)
                else:
                    return None
            else:
                converted = int(amount * rate)

        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        ws = self._worksheets.get(SHEET_KASSA)
        rows = ws.get_all_records()
        for i, r in enumerate(rows):
            rid = int(_get(SHEET_KASSA, r, "id", 0))
            if rid == from_kassa_id:
                bal = int(_get(SHEET_KASSA, r, "balance", 0))
                self._update_row(SHEET_KASSA, i + 2, {
                    "id": rid, "name": _get(SHEET_KASSA, r, "name", ""),
                    "currency": _get(SHEET_KASSA, r, "currency", "UZS"),
                    "balance": bal - amount,
                    "type": _get(SHEET_KASSA, r, "type", ""),
                    "note": _get(SHEET_KASSA, r, "note", ""),
                    "active": "1", "updated_at": now,
                })
            elif rid == to_kassa_id:
                bal = int(_get(SHEET_KASSA, r, "balance", 0))
                self._update_row(SHEET_KASSA, i + 2, {
                    "id": rid, "name": _get(SHEET_KASSA, r, "name", ""),
                    "currency": _get(SHEET_KASSA, r, "currency", "UZS"),
                    "balance": bal + converted,
                    "type": _get(SHEET_KASSA, r, "type", ""),
                    "note": _get(SHEET_KASSA, r, "note", ""),
                    "active": "1", "updated_at": now,
                })
        return {
            "from": from_w["name"], "to": to_w["name"],
            "amount": amount, "converted": converted,
            "rate": rate if cur_from != cur_to else 1,
            "note": note,
        }
