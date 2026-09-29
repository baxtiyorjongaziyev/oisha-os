import datetime
import os
import sys

sys.path.insert(0, os.path.abspath("."))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.services.core.instagram.leadgen_sheets import get_leadgen_spreadsheet


def excel_serial_to_dt(serial: float) -> str:
    """Converts Excel/Sheets serial date (e.g. 46290.4555) to DD.MM.YYYY HH:MM string."""
    dt = datetime.datetime(1899, 12, 30) + datetime.timedelta(days=serial)
    return dt.strftime("%d.%m.%Y %H:%M")


def fix_sheets():
    sh = get_leadgen_spreadsheet()
    if not sh:
        print("[!] Cannot open spreadsheet")
        return

    # 1. Fix UTC Outsource sheet (Rows 102 - 106)
    ws_utc = sh.worksheet("Gaplashilmagan Leadlar (UTC Outsource)")
    print("[*] Fixing 'Gaplashilmagan Leadlar (UTC Outsource)' rows 102-106...")

    utc_fixes = {
        102: {"phone": "'+998 (88) 931-00-25", "date_serial": 46290.455555555556},
        103: {"phone": "'+998 (97) 703-80-95", "date_serial": 46290.475},
        104: {"phone": "'+998 (99) 287-11-11", "date_serial": 46290.64513888889},
        105: {"phone": "'+998 (93) 996-96-96", "date_serial": 46290.67986111111},
        106: {"phone": "'+998 (97) 414-13-01", "date_serial": 46290.77013888889},
    }

    # Batch update A102:D106
    utc_rows_to_update = []
    for r in range(102, 107):
        fix = utc_fixes[r]
        sana = excel_serial_to_dt(fix["date_serial"])
        phone = fix["phone"]
        # We need name as well from current row
        name = ws_utc.acell(f"C{r}").value
        utc_rows_to_update.append(["=ROW()-1", sana, name, phone])

    ws_utc.update(range_name="A102:D106", values=utc_rows_to_update, value_input_option="USER_ENTERED")
    print("  [+] UTC Outsource A102:D106 updated successfully.")

    # 2. Fix Inhouse sheet (Rows 200 - 203)
    ws_inh = sh.worksheet("Target Leads Inhouse (Sentabr)")
    print("[*] Fixing 'Target Leads Inhouse (Sentabr)' rows 200-203...")

    inh_fixes = {
        200: {"phone": "'+998 (91) 027-11-11", "date_serial": 46290.63263888889},
        201: {"phone": "'+998 (88) 863-12-25", "date_serial": 46290.65694444445},
        202: {"phone": "'+998 (88) 451-48-81", "date_serial": 46290.75625},
        203: {"phone": "'+998 (99) 008-99-08", "date_serial": 46290.81805555556},
    }

    inh_rows_to_update = []
    for r in range(200, 204):
        fix = inh_fixes[r]
        sana = excel_serial_to_dt(fix["date_serial"])
        phone = fix["phone"]
        name = ws_inh.acell(f"C{r}").value
        inh_rows_to_update.append(["=ROW()-1", sana, name, phone])

    ws_inh.update(range_name="A200:D203", values=inh_rows_to_update, value_input_option="USER_ENTERED")
    print("  [+] Target Leads Inhouse A200:D203 updated successfully.")


if __name__ == "__main__":
    fix_sheets()
