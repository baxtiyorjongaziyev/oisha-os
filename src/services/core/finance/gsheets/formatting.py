import logging
from typing import Any
import gspread
from src.services.core.finance.gsheets.constants import *

logger = logging.getLogger(__name__)

class GsheetFormattingMixin:
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
