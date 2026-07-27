"""Clear only Hisobchi ledger/learning data before the 2026-08-01 restart.

Requires an explicit confirmation environment variable so this cannot run
accidentally from a deploy or an interactive shell typo.
"""

from __future__ import annotations

import asyncio
import argparse
import os

import gspread

from src.database_pool import db_pool
from src.services.core.finance.hisobchi_engine import HisobchiEngine
from src.services.core.finance.hisobchi_schema import (
    init_hisobchi_tables,
)
from src.services.core.hisobchi_gsheets import (
    SHEET_BALANS,
    SHEET_FOYDA_ZARAR,
    SHEET_HEADERS,
    SHEET_PUL_OQIMI,
    SHEET_QOIDALAR,
    SHEET_SHAXSIY,
    SHEET_XOTIRA,
)
from src.settings import settings


CONFIRMATION = "2026-08-01"
RESET_SHEETS = (
    SHEET_PUL_OQIMI,
    SHEET_SHAXSIY,
    SHEET_BALANS,
    SHEET_FOYDA_ZARAR,
    SHEET_XOTIRA,
    SHEET_QOIDALAR,
)


def reset_google_sheets(
    spreadsheet_id: str,
    credentials_file: str,
) -> None:
    """Reset only the approved tabs without initializing unrelated worksheets."""
    spreadsheet = gspread.service_account(filename=credentials_file).open_by_key(
        spreadsheet_id
    )
    for title in RESET_SHEETS:
        worksheet = spreadsheet.worksheet(title)
        headers = SHEET_HEADERS[title]
        if worksheet.col_count < len(headers):
            worksheet.resize(cols=len(headers))
        worksheet.clear()
        worksheet.append_row(headers)


async def main(*, google_sheets_only: bool = False) -> None:
    if os.getenv("CONFIRM_HISOBCHI_RESET") != CONFIRMATION:
        raise SystemExit(
            "Refusing reset: set CONFIRM_HISOBCHI_RESET=2026-08-01 explicitly"
        )

    cleared: list[str] = []

    spreadsheet_id = (settings.HISOBCHI_GSHEET_ID or "").strip()
    if spreadsheet_id:
        credentials_file = (
            settings.HISOBCHI_GSHEET_CREDS_FILE
            or getattr(settings, "GSHEET_CREDS_FILE", "service_account.json")
        )
        reset_google_sheets(spreadsheet_id, credentials_file)
        cleared.append("google_sheets")

    if not google_sheets_only:
        await init_hisobchi_tables(db_pool)
        await HisobchiEngine(db=db_pool).reset_learning_and_transactions()
        cleared.append("sql")

    print("Hisobchi reset complete: " + ", ".join(cleared))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--google-sheets-only",
        action="store_true",
        help="Clear only the configured Hisobchi Google Sheets tabs.",
    )
    args = parser.parse_args()
    asyncio.run(main(google_sheets_only=args.google_sheets_only))
