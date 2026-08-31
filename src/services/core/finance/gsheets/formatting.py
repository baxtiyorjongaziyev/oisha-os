"""
GSheets formatting and validation rules builder.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List
import gspread

from src.services.core.finance.gsheets.constants import (
    SHEET_HEADERS,
    SHEET_PUL_OQIMI,
    SHEET_SHAXSIY,
    SHEET_QARZ,
)

logger = logging.getLogger(__name__)


def _build_base_sheet_requests(sid: int, num_cols: int) -> List[Dict[str, Any]]:
    """Frozen headers, dark header styling, and alternating row bands."""
    return [
        {
            "updateSheetProperties": {
                "properties": {"sheetId": sid, "gridProperties": {"frozenRowCount": 1}},
                "fields": "gridProperties.frozenRowCount",
            }
        },
        {
            "repeatCell": {
                "range": {
                    "sheetId": sid, "startRowIndex": 0, "endRowIndex": 1,
                    "startColumnIndex": 0, "endColumnIndex": num_cols,
                },
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": {"red": 0.18, "green": 0.2, "blue": 0.27},
                        "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}, "fontSize": 10},
                        "horizontalAlignment": "CENTER",
                    }
                },
                "fields": "userEnteredFormat(textFormat,backgroundColor,horizontalAlignment)",
            }
        },
        {
            "addBanding": {
                "bandedRange": {
                    "range": {"sheetId": sid, "startRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": num_cols},
                    "rowProperties": {
                        "firstBandColor": {"red": 0.97, "green": 0.97, "blue": 0.97},
                        "secondBandColor": {"red": 1, "green": 1, "blue": 1},
                        "headerColor": {"red": 0.9, "green": 0.9, "blue": 0.9},
                    },
                }
            }
        },
        {
            "updateSheetProperties": {
                "properties": {"sheetId": sid, "gridProperties": {"columnCount": num_cols}},
                "fields": "gridProperties.columnCount",
            }
        },
    ]


def _build_pul_oqimi_conditional_rules(sid: int) -> List[Dict[str, Any]]:
    """Kirim/Chiqim color highlights, status tags and dropdown validation."""
    return [
        {
            "addConditionalFormatRule": {
                "rule": {
                    "ranges": [{"sheetId": sid, "startRowIndex": 1, "startColumnIndex": 2, "endColumnIndex": 3}],
                    "booleanRule": {
                        "condition": {"type": "TEXT_EQ", "values": [{"userEnteredValue": "Kirim"}]},
                        "format": {"backgroundColor": {"red": 0.78, "green": 0.92, "blue": 0.78}, "textFormat": {"bold": True, "foregroundColor": {"red": 0, "green": 0.4, "blue": 0}}},
                    },
                }
            }
        },
        {
            "addConditionalFormatRule": {
                "rule": {
                    "ranges": [{"sheetId": sid, "startRowIndex": 1, "startColumnIndex": 2, "endColumnIndex": 3}],
                    "booleanRule": {
                        "condition": {"type": "TEXT_EQ", "values": [{"userEnteredValue": "Chiqim"}]},
                        "format": {"backgroundColor": {"red": 0.95, "green": 0.78, "blue": 0.78}, "textFormat": {"bold": True, "foregroundColor": {"red": 0.5, "green": 0, "blue": 0}}},
                    },
                }
            }
        },
        {
            "addConditionalFormatRule": {
                "rule": {
                    "ranges": [{"sheetId": sid, "startRowIndex": 1, "startColumnIndex": 10, "endColumnIndex": 11}],
                    "booleanRule": {
                        "condition": {"type": "TEXT_EQ", "values": [{"userEnteredValue": "pending"}]},
                        "format": {"backgroundColor": {"red": 1, "green": 1, "blue": 0.7}},
                    },
                }
            }
        },
        {
            "addConditionalFormatRule": {
                "rule": {
                    "ranges": [{"sheetId": sid, "startRowIndex": 1, "startColumnIndex": 10, "endColumnIndex": 11}],
                    "booleanRule": {
                        "condition": {"type": "TEXT_EQ", "values": [{"userEnteredValue": "categorized"}]},
                        "format": {"backgroundColor": {"red": 0.78, "green": 0.92, "blue": 0.78}},
                    },
                }
            }
        },
        {
            "setDataValidation": {
                "range": {"sheetId": sid, "startRowIndex": 1, "endRowIndex": 9999, "startColumnIndex": 2, "endColumnIndex": 3},
                "rule": {"condition": {"type": "ONE_OF_LIST", "values": [{"userEnteredValue": "Kirim"}, {"userEnteredValue": "Chiqim"}]}, "inputMessage": "Kirim yoki Chiqim", "showCustomUi": True},
            }
        },
    ]


def _build_qarz_and_contract_rules(sid: int, title: str) -> List[Dict[str, Any]]:
    """Dropdown and status coloring for Qarz and Shartnomalar sheets."""
    rules = []
    if title == SHEET_QARZ:
        rules.append({
            "setDataValidation": {
                "range": {"sheetId": sid, "startRowIndex": 1, "endRowIndex": 9999, "startColumnIndex": 1, "endColumnIndex": 2},
                "rule": {"condition": {"type": "ONE_OF_LIST", "values": [{"userEnteredValue": "Berilgan"}, {"userEnteredValue": "Olingan"}]}, "inputMessage": "Berilgan yoki Olingan", "showCustomUi": True},
            }
        })
    elif title == SHEET_SHARTNOMALAR:
        rules.append({
            "setDataValidation": {
                "range": {"sheetId": sid, "startRowIndex": 1, "endRowIndex": 9999, "startColumnIndex": 9, "endColumnIndex": 10},
                "rule": {"condition": {"type": "ONE_OF_LIST", "values": [{"userEnteredValue": "Faol"}, {"userEnteredValue": "Tugallangan"}, {"userEnteredValue": "Bekor qilingan"}]}, "inputMessage": "Shartnoma holati", "showCustomUi": True},
            }
        })
    return rules


def _build_column_widths(sid: int, title: str) -> List[Dict[str, Any]]:
    """Specific column pixel widths per worksheet."""
    widths = {0: 100, 1: 140, 2: 90, 3: 150, 4: 120, 5: 140, 6: 180, 7: 180, 8: 100, 9: 120, 10: 100}
    if title == SHEET_HISOBOT_OYLIK:
        widths = {0: 120, 1: 140, 2: 140, 3: 140, 4: 120, 5: 140}
    return [
        {
            "updateDimensionProperties": {
                "range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": col, "endIndex": col + 1},
                "properties": {"pixelSize": size},
                "fields": "pixelSize",
            }
        }
        for col, size in widths.items()
    ]


class GsheetFormattingMixin:
    """Google Sheets UI formatting, banding and validation rules."""

    def _apply_formatting(self):
        if not self.spreadsheet:
            return
        try:
            requests: List[Dict[str, Any]] = []
            for title in SHEET_HEADERS:
                ws = self._worksheets.get(title)
                if not ws:
                    continue
                sid = ws.id
                num_cols = len(SHEET_HEADERS[title])

                requests.extend(_build_base_sheet_requests(sid, num_cols))

                if title in (SHEET_PUL_OQIMI, SHEET_SHAXSIY):
                    requests.extend(_build_pul_oqimi_conditional_rules(sid))
                else:
                    requests.extend(_build_qarz_and_contract_rules(sid, title))

                requests.extend(_build_column_widths(sid, title))

            self.spreadsheet.batch_update({"requests": requests})
            logger.info("Sheet formatting applied successfully.")
        except Exception as e:
            logger.warning("Failed to apply full formatting: %s", e)
