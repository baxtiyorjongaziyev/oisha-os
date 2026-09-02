import os
import logging
import asyncio
from typing import Any, Optional
import gspread
try:
    from google.oauth2.service_account import Credentials
except ImportError:
    Credentials = None
from src.services.core.finance.gsheets.constants import *

logger = logging.getLogger(__name__)

class GsheetClientMixin:
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
        self._load_existing_worksheets()
        if self.spreadsheet and any(
            title not in self._worksheets for title in SHEET_HEADERS
        ):
            self._ensure_worksheets()

    def _load_existing_worksheets(self) -> None:
        """Load the existing workbook schema with one read-only API call.

        Full schema repair and formatting are only needed when a required tab is
        missing. Re-running them on every boot is slow, mutates the workbook,
        and can keep a small production VM in a watchdog restart loop.
        """
        if not self.spreadsheet:
            return
        if all(title in self._worksheets for title in SHEET_HEADERS):
            return
        try:
            existing = {worksheet.title: worksheet for worksheet in self.spreadsheet.worksheets()}
        except Exception as exc:
            logger.error("[HISOBCHI-GS] Worksheet list xatosi: %s", exc)
            return
        self._worksheets.update(
            (title, existing[title]) for title in SHEET_HEADERS if title in existing
        )
        if SHEET_HISOBOT in existing:
            self._worksheets[SHEET_HISOBOT] = existing[SHEET_HISOBOT]

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
                metadata = self.client.http_client.fetch_sheet_metadata(
                    self.spreadsheet_id,
                    params={
                        "includeGridData": False,
                        "fields": "properties,sheets(properties)",
                    },
                )
                spreadsheet = object.__new__(Spreadsheet)
                spreadsheet.client = self.client.http_client
                spreadsheet._properties = {
                    "id": self.spreadsheet_id,
                    **metadata["properties"],
                }
                self.spreadsheet = spreadsheet
                self._worksheets.update(
                    {
                        item["properties"]["title"]: Worksheet(
                            spreadsheet,
                            item["properties"],
                            self.spreadsheet_id,
                            spreadsheet.client,
                        )
                        for item in metadata.get("sheets", ())
                    }
                )
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
